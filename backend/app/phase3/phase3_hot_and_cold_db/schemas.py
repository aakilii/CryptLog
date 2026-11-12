from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Phase2Payload(BaseModel):
    Target_User: str = Field(default="")
    Notes: str = Field(default="")
    Lineage: str = Field(default="")
    audit_id: str = Field(default="")
    source_type: str = Field(default="")
    extracted_variables: str = Field(default="{}")
    ner_tags: str = Field(default="{}")
    normalized_timestamp: Optional[str] = Field(default=None)
    row_hash: str = Field(default="")
    final_row_hash: str = Field(default="")


class LockRequest(BaseModel):
    Lineage: str


class ExtendRequest(BaseModel):
    Lineage: str
    seconds: int = 30


class RemoveRequest(BaseModel):
    Lineage: str


class GraphQLQueryRequest(BaseModel):
    depth: int = 1
    Target_User: str = Field(default="")
    limit: int = 1000
    offset: int = 0


class QueryLogsRequest(BaseModel):
    """Flexible log query used by Operation Room import and other consumers."""
    source_type: str = Field(default="")
    time_start: str = Field(default="")
    time_end: str = Field(default="")
    target_user: str = Field(default="")
    limit: int = Field(default=5000, ge=1, le=20000)
    offset: int = Field(default=0, ge=0)
