"""
Data Exfiltration Intelligence API routes.
"""

import json
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/cases/{case_id}/exfiltration", tags=["exfiltration"])


class RunExfilRequest(BaseModel):
    source_filters: list[str] = []
    time_start: Optional[str] = None
    time_end: Optional[str] = None


@router.post("/run")
async def run_exfiltration(case_id: str, body: RunExfilRequest):
    from operation_room.services.exfiltration_agent import run_exfiltration_analysis
    try:
        return run_exfiltration_analysis(
            case_id, source_filters=body.source_filters,
            time_start=body.time_start, time_end=body.time_end,
        )
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/run/stream")
async def run_exfiltration_stream(case_id: str, request: Request):
    """SSE endpoint — streams engine-by-engine progress to the browser."""
    from operation_room.services.exfiltration_agent import run_exfiltration_analysis_streamed

    async def event_generator():
        try:
            for event in run_exfiltration_analysis_streamed(case_id):
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except FileNotFoundError:
            yield f"data: {json.dumps({'type': 'error', 'message': f'No vault for case {case_id}'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/summary")
async def get_summary(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.exfiltration_agent import get_exfil_summary
    try:
        return get_exfil_summary(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/incidents")
async def get_incidents(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.exfiltration_agent import get_exfil_incidents
    try:
        return get_exfil_incidents(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/graph")
async def get_graph(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.exfiltration_agent import get_exfil_graph
    try:
        return get_exfil_graph(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/channels")
async def get_channels(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.exfiltration_agent import get_exfil_channels
    try:
        return get_exfil_channels(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/runs")
async def list_runs(case_id: str):
    from operation_room.services.exfiltration_agent import get_exfil_runs
    try:
        return get_exfil_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
