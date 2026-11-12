"""
app/ingestion/auth_gateway.py
------------------------------
JIT Authentication Gateway — Forensic Airlock.

Enforces three mandatory rules before a WebSocket session is admitted:
  RULE 1 — IP Binding      : bound_ip must match request IP
  RULE 2 — Time-to-Live    : session must not have expired (30-min TTL)
  RULE 3 — Burn-on-Use     : session may only be consumed once (OTP)

Architecture note: Session persistence is abstracted behind SessionStore so
that a Redis backend can be dropped in without changing call-sites.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, WebSocket, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import IngestionSession
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_TTL_MINUTES: int = 30


# ---------------------------------------------------------------------------
# Session store abstraction (SQLite-backed; Redis-replaceable)
# ---------------------------------------------------------------------------

class SessionStore:
    """
    Thin wrapper around the SQLAlchemy Session for IngestionSession CRUD.
    Swap the internals for a Redis client to achieve stateless horizontal
    scaling without modifying any call-site.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, bound_ip: str, mode: str) -> IngestionSession:
        """Persist a new ephemeral session and return it."""
        session = IngestionSession(
            session_id=str(uuid.uuid4()),
            bound_ip=bound_ip,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(minutes=SESSION_TTL_MINUTES),
            used=False,
            mode=mode,
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        logger.info(
            f"[AuthGateway] Session created: {session.session_id} "
            f"mode={mode} bound_ip={bound_ip} "
            f"expires_at={session.expires_at.isoformat()}Z"
        )
        return session

    def get(self, session_id: str) -> Optional[IngestionSession]:
        return (
            self._db.query(IngestionSession)
            .filter(IngestionSession.session_id == session_id)
            .first()
        )

    def mark_used(self, session: IngestionSession) -> None:
        session.used = True
        self._db.commit()

    def link_audit(self, session: IngestionSession, audit_id: str) -> None:
        session.audit_id = audit_id
        self._db.commit()


# ---------------------------------------------------------------------------
# Airlock enforcement helpers
# ---------------------------------------------------------------------------

def _extract_client_ip(request: Request) -> str:
    """
    Extract the true client IP, respecting X-Forwarded-For when present
    (e.g. behind a reverse proxy / load balancer).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _extract_ws_client_ip(websocket: WebSocket) -> str:
    """Same as _extract_client_ip but for WebSocket objects."""
    forwarded_for = websocket.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if websocket.client:
        return websocket.client.host
    return "unknown"


def _now_utc() -> datetime:
    """Return offset-naive UTC datetime for consistent comparison."""
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# HTTP-layer validation (used by /manual and /cloud entry routes)
# ---------------------------------------------------------------------------

def validate_http_session(
    session_id: str,
    request: Request,
    store: SessionStore,
) -> IngestionSession:
    """
    Validate an existing session for HTTP-based entry points.
    Returns the session on success; raises HTTPException on any failure.
    """
    session = store.get(session_id)
    if session is None:
        logger.warning(f"[AuthGateway] Unknown session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found.",
        )

    client_ip = _extract_client_ip(request)
    _enforce_rules(session, client_ip, context="HTTP")
    return session


# ---------------------------------------------------------------------------
# WebSocket-layer validation (used by /ws/secure-stream/{session_id})
# ---------------------------------------------------------------------------

def validate_websocket_session(
    session_id: str,
    websocket: WebSocket,
    store: SessionStore,
) -> IngestionSession:
    """
    Validate session for WebSocket upgrade requests.
    Returns the session on success; raises PermissionError on any failure
    (the WS route catches this and closes with the appropriate code).
    """
    session = store.get(session_id)
    if session is None:
        logger.warning(f"[AuthGateway] WS: Unknown session_id={session_id}")
        raise PermissionError("Session not found.")

    client_ip = _extract_ws_client_ip(websocket)
    _enforce_rules(session, client_ip, context="WS")
    return session


# ---------------------------------------------------------------------------
# Core rule-enforcement logic
# ---------------------------------------------------------------------------

def _enforce_rules(
    session: IngestionSession,
    client_ip: str,
    context: str = "UNKNOWN",
) -> None:
    """
    Apply all three airlock rules.  Raises PermissionError or HTTPException
    if any rule is violated so the caller can respond appropriately.
    """
    prefix = f"[AuthGateway][{context}] session={session.session_id}"

    # RULE 1 — IP Binding
    if client_ip != session.bound_ip:
        logger.warning(
            f"{prefix} IP_MISMATCH: expected={session.bound_ip} got={client_ip}"
        )
        raise PermissionError(
            f"IP binding violation: expected {session.bound_ip}, got {client_ip}."
        )

    # RULE 2 — Time-to-Live
    if _now_utc() > session.expires_at:
        logger.warning(f"{prefix} SESSION_EXPIRED: expired_at={session.expires_at}Z")
        raise PermissionError(
            f"Session expired at {session.expires_at.isoformat()}Z."
        )

    # RULE 3 — Burn-on-Use
    if session.used:
        logger.warning(f"{prefix} SESSION_ALREADY_USED")
        raise PermissionError("Session has already been consumed (burn-on-use).")

    logger.info(f"{prefix} All airlock rules passed for IP={client_ip}.")


# ---------------------------------------------------------------------------
# Convenience factory for route handlers
# ---------------------------------------------------------------------------

def get_session_store(db: Session) -> SessionStore:
    """Dependency-injection helper."""
    return SessionStore(db)


def create_ingestion_session(
    db: Session,
    request: Request,
    mode: str,
) -> IngestionSession:
    """
    High-level helper: extract client IP and create a new session.
    Called from the three entry-point routes.
    """
    client_ip = _extract_client_ip(request)
    store = SessionStore(db)
    return store.create(bound_ip=client_ip, mode=mode)
