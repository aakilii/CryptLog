"""
Network & Exfiltration Analysis API routes.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/cases/{case_id}/network", tags=["network"])


class RunNetworkRequest(BaseModel):
    source_filters: list[str] = []
    time_start: Optional[str] = None
    time_end: Optional[str] = None


@router.post("/run")
async def run_network(case_id: str, body: RunNetworkRequest):
    from operation_room.services.network_agent import run_network_analysis
    try:
        return run_network_analysis(
            case_id, source_filters=body.source_filters,
            time_start=body.time_start, time_end=body.time_end,
        )
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/flows")
async def get_flows(case_id: str,
                    run_id: Optional[str] = None,
                    suspicious_only: bool = False,
                    direction: Optional[str] = None,
                    protocol: Optional[str] = None):
    from operation_room.services.network_agent import get_network_flows
    try:
        return get_network_flows(case_id, run_id, suspicious_only, direction, protocol)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/exfil")
async def get_exfil(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.network_agent import get_exfil_candidates
    try:
        return get_exfil_candidates(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/destinations")
async def get_destinations_route(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.network_agent import get_destinations
    try:
        return get_destinations(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/runs")
async def list_runs(case_id: str):
    from operation_room.services.network_agent import get_network_runs
    try:
        return get_network_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/summary")
async def get_network_summary(case_id: str, run_id: Optional[str] = None):
    """Aggregated network summary used by Studio refresh and cards."""
    from operation_room.services.network_agent import get_network_flows, get_exfil_candidates, get_network_entities
    try:
        flows = get_network_flows(case_id, run_id=run_id, limit=500)
        exfil = get_exfil_candidates(case_id, run_id=run_id)
        high_risk_entities = get_network_entities(case_id, risk_level="high", limit=50)
        total_bytes_out = 0
        for flow in flows:
            total_bytes_out += int(flow.get("bytes_sent") or flow.get("bytes_out") or 0)
        return {
            "run_id": run_id,
            "total_flows": len(flows),
            "exfil_candidates": len(exfil),
            "high_risk_entities": len(high_risk_entities),
            "total_bytes_out": total_bytes_out,
            "top_exfil_candidates": exfil[:10],
            "top_high_risk_entities": high_risk_entities[:10],
        }
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/flows/search")
async def search_network_flows(case_id: str, payload: dict = Body(...), limit: int = Query(default=500, le=5000), offset: int = Query(default=0)):
    from operation_room.services.network_agent import get_network_flows_search
    try:
        return get_network_flows_search(case_id, payload, limit, offset)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.post("/flows/stats/search")
async def search_network_flows_stats(case_id: str, payload: dict = Body(...)):
    from operation_room.services.network_agent import get_network_flows_stats_search
    try:
        return get_network_flows_stats_search(case_id, payload)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.get("/fields/{field_name}/distinct")
async def get_network_distinct_route(case_id: str, field_name: str):
    from operation_room.services.network_agent import get_network_distinct
    try:
        return get_network_distinct(case_id, field_name)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/entities")
async def get_network_entities(case_id: str, risk: Optional[str] = None, limit: int = Query(default=50, le=200)):
    """Get network entities with risk scoring."""
    from operation_room.services.network_agent import get_network_entities
    try:
        return get_network_entities(case_id, risk_level=risk, limit=limit)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        return []
