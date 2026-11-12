"""
Investigation API Routes

These routes expose the UnifiedInvestigationOrchestrator to the frontend.

Endpoints:
- POST /api/investigation/start - Start new investigation with SSE streaming
- GET /api/investigation/{id} - Get investigation status
- GET /api/investigation/list - List all investigations
- POST /api/investigation/{id}/stop - Stop running investigation
- GET /api/investigation/{id}/report - Get investigation report
- POST /api/investigation/{id}/canvas - Stream to canvas
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio

from operation_room.services.unified_orchestrator import unified_orchestrator
from operation_room.tools.base_tool import EventType


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/investigation", tags=["investigation"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class StartInvestigationRequest(BaseModel):
    """Request to start a new investigation."""
    case_id: str = Field(..., description="Case ID")
    scenario: str = Field(..., description="Investigation scenario text")
    options: Optional[dict] = Field(default=None, description="Investigation options")
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "case-001",
                "scenario": "A Windows computer and Android phone were seized. Suspect transferred confidential files via USB, Bluetooth, and email.",
                "options": {
                    "traversal": "bfs_then_dfs",
                    "auto_answer_timeout": 60,
                    "llm_provider": "gemini"
                }
            }
        }


class InvestigationSummary(BaseModel):
    """Summary of an investigation."""
    investigation_id: str
    case_id: str
    scenario: str
    phase: str
    progress_percent: float
    hypotheses_count: int
    evidence_count: int
    findings_count: int
    created_at: str
    updated_at: str
    error: Optional[str] = None


class InvestigationDetail(BaseModel):
    """Detailed investigation state."""
    investigation_id: str
    case_id: str
    scenario: str
    phase: str
    progress_percent: float
    entities: list
    hypotheses: list
    plan: Optional[dict]
    evidence: list
    tool_results: dict
    confidence_scores: dict
    findings: list
    report: Optional[dict]
    created_at: str
    updated_at: str
    error: Optional[str] = None


# ─── SSE Helper ──────────────────────────────────────────────────────────────

async def investigation_event_stream(
    case_id: str,
    scenario: str,
    options: Optional[dict] = None
):
    """Generate SSE events from investigation stream."""
    stream_investigation_id: Optional[str] = None

    try:
        async for event in unified_orchestrator.run_investigation(
            case_id=case_id,
            scenario=scenario,
            options=options
        ):
            resolved_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)

            # Promote specialized finding payloads to top-level event types for UI compatibility.
            if resolved_type == EventType.FINDING.value and isinstance(event.data, dict):
                finding_type = event.data.get("type")
                if finding_type in {"hypothesis", "hypothesis_verdict"}:
                    resolved_type = finding_type
                elif finding_type == "overall_confidence":
                    resolved_type = "confidence"

            # Format as SSE - use 'type' to match frontend contract
            payload: Dict[str, Any]
            if isinstance(event.data, dict):
                payload = dict(event.data)
            else:
                payload = {"value": event.data}

            if resolved_type == EventType.ERROR.value and "message" not in payload and "error" in payload:
                payload["message"] = str(payload.get("error"))

            event_data = {
                "type": resolved_type,
                "timestamp": event.timestamp,
                "data": payload,
            }
            # Add phase at top-level if available in data
            if "phase" in payload:
                event_data["phase"] = payload["phase"]

            if isinstance(payload.get("investigation_id"), str):
                stream_investigation_id = payload["investigation_id"]

            if stream_investigation_id:
                event_data["investigation_id"] = stream_investigation_id

            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Allow other coroutines to run
            await asyncio.sleep(0)
            
    except Exception as e:
        logger.error(f"Investigation stream error: {e}", exc_info=True)
        error_event = {
            "type": "error",
            "timestamp": "",
            "data": {"message": str(e)},
        }
        if stream_investigation_id:
            error_event["investigation_id"] = stream_investigation_id
        yield f"data: {json.dumps(error_event)}\n\n"
    
    # Signal completion
    complete_event = {"type": "complete", "timestamp": "", "data": {}}
    if stream_investigation_id:
        complete_event["investigation_id"] = stream_investigation_id
    yield f"data: {json.dumps(complete_event)}\n\n"


# ─── API Routes ──────────────────────────────────────────────────────────────

@router.post("/start", response_class=StreamingResponse)
async def start_investigation(request: StartInvestigationRequest):
    """
    Start a new investigation with SSE streaming.
    
    Returns a Server-Sent Events stream with real-time updates:
    - Phase transitions
    - Tool executions
    - Findings
    - Visualizations
    - Progress updates
    
    Example usage with EventSource:
    ```javascript
    const evtSource = new EventSource('/api/investigation/start', {
        method: 'POST',
        body: JSON.stringify({ case_id: 'case-001', scenario: '...' })
    });
    
    evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Event:', data.event_type, data.data);
    };
    ```
    """
    return StreamingResponse(
        investigation_event_stream(
            case_id=request.case_id,
            scenario=request.scenario,
            options=request.options
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/list", response_model=list[InvestigationSummary])
async def list_investigations():
    """List all investigations with summary information."""
    investigations = unified_orchestrator.list_investigations()
    return investigations


@router.get("/{investigation_id}", response_model=InvestigationDetail)
async def get_investigation(investigation_id: str):
    """Get detailed investigation state."""
    state = unified_orchestrator.get_investigation(investigation_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    
    return InvestigationDetail(
        investigation_id=state.investigation_id,
        case_id=state.case_id,
        scenario=state.scenario,
        phase=state.phase.value,
        progress_percent=state.progress_percent,
        entities=state.entities,
        hypotheses=state.hypotheses,
        plan=state.plan,
        evidence=state.evidence,
        tool_results={k: v.to_dict() if hasattr(v, 'to_dict') else {} for k, v in state.tool_results.items()},
        confidence_scores=state.confidence_scores,
        findings=state.findings,
        report=state.report,
        created_at=state.created_at,
        updated_at=state.updated_at,
        error=state.error,
    )


@router.get("/{investigation_id}/report")
async def get_investigation_report(investigation_id: str):
    """Get investigation report."""
    state = unified_orchestrator.get_investigation(investigation_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    
    if not state.report:
        raise HTTPException(status_code=404, detail="Report not yet generated")
    
    return state.report


@router.post("/{investigation_id}/stop")
async def stop_investigation(investigation_id: str):
    """Stop a running investigation."""
    if not unified_orchestrator.request_stop(investigation_id):
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")

    return {
        "status": "stopping",
        "investigation_id": investigation_id,
        "message": "Stop requested. Investigation will halt gracefully.",
    }


# ─── Canvas Integration ──────────────────────────────────────────────────────

class CanvasStreamRequest(BaseModel):
    """Request to stream investigation to canvas."""
    doc_id: str = Field(..., description="Canvas document ID")
    starting_page: int = Field(default=1, description="Starting page number")


def _extract_tool_primary_data(tool_output: Any) -> Dict[str, Any]:
    """Extract best-effort visualization payload from ToolOutput."""
    legacy = getattr(tool_output, "primary_data", None)
    if isinstance(legacy, dict):
        return legacy

    visualizations = getattr(tool_output, "visualizations", None)
    if isinstance(visualizations, list) and visualizations:
        first = visualizations[0]
        if hasattr(first, "to_dict"):
            first_dict = first.to_dict()
            if isinstance(first_dict, dict):
                data = first_dict.get("data")
                if isinstance(data, dict):
                    return data

        data_attr = getattr(first, "data", None)
        if isinstance(data_attr, dict):
            return data_attr

    tables = getattr(tool_output, "tables", None)
    if isinstance(tables, list) and tables and isinstance(tables[0], dict):
        return tables[0]

    return {}


@router.post("/{investigation_id}/canvas")
async def stream_to_canvas(investigation_id: str, request: CanvasStreamRequest):
    """
    Stream investigation results to a canvas document.
    
    This creates canvas elements from investigation findings:
    - Timeline charts
    - Anomaly heatmaps
    - Entity graphs
    - Evidence blocks
    - Narrative text
    
    The canvas is updated in real-time as findings are processed.
    """
    state = unified_orchestrator.get_investigation(investigation_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} not found")
    
    # Generate canvas layout from investigation state
    canvas_elements = []
    current_page = request.starting_page
    
    # 1. Executive Summary text block
    canvas_elements.append({
        "page": current_page,
        "element": {
            "type": "text",
            "content": f"# Executive Summary\n\nInvestigation: {state.scenario[:200]}...\n\nTotal Findings: {len(state.findings)}\nOverall Confidence: {sum(state.confidence_scores.values()) / max(1, len(state.confidence_scores)):.0%}",
        }
    })
    
    # 2. Hypothesis summary
    current_page += 1
    for hyp in state.hypotheses:
        canvas_elements.append({
            "page": current_page,
            "element": {
                "type": "hypothesis_card",
                "data": {
                    "id": hyp.get("id"),
                    "statement": hyp.get("statement"),
                    "verdict": hyp.get("verdict", "PENDING"),
                    "confidence": hyp.get("final_confidence", hyp.get("posterior_confidence", 0.5)),
                }
            }
        })
    
    # 3. Timeline visualization
    current_page += 1
    if "timeline" in state.tool_results:
        timeline_result = state.tool_results["timeline"]
        canvas_elements.append({
            "page": current_page,
            "element": {
                "type": "visualization",
                "widget": "TimelineHeatmap",
                "data": _extract_tool_primary_data(timeline_result),
            }
        })
    
    # 4. Anomaly chart
    current_page += 1
    if "anomaly" in state.tool_results:
        anomaly_result = state.tool_results["anomaly"]
        canvas_elements.append({
            "page": current_page,
            "element": {
                "type": "visualization",
                "widget": "AnomalyScatter",
                "data": _extract_tool_primary_data(anomaly_result),
            }
        })
    
    # 5. Network graph
    current_page += 1
    if "correlation" in state.tool_results:
        correlation_result = state.tool_results["correlation"]
        canvas_elements.append({
            "page": current_page,
            "element": {
                "type": "visualization",
                "widget": "EntityGraph",
                "data": _extract_tool_primary_data(correlation_result),
            }
        })
    
    # 6. Evidence blocks
    current_page += 1
    for idx, evidence in enumerate(state.evidence[:10]):  # Limit to 10
        canvas_elements.append({
            "page": current_page + (idx // 3),  # 3 per page
            "element": {
                "type": "evidence_block",
                "data": evidence,
            }
        })
    
    # 7. Confidence breakdown
    current_page += (len(state.evidence) // 3) + 1
    canvas_elements.append({
        "page": current_page,
        "element": {
            "type": "visualization",
            "widget": "ConfidenceRadar",
            "data": {
                "scores": state.confidence_scores,
            }
        }
    })
    
    return {
        "investigation_id": investigation_id,
        "doc_id": request.doc_id,
        "canvas_elements": canvas_elements,
        "total_pages": current_page,
    }
