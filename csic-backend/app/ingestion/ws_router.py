"""
app/ingestion/ws_router.py
---------------------------
Secure WebSocket Chunk-Stream Endpoint.

Route:
    /ws/secure-stream/{session_id}

Protocol (client → server per message):
    • JSON text (legacy / collectors): {
      "chunk_number": int,    // 0-based sequence number
      "chunk_hash":   str,    // client-computed SHA-256 hex of this chunk
      "data":         str,    // base64-encoded raw bytes of the chunk
      "is_final":     bool    // true on the last chunk
    }
    • Binary WebSocket frame (browser): WSC1 | u32 BE chunk# | u8 flags (bit0=is_final)
      | u32 BE payload_len | 32-byte SHA-256 digest | raw payload

Server responses (server → client):
    {"status": "ok",    "chunk_number": N}  — chunk accepted
    {"status": "error", "detail": "..."}    — fatal error (connection closes)
    {"status": "done",  "audit_id": "...",
     "merkle_root": "...", "sha256": "..."}  — pipeline completed

Security enforcement order:
    1. Session validation   (JIT Gateway — all 3 rules)
    2. Session consumption  (burn-on-use)
    3. Per-chunk hash verification
    4. Stream chunks to a single temp file (bounded by max chunk size)
    5. Post-stream Merkle root construction
    6. Monolithic SHA-256 (incremental, verified against streamed bytes)
    7. Synchronous sandbox triage
    8. Ledger commit → WORM storage
    9. Async malware scan (background, after WebSocket closes)
"""

import asyncio
import base64
import hashlib
import json
import os
import shutil
import stat
import struct
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.merkle import build_merkle_root
from app.db.session import SessionLocal
from app.ingestion.auth_gateway import (
    SessionStore,
    _extract_ws_client_ip,
    _enforce_rules,
)
from app.ingestion.sandbox import async_malware_scan, run_sync_triage, collect_triage_info
from app.ingestion.secure_ledger import commit_to_ledger
from app.ingestion.audit_trail import build_trail_from_ws_session
from app.phase2.service import process_file_phase2

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: Trigger Phase 2 Processing
# ---------------------------------------------------------------------------

async def trigger_phase2_processing(
    audit_id: str,
    file_path: str,
    source_ip: str,
) -> None:
    """
    Automatically trigger Phase 2 (Parsing Pipeline) after Phase 1 completes.
    
    This function is called asynchronously after Phase 1 ingestion completes
    to automatically start the parsing pipeline.
    
    Payload format matches Phase 2 expectations:
        {
            "status": "done",
            "audit_id": "uuid",
            "sha256": "file_hash",
            "file_path": "/worm/vault/file.log",
            "source_ip": "127.0.0.1"
        }
    """
    try:
        import os, asyncio
        auto_trigger = os.getenv("AUTO_TRIGGER_PHASE2", "true").lower()
        if auto_trigger in {"0", "false", "no", "off"}:
            return
        logger.info(
            f"[WSRouter] Auto-triggering Phase 2: audit_id={audit_id} "
            f"file_path={file_path} source_ip={source_ip}"
        )

        def _run_phase2():
            phase2_db: Optional[Session] = None
            try:
                phase2_db = SessionLocal()
                return process_file_phase2(
                    db=phase2_db,
                    audit_id=audit_id,
                    file_path=file_path,
                    source_ip=source_ip,
                )
            finally:
                if phase2_db is not None:
                    phase2_db.close()

        result = await asyncio.to_thread(_run_phase2)

        logger.info(
            f"[WSRouter] Phase 2 processing started: audit_id={audit_id} "
            f"staging_ids={result.get('staging_ids', [])} "
            f"rows_processed={result.get('rows_processed', 0)}"
        )
        
    except ValueError as e:
        logger.warning(
            f"[WSRouter] Phase 2 trigger failed (ValueError): audit_id={audit_id} "
            f"error={str(e)}"
        )
    except FileNotFoundError as e:
        logger.warning(
            f"[WSRouter] Phase 2 trigger failed (FileNotFound): audit_id={audit_id} "
            f"file_path={file_path} error={str(e)}"
        )
    except Exception as e:
        logger.error(
            f"[WSRouter] Phase 2 trigger failed (unexpected): audit_id={audit_id} "
            f"error={str(e)}",
            exc_info=True
        )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMP_CHUNKS_DIR = Path("data/temp")
WORM_DIR = Path("data/worm")
MAX_CHUNKS = 10_000          # hard cap — prevents runaway streams
MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB per chunk

WS_CHUNK_MAGIC = b"WSC1"
WS_CHUNK_HDR = struct.Struct("!4sIBI32s")  # magic, chunk#, flags, payload_len, sha256 digest


def _parse_ws_binary_chunk(body: bytes) -> tuple[int, bool, bytes, bytes]:
    """Parse a binary chunk frame; returns chunk_number, is_final, payload, expected_sha256_digest."""
    if len(body) < WS_CHUNK_HDR.size:
        raise ValueError("frame too short")
    magic, chunk_number, flags, payload_len, digest = WS_CHUNK_HDR.unpack_from(body, 0)
    if magic != WS_CHUNK_MAGIC:
        raise ValueError("bad magic")
    end = WS_CHUNK_HDR.size + payload_len
    if len(body) != end:
        raise ValueError("payload length mismatch")
    chunk_data = body[WS_CHUNK_HDR.size : end]
    is_final = bool(flags & 1)
    return chunk_number, is_final, chunk_data, digest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _worm_store(source: Path, filename: str) -> Path:
    """
    Move *source* into the WORM directory and make it read-only.
    Returns the final WORM path.
    """
    WORM_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORM_DIR / filename
    if dest.exists():
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        dest = WORM_DIR / f"{ts}_{filename}"

    shutil.move(str(source), str(dest))
    # Read-only for owner; no write permission for anyone
    try:
        os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception as exc:
        logger.warning(f"[WSRouter] WORM chmod failed for {dest}: {exc}")

    logger.info(f"[WSRouter] WORM: {filename} → {dest}")
    return dest


async def _ws_reject(websocket: WebSocket, detail: str, code: int = 4003) -> None:
    """Send error frame and close the WebSocket cleanly."""
    try:
        await websocket.send_text(json.dumps({"status": "error", "detail": detail}))
    except Exception:
        pass
    await websocket.close(code=code)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/secure-stream/{session_id}")
async def websocket_secure_stream(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """
    Secure chunk-stream ingestion over WebSocket.

    Lifecycle:
      1.  Accept TCP upgrade (before authentication — required by WebSocket spec)
      2.  Validate JIT session (all 3 rules)
      3.  Receive chunks, verify each hash, stream to final temp file + incremental SHA-256
      4.  Merkle root + monolithic SHA-256 (from streaming hasher)
      5.  Sandbox triage
      6.  Ledger commit + WORM
      7.  Launch async malware scan
    """
    # Accept at TCP level first (required before we can send close frames)
    await websocket.accept()

    db: Optional[Session] = None
    session_dir: Optional[Path] = None
    out_fh = None
    reconstructed_path: Optional[Path] = None

    try:
        db = _get_db()
        store = SessionStore(db)

        # ── Step 1: Validate all three JIT rules ────────────────────────────
        session = store.get(session_id)
        client_ip = _extract_ws_client_ip(websocket)

        if session is None:
            logger.warning(f"[WSRouter] Unknown session_id={session_id}")
            await _ws_reject(websocket, "Session not found.", code=4001)
            return

        try:
            _enforce_rules(session, client_ip, context="WS")
        except PermissionError as exc:
            await _ws_reject(websocket, str(exc), code=4003)
            return

        # ── Step 2: Burn the session (OTP) ──────────────────────────────────
        store.mark_used(session)
        logger.info(
            f"[WSRouter] Session consumed: {session_id} mode={session.mode}"
        )

        # ── Step 3: Prepare temp storage ────────────────────────────────────
        session_dir = TEMP_CHUNKS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        chunk_hashes: list[str] = []
        chunk_number_expected: int = 0
        filename: str = f"stream_{session_id}.bin"   # overwritten by client meta
        mono_hasher = hashlib.sha256()

        # ── Step 4: Receive chunks (stream to final file + incremental hash) ─
        t_recv_start = time.perf_counter()
        while True:
            try:
                raw_message = await websocket.receive()
            except WebSocketDisconnect:
                logger.warning(
                    f"[WSRouter] Client disconnected mid-stream for session {session_id}"
                )
                return

            chunk_number = -1
            is_final = False
            chunk_data = b""
            client_chunk_hash_hex: Optional[str] = None
            client_chunk_hash_digest: Optional[bytes] = None

            if raw_message.get("bytes") is not None:
                body = raw_message["bytes"]
                if not isinstance(body, (bytes, bytearray, memoryview)):
                    await _ws_reject(
                        websocket,
                        "Invalid binary chunk frame.",
                    )
                    return
                try:
                    chunk_number, is_final, chunk_data, client_chunk_hash_digest = (
                        _parse_ws_binary_chunk(bytes(body))
                    )
                except ValueError as exc:
                    await _ws_reject(
                        websocket,
                        f"Binary chunk: {exc}",
                    )
                    return

            elif "text" in raw_message:
                message: dict = json.loads(raw_message["text"])
                msg_type = message.get("type")

                # ── META message: optionally sent before the first chunk ────
                if msg_type == "meta":
                    filename = message.get("filename", filename)
                    logger.debug(f"[WSRouter] Meta received: filename={filename}")
                    await websocket.send_text(
                        json.dumps({"status": "meta_ack", "filename": filename})
                    )
                    continue

                chunk_number = int(message.get("chunk_number", -1))
                client_chunk_hash_hex = message.get("chunk_hash", "")
                encoded_data: str = message.get("data", "")
                is_final = bool(message.get("is_final", False))

                if len(encoded_data) > MAX_CHUNK_SIZE_BYTES * 4 // 3 + 4:
                    await _ws_reject(
                        websocket,
                        f"Chunk {chunk_number} exceeds maximum allowed size.",
                    )
                    return

                try:
                    chunk_data = base64.b64decode(encoded_data)
                except Exception:
                    await _ws_reject(
                        websocket,
                        f"Chunk {chunk_number}: base64 decode failed.",
                    )
                    return

            else:
                continue

            # Sequence enforcement
            if chunk_number != chunk_number_expected:
                await _ws_reject(
                    websocket,
                    f"Out-of-order chunk: expected {chunk_number_expected}, "
                    f"got {chunk_number}.",
                )
                return

            if len(chunk_data) > MAX_CHUNK_SIZE_BYTES:
                await _ws_reject(
                    websocket,
                    f"Chunk {chunk_number} exceeds maximum allowed size.",
                )
                return

            if chunk_number >= MAX_CHUNKS:
                await _ws_reject(
                    websocket,
                    f"Maximum chunk count ({MAX_CHUNKS}) exceeded.",
                )
                return

            server_digest = hashlib.sha256(chunk_data).digest()
            if client_chunk_hash_digest is not None:
                if server_digest != client_chunk_hash_digest:
                    logger.error(
                        f"[WSRouter] Chunk {chunk_number} hash mismatch (binary frame)."
                    )
                    await _ws_reject(
                        websocket,
                        f"Chunk {chunk_number} hash mismatch — data corruption detected.",
                    )
                    return
            else:
                server_chunk_hash_hex = server_digest.hex()
                if server_chunk_hash_hex != (client_chunk_hash_hex or ""):
                    logger.error(
                        f"[WSRouter] Chunk {chunk_number} hash mismatch! "
                        f"client={client_chunk_hash_hex} server={server_chunk_hash_hex}"
                    )
                    await _ws_reject(
                        websocket,
                        f"Chunk {chunk_number} hash mismatch — data corruption detected.",
                    )
                    return

            if out_fh is None:
                reconstructed_path = session_dir / filename
                out_fh = open(reconstructed_path, "wb")

            out_fh.write(chunk_data)
            mono_hasher.update(chunk_data)

            server_chunk_hash = server_digest.hex()
            chunk_hashes.append(server_chunk_hash)
            chunk_number_expected += 1

            await websocket.send_text(
                json.dumps({"status": "ok", "chunk_number": chunk_number})
            )
            logger.debug(
                f"[WSRouter] Chunk {chunk_number} stored "
                f"hash={server_chunk_hash[:12]}…"
            )

            if is_final:
                break

        t_recv_end = time.perf_counter()

        if out_fh is not None:
            out_fh.close()
            out_fh = None

        if reconstructed_path is None:
            await _ws_reject(websocket, "No file data received.")
            return

        t_finalize_start = time.perf_counter()
        merkle_root = build_merkle_root(chunk_hashes)
        mono_sha256 = mono_hasher.hexdigest()
        t_finalize_end = time.perf_counter()

        file_size = reconstructed_path.stat().st_size
        logger.info(
            f"[WSRouter] merkle_root={merkle_root[:12]}… "
            f"sha256={mono_sha256[:12]}…"
        )
        logger.info(
            "[WSRouter] ingest_timing session=%s recv_chunks_s=%.3f finalize_s=%.3f "
            "chunks=%d bytes=%d",
            session_id,
            t_recv_end - t_recv_start,
            t_finalize_end - t_finalize_start,
            len(chunk_hashes),
            file_size,
        )

        # ── Step 5: Synchronous sandbox triage ───────────────────────────────
        t_triage_start = time.perf_counter()
        triage_info = collect_triage_info(reconstructed_path)

        quarantine_record = run_sync_triage(
            file_path=reconstructed_path,
            db=db,
            source_ip=client_ip,
            ingestion_mode=session.mode,
            session_id=session_id,
        )

        t_triage_end = time.perf_counter()

        if quarantine_record is not None:
            logger.warning(
                f"[WSRouter] File quarantined: reason={quarantine_record.reason}"
            )
            # Build quarantined audit trail
            _quarantined_trail = build_trail_from_ws_session(
                ingestion_mode=session.mode,
                source_ip=client_ip,
                file_name=filename,
                file_size_bytes=reconstructed_path.stat().st_size if reconstructed_path.exists() else 0,
                session_id=session_id,
                bound_ip=session.bound_ip,
                expires_at=session.expires_at.isoformat() + "Z" if session.expires_at else "",
                total_chunks=len(chunk_hashes),
                verified_chunks=len(chunk_hashes),
                sha256_hash=mono_sha256,
                merkle_root=merkle_root,
                chunk_hash_count=len(chunk_hashes),
                sandbox_status="quarantined",
                **triage_info,
            )
            await websocket.send_text(json.dumps({
                "status": "error",
                "detail": f"File failed sandbox triage: {quarantine_record.reason}",
                "audit_trail": _quarantined_trail,
            }))
            await websocket.close(code=4010)
            return

        # ── Step 6: Ledger commit + WORM storage ─────────────────────────────
        t_worm_start = time.perf_counter()
        worm_path = _worm_store(reconstructed_path, filename)

        audit_entry = commit_to_ledger(
            db=db,
            filename=filename,
            file_path=worm_path,
            sha256_hash=mono_sha256,
            merkle_root=merkle_root,
            source_ip=client_ip,
            ingestion_mode=session.mode,
            file_size=worm_path.stat().st_size,
        )

        store.link_audit(session, audit_entry.id)
        t_worm_end = time.perf_counter()

        logger.info(
            "[WSRouter] ingest_timing session=%s triage_s=%.3f worm_ledger_s=%.3f",
            session_id,
            t_triage_end - t_triage_start,
            t_worm_end - t_worm_start,
        )

        logger.info(
            f"[WSRouter] Ledger commit successful: audit_id={audit_entry.id}"
        )

        # ── Step 7: Async malware scan (background, non-blocking) ────────────
        asyncio.create_task(
            async_malware_scan(
                file_path=worm_path,
                db=db,
                source_ip=client_ip,
                ingestion_mode=session.mode,
                session_id=session_id,
            )
        )

        # ── Step 8: Build full audit trail ──────────────────────────────────
        audit_trail = build_trail_from_ws_session(
            ingestion_mode=session.mode,
            source_ip=client_ip,
            file_name=filename,
            file_size_bytes=worm_path.stat().st_size,
            session_id=session_id,
            bound_ip=session.bound_ip,
            expires_at=session.expires_at.isoformat() + "Z" if session.expires_at else "",
            total_chunks=len(chunk_hashes),
            verified_chunks=len(chunk_hashes),
            sha256_hash=mono_sha256,
            merkle_root=merkle_root,
            chunk_hash_count=len(chunk_hashes),
            sandbox_status="clean",
            ledger_entry_id=audit_entry.id,
            previous_hash=audit_entry.previous_hash,
            worm_storage_path=str(worm_path),
            **triage_info,
        )

        # ── Final ACK ────────────────────────────────────────────────────────
        # Phase 1 response format:
        # - top-level status="done" (used by frontend WS client)
        # - nested "result" object (backward compatibility)
        await websocket.send_text(
            json.dumps({
                "status": "done",
                "result": {
                    "status": "done",
                    "audit_id": audit_entry.id,
                    "sha256": mono_sha256,
                    "file_path": str(worm_path),  # Phase 2 handoff: WORM path
                    "merkle_root": merkle_root,  # Merkle root hash
                    "binary_signature": merkle_root,  # Merkle root as binary signature (backward compatibility)
                    "source_ip": client_ip,  # Source IP for Phase 2
                }
            })
        )
        
        # ── Step 9: Automatically trigger Phase 2 ONLY after Phase 1 completes successfully ────────
        # Verify Phase 1 completion: audit entry exists, file exists, and final ACK sent
        if audit_entry and audit_entry.id and worm_path.exists():
            logger.info(
                f"[WSRouter] Phase 1 ingestion completed successfully. "
                f"Triggering Phase 2 (Parsing Pipeline) for audit_id={audit_entry.id}"
            )
            asyncio.create_task(
                trigger_phase2_processing(
                    audit_id=audit_entry.id,
                    file_path=str(worm_path),
                    source_ip=client_ip,
                )
            )
        else:
            logger.error(
                f"[WSRouter] Phase 1 completion verification failed. "
                f"audit_entry={audit_entry is not None}, "
                f"file_exists={worm_path.exists() if 'worm_path' in locals() else False}. "
                f"Phase 2 will NOT be triggered."
            )
        
        await websocket.close(code=1000)

    except WebSocketDisconnect:
        logger.info(f"[WSRouter] WebSocket disconnected: session={session_id}")
    except Exception as exc:
        logger.exception(f"[WSRouter] Unhandled error in session {session_id}: {exc}")
        try:
            await _ws_reject(websocket, "Internal server error.", code=4500)
        except Exception:
            pass
    finally:
        if out_fh is not None:
            try:
                out_fh.close()
            except Exception:
                pass
        # Clean up session temp directory
        if session_dir is not None and session_dir.exists():
            try:
                shutil.rmtree(session_dir, ignore_errors=True)
            except Exception as cleanup_exc:
                logger.warning(
                    f"[WSRouter] Temp cleanup failed for {session_dir}: {cleanup_exc}"
                )
        if db is not None:
            db.close()
