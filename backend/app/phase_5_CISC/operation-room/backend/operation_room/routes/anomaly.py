"""
Anomaly detection API routes.

POST /api/cases/{id}/anomalies/run     — Execute ML-based anomaly detection
GET  /api/cases/{id}/anomalies         — Get scored events (latest run)
GET  /api/cases/{id}/anomalies/summary — Get JSON summary
GET  /api/cases/{id}/anomalies/runs    — List past detection runs
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from typing import Optional

from operation_room.services.anomaly_agent import (
    run_anomaly_detection,
    get_anomalies as get_anomalies_service,
    get_anomaly_summary,
    get_anomaly_runs,
    search_anomalies as search_anomalies_service,
    get_distinct_field,
)

router = APIRouter(prefix="/api/cases/{case_id}/anomalies", tags=["anomalies"])


class RunDetectionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_type: str = "ensemble"           # isolation_forest, lof, ensemble
    contamination: float = 0.1             # 0.01 – 0.5
    n_estimators: int = 100
    source_filters: list[str] = Field(default_factory=list)
    actor_filters: list[str] = Field(default_factory=list)


@router.post("/run")
async def run_detection(case_id: str, body: RunDetectionRequest):
    """Execute ML-based anomaly detection on timeline events."""
    try:
        result = run_anomaly_detection(
            case_id=case_id,
            model_type=body.model_type,
            contamination=body.contamination,
            n_estimators=body.n_estimators,
            source_filters=body.source_filters if body.source_filters else None,
            actor_filters=body.actor_filters if body.actor_filters else None
        )
        return result
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("")
async def get_anomalies(case_id: str, run_id: Optional[str] = None, anomalies_only: bool = False):
    """Get anomalies from detection run."""
    try:
        return get_anomalies_service(case_id, run_id, anomalies_only)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/summary")
async def get_summary(case_id: str, run_id: Optional[str] = None):
    """Get anomaly detection summary statistics."""
    try:
        return get_anomaly_summary(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/sequences")
async def get_sequences(case_id: str, run_id: Optional[str] = None):
    """Get anomaly sequences (clusters of related anomalies)."""
    # TODO: Implement sequence clustering
    return []


@router.get("/runs")
async def list_runs(case_id: str):
    """List all anomaly detection runs."""
    try:
        return get_anomaly_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.post("/search")
async def search_anomalies(case_id: str, payload: dict = Body(...), limit: int = Query(default=500, le=5000), offset: int = Query(default=0)):
    """Search anomalies with filters."""
    try:
        return search_anomalies_service(case_id, payload, limit, offset)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/fields/{field_name}/distinct")
async def get_anomaly_distinct_route(case_id: str, field_name: str):
    """Get distinct values for a field."""
    try:
        return get_distinct_field(case_id, field_name)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as e:
        raise HTTPException(400, str(e))

class ThreatIntelRequest(BaseModel):
    category: str
    value: str
    justification: Optional[str] = None
    added_by: str = "investigator"

@router.post("/threat_intel")
async def add_threat_intel(case_id: str, body: ThreatIntelRequest):
    """Add a threat intel rule to ignore false positives in future runs (Phase 3 Feedback Loop)."""
    from operation_room.database import open_vault
    import uuid
    try:
        conn = open_vault(case_id)
        intel_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO threat_intel (intel_id, case_id, category, value, justification, added_by) VALUES (?, ?, ?, ?, ?, ?)",
            [intel_id, case_id, body.category, body.value, body.justification, body.added_by]
        )
        conn.close()
        return {"status": "ok", "intel_id": intel_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

