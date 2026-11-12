"""Pydantic models for Audit / Chain‑of‑Custody events."""

from pydantic import BaseModel, Field
from typing import Optional


class ChainOfCustodyEntry(BaseModel):
    """A single chain‑of‑custody event."""
    event_id: str
    case_id: str
    timestamp: str
    actor: str
    action: str
    target_artefact: str
    justification: Optional[str] = None
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    details: Optional[str] = None


class AuditEntry(BaseModel):
    """Global audit log entry (written to audit_log.jsonl)."""
    timestamp: str
    actor: str
    action: str
    case_id: Optional[str] = None
    target: str
    details: Optional[str] = None
