"""
app/ingestion/secure_ledger.py
--------------------------------
Ledger commit module for WebSocket-based ingestion.

Only called after ALL of the following preconditions are satisfied:
  ✓ All chunk hashes verified
  ✓ Merkle root generated
  ✓ Monolithic SHA-256 computed
  ✓ Synchronous sandbox triage passed

Writes a fully-decorated record to the SQLite AuditLog table and returns
the persisted entry.
"""

from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.core.logging import logger


def _get_last_hash(db: Session) -> str | None:
    last = (
        db.query(AuditLog)
        .order_by(AuditLog.upload_time.desc())
        .first()
    )
    return last.sha256_hash if last else None


def commit_to_ledger(
    db: Session,
    filename: str,
    file_path: Path,
    sha256_hash: str,
    merkle_root: str,
    source_ip: str,
    ingestion_mode: str,
    file_size: int,
    uploader: str | None = None,
    status: str = "ingested",
) -> AuditLog:
    """
    Build the immutable chain-append ledger entry.

    The previous_hash is taken from the most recent AuditLog row so that
    the entire log corpus forms an unbroken hash chain.

    Returns:
        Persisted AuditLog ORM object.

    Raises:
        Exception: Propagated to caller so the WebSocket route can abort
                   cleanly on any DB failure.
    """
    try:
        previous_hash = _get_last_hash(db)

        entry = AuditLog(
            filename=filename,
            sha256_hash=sha256_hash,
            previous_hash=previous_hash,
            merkle_root=merkle_root,
            upload_time=datetime.utcnow(),
            file_size=file_size,
            uploader=uploader,
            source_ip=source_ip,
            ingestion_mode=ingestion_mode,
            status=status,
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(
            f"[SecureLedger] Committed: audit_id={entry.id} "
            f"file={filename} mode={ingestion_mode} ip={source_ip} "
            f"merkle={merkle_root[:12]}… sha256={sha256_hash[:12]}…"
        )
        return entry

    except Exception as exc:
        db.rollback()
        logger.error(f"[SecureLedger] Commit failed for {filename}: {exc}")
        raise
