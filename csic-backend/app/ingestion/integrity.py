import os
from sqlalchemy.orm import Session
from app.db.models import AuditLog
from app.core.security import compute_sha256
from app.config import settings


def verify_file_integrity(db: Session, audit_id: str):
    record = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not record:
        return {"status": "not_found"}

    file_path = os.path.join(settings.RAW_STORAGE_PATH, record.filename)

    if not os.path.exists(file_path):
        return {"status": "file_missing"}

    with open(file_path, "rb") as f:
        current_hash = compute_sha256(f.read())

    if current_hash != record.sha256_hash:
        return {
            "status": "tampered",
            "expected_hash": record.sha256_hash,
            "current_hash": current_hash
        }

    return {"status": "valid"}


def verify_hash_chain(db: Session):
    records = db.query(AuditLog).order_by(AuditLog.upload_time.asc()).all()

    previous_hash = None

    for record in records:
        if record.previous_hash != previous_hash:
            return {
                "status": "chain_broken",
                "broken_at": record.id
            }

        previous_hash = record.sha256_hash

    return {"status": "chain_valid"}
