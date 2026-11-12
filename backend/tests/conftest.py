"""Shared pytest fixtures providing isolated DB and temporary storage per test."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.db.base import Base
import app.db.models  # noqa: F401 - ensure all ORM models register on Base.metadata
import app.auth.models  # noqa: F401 - ensure User registers on Base.metadata
from app.db import session as db_session_module
from app.db.session import get_db
from app.main import new_app


@pytest.fixture()
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all storage directories to a per-test temporary directory."""
    dirs = {
        "RAW_STORAGE_PATH": tmp_path / "raw",
        "PARQUET_STORAGE_PATH": tmp_path / "parquet",
        "WORM_STORAGE_PATH": tmp_path / "worm",
        "QUARANTINE_PATH": tmp_path / "quarantine",
        "TEMP_CHUNKS_PATH": tmp_path / "temp",
    }
    for attr, folder in dirs.items():
        folder.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, attr, str(folder))

    # Patch module-level Path constants where ingestion modules cache them.
    from app.ingestion import sandbox, ws_router

    monkeypatch.setattr(ws_router, "TEMP_CHUNKS_DIR", dirs["TEMP_CHUNKS_PATH"])
    monkeypatch.setattr(ws_router, "WORM_DIR", dirs["WORM_STORAGE_PATH"])
    if hasattr(sandbox, "QUARANTINE_DIR"):
        monkeypatch.setattr(sandbox, "QUARANTINE_DIR", dirs["QUARANTINE_PATH"])

    return tmp_path


@pytest.fixture()
def db_session(
    isolated_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite session wired into app.db.session."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(db_session_module, "engine", test_engine)
    monkeypatch.setattr(db_session_module, "SessionLocal", TestingSessionLocal)

    from app.ingestion import ws_router

    monkeypatch.setattr(ws_router, "SessionLocal", TestingSessionLocal)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient backed by the isolated test DB session."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    new_app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(new_app) as test_client:
            yield test_client
    finally:
        new_app.dependency_overrides.clear()

