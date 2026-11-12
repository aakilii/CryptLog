"""Pydantic models for Timeline operations."""

from pydantic import BaseModel, Field
from typing import Optional


class TimelineBuildRequest(BaseModel):
    """Request to build / rebuild the unified timeline."""
    force_rebuild: bool = Field(default=False, description="If True, wipe and rebuild from scratch")
    time_start: Optional[str] = Field(default=None, description="Override scope start ISO-8601")
    time_end: Optional[str] = Field(default=None, description="Override scope end ISO-8601")
    source_types: list[str] = Field(default_factory=list, description="Filter to specific sources")
    cluster_window_seconds: Optional[int] = Field(default=300, description="DBSCAN window size in seconds")


class TimelineFilters(BaseModel):
    """Query-string filters for reading the timeline."""
    actor: Optional[str] = None
    source_type: Optional[str] = None
    source_system: Optional[str] = None
    action: Optional[str] = None
    severity: Optional[str] = None
    anchors_only: bool = False
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = Field(default=500, le=5000)
    offset: int = 0


class TimelineEvent(BaseModel):
    """A single normalised timeline event."""
    tl_event_id: str
    case_id: str
    original_event_id: str
    normalised_ts: str
    utc_offset: str
    source_type: str
    source_system: Optional[str] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    severity: str = "INFO"
    detail: Optional[str] = None
    is_anchor: bool = False
    anchor_label: Optional[str] = None


class AnchorEvent(BaseModel):
    """A flagged anchor event."""
    anchor_id: str
    case_id: str
    tl_event_id: str
    label: str
    auto_detected: bool
    created_by: Optional[str] = None
    created_at: Optional[str] = None


class AnchorToggleRequest(BaseModel):
    """Toggle anchor status on a timeline event."""
    tl_event_id: str
    label: str = "Manual anchor"
    is_anchor: bool = True


class TimelineStats(BaseModel):
    """Summary statistics for the timeline."""
    total_events: int
    total_anchors: int
    sources: dict
    actors: dict
    time_span_start: Optional[str] = None
    time_span_end: Optional[str] = None
    events_by_hour: dict


class TimelineBuildResult(BaseModel):
    """Result after building / rebuilding the timeline."""
    total_events: int
    clusters_detected: int
    hash_value: str
    coc_event_id: str
    message: str
