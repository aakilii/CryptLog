"""Pydantic models for Case operations."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ScopeEntry(BaseModel):
    """A single scope entry — one log source + time window."""
    source_type: str = Field(..., description="AUTH, VPN, FW, DB, APP, EPP, FILE")
    time_start: str = Field(..., description="ISO‑8601 start timestamp")
    time_end: str = Field(..., description="ISO‑8601 end timestamp")
    target_actors: list[str] = Field(default_factory=list)
    target_systems: list[str] = Field(default_factory=list)


class CaseCreate(BaseModel):
    """Payload for creating a new case."""
    title: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    classification: str = Field(default="UNCLASSIFIED")
    priority: str = Field(default="MEDIUM")
    lead_investigator: str = Field(default="analyst")
    suspects: list[str] = Field(default_factory=list)
    investigation_reason: str = ""
    log_sources: list[str] = Field(default_factory=list, description="List of log source types to include")
    scope: list[ScopeEntry] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    """Partial update payload."""
    title: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    suspects: Optional[list[str]] = None
    investigation_reason: Optional[str] = None
    log_sources: Optional[list[str]] = None


class CaseResponse(BaseModel):
    """Case record returned to the client."""
    case_id: str
    title: str
    description: str
    classification: str
    priority: str
    status: str
    lead_investigator: str
    suspects: list[str]
    investigation_reason: str
    log_sources: list[str]
    created_at: str
    updated_at: str
    evidence_count: int = 0
    coc_count: int = 0


class CaseSummary(BaseModel):
    """Lightweight case card for dashboard listing."""
    case_id: str
    title: str
    priority: str
    status: str
    lead_investigator: str
    created_at: str
    evidence_count: int = 0
