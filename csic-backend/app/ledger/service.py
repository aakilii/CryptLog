from sqlalchemy.orm import Session
from app.db.models import AuditLog


def list_ledger(db: Session, limit: int = 200, offset: int = 0, q: str = ""):
    x = db.query(AuditLog)

    if q:
        s = f"%{q.strip()}%"
        x = x.filter(
            (AuditLog.filename.ilike(s)) |
            (AuditLog.uploader.ilike(s))
        )

    total = x.count()

    rows = (
        x.order_by(AuditLog.upload_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "filename": r.filename,
            "sha256_hash": r.sha256_hash,
            "previous_hash": r.previous_hash,
            "merkle_root": r.merkle_root,
            "upload_time": r.upload_time.isoformat() if r.upload_time else None,
            "file_size": r.file_size,
            "uploader": r.uploader,
            "source_ip": r.source_ip,
            "ingestion_mode": r.ingestion_mode,
            "status": r.status,
        })

    return {"status": "ok", "total": total, "items": items, "limit": limit, "offset": offset}


def get_ledger_item(db: Session, audit_id: str):
    r = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not r:
        return {"status": "not_found"}

    return {
        "status": "ok",
        "item": {
            "id": r.id,
            "filename": r.filename,
            "sha256_hash": r.sha256_hash,
            "previous_hash": r.previous_hash,
            "merkle_root": r.merkle_root,
            "upload_time": r.upload_time.isoformat() if r.upload_time else None,
            "file_size": r.file_size,
            "uploader": r.uploader,
            "source_ip": r.source_ip,
            "ingestion_mode": r.ingestion_mode,
            "status": r.status,
        }
    }
