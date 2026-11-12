from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.dashboard.service import (
    get_summary,
    get_timeline,
    get_severity,
    get_recent_uploads,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return get_summary(db)


@router.get("/dashboard/timeline")
def dashboard_timeline():
    return get_timeline()


@router.get("/dashboard/severity")
def dashboard_severity():
    return get_severity()


@router.get("/dashboard/recent-uploads")
def dashboard_recent_uploads(db: Session = Depends(get_db)):
    return get_recent_uploads(db)
