"""
CRUD & Data-Access Analysis API routes.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional
from operation_room.database import open_vault, get_vault_path

router = APIRouter(prefix="/api/cases/{case_id}/crud", tags=["crud"])


class RunCrudRequest(BaseModel):
    source_filters: list[str] = []
    sensitivity_threshold: str = "LOW"
    time_start: Optional[str] = None
    time_end: Optional[str] = None


@router.post("/run")
async def run_crud(case_id: str, body: RunCrudRequest):
    from operation_room.services.crud_agent import run_crud_analysis
    try:
        return run_crud_analysis(
            case_id, source_filters=body.source_filters,
            sensitivity_threshold=body.sensitivity_threshold,
            time_start=body.time_start, time_end=body.time_end,
        )
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/events")
async def get_events(case_id: str,
                     run_id: Optional[str] = None,
                     high_risk_only: bool = False,
                     sensitivity: Optional[str] = None,
                     crud_type: Optional[str] = None):
    from operation_room.services.crud_agent import get_crud_events
    try:
        return get_crud_events(case_id, run_id, high_risk_only, sensitivity, crud_type)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/summary")
async def get_summary(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.crud_agent import get_crud_summary
    try:
        return get_crud_summary(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/runs")
async def list_runs(case_id: str):
    from operation_room.services.crud_agent import get_crud_runs
    try:
        return get_crud_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")

@router.post("/events/search")
async def search_crud_events(case_id: str, payload: dict = Body(...), limit: int = Query(default=500, le=5000), offset: int = Query(default=0)):
    from operation_room.services.crud_agent import get_crud_search
    try:
        return get_crud_search(case_id, payload, limit, offset)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.post("/events/stats/search")
async def search_crud_stats(case_id: str, payload: dict = Body(...)):
    from operation_room.services.crud_agent import get_crud_stats_search
    try:
        return get_crud_stats_search(case_id, payload)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.get("/fields/{field_name}/distinct")
async def get_crud_distinct_route(case_id: str, field_name: str):
    from operation_room.services.crud_agent import get_crud_distinct
    try:
        return get_crud_distinct(case_id, field_name)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.get("/heuristics/ransomware")
async def detect_ransomware_burst(case_id: str):
    import duckdb
    from operation_room.config import settings
    # Sliding window logic for detecting > 5000 UPDATE/DELETEs
    vault_db = get_vault_path(case_id)
    
    if not vault_db.exists():
        raise HTTPException(404, "Vault not found")

    con = open_vault(case_id)
    try:
        # First check if unified_timeline table exists
        table_check = con.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = 'unified_timeline'
        """).fetchone()
        
        if not table_check:
            con.close()
            return {"bursts": [], "message": "No timeline data available"}
        
        query = """
        WITH bucketed AS (
            SELECT 
                time_bucket(INTERVAL '5 MINUTE', normalised_ts) as time_window,
                action,
                COUNT(*) as event_count
            FROM unified_timeline
            WHERE source_system = 'CRUD' AND action IN ('UPDATE', 'DELETE')
            GROUP BY 1, 2
        )
        SELECT * FROM bucketed WHERE event_count > 5000 ORDER BY time_window ASC
        """
        results = con.execute(query).fetchall()
        
        return {
            "bursts": [
                {"window": str(row[0]), "action": row[1], "count": row[2]}
                for row in results
            ]
        }
    except Exception as e:
        import logging
        logging.error(f"Error in detect_ransomware_burst: {e}")
        raise HTTPException(500, f"Query failed: {str(e)}")
    finally:
        con.close()
