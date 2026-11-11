from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ledger.service import list_ledger, get_ledger_item

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/ledger/list")
def ledger_list(limit: int = 200, offset: int = 0, q: str = "", db: Session = Depends(get_db)):
    return list_ledger(db, limit=limit, offset=offset, q=q)


@router.get("/ledger/{audit_id}")
def ledger_item(audit_id: str, db: Session = Depends(get_db)):
    return get_ledger_item(db, audit_id)
