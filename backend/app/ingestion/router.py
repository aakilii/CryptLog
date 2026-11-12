"""
app/ingestion/router.py
------------------------
Ingestion API router.

Existing endpoints (UNCHANGED — backward-compatible):
    POST /ingestion/upload-log          Legacy single-shot upload
    GET  /ingestion/verify/{audit_id}   Per-file integrity check
    GET  /ingestion/verify-chain        Full hash-chain verification

Phase-1 secure ingestion endpoints (NEW):
    POST /ingestion/manual              Create JIT session for UI upload
    POST /ingestion/cloud               Create JIT session for cloud pull
    POST /ingestion/generate-telemetry-link  Agentless telemetry link

WebSocket endpoint is registered separately in app/ingestion/ws_router.py,
mounted at the application root (not under /api) to avoid prefix conflicts.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ingestion.integrity import verify_file_integrity, verify_hash_chain
from app.ingestion.service import (
    create_cloud_session,
    create_manual_session,
    create_telemetry_link,
    ingest_file,
)
from app.ingestion.audit_trail import build_trail_from_legacy_upload
from app.ingestion.sandbox import collect_triage_info
from app.schemas.audit import AuditResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Valid ingestion modes (any alias → canonical name via AuditTrail.MODE_MAP)
# ---------------------------------------------------------------------------
_VALID_MODES = {"manual", "cloud", "agent", "manual_upload", "cloud_pull", "agentless_telemetry"}


def _resolve_mode(source: str | None) -> str:
    """Normalise the user-supplied source string into a valid mode."""
    if not source:
        return "manual"                     # default for REST uploads
    cleaned = source.strip().lower()
    if cleaned in _VALID_MODES:
        return cleaned
    return "manual"                          # fallback


# ---------------------------------------------------------------------------
# DB dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CloudIngestRequest(BaseModel):
    oauth_token: str
    cloud_provider: str = "generic"


# ---------------------------------------------------------------------------
# ── LEGACY ENDPOINT (preserved, backward-compatible) ─────────────────────
# ---------------------------------------------------------------------------

@router.post("/upload-log", response_model=AuditResponse)
async def upload_log(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    uploader: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Legacy single-shot log upload.
    Kept for backward compatibility with existing integrations.

    Form fields:
        source: ingestion mode — 'manual', 'cloud', 'agent' (default: 'manual')
    """
    try:
        content = await file.read()
        source_ip = request.client.host if request.client else None
        mode = _resolve_mode(source)

        result = ingest_file(
            db,
            file.filename,
            content,
            uploader=uploader,
            source_ip=source_ip,
            ingestion_mode=mode,
        )

        # Phase 1 -> Phase 2 handoff (async, gated)
        async def _trigger_phase2(audit_id: str, filename: str, src_ip: str | None) -> None:
            from pathlib import Path
            import os, asyncio
            from app.config import settings
            from app.db.session import SessionLocal
            from app.phase2.service import process_file_phase2

            auto_trigger = os.getenv("AUTO_TRIGGER_PHASE2", "true").lower()
            if auto_trigger in {"0", "false", "no", "off"}:
                return

            def _run():
                phase2_db = SessionLocal()
                try:
                    worm_path = str(Path(settings.WORM_STORAGE_PATH) / str(audit_id) / filename)
                    process_file_phase2(db=phase2_db, audit_id=audit_id, file_path=worm_path, source_ip=src_ip)
                finally:
                    phase2_db.close()

            await asyncio.to_thread(_run)

        background_tasks.add_task(_trigger_phase2, result.id, result.filename, source_ip)

        return result

    except ValueError as exc:
        # File was quarantined by sandbox triage — not a server error
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# ── PHASE-1 ENTRY ROUTES (NODE 1) ─────────────────────────────────────────
# ---------------------------------------------------------------------------

@router.post("/manual")
async def manual_ingestion_init(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    NODE 1 — MANUAL UPLOAD ENTRY POINT

    Creates a JIT-bound ephemeral session for UI-initiated uploads.

    Returns:
        session_id, websocket_url, expires_at
        The client connects to websocket_url and streams file chunks.
    """
    try:
        return create_manual_session(db, request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cloud")
async def cloud_ingestion_init(
    request: Request,
    body: CloudIngestRequest,
    db: Session = Depends(get_db),
):
    """
    NODE 1 — CLOUD DRIVE / S3 / AZURE PULL ENTRY POINT

    Validates the OAuth2 token, then creates a JIT session for a
    server-to-server streaming proxy.

    Body:
        oauth_token:    Provider OAuth2 / STS token
        cloud_provider: 'gdrive' | 's3' | 'azure' | 'generic'

    Returns:
        session_id, websocket_url, expires_at, cloud_provider
    """
    try:
        return create_cloud_session(
            db, request,
            oauth_token=body.oauth_token,
            cloud_provider=body.cloud_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate-telemetry-link")
async def generate_telemetry_link(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    NODE 1 — AGENTLESS TELEMETRY LINK GENERATOR

    Issues a time-limited, IP-bound, OTP WebSocket link for live
    victim / endpoint artefact extraction without installing an agent.

    Returns:
        ephemeral_token, websocket_url, expires_at, usage instructions
    """
    try:
        return create_telemetry_link(db, request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# ── INTEGRITY VERIFICATION (preserved) ────────────────────────────────────
# ---------------------------------------------------------------------------

@router.get("/verify/{audit_id}")
def verify_log(audit_id: str, db: Session = Depends(get_db)):
    """Verify SHA-256 integrity for a single audited file."""
    return verify_file_integrity(db, audit_id)


@router.get("/verify-chain")
def verify_chain(db: Session = Depends(get_db)):
    """Verify the complete cryptographic hash chain across all audit records."""
    return verify_hash_chain(db)


# ---------------------------------------------------------------------------
# ── AUDIT TRAIL ENDPOINT ──────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@router.post("/audit-trail")
async def upload_with_audit_trail(
    request: Request,
    file: UploadFile = File(...),
    source: Optional[str] = Form(None),
    uploader: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a file and return the full session audit trail JSON.

    This endpoint performs the exact same pipeline as /upload-log but
    returns the detailed 6-node audit trail instead of the compact
    AuditResponse schema.

    Form fields:
        source: ingestion mode — 'manual', 'cloud', 'agent' (default: 'manual')

    Returns:
        Full JSON audit object with session, nodes, security_summary, result.
    """
    import tempfile
    from pathlib import Path
    from app.core.security import compute_sha256
    from app.ingestion.sandbox import (
        run_sync_triage, run_sync_deep_scan, collect_triage_info,
    )

    content = await file.read()
    source_ip = request.client.host if request.client else "unknown"
    filename = file.filename or "unknown"
    mode = _resolve_mode(source)
    file_hash = compute_sha256(content)

    # Write temp file for sandbox
    tmp_dir = Path(tempfile.mkdtemp(prefix="audit_trail_"))
    tmp_file = tmp_dir / filename
    tmp_file.write_bytes(content)

    sandbox_passed = False
    quarantine_reason = None
    ledger_entry_id = ""
    previous_hash = None
    raw_path = ""
    triage_info = {}
    merkle_root = ""

    try:
        triage_info = collect_triage_info(tmp_file)

        # Sync triage
        q_rec = run_sync_triage(
            file_path=tmp_file, db=db,
            source_ip=source_ip, ingestion_mode=mode, session_id=None,
        )
        if q_rec:
            quarantine_reason = q_rec.reason
        else:
            # Deep scan
            d_rec = run_sync_deep_scan(
                file_path=tmp_file, db=db,
                source_ip=source_ip, ingestion_mode=mode, session_id=None,
            )
            if d_rec:
                quarantine_reason = d_rec.reason
            else:
                sandbox_passed = True

        if sandbox_passed:
            from app.ingestion.service import save_raw_file, get_last_hash, _compute_merkle_root
            from app.db.models import AuditLog
            from datetime import datetime

            raw_path = save_raw_file(filename, content)
            previous_hash = get_last_hash(db)
            merkle_root = _compute_merkle_root(content)

            audit_entry = AuditLog(
                filename=filename,
                sha256_hash=file_hash,
                previous_hash=previous_hash,
                merkle_root=merkle_root,
                upload_time=datetime.utcnow(),
                file_size=len(content),
                uploader=uploader,
                source_ip=source_ip,
                ingestion_mode=mode,
                status="ingested",
            )
            db.add(audit_entry)
            db.commit()
            db.refresh(audit_entry)
            ledger_entry_id = audit_entry.id

            from app.parsing.service import process_log_file
            process_log_file(filename, content, file_hash, audit_entry.id)

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    merkle = merkle_root if sandbox_passed else ""

    trail = build_trail_from_legacy_upload(
        ingestion_mode=mode,
        source_ip=source_ip,
        file_name=filename,
        file_size_bytes=len(content),
        content=content,
        sandbox_passed=sandbox_passed,
        quarantine_reason=quarantine_reason,
        ledger_entry_id=ledger_entry_id,
        sha256_hash=file_hash,
        previous_hash=previous_hash,
        merkle_root=merkle,
        worm_storage_path=raw_path,
        **triage_info,
    )

    return trail


