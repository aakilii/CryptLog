"""Pydantic models for evidence / log import operations."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ImportRequest(BaseModel):
    """Request to import logs for a case."""
    source_type: str = Field(..., description="AUTH, VPN, FW, DB, APP, EPP, FILE")
    time_start: str = Field(..., description="ISO‑8601 start timestamp")
    time_end: str = Field(..., description="ISO‑8601 end timestamp")
    target_actors: list[str] = Field(default_factory=list)
    target_systems: list[str] = Field(default_factory=list)
    query_text: str = Field(default="", description="Optional custom NLP query override")
    justification: str = Field(default="Initial evidence collection")


class EvidenceRecord(BaseModel):
    """A single evidence artefact with its hash."""
    hash_id: str
    case_id: str
    artefact_name: str
    artefact_type: str
    hash_algorithm: str
    hash_value: str
    record_count: int
    byte_size: int
    created_at: str
    created_by: str


class ImportResult(BaseModel):
    """Result returned after a successful import."""
    import_batch_id: str
    artefact_name: str
    record_count: int
    byte_size: int
    hash_algorithm: str
    hash_value: str
    coc_event_id: str
    message: str


class MagicQueryImportRequest(BaseModel):
    """Import rows produced by Magic Query (Phase 4 parsed_logs shape) into the case vault."""

    rows: list[dict[str, Any]] = Field(..., description="Result rows from Magic Query / parsed_logs")
    audit_id: str | None = Field(default=None, description="Active pipeline audit id when present")
    justification: str = Field(default="Magic Query result import")

    @field_validator("rows")
    @classmethod
    def limit_row_count(cls, v: list) -> list:
        if len(v) > 5000:
            raise ValueError("At most 5000 rows per import")
        if len(v) < 1:
            raise ValueError("At least one row is required")
        return v


class VerifyHashRequest(BaseModel):
    """Request to verify the integrity of an artefact."""
    hash_id: str


class VerifyHashResult(BaseModel):
    """Result of hash verification."""
    hash_id: str
    artefact_name: str
    stored_hash: str
    computed_hash: str
    match: bool
    message: str
