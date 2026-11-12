"""API routes for Timeline Reconstruction."""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, Dict, Any
from operation_room.models.timeline import TimelineBuildRequest, AnchorToggleRequest
from operation_room.services import timeline_service

router = APIRouter(prefix="/api/cases/{case_id}/timeline", tags=["Timeline"])


@router.post("/build", status_code=201)
def build_timeline(case_id: str, payload: TimelineBuildRequest):
    """Normalise raw_events, merge into unified_timeline, detect anchors."""
    try:
        data = payload.model_dump()
        return timeline_service.build_timeline(case_id, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("")
def get_timeline(
    case_id: str,
    actor: Optional[str] = None,
    source_type: Optional[str] = None,
    source_system: Optional[str] = None,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    time_stomped_only: bool = False,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = Query(default=5000, le=50000),
    offset: int = 0,
):
    """Fetch timeline events with optional filters."""
    try:
        filters = {
            "actor": actor,
            "source_type": source_type,
            "source_system": source_system,
            "action": action,
            "severity": severity,
            "time_stomped_only": time_stomped_only,
            "time_start": time_start,
            "time_end": time_end,
            "keyword": keyword,
            "limit": limit,
            "offset": offset,
        }
        return timeline_service.get_timeline(case_id, filters)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/anchors")
def get_anchors(case_id: str):
    """List all anchor events for the case."""
    try:
        return timeline_service.get_anchors(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/anchors")
def toggle_anchor(case_id: str, payload: AnchorToggleRequest):
    """Manually add or remove an anchor flag on a timeline event."""
    try:
        return timeline_service.toggle_anchor(case_id, payload.model_dump())
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/virtualized")
def get_virtualized_timeline(case_id: str, bucket_interval: str = Query("1 hour")):
    """Get aggregated timeline to mitigate browser crashing on large datasets (>5,000 logs)."""
    try:
        return timeline_service.get_virtualized_timeline(case_id, bucket_interval)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/stats")
def get_timeline_stats(case_id: str):
    """Summary statistics: events by source, actor, hour, time span."""
    try:
        return timeline_service.get_timeline_stats(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post("/search")
def search_timeline(case_id: str, payload: dict = Body(...), limit: int = Query(default=500, le=5000), offset: int = Query(default=0), anchors_only: bool = Query(default=False)):
    """Search timeline using advanced Filter DSL."""
    try:
        return timeline_service.get_timeline_search(case_id, payload, limit, offset, anchors_only)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/stats/search")
def search_timeline_stats(case_id: str, payload: dict = Body(...), anchors_only: bool = Query(default=False)):
    """Get aggregated stats using advanced Filter DSL."""
    try:
        return timeline_service.get_timeline_stats_search(case_id, payload, anchors_only)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/fields/{field_name}/distinct")
def get_timeline_distinct(case_id: str, field_name: str):
    """Get distinct values for a field for type-ahead UI."""
    try:
        return timeline_service.get_timeline_distinct(case_id, field_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
