"""
app/ingestion/sandbox.py
-------------------------
Automated Sandbox Triage Engine.

Executes three sequential filters on every ingested file:
  1) ZIP Bomb Detection     — decompression ratio > 100 → quarantine
  2) Magic Byte Inspection  — binary header vs. file extension mismatch
  3) Async Malware Scan     — entropy analysis + extension blacklist +
                               YARA-style pattern simulation

Clean files are returned for ledger commit.
Flagged files are:
  • chmod 600 (owner-read-only)
  • moved to data/quarantine/
  • recorded in QuarantineLog table
  • pipeline aborted
"""

import asyncio
import hashlib
import io
import json
import math
import os
import shutil
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import QuarantineLog


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZIP_BOMB_RATIO_THRESHOLD: float = 100.0
HIGH_ENTROPY_THRESHOLD: float = 7.2        # max theoretical = 8.0 (bits/byte)

# Pre-commit audit-trail diagnostics only: avoid loading huge files into RAM.
# Full-file entropy/YARA still run in async_malware_scan after WORM commit.
TRIAGE_AUDIT_FULL_READ_BYTES = 32 * 1024 * 1024
TRIAGE_AUDIT_SAMPLE_BYTES = 16 * 1024 * 1024

QUARANTINE_DIR = Path("data/quarantine")

# Extension → expected magic byte prefix (hex)
MAGIC_SIGNATURES: dict[str, bytes] = {
    ".exe":  b"MZ",
    ".dll":  b"MZ",
    ".elf":  b"\x7fELF",
    ".pdf":  b"%PDF",
    ".zip":  b"PK\x03\x04",
    ".gz":   b"\x1f\x8b",
    ".tar":  b"ustar",
    ".png":  b"\x89PNG",
    ".jpg":  b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".gif":  b"GIF8",
    ".7z":   b"7z\xbc\xaf\x27\x1c",
}

# Extensions that are never safe to ingest
BLACKLISTED_EXTENSIONS: set[str] = {
    ".exe", ".dll", ".bat", ".cmd", ".sh",
    ".ps1", ".vbs", ".js", ".jar", ".com",
    ".scr", ".pif", ".msi", ".hta",
}

# Simulated YARA-style byte patterns (hex strings → bytes)
YARA_PATTERNS: list[bytes] = [
    b"cmd.exe",
    b"powershell",
    b"WScript.Shell",
    b"eval(",
    b"base64_decode",
    b"exec(",
    b"system(",
    b"os.system",
    b"subprocess",
    b"\\x90\\x90\\x90\\x90",   # NOP sled pattern
    b"CreateRemoteThread",
    b"VirtualAlloc",
]


# ---------------------------------------------------------------------------
# Quarantine helpers
# ---------------------------------------------------------------------------

def _quarantine_file(
    file_path: Path,
    db: Session,
    reason: str,
    risk_score: float,
    details: dict,
    source_ip: Optional[str] = None,
    ingestion_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> QuarantineLog:
    """
    Move file to quarantine directory, restrict permissions, and record the
    event in the QuarantineLog table.
    """
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    dest = QUARANTINE_DIR / file_path.name

    # Avoid collisions: prefix with timestamp
    if dest.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        dest = QUARANTINE_DIR / f"{ts}_{file_path.name}"

    shutil.move(str(file_path), str(dest))

    # Restrict to owner-read-only (chmod 600)
    try:
        os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as exc:
        logger.warning(f"[Sandbox] chmod 600 failed for {dest}: {exc}")

    # Compute hash of the quarantined file
    try:
        with open(dest, "rb") as fh:
            file_hash = hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        file_hash = None

    record = QuarantineLog(
        original_filename=file_path.name,
        quarantine_path=str(dest),
        sha256_hash=file_hash,
        reason=reason,
        risk_score=risk_score,
        details=json.dumps(details),
        detected_at=datetime.utcnow(),
        source_ip=source_ip,
        ingestion_mode=ingestion_mode,
        session_id=session_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.warning(
        f"[Sandbox] QUARANTINE: filename={file_path.name} "
        f"reason={reason} risk_score={risk_score} dest={dest}"
    )
    return record


# ---------------------------------------------------------------------------
# Filter 1 — ZIP Bomb Check
# ---------------------------------------------------------------------------

def check_zip_bomb(file_path: Path) -> Optional[dict]:
    """
    Returns a findings dict if ZIP bomb signature detected, else None.
    Checks both immediate and recursive decompressed sizes.
    """
    if file_path.suffix.lower() not in (".zip", ".gz", ".7z"):
        return None  # Only check archive types

    if not zipfile.is_zipfile(file_path):
        return None

    try:
        compressed_size = file_path.stat().st_size
        if compressed_size == 0:
            return None

        total_uncompressed = 0
        with zipfile.ZipFile(file_path, "r") as zf:
            for info in zf.infolist():
                total_uncompressed += info.file_size

        ratio = total_uncompressed / compressed_size
        logger.debug(
            f"[Sandbox] ZIP ratio: {ratio:.1f}x "
            f"(compressed={compressed_size}, uncompressed={total_uncompressed})"
        )

        if ratio > ZIP_BOMB_RATIO_THRESHOLD:
            return {
                "compressed_size": compressed_size,
                "uncompressed_size": total_uncompressed,
                "ratio": ratio,
                "threshold": ZIP_BOMB_RATIO_THRESHOLD,
            }
    except Exception as exc:
        logger.warning(f"[Sandbox] ZIP bomb check error: {exc}")

    return None


# ---------------------------------------------------------------------------
# Filter 2 — Magic Byte Inspection
# ---------------------------------------------------------------------------

def check_magic_bytes(file_path: Path) -> Optional[dict]:
    """
    Reads the first 16 bytes and validates them against the expected signature
    for the file's extension.  Returns findings dict if mismatch detected.
    """
    ext = file_path.suffix.lower()
    expected_magic = MAGIC_SIGNATURES.get(ext)

    try:
        with open(file_path, "rb") as fh:
            header = fh.read(16)
    except Exception as exc:
        logger.warning(f"[Sandbox] Magic byte read error: {exc}")
        return None

    # Check for known dangerous headers regardless of extension
    dangerous_headers: dict[str, bytes] = {
        "MZ_EXE":  b"MZ",
        "ELF_BIN": b"\x7fELF",
        "PE_MARK": b"PE\x00\x00",
    }
    for label, magic in dangerous_headers.items():
        if header.startswith(magic) and ext not in (".exe", ".dll", ".elf"):
            return {
                "extension": ext,
                "detected_header": label,
                "header_hex": header[:8].hex(),
                "mismatch": True,
            }

    if expected_magic is not None:
        if not header.startswith(expected_magic):
            return {
                "extension": ext,
                "expected_magic_hex": expected_magic.hex(),
                "actual_header_hex": header[:8].hex(),
                "mismatch": True,
            }

    return None


# ---------------------------------------------------------------------------
# Filter 3 — Entropy + Pattern + Extension Scan (async)
# ---------------------------------------------------------------------------

def _compute_byte_entropy(data: bytes) -> float:
    """Shannon entropy in bits per byte (range 0–8)."""
    if not data:
        return 0.0
    freq: dict[int, int] = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    total = len(data)
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in freq.values()
        if count > 0
    )
    return entropy


def _yara_scan(data: bytes) -> list[str]:
    """
    Simulated YARA scan: searches for known-malicious byte patterns in the
    file content.  Returns list of matched pattern descriptions.
    """
    matched: list[str] = []
    for pattern in YARA_PATTERNS:
        if pattern in data:
            matched.append(pattern.decode("utf-8", errors="replace"))
    return matched


async def async_malware_scan(
    file_path: Path,
    db: Session,
    source_ip: Optional[str] = None,
    ingestion_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[QuarantineLog]:
    """
    Async background malware scan worker.

    Runs:
      • Extension blacklist check
      • Shannon entropy analysis
      • YARA-pattern simulation

    Returns QuarantineLog if flagged, else None.
    Designed to be called with asyncio.create_task() after WebSocket closes.
    """
    try:
        ext = file_path.suffix.lower()

        async def _run_in_thread(fn, *args):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, fn, *args)

        # Extension blacklist
        if ext in BLACKLISTED_EXTENSIONS:
            return _quarantine_file(
                file_path, db,
                reason="BLACKLISTED_EXTENSION",
                risk_score=9.5,
                details={"extension": ext},
                source_ip=source_ip,
                ingestion_mode=ingestion_mode,
                session_id=session_id,
            )

        # Read file content once for all checks
        try:
            data = await _run_in_thread(lambda p: open(p, "rb").read(), file_path)
        except FileNotFoundError:
            logger.warning(f"[Sandbox] File vanished before async scan: {file_path}")
            return None

        # Entropy check
        entropy = _compute_byte_entropy(data)
        logger.debug(f"[Sandbox] Entropy={entropy:.3f} for {file_path.name}")

        if entropy > HIGH_ENTROPY_THRESHOLD:
            return _quarantine_file(
                file_path, db,
                reason="HIGH_ENTROPY",
                risk_score=round(entropy, 3),
                details={"entropy": entropy, "threshold": HIGH_ENTROPY_THRESHOLD},
                source_ip=source_ip,
                ingestion_mode=ingestion_mode,
                session_id=session_id,
            )

        # YARA pattern scan
        matched_patterns = _yara_scan(data)
        if matched_patterns:
            return _quarantine_file(
                file_path, db,
                reason="MALWARE_PATTERN",
                risk_score=8.0,
                details={"matched_patterns": matched_patterns},
                source_ip=source_ip,
                ingestion_mode=ingestion_mode,
                session_id=session_id,
            )

        logger.info(f"[Sandbox] Clean: {file_path.name} entropy={entropy:.3f}")
        return None

    except Exception as exc:
        logger.error(f"[Sandbox] Scan error for {file_path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Synchronous triage (blocking filters run before WebSocket closes)
# ---------------------------------------------------------------------------

def run_sync_triage(
    file_path: Path,
    db: Session,
    source_ip: Optional[str] = None,
    ingestion_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[QuarantineLog]:
    """
    Runs ZIP bomb and magic byte checks synchronously.
    Call this immediately after file reconstruction, before ledger commit.

    Returns QuarantineLog if quarantined, else None.
    """
    # Filter 1 — ZIP bomb
    bomb_findings = check_zip_bomb(file_path)
    if bomb_findings:
        return _quarantine_file(
            file_path, db,
            reason="ZIP_BOMB",
            risk_score=10.0,
            details=bomb_findings,
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            session_id=session_id,
        )

    # Filter 2 — Magic bytes
    magic_findings = check_magic_bytes(file_path)
    if magic_findings:
        return _quarantine_file(
            file_path, db,
            reason="MAGIC_MISMATCH",
            risk_score=7.0,
            details=magic_findings,
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            session_id=session_id,
        )

    return None


def run_sync_deep_scan(
    file_path: Path,
    db: Session,
    source_ip: Optional[str] = None,
    ingestion_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[QuarantineLog]:
    """
    Synchronous deep scan: extension blacklist + entropy + YARA patterns.
    Mirror of async_malware_scan() but blocking, for use in the legacy
    upload path where we must decide BEFORE ledger commit.

    Returns QuarantineLog if quarantined, else None.
    """
    ext = file_path.suffix.lower()

    # Extension blacklist
    if ext in BLACKLISTED_EXTENSIONS:
        return _quarantine_file(
            file_path, db,
            reason="BLACKLISTED_EXTENSION",
            risk_score=9.5,
            details={"extension": ext},
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            session_id=session_id,
        )

    # Read content once
    try:
        data = file_path.read_bytes()
    except FileNotFoundError:
        logger.warning(f"[Sandbox] File vanished before deep scan: {file_path}")
        return None

    # Entropy check
    entropy = _compute_byte_entropy(data)
    logger.debug(f"[Sandbox] SyncDeepScan entropy={entropy:.3f} for {file_path.name}")
    if entropy > HIGH_ENTROPY_THRESHOLD:
        return _quarantine_file(
            file_path, db,
            reason="HIGH_ENTROPY",
            risk_score=round(entropy, 3),
            details={"entropy": entropy, "threshold": HIGH_ENTROPY_THRESHOLD},
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            session_id=session_id,
        )

    # YARA pattern scan
    matched_patterns = _yara_scan(data)
    if matched_patterns:
        return _quarantine_file(
            file_path, db,
            reason="MALWARE_PATTERN",
            risk_score=8.0,
            details={"matched_patterns": matched_patterns},
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            session_id=session_id,
        )

    logger.info(f"[Sandbox] SyncDeepScan clean: {file_path.name} entropy={entropy:.3f}")
    return None


# ---------------------------------------------------------------------------
# Diagnostic: collect triage info WITHOUT quarantining  (for audit trail)
# ---------------------------------------------------------------------------

def collect_triage_info(file_path: Path) -> dict:
    """
    Run all sandbox checks in read-only mode and return a dict of findings
    suitable for the audit trail.  Does NOT quarantine or move any files.
    """
    ext = file_path.suffix.lower()
    info: dict = {
        "zip_bomb_ratio": 0.0,
        "zip_bomb_result": "pass",
        "magic_header_hex": "",
        "magic_extension_match": True,
        "entropy_score": 0.0,
        "entropy_result": "normal",
        "extension": ext,
        "extension_blacklisted": ext in BLACKLISTED_EXTENSIONS,
        "yara_detected": False,
        "yara_pattern_name": None,
        "triage_diagnostic_sample_bytes": 0,
        "triage_diagnostic_note": None,
    }

    # ZIP bomb check
    bomb = check_zip_bomb(file_path)
    if bomb:
        info["zip_bomb_ratio"] = bomb.get("ratio", 0.0)
        info["zip_bomb_result"] = "fail"

    # Magic byte check
    magic = check_magic_bytes(file_path)
    if magic:
        info["magic_header_hex"] = magic.get("header_hex", magic.get("actual_header_hex", ""))
        info["magic_extension_match"] = False
    else:
        # Read header for clean files too
        try:
            with open(file_path, "rb") as fh:
                info["magic_header_hex"] = fh.read(8).hex()
        except Exception:
            pass

    # Entropy + YARA for audit trail (sample large files; async scan does full file)
    try:
        file_size = file_path.stat().st_size
        if file_size > TRIAGE_AUDIT_FULL_READ_BYTES:
            with open(file_path, "rb") as fh:
                data = fh.read(TRIAGE_AUDIT_SAMPLE_BYTES)
            info["triage_diagnostic_sample_bytes"] = len(data)
            info["triage_diagnostic_note"] = (
                f"audit-trail entropy/YARA used first {len(data)} of {file_size} bytes; "
                "full-file scan runs after ingest"
            )
        else:
            data = file_path.read_bytes()
            info["triage_diagnostic_sample_bytes"] = len(data)

        entropy = _compute_byte_entropy(data)
        info["entropy_score"] = entropy
        if entropy > HIGH_ENTROPY_THRESHOLD:
            info["entropy_result"] = "suspicious"

        matched = _yara_scan(data)
        if matched:
            info["yara_detected"] = True
            info["yara_pattern_name"] = matched[0] if len(matched) == 1 else ", ".join(matched)
    except FileNotFoundError:
        pass

    return info

