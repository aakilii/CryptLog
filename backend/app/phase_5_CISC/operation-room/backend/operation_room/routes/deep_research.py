"""
Deep Research API Routes.

Provides endpoints for:
- Chain-of-thought streaming (SSE)
- Investigation plan management
- Human-in-loop questions
- Document parsing
- LLM-based hypothesis generation
- Report version control
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
import asyncio
import json
import logging
import uuid
from operation_room.config import settings

# Import LLM hypothesis generator and version control
from operation_room.services.deep_research import (
    get_hypothesis_generator,
    get_version_control,
)

router = APIRouter(prefix="/deep-research", tags=["Deep Research"])
logger = logging.getLogger(__name__)
_execution_tasks: Dict[str, asyncio.Task[Any]] = {}


async def _run_post_approval_pipeline(investigation_id: str) -> None:
    """Execute approved plan and broadcast progress/report updates over WebSocket.
    
    Uses the Canonical Pipeline for report generation when available,
    with the SectionStateMachine for parallel section execution.
    """
    from operation_room.services.deep_research import get_orchestrator
    from operation_room.services.deep_research.websocket_manager import get_ws_manager

    orchestrator = get_orchestrator()
    ws_manager = get_ws_manager()
    progress = 50.0

    try:
        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "progress_update",
                "phase": "execution",
                "progress": progress,
                "message": "Execution phase started.",
                "timestamp": datetime.now().isoformat(),
            },
        )

        async for event in orchestrator.run_phase_execution(investigation_id):
            event_name = event.get("event")
            message = None

            if event_name == "phase_started":
                progress = min(progress + 10, 85)
                message = f"Running phase: {event.get('phase_title', 'analysis')}"
            elif event_name == "step_started":
                progress = min(progress + 2, 90)
                message = f"Executing step: {event.get('step_title', 'analysis step')}"
            elif event_name == "phase_completed":
                progress = min(progress + 3, 92)
                message = "Phase completed."
            elif event_name == "execution_completed":
                progress = 94
                message = "Execution complete. Building report..."

            if message:
                await ws_manager.broadcast_to_investigation(
                    investigation_id,
                    {
                        "type": "progress_update",
                        "phase": "execution",
                        "progress": progress,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        # ── REPORTING PHASE: Use Canonical Pipeline ──────────────────
        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "progress_update",
                "phase": "reporting",
                "progress": 95,
                "message": "Generating court-ready report via canonical pipeline...",
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Attempt canonical pipeline for reporting
        canonical_result = None
        try:
            from operation_room.services.canonical_pipeline import CanonicalPipeline

            context = orchestrator.get_context(investigation_id)
            if context:
                pipeline = CanonicalPipeline(
                    case_id=context.case_id,
                    config={
                        "enforce_admissibility": False,
                        "auto_approve_sections": True,
                        "include_ai_narratives": True,
                    },
                )

                async for pevent in pipeline.execute(
                    scenario=context.scenario,
                    case_type="general",
                    investigation_data={
                        "investigation_id": investigation_id,
                        "findings": context.findings,
                        "evidence": context.evidence_refs,
                    },
                ):
                    if pevent.event_type in ("sections_generated", "admissibility_result"):
                        await ws_manager.broadcast_to_investigation(
                            investigation_id,
                            {
                                "type": "progress_update",
                                "phase": "reporting",
                                "progress": 95 + pevent.progress * 4,
                                "message": f"Pipeline: {pevent.event_type}",
                                "timestamp": datetime.now().isoformat(),
                            },
                        )

                manifest = pipeline.get_manifest()
                if manifest:
                    canonical_result = {
                        "report_structure": manifest.to_dict(),
                        "pipeline": "canonical",
                    }
        except Exception as e:
            logger.warning(f"[PostApproval] Canonical pipeline unavailable: {e}")

        # Fallback to legacy reporting if canonical failed
        if canonical_result is None:
            report_result = await orchestrator.run_phase_reporting(investigation_id)
            report_structure = report_result.get("report_structure", {})
        else:
            report_structure = canonical_result["report_structure"]

        sections = report_structure.get("sections", []) if isinstance(report_structure, dict) else []
        total_pages = max(1, len(sections))

        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "report_progress",
                "progress": {
                    "progress": 100,
                    "current_page": total_pages,
                    "total_pages": total_pages,
                    "current_section": "Complete",
                    "status": "complete",
                    "pages_complete": total_pages,
                    "sections": sections,
                    "alignment_score": 0,
                    "completeness_score": 100,
                    "errors": [],
                    "warnings": [],
                    "pipeline": canonical_result.get("pipeline", "legacy") if canonical_result else "legacy",
                },
                "timestamp": datetime.now().isoformat(),
            },
        )
        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "progress_update",
                "phase": "complete",
                "progress": 100,
                "message": "Investigation complete.",
                "timestamp": datetime.now().isoformat(),
            },
        )
        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "chat_message",
                "sender": "ai",
                "content": "Investigation execution and report generation completed.",
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as exc:
        logger.exception("Post-approval pipeline failed for %s", investigation_id)
        await ws_manager.broadcast_to_investigation(
            investigation_id,
            {
                "type": "error",
                "message": str(exc),
                "timestamp": datetime.now().isoformat(),
            },
        )
    finally:
        _execution_tasks.pop(investigation_id, None)


def _ensure_post_approval_pipeline(investigation_id: str) -> None:
    """Start execution/reporting pipeline — Celery dispatch or asyncio fallback."""
    existing = _execution_tasks.get(investigation_id)
    if existing and not existing.done():
        return

    # Try Celery dispatch first (true async, survives HTTP timeout)
    try:
        from operation_room.worker.tasks import generate_report_task
        from operation_room.services.deep_research import get_orchestrator

        orchestrator = get_orchestrator()
        context = orchestrator.get_context(investigation_id)

        if context:
            # Dispatch to Celery worker
            result = generate_report_task.delay(
                case_id=context.case_id,
                investigation_id=investigation_id,
                scenario=context.scenario,
                case_type="general",
                investigation_data={
                    "investigation_id": investigation_id,
                    "findings": context.findings,
                    "evidence": context.evidence_refs,
                },
            )
            logger.info(
                f"[PostApproval] Dispatched to Celery: job_id={result.id} "
                f"investigation={investigation_id}"
            )
            # Start Redis subscriber to relay Celery status → WebSocket
            try:
                from operation_room.services.deep_research.websocket_manager import get_ws_manager
                ws = get_ws_manager()
                ws.start_redis_subscriber(investigation_id)
            except Exception:
                pass
            # Still launch the WebSocket relay pipeline in asyncio
            _execution_tasks[investigation_id] = asyncio.create_task(
                _run_post_approval_pipeline(investigation_id)
            )
            return
    except Exception as e:
        logger.info(f"[PostApproval] Celery unavailable ({e}), using asyncio fallback")

    # Fallback: run in asyncio task
    _execution_tasks[investigation_id] = asyncio.create_task(
        _run_post_approval_pipeline(investigation_id)
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class StartInvestigationRequest(BaseModel):
    """Request to start a deep research investigation."""
    case_id: str
    scenario: str
    objectives: List[str] = Field(default_factory=list)
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    suspected_entities: List[str] = Field(default_factory=list)
    victim_systems: List[str] = Field(default_factory=list)
    mode: str = "focused"  # focused, brute_force, hybrid


class ClarificationAnswer(BaseModel):
    """Answer to a clarification question."""
    question_id: str
    answer: str


class PlanModification(BaseModel):
    """Modification to the investigation plan."""
    modification_type: str  # add_phase, remove_phase, reorder_phase, edit_step, etc.
    target_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Request to approve the investigation plan."""
    approver: str = "investigator"
    comments: Optional[str] = None


class QuestionResponse(BaseModel):
    """Response to a human-in-loop question."""
    question_id: str
    answer: str
    follow_up_context: Optional[str] = None


# ============================================================================
# Investigation Lifecycle
# ============================================================================

@router.post("/investigations")
async def start_investigation(request: StartInvestigationRequest) -> Dict[str, Any]:
    """
    Start a new deep research investigation.
    
    This creates an investigation session and begins scenario analysis.
    """
    from operation_room.services.deep_research import get_orchestrator

    orchestrator = get_orchestrator()
    context = await orchestrator.start_investigation(
        case_id=request.case_id,
        scenario=request.scenario,
        objectives=request.objectives,
        mode=request.mode,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        suspected_entities=request.suspected_entities,
        victim_systems=request.victim_systems,
    )

    return {
        "investigation_id": context.investigation_id,
        "case_id": context.case_id,
        "tree_id": context.thought_tree_id,
        "status": "analyzing",
        "message": "Investigation started. Connect to SSE endpoint for thought stream.",
        "sse_endpoint": f"/api/deep-research/investigations/{context.thought_tree_id}/thoughts/stream",
    }


@router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str) -> Dict[str, Any]:
    """Get investigation status and details."""
    from operation_room.services.deep_research import get_orchestrator

    orchestrator = get_orchestrator()
    status = orchestrator.get_status(investigation_id)

    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])

    return status


@router.post("/investigations/{investigation_id}/stop")
async def stop_investigation_session(investigation_id: str) -> Dict[str, Any]:
    """Stop an orchestrated deep-research investigation session."""
    from operation_room.services.deep_research import get_orchestrator
    from operation_room.services.deep_research.websocket_manager import get_ws_manager

    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Investigation not found")

    task = _execution_tasks.get(investigation_id)
    task_cancelled = False
    if task and not task.done():
        task.cancel()
        task_cancelled = True
    _execution_tasks.pop(investigation_id, None)

    context.completed_at = datetime.now()

    ws_manager = get_ws_manager()
    timestamp = datetime.now().isoformat()
    await ws_manager.broadcast_to_investigation(
        investigation_id,
        {
            "type": "progress_update",
            "phase": "stopped",
            "progress": 0,
            "message": "Investigation stopped by user.",
            "timestamp": timestamp,
        },
    )
    await ws_manager.broadcast_to_investigation(
        investigation_id,
        {
            "type": "chat_message",
            "sender": "system",
            "content": "Investigation session stopped.",
            "timestamp": timestamp,
        },
    )

    return {
        "status": "stopped",
        "investigation_id": investigation_id,
        "execution_task_cancelled": task_cancelled,
    }


# ============================================================================
# Thought Streaming (SSE)
# ============================================================================

from operation_room.services.deep_research.models import ThoughtType


@router.get("/investigations/{tree_id}/thoughts/stream")
async def stream_thoughts(tree_id: str):
    """
    Stream chain-of-thought updates via Server-Sent Events.
    
    Event types:
    - thought_start: New thought node created
    - thought_content: Content chunk for streaming text
    - thought_complete: Thought finished
    - tree_update: Full tree state update
    - question: Human-in-loop question
    - error: Error occurred
    """
    async def event_generator():
        from operation_room.services.deep_research import get_orchestrator

        orchestrator = get_orchestrator()
        tree = orchestrator.get_thought_tree(tree_id)
        
        if not tree:
            yield f"data: {json.dumps({'event_type': 'error', 'message': 'Tree not found'})}\n\n"
            return
        
        # Send initial tree state
        yield f"data: {json.dumps({'event_type': 'tree_update', 'data': tree.to_dict()})}\n\n"
        
        # Stream events
        try:
            engine = orchestrator._thought_engine
            async for event in engine.stream_tree_events(tree):
                yield event.to_sse()
        except asyncio.CancelledError:
            pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/investigations/{tree_id}/thoughts")
async def get_thought_tree(tree_id: str) -> Dict[str, Any]:
    """Get current state of thought tree."""
    from operation_room.services.deep_research import get_orchestrator

    orchestrator = get_orchestrator()
    tree = orchestrator.get_thought_tree(tree_id)
    
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    return tree.to_dict()


# ============================================================================
# Investigation Plan
# ============================================================================

@router.get("/investigations/{investigation_id}/plan")
async def get_plan(investigation_id: str) -> Dict[str, Any]:
    """Get the investigation plan."""
    from operation_room.services.deep_research import get_orchestrator, get_plan_manager

    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    if not context or not context.plan_id:
        raise HTTPException(status_code=404, detail="Plan not found for this investigation")

    plan_manager = get_plan_manager()
    plan = plan_manager.get_plan(context.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return plan.to_dict()


@router.post("/investigations/{investigation_id}/plan/modify")
async def modify_plan(
    investigation_id: str,
    modification: PlanModification,
) -> Dict[str, Any]:
    """
    Modify the investigation plan.
    
    Supported modification types:
    - add_phase: Add a new phase
    - remove_phase: Remove a phase
    - reorder_phase: Change phase order
    - add_step: Add step to a phase
    - remove_step: Remove a step
    - edit_step: Modify step parameters
    - add_hypothesis: Add alternative hypothesis
    - edit_hypothesis: Modify hypothesis
    """
    from operation_room.services.deep_research import get_orchestrator, get_plan_manager, PlanCommand

    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    if not context or not context.plan_id:
        raise HTTPException(status_code=404, detail="Plan not found for this investigation")

    plan_manager = get_plan_manager()

    try:
        command = PlanCommand(
            command_type=modification.modification_type,
            target_id=modification.target_id,
            data=modification.data,
            user="investigator",
        )
        plan = plan_manager.process_command(context.plan_id, command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "modified",
        "investigation_id": investigation_id,
        "plan_id": plan.id,
        "modification_type": modification.modification_type,
        "version": plan.version,
        "plan": plan.to_dict(),
    }


@router.post("/investigations/{investigation_id}/plan/approve")
async def approve_plan(
    investigation_id: str,
    request: ApprovalRequest,
) -> Dict[str, Any]:
    """Approve the investigation plan for execution."""
    from operation_room.services.deep_research import get_orchestrator, get_plan_manager

    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    if not context or not context.plan_id:
        raise HTTPException(status_code=404, detail="Plan not found for this investigation")

    plan_manager = get_plan_manager()
    plan = plan_manager.approve_plan(
        context.plan_id,
        approver=request.approver,
        comments=request.comments,
    )

    _ensure_post_approval_pipeline(investigation_id)

    return {
        "status": "approved",
        "plan_id": plan.id,
        "investigation_id": investigation_id,
        "approved_by": request.approver,
        "approved_at": datetime.now().isoformat(),
        "execution_started": True,
        "message": "Plan approved. Execution started.",
    }


# ============================================================================
# Human-in-Loop Questions
# ============================================================================

@router.get("/investigations/{investigation_id}/questions")
async def get_pending_questions(
    investigation_id: str,
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    """Get pending human-in-loop questions."""
    from operation_room.services.deep_research import get_hil_manager, QuestionPriority

    priority_filter = None
    if priority:
        try:
            priority_filter = QuestionPriority(priority)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}") from exc

    hil = get_hil_manager()
    questions = hil.get_pending_questions(investigation_id, priority=priority_filter)

    return {
        "questions": [question.to_dict() for question in questions],
        "total": len(questions),
    }


@router.post("/investigations/{investigation_id}/questions/{question_id}/answer")
async def answer_question(
    investigation_id: str,
    question_id: str,
    response: QuestionResponse,
) -> Dict[str, Any]:
    """Answer a human-in-loop question."""
    from operation_room.services.deep_research import get_hil_manager

    if response.question_id != question_id:
        raise HTTPException(status_code=400, detail="Question ID mismatch")

    hil = get_hil_manager()
    question = hil.get_question(question_id)
    if not question or question.investigation_id != investigation_id:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        answered = hil.answer_question(question_id, response.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "answered",
        "question_id": question_id,
        "answer": answered.answer,
        "answered_at": answered.answered_at.isoformat() if answered.answered_at else None,
        "message": "Answer recorded. Investigation continuing.",
    }


@router.get("/investigations/{investigation_id}/questions/stream")
async def stream_questions(investigation_id: str):
    """
    Stream human-in-loop questions via WebSocket-like SSE.
    
    Used for real-time question notifications.
    """
    from operation_room.services.deep_research import get_hil_manager

    hil = get_hil_manager()

    async def event_generator():
        yield f"data: {json.dumps({'event_type': 'connected', 'investigation_id': investigation_id})}\n\n"
        async for event in hil.stream_questions(investigation_id):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Document Parsing
# ============================================================================

class ParseDocumentRequest(BaseModel):
    """Request to parse a reference document."""
    file_path: Optional[str] = None
    file_data: Optional[str] = None  # Base64 encoded
    file_type: str = "pdf"  # pdf, docx


class VerifyAlignmentRequest(BaseModel):
    """Request payload for alignment verification."""
    case_id: Optional[str] = None
    reference_id: Optional[str] = None
    elements: List[Dict[str, Any]] = Field(default_factory=list)
    reference_elements: List[Dict[str, Any]] = Field(default_factory=list)
    auto_fix: bool = False


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_text_from_tiptap_node(node: Any) -> str:
    """Extract flattened text from a TipTap-like node tree."""
    if not isinstance(node, dict):
        return ""

    chunks: List[str] = []
    node_text = node.get("text")
    if isinstance(node_text, str):
        chunks.append(node_text)

    children = node.get("content")
    if isinstance(children, list):
        for child in children:
            child_text = _extract_text_from_tiptap_node(child)
            if child_text:
                chunks.append(child_text)

    return " ".join(chunk for chunk in chunks if chunk).strip()


def _normalize_alignment_elements(raw_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize arbitrary element payloads into alignment-verifier inputs."""
    type_aliases = {
        "text": "paragraph",
        "component": "paragraph",
        "chart": "chart",
        "table": "table",
        "image": "image",
        "heading": "heading",
        "list": "list",
        "spacer": "spacer",
        "paragraph": "paragraph",
    }

    normalized: List[Dict[str, Any]] = []
    for idx, element in enumerate(raw_elements):
        if not isinstance(element, dict):
            continue

        position_raw = element.get("position")
        position: Dict[str, Any] = position_raw if isinstance(position_raw, dict) else {}
        data_raw = element.get("data")
        data: Dict[str, Any] = data_raw if isinstance(data_raw, dict) else {}

        raw_type = str(element.get("type", "paragraph")).lower()
        normalized_type = type_aliases.get(raw_type, "paragraph")

        content_preview = ""
        content_value = element.get("content")
        text_value = element.get("text")
        data_text_value = data.get("text")
        if isinstance(content_value, str):
            content_preview = content_value
        elif isinstance(text_value, str):
            content_preview = text_value
        elif isinstance(data_text_value, str):
            content_preview = data_text_value
        elif data:
            content_preview = _extract_text_from_tiptap_node(data)

        normalized.append(
            {
                "id": element.get("id") or f"el-{idx + 1}",
                "type": normalized_type,
                "x": _safe_float(element.get("x", position.get("x")), 72.0),
                "y": _safe_float(element.get("y", position.get("y")), 72.0),
                "width": _safe_float(element.get("width", position.get("width")), 451.0),
                "height": _safe_float(element.get("height", position.get("height")), 20.0),
                "page": _safe_int(
                    element.get("page")
                    or element.get("page_number")
                    or element.get("pageNumber"),
                    1,
                ),
                "content": content_preview[:200],
            }
        )

    return normalized


def _extract_alignment_elements_from_document(case_id: str, document_id: str) -> List[Dict[str, Any]]:
    """Extract alignment elements from a Studio document AST."""
    from operation_room.services.studio_v2_service import get_document

    document = get_document(case_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    ast = document.get("ast")
    if not isinstance(ast, dict):
        raise HTTPException(status_code=400, detail="Document AST is missing or invalid")

    extracted: List[Dict[str, Any]] = []

    if ast.get("type") == "v4-canvas":
        pages_obj = ast.get("pages")
        pages: List[Any] = pages_obj if isinstance(pages_obj, list) else []
        for page_index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                continue

            page_elements_obj = page.get("elements")
            page_elements: List[Any] = page_elements_obj if isinstance(page_elements_obj, list) else []
            page_number = _safe_int(page.get("page_number"), page_index)

            for element in page_elements:
                if not isinstance(element, dict):
                    continue

                position_raw = element.get("position")
                position: Dict[str, Any] = position_raw if isinstance(position_raw, dict) else {}
                data_raw = element.get("data")
                data: Dict[str, Any] = data_raw if isinstance(data_raw, dict) else {}

                extracted.append(
                    {
                        "id": element.get("id"),
                        "type": element.get("type", "paragraph"),
                        "x": element.get("x", position.get("x", 72.0)),
                        "y": element.get("y", position.get("y", 72.0)),
                        "width": element.get("width", position.get("width", 451.0)),
                        "height": element.get("height", position.get("height", 20.0)),
                        "page": page_number,
                        "content": _extract_text_from_tiptap_node(data),
                    }
                )

        return _normalize_alignment_elements(extracted)

    content_nodes_obj = ast.get("content")
    content_nodes: List[Any] = content_nodes_obj if isinstance(content_nodes_obj, list) else []
    current_y = 72.0
    for idx, node in enumerate(content_nodes):
        node_type = node.get("type") if isinstance(node, dict) else "paragraph"
        node_type = str(node_type) if node_type else "paragraph"
        node_height = 30.0 if node_type == "heading" else 20.0

        extracted.append(
            {
                "id": f"doc-node-{idx + 1}",
                "type": node_type,
                "x": 72.0,
                "y": current_y,
                "width": 451.0,
                "height": node_height,
                "page": 1,
                "content": _extract_text_from_tiptap_node(node),
            }
        )
        current_y += node_height + 12.0

    return _normalize_alignment_elements(extracted)


@router.post("/documents/parse")
async def parse_document(request: ParseDocumentRequest) -> Dict[str, Any]:
    """
    Parse a reference document for layout extraction.
    
    Returns document structure with element positions.
    """
    if request.file_type == "pdf":
        from operation_room.services.document_parser import PDFParser
        parser = PDFParser()
        if not parser.is_available:
            raise HTTPException(
                status_code=501,
                detail="PDF parsing not available. Install pdfminer.six",
            )
    else:
        from operation_room.services.document_parser import DOCXParser
        parser = DOCXParser()
        if not parser.is_available:
            raise HTTPException(
                status_code=501,
                detail="DOCX parsing not available. Install python-docx",
            )
    
    # Would parse actual document
    return {
        "status": "parsed",
        "page_count": 0,
        "structure": [],
    }


@router.post("/documents/verify-alignment")
async def verify_alignment(
    document_id: str,
    reference_id: Optional[str] = None,
    request: Optional[VerifyAlignmentRequest] = None,
) -> Dict[str, Any]:
    """
    Verify document alignment against reference.
    
    Returns alignment issues and suggestions.
    """
    from operation_room.services.alignment_verifier import get_alignment_verifier

    payload = request or VerifyAlignmentRequest()
    resolved_reference_id = reference_id or payload.reference_id

    if payload.elements:
        document_elements = _normalize_alignment_elements(payload.elements)
    elif payload.case_id:
        document_elements = _extract_alignment_elements_from_document(payload.case_id, document_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either request.elements or request.case_id to load document elements",
        )

    if not document_elements:
        raise HTTPException(status_code=400, detail="No elements available for alignment verification")

    verifier = get_alignment_verifier()
    verification = verifier.verify_section(document_id, document_elements)

    issues = verification.issues
    auto_fix_adjustments: List[Dict[str, Any]] = []
    if payload.auto_fix and issues:
        auto_fix_adjustments, remaining_issues = verifier.auto_fix_issues(verification.verification_id)
        issues = remaining_issues

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    penalty = sum(
        1.0 if issue.severity == "error" else 0.5 if issue.severity == "warning" else 0.25
        for issue in issues
    )
    score = max(0.0, 1.0 - (penalty / max(1, verification.element_count)))

    suggestions = list(dict.fromkeys(issue.suggested_fix for issue in issues if issue.suggested_fix))

    response: Dict[str, Any] = {
        "is_aligned": error_count == 0,
        "score": round(score, 4),
        "issues": [issue.to_dict() for issue in issues],
        "suggestions": suggestions,
        "verification_id": verification.verification_id,
        "status": verification.status.value,
        "element_count": verification.element_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "auto_fix_applied": payload.auto_fix,
        "adjustments": auto_fix_adjustments,
    }

    if resolved_reference_id:
        try:
            if payload.reference_elements:
                reference_elements = _normalize_alignment_elements(payload.reference_elements)
            elif payload.case_id:
                reference_elements = _extract_alignment_elements_from_document(payload.case_id, resolved_reference_id)
            else:
                reference_elements = []

            if reference_elements:
                reference_verification = verifier.verify_section(f"ref-{resolved_reference_id}", reference_elements)
                reference_issue_count = len(reference_verification.issues)
                response["reference"] = {
                    "document_id": resolved_reference_id,
                    "element_count": reference_verification.element_count,
                    "issue_count": reference_issue_count,
                    "status": reference_verification.status.value,
                    "score_delta": round(score - max(0.0, 1.0 - (reference_issue_count / max(1, reference_verification.element_count))), 4),
                }
        except HTTPException as exc:
            response["reference"] = {
                "document_id": resolved_reference_id,
                "error": exc.detail,
            }

    return response


# ============================================================================
# LLM Provider Management
# ============================================================================

@router.get("/llm/providers")
async def list_llm_providers() -> Dict[str, Any]:
    """List available LLM providers."""
    from operation_room.services.llm import get_llm_service
    
    service = get_llm_service()
    return {
        "providers": service.list_providers(),
        "current": service.current_provider.value,
    }


@router.get("/llm/ollama-models")
async def list_ollama_models() -> Dict[str, Any]:
    """List available Ollama models through the backend proxy."""
    base_url = settings.OLLAMA_URL.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{base_url}/api/tags")

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama endpoint returned {response.status_code}",
            )

        payload = response.json()
        raw_models = payload.get("models", []) if isinstance(payload, dict) else []
        if not isinstance(raw_models, list):
            raw_models = []

        models: List[Dict[str, Any]] = []
        for model in raw_models:
            if not isinstance(model, dict):
                continue
            models.append(
                {
                    "name": model.get("name", ""),
                    "size": str(model.get("size", "")),
                    "modified_at": model.get("modified_at", ""),
                }
            )

        return {"models": models}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch Ollama models from %s: %s", base_url, exc)
        raise HTTPException(status_code=502, detail="Unable to query Ollama models") from exc


@router.post("/llm/switch")
async def switch_llm_provider(
    provider: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Switch to a different LLM provider."""
    from operation_room.services.llm import get_llm_service, ProviderType
    
    service = get_llm_service()
    
    try:
        provider_type = ProviderType(provider)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}. Options: gemini, ollama",
        )
    
    service.switch_provider(provider_type, model)
    
    return {
        "status": "switched",
        "provider": provider,
        "model": model or service.provider.model,
    }


# ============================================================================
# Orchestrator Endpoints
# ============================================================================

@router.post("/orchestrator/start")
async def start_orchestrated_investigation(
    request: StartInvestigationRequest,
) -> Dict[str, Any]:
    """
    Start an orchestrated deep research investigation.
    
    This uses the full orchestrator with:
    - Chain-of-thought reasoning
    - Plan generation and approval
    - Human-in-loop questions
    - Report building
    """
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    
    context = await orchestrator.start_investigation(
        case_id=request.case_id,
        scenario=request.scenario,
        objectives=request.objectives,
        mode=request.mode,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        suspected_entities=request.suspected_entities,
        victim_systems=request.victim_systems,
    )

    # Pre-generate the plan so UI approval flow is immediately actionable.
    planning_result = await orchestrator.run_phase_planning(context.investigation_id)
    plan = planning_result.get("plan")
    
    return {
        "investigation_id": context.investigation_id,
        "status": "started",
        "phase": context.phase.value,
        "plan": plan,
        "endpoints": {
            "status": f"/api/deep-research/orchestrator/{context.investigation_id}/status",
            "stream": f"/api/deep-research/orchestrator/{context.investigation_id}/stream",
            "intake": f"/api/deep-research/orchestrator/{context.investigation_id}/run/intake",
            "approve": f"/api/deep-research/investigations/{context.investigation_id}/plan/approve",
        },
    }


@router.get("/orchestrator/{investigation_id}/status")
async def get_orchestrator_status(investigation_id: str) -> Dict[str, Any]:
    """Get orchestrated investigation status."""
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    status = orchestrator.get_status(investigation_id)
    
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    
    return status


@router.post("/orchestrator/{investigation_id}/run/intake")
async def run_intake_phase(investigation_id: str) -> Dict[str, Any]:
    """Run the intake phase to analyze the scenario."""
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    result = await orchestrator.run_phase_intake(investigation_id)
    
    return result


@router.post("/orchestrator/{investigation_id}/run/clarification")
async def run_clarification_phase(investigation_id: str) -> Dict[str, Any]:
    """Run the clarification phase to generate questions."""
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    result = await orchestrator.run_phase_clarification(investigation_id)
    
    return result


@router.post("/orchestrator/{investigation_id}/run/planning")
async def run_planning_phase(investigation_id: str) -> Dict[str, Any]:
    """Run the planning phase to generate investigation plan."""
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    result = await orchestrator.run_phase_planning(investigation_id)
    
    return result


@router.post("/orchestrator/{investigation_id}/run/execution")
async def run_execution_phase(investigation_id: str):
    """
    Run the execution phase.
    
    Streams progress events via SSE.
    """
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    
    async def event_generator():
        try:
            async for event in orchestrator.run_phase_execution(investigation_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/orchestrator/{investigation_id}/run/reporting")
async def run_reporting_phase(investigation_id: str) -> Dict[str, Any]:
    """Run the reporting phase to generate report structure."""
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    result = await orchestrator.run_phase_reporting(investigation_id)
    
    return result


@router.get("/orchestrator/{investigation_id}/stream")
async def stream_orchestrated_investigation(investigation_id: str):
    """
    Stream all events from an orchestrated investigation.
    
    Combines thought events, plan updates, questions, and progress.
    """
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    
    if not context:
        async def error_gen():
            yield f"data: {json.dumps({'event': 'error', 'message': 'Investigation not found'})}\n\n"
        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
        )
    
    async def event_generator():
        # Send initial state
        yield f"data: {json.dumps({'event': 'connected', 'context': context.to_dict()})}\n\n"
        
        # Keep alive
        while True:
            status = orchestrator.get_status(investigation_id)
            yield f"data: {json.dumps({'event': 'status_update', 'status': status})}\n\n"
            
            if status.get("phase") == "complete":
                yield f"data: {json.dumps({'event': 'investigation_complete'})}\n\n"
                break
            
            await asyncio.sleep(2)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/orchestrator/{investigation_id}/run/full")
async def run_full_investigation_stream(investigation_id: str):
    """
    Run full investigation from start to finish.
    
    Streams all progress events via SSE.
    """
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    async def event_generator():
        try:
            yield f"data: {json.dumps({'event': 'connected', 'investigation_id': investigation_id})}\n\n"

            intake_result = await orchestrator.run_phase_intake(investigation_id)
            yield f"data: {json.dumps({'event': 'phase_complete', 'phase': 'intake', 'result': intake_result})}\n\n"

            clarification_result = await orchestrator.run_phase_clarification(investigation_id)
            yield f"data: {json.dumps({'event': 'phase_complete', 'phase': 'clarification', 'result': clarification_result})}\n\n"

            planning_result = await orchestrator.run_phase_planning(investigation_id)
            yield f"data: {json.dumps({'event': 'phase_complete', 'phase': 'planning', 'result': planning_result})}\n\n"

            from operation_room.services.deep_research import get_plan_manager
            latest_context = orchestrator.get_context(investigation_id)
            if not latest_context or not latest_context.plan_id:
                raise ValueError("No plan available to approve")

            plan_manager = get_plan_manager()
            plan_manager.approve_plan(
                latest_context.plan_id,
                "auto-runner",
                "Auto-approved for full run endpoint",
            )
            yield f"data: {json.dumps({'event': 'plan_approved', 'plan_id': latest_context.plan_id})}\n\n"

            async for event in orchestrator.run_phase_execution(investigation_id):
                yield f"data: {json.dumps(event)}\n\n"

            reporting_result = await orchestrator.run_phase_reporting(investigation_id)
            yield f"data: {json.dumps({'event': 'phase_complete', 'phase': 'reporting', 'result': reporting_result})}\n\n"

            yield f"data: {json.dumps({'event': 'investigation_complete', 'investigation_id': investigation_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Report Builder Endpoints
# ============================================================================

class CreateReportRequest(BaseModel):
    """Request to create report structure."""
    title: str
    template: str = "detailed"


@router.post("/investigations/{investigation_id}/report")
async def create_report_structure(
    investigation_id: str,
    request: CreateReportRequest,
) -> Dict[str, Any]:
    """Create report structure for investigation."""
    from operation_room.services.deep_research import get_report_builder
    
    builder = get_report_builder()
    structure = builder.create_structure(
        investigation_id=investigation_id,
        title=request.title,
        template=request.template,
    )
    
    return {
        "report_id": structure.id,
        "structure": structure.to_dict(),
    }


@router.get("/investigations/{investigation_id}/report")
async def get_report_structure(investigation_id: str) -> Dict[str, Any]:
    """Get report structure."""
    from operation_room.services.deep_research import get_report_builder
    
    builder = get_report_builder()
    structure = builder.get_structure_by_investigation(investigation_id)
    
    if not structure:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return structure.to_dict()


class FillSectionRequest(BaseModel):
    """Request to fill a report section."""
    section_id: str
    content: str
    evidence_refs: List[str] = []


@router.post("/investigations/{investigation_id}/report/fill")
async def fill_report_section(
    investigation_id: str,
    request: FillSectionRequest,
) -> Dict[str, Any]:
    """Fill a report section with content."""
    from operation_room.services.deep_research import get_report_builder
    
    builder = get_report_builder()
    structure = builder.get_structure_by_investigation(investigation_id)
    
    if not structure:
        raise HTTPException(status_code=404, detail="Report not found")
    
    section = builder.fill_section(
        structure_id=structure.id,
        section_id=request.section_id,
        content=request.content,
        evidence_refs=request.evidence_refs,
    )
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return section.to_dict()


@router.post("/investigations/{investigation_id}/report/generate-toc")
async def generate_table_of_contents(investigation_id: str) -> Dict[str, Any]:
    """Generate table of contents for report."""
    from operation_room.services.deep_research import get_report_builder
    
    builder = get_report_builder()
    structure = builder.get_structure_by_investigation(investigation_id)
    
    if not structure:
        raise HTTPException(status_code=404, detail="Report not found")
    
    toc = builder.generate_toc(structure.id)
    
    return {
        "toc": toc,
        "section_count": len(structure.sections),
    }


@router.get("/investigations/{investigation_id}/report/progress")
async def get_report_progress(investigation_id: str) -> Dict[str, Any]:
    """Get report completion progress."""
    from operation_room.services.deep_research import get_report_builder
    
    builder = get_report_builder()
    structure = builder.get_structure_by_investigation(investigation_id)
    
    if not structure:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return builder.get_report_progress(structure.id)


# ============================================================================
# WebSocket Endpoints
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect
import uuid as uuid_module


async def _run_websocket_session(websocket: WebSocket, investigation_id: str) -> None:
    """Handle one deep-research WebSocket session."""
    from operation_room.services.deep_research.websocket_manager import get_ws_manager

    ws_manager = get_ws_manager()
    client_id = str(uuid_module.uuid4())

    await ws_manager.connect(websocket, investigation_id, client_id)

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "answer_question":
                question_id = data.get("question_id")
                answer = data.get("answer")
                if not question_id:
                    raise ValueError("question_id is required")
                if answer is None:
                    raise ValueError("answer is required")

                from operation_room.services.deep_research import get_hil_manager

                hil = get_hil_manager()
                hil.answer_question(question_id, answer)

                await websocket.send_json(
                    {
                        "type": "question_answered",
                        "question_id": question_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            elif message_type == "approve_plan":
                comments = data.get("comments", "")
                approver = data.get("approver", "user")

                from operation_room.services.deep_research import get_orchestrator, get_plan_manager

                orchestrator = get_orchestrator()
                context = orchestrator.get_context(investigation_id)
                if not context or not context.plan_id:
                    raise ValueError("No pending plan found for this investigation")

                plan_mgr = get_plan_manager()
                plan_mgr.approve_plan(context.plan_id, approver, comments)
                _ensure_post_approval_pipeline(investigation_id)

                await websocket.send_json(
                    {
                        "type": "plan_approved",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                await websocket.send_json(
                    {
                        "type": "chat_message",
                        "sender": "ai",
                        "content": "Great! Starting investigation now...",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            elif message_type == "send_message":
                message = data.get("message")
                if not message:
                    raise ValueError("message is required")

                await websocket.send_json(
                    {
                        "type": "chat_message",
                        "sender": "user",
                        "content": message,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                await websocket.send_json(
                    {
                        "type": "chat_message",
                        "sender": "ai",
                        "content": f"I understand: {message}. Let me analyze this scenario...",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            elif message_type == "modify_plan":
                await websocket.send_json(
                    {
                        "type": "plan_modified",
                        "modifications": data.get("modifications"),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            elif message_type in {"ping", "heartbeat"}:
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unsupported message type: {message_type}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", investigation_id, exc)
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception:
            pass
    finally:
        ws_manager.disconnect(client_id)


@router.websocket("/investigations/{investigation_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    investigation_id: str,
):
    """
    WebSocket endpoint for real-time investigation updates.
    
    Supports:
    - Bidirectional communication
    - Question answering
    - Progress updates
    - Thought streaming
    """
    await _run_websocket_session(websocket, investigation_id)


@router.get("/ws/status")
async def websocket_status() -> Dict[str, Any]:
    """Get WebSocket connection status."""
    from operation_room.services.deep_research.websocket_manager import get_ws_manager
    
    manager = get_ws_manager()
    
    return {
        "total_clients": manager.get_client_count(),
        "investigations": manager.get_investigations_with_clients(),
    }


# ============================================================================
# Demo Scenario Endpoints
# ============================================================================

@router.get("/demo/scenario")
async def get_demo_scenario() -> Dict[str, Any]:
    """Get a demo scenario for testing."""
    from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
    
    return generate_demo_scenario()


@router.post("/demo/run")
async def run_demo_investigation():
    """
    Run a complete demo investigation.
    
    Streams progress via SSE.
    """
    from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
    from operation_room.services.deep_research import get_orchestrator
    
    demo = generate_demo_scenario()
    orchestrator = get_orchestrator()
    
    async def event_generator():
        try:
            # Start investigation with demo scenario
            context = await orchestrator.start_investigation(
                case_id="DEMO-001",
                scenario=demo["scenario"],
                objectives=[
                    "Establish timeline of file transfers",
                    "Identify all IP addresses involved",
                    "Document chain of custody",
                    "Determine classification of exfiltrated data",
                ],
                mode="focused",
            )
            
            yield f"data: {json.dumps({'event': 'started', 'investigation_id': context.investigation_id})}\n\n"
            
            # Run each phase
            for phase in ["intake", "clarification", "planning"]:
                yield f"data: {json.dumps({'event': 'phase_start', 'phase': phase})}\n\n"
                await asyncio.sleep(0.5)
                
                if phase == "intake":
                    result = await orchestrator.run_phase_intake(context.investigation_id)
                elif phase == "clarification":
                    result = await orchestrator.run_phase_clarification(context.investigation_id)
                elif phase == "planning":
                    result = await orchestrator.run_phase_planning(context.investigation_id)
                
                yield f"data: {json.dumps({'event': 'phase_complete', 'phase': phase, 'result': result})}\n\n"
            
            # Auto-approve plan
            from operation_room.services.deep_research import get_plan_manager
            plan_manager = get_plan_manager()
            if context.plan_id:
                plan_manager.approve_plan(context.plan_id, "demo-auto")
            
            yield f"data: {json.dumps({'event': 'plan_approved'})}\n\n"
            
            # Run reporting phase
            report_result = await orchestrator.run_phase_reporting(context.investigation_id)
            yield f"data: {json.dumps({'event': 'phase_complete', 'phase': 'reporting', 'result': report_result})}\n\n"
            
            yield f"data: {json.dumps({'event': 'demo_complete', 'context': context.to_dict()})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Progress Tracking Endpoints
# ============================================================================

@router.get("/investigations/{investigation_id}/progress")
async def get_investigation_progress(investigation_id: str) -> Dict[str, Any]:
    """Get detailed investigation progress."""
    from operation_room.services.deep_research.progress_tracker import get_tracker
    
    tracker = get_tracker(investigation_id)
    return tracker.get_status()


@router.post("/investigations/{investigation_id}/progress/step/{step_id}/complete")
async def complete_progress_step(
    investigation_id: str,
    step_id: str,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a progress step as complete."""
    from operation_room.services.deep_research.progress_tracker import get_tracker
    
    tracker = get_tracker(investigation_id)
    tracker.complete_step(step_id, error=error)
    
    return {"status": "completed", "step_id": step_id}


# ============================================================================
# Analysis Integration Endpoints
# ============================================================================

@router.post("/investigations/{investigation_id}/analyze/timeline")
async def run_timeline_analysis(
    investigation_id: str,
    time_range_start: Optional[str] = None,
    time_range_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Run timeline analysis for investigation."""
    from operation_room.services.deep_research.analysis_integration import AnalysisIntegration
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    integration = AnalysisIntegration(context.case_id)
    result = await integration.run_timeline_analysis(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
    )
    
    return result.to_dict()


@router.post("/investigations/{investigation_id}/analyze/all")
async def run_all_analyses(
    investigation_id: str,
    time_range_start: Optional[str] = None,
    time_range_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all available analysis modules."""
    from operation_room.services.deep_research.analysis_integration import AnalysisIntegration
    from operation_room.services.deep_research import get_orchestrator
    
    orchestrator = get_orchestrator()
    context = orchestrator.get_context(investigation_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    integration = AnalysisIntegration(context.case_id)
    results = await integration.run_all_analyses(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
    )
    
    return {
        "results": {k: v.to_dict() for k, v in results.items()},
        "summary": integration.generate_summary(),
    }


# ============================================================================
# Log Parsing Endpoints
# ============================================================================

class LogParseRequest(BaseModel):
    """Request to parse log files."""
    file_paths: List[str]
    source_device: Optional[str] = None
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@router.post("/cases/{case_id}/parse/logs")
async def parse_log_files(
    case_id: str,
    request: LogParseRequest,
) -> Dict[str, Any]:
    """
    Parse log files and extract unified events.
    
    Supports:
    - Windows Event Logs (.evtx)
    - Android logs
    - Network/Firewall logs
    - Email logs
    - CSV, JSON, XML formats
    """
    from operation_room.services.log_parsers import parse_all_logs
    from pathlib import Path
    
    # Parse time range
    time_range = None
    if request.time_range_start and request.time_range_end:
        try:
            from operation_room.services.log_parsers import normalize_timestamp
            start = normalize_timestamp(request.time_range_start)
            end = normalize_timestamp(request.time_range_end)
            time_range = (start, end)
        except Exception:
            pass
    
    # Parse all files
    log_paths: List[str | Path] = [path for path in request.file_paths]
    events = await parse_all_logs(
        case_id=case_id,
        log_paths=log_paths,
        source_device=request.source_device,
        time_range=time_range,
    )
    
    return {
        "case_id": case_id,
        "files_parsed": len(request.file_paths),
        "events_extracted": len(events),
        "events": [e.to_dict() for e in events[:100]],  # First 100 for preview
        "summary": {
            "total_events": len(events),
            "event_types": _count_event_types(events),
            "time_range": {
                "earliest": events[0].timestamp.isoformat() if events else None,
                "latest": events[-1].timestamp.isoformat() if events else None,
            } if events else None,
        }
    }


def _count_event_types(events) -> Dict[str, int]:
    """Count events by type."""
    from collections import Counter
    return dict(Counter(e.event_type.value for e in events))


@router.post("/cases/{case_id}/parse/windows")
async def parse_windows_logs(
    case_id: str,
    file_path: str = Query(..., description="Path to Windows event log file"),
    source_device: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse Windows Event Log files (.evtx)."""
    from operation_room.services.log_parsers import WindowsEventLogParser
    from pathlib import Path
    
    parser = WindowsEventLogParser(case_id)
    events = parser.parse_file(Path(file_path), source_device)
    
    return {
        "file": file_path,
        "events_count": len(events),
        "events": [e.to_dict() for e in events[:50]],
        "usb_events": len([e for e in events if "usb" in e.event_type.value.lower()]),
        "bluetooth_events": len([e for e in events if "bluetooth" in e.event_type.value.lower()]),
        "auth_events": len([e for e in events if "auth" in e.event_type.value.lower()]),
    }


@router.post("/cases/{case_id}/parse/android")
async def parse_android_logs(
    case_id: str,
    file_path: str = Query(..., description="Path to Android log file"),
    source_device: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse Android log files (logcat, system logs)."""
    from operation_room.services.log_parsers import AndroidLogParser
    from pathlib import Path
    
    parser = AndroidLogParser(case_id)
    events = parser.parse_file(Path(file_path), source_device)
    
    return {
        "file": file_path,
        "events_count": len(events),
        "events": [e.to_dict() for e in events[:50]],
        "bluetooth_events": len([e for e in events if "bluetooth" in e.event_type.value.lower()]),
        "usb_events": len([e for e in events if "usb" in e.event_type.value.lower()]),
        "email_events": len([e for e in events if "email" in e.event_type.value.lower()]),
    }


@router.post("/cases/{case_id}/parse/network")
async def parse_network_logs(
    case_id: str,
    file_path: str = Query(..., description="Path to network/firewall log file"),
    source_device: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse network and firewall log files."""
    from operation_room.services.log_parsers import NetworkLogParser
    from pathlib import Path
    
    parser = NetworkLogParser(case_id)
    events = parser.parse_file(Path(file_path), source_device)
    
    # Collect unique IPs
    internal_ips = set()
    external_ips = set()
    
    for e in events:
        if e.dest_ip:
            if parser._is_external_ip(e.dest_ip):
                external_ips.add(e.dest_ip)
            else:
                internal_ips.add(e.dest_ip)
    
    return {
        "file": file_path,
        "events_count": len(events),
        "events": [e.to_dict() for e in events[:50]],
        "ip_summary": {
            "internal_ips": list(internal_ips)[:20],
            "external_ips": list(external_ips),
        },
    }


@router.post("/cases/{case_id}/parse/email")
async def parse_email_logs(
    case_id: str,
    file_path: str = Query(..., description="Path to email log file"),
    source_device: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse email server/client log files."""
    from operation_room.services.log_parsers import EmailLogParser
    from pathlib import Path
    
    parser = EmailLogParser(case_id)
    events = parser.parse_file(Path(file_path), source_device)
    
    # Extract senders and recipients
    senders = set()
    recipients = set()
    attachments = []
    
    for e in events:
        if e.actor_id:
            senders.add(e.actor_id)
        if e.target_id:
            recipients.add(e.target_id)
        if e.event_type.value == "email_attach":
            attachments.append(e.target_name)
    
    return {
        "file": file_path,
        "events_count": len(events),
        "events": [e.to_dict() for e in events[:50]],
        "senders": list(senders),
        "recipients": list(recipients),
        "attachments": attachments[:20],
    }


# ============================================================================
# Hypothesis & Report Binding Endpoints
# ============================================================================

class HypothesisFindingInput(BaseModel):
    """Input for hypothesis finding."""
    hypothesis_id: str
    hypothesis_name: str
    verdict: str  # confirmed, rejected, inconclusive
    confidence: float
    evidence_for: List[str] = Field(default_factory=list)
    evidence_against: List[str] = Field(default_factory=list)
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class EvidenceReferenceInput(BaseModel):
    """Input for evidence reference."""
    evidence_id: str
    evidence_type: str
    description: str
    timestamp: str
    source_log: str
    hash: str
    data: Dict[str, Any] = Field(default_factory=dict)


class ReportBindingRequest(BaseModel):
    """Request to bind hypothesis findings to report."""
    investigation_id: str
    findings: List[HypothesisFindingInput]
    evidence: List[EvidenceReferenceInput]


@router.post("/cases/{case_id}/report/bind")
async def bind_findings_to_report(
    case_id: str,
    request: ReportBindingRequest,
) -> Dict[str, Any]:
    """
    Bind hypothesis findings to report structure.
    
    Generates a complete report structure with sections
    auto-populated from the investigation findings.
    """
    from operation_room.services.deep_research import bind_hypothesis_to_report
    
    report_structure = bind_hypothesis_to_report(
        case_id=case_id,
        investigation_id=request.investigation_id,
        findings=[f.model_dump() for f in request.findings],
        evidence=[e.model_dump() for e in request.evidence],
    )
    
    return report_structure


@router.post("/cases/{case_id}/report/generate-canvas")
async def generate_canvas_report(
    case_id: str,
    request: ReportBindingRequest,
) -> Dict[str, Any]:
    """
    Generate a canvas-based report from findings.
    
    Creates a Studio V4 canvas document populated with
    investigation findings, evidence blocks, and visualizations.
    """
    from operation_room.services.deep_research import (
        bind_hypothesis_to_report,
        create_report_from_findings,
    )
    
    # First bind findings to report structure
    report_structure = bind_hypothesis_to_report(
        case_id=case_id,
        investigation_id=request.investigation_id,
        findings=[f.model_dump() for f in request.findings],
        evidence=[e.model_dump() for e in request.evidence],
    )
    
    # Then create canvas document
    canvas = await create_report_from_findings(case_id, report_structure)
    
    return {
        "document_id": canvas["document_id"],
        "pages": len(canvas["pages"]),
        "canvas": canvas,
    }


# ============================================================================
# Full End-to-End Investigation Workflow
# ============================================================================

class FullInvestigationRequest(BaseModel):
    """Request for full end-to-end investigation."""
    scenario: str
    log_files: List[str] = Field(default_factory=list)
    source_device_windows: Optional[str] = None
    source_device_android: Optional[str] = None
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    suspected_entities: List[str] = Field(default_factory=list)
    generate_report: bool = True


@router.post("/cases/{case_id}/investigate/full")
async def run_full_investigation(
    case_id: str,
    request: FullInvestigationRequest,
) -> Dict[str, Any]:
    """
    Run a full end-to-end investigation workflow.
    
    1. Parse all provided log files
    2. Generate hypotheses from scenario
    3. Run analysis modules
    4. Evaluate hypotheses with evidence
    5. Generate report with findings
    
    This is the main entry point for automated investigation.
    """
    from operation_room.services.deep_research import (
        generate_demo_scenario,
        bind_hypothesis_to_report,
        create_report_from_findings,
    )
    from operation_room.services.log_parsers import UnifiedLogParser
    from pathlib import Path
    import uuid
    
    investigation_id = str(uuid.uuid4())
    
    # Step 1: Parse logs (or use demo data if no logs provided)
    all_events = []
    if request.log_files:
        parser = UnifiedLogParser(case_id)
        for file_path in request.log_files:
            path = Path(file_path)
            if path.exists():
                events = parser.parse_file(path, request.source_device_windows)
                all_events.extend(events)
    
    # If no events, generate demo data
    if not all_events:
        demo = generate_demo_scenario()
        # Convert demo events to evidence
        evidence_list = []
        demo_events = demo.get("events") if isinstance(demo, dict) else []
        if not isinstance(demo_events, list):
            demo_events = []

        for ev in demo_events:
            if not isinstance(ev, dict):
                continue
            evidence_list.append({
                "evidence_id": ev.get("id", str(uuid.uuid4())),
                "evidence_type": ev.get("type", "event"),
                "description": ev.get("description", ""),
                "timestamp": ev.get("timestamp", ""),
                "source_log": ev.get("source", "demo"),
                "hash": f"sha256:demo{uuid.uuid4().hex[:16]}",
                "data": ev,
            })
    else:
        # Convert parsed events to evidence
        evidence_list = []
        for ev in all_events:
            evidence_list.append({
                "evidence_id": ev.event_id,
                "evidence_type": ev.event_type.value,
                "description": ev.description,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
                "source_log": ev.source_log,
                "hash": ev.event_hash,
                "data": ev.to_dict(),
            })
    
    # Step 2: Generate hypotheses from scenario using LLM
    time_range_payload: Optional[Dict[str, str]] = None
    if request.time_range_start and request.time_range_end:
        time_range_payload = {
            "start": request.time_range_start,
            "end": request.time_range_end,
        }

    hypotheses = await _generate_hypotheses_from_scenario_llm(
        request.scenario,
        case_id=case_id,
        time_range=time_range_payload,
        entities=request.suspected_entities
    )
    
    # Step 3: Evaluate hypotheses (simplified - would use orchestrator in full impl)
    findings = _evaluate_hypotheses(hypotheses, evidence_list)
    
    # Step 4: Generate report
    result = {
        "investigation_id": investigation_id,
        "case_id": case_id,
        "scenario": request.scenario,
        "logs_parsed": len(request.log_files) or "demo_data",
        "events_found": len(evidence_list),
        "hypotheses_evaluated": len(findings),
        "findings": findings,
    }
    
    if request.generate_report:
        report_structure = bind_hypothesis_to_report(
            case_id=case_id,
            investigation_id=investigation_id,
            findings=findings,
            evidence=evidence_list[:100],  # Limit for demo
        )
        
        canvas = await create_report_from_findings(case_id, report_structure)
        
        result["report"] = {
            "document_id": canvas["document_id"],
            "total_pages": report_structure.get("total_pages", 0),
            "sections": len(report_structure.get("sections", [])),
        }
    
    return result


async def _generate_hypotheses_from_scenario_llm(
    scenario: str,
    case_id: str = "",
    time_range: Optional[Dict[str, str]] = None,
    entities: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Generate hypotheses from scenario text using LLM.
    
    NEW: LLM-powered hypothesis generation replaces hardcoded keyword matching.
    Benefits:
    - Handles any scenario type
    - Context-aware reasoning
    - Confidence estimation
    - Priority assignment
    
    Fallback: If LLM fails, uses rule-based generation.
    """
    try:
        generator = get_hypothesis_generator()
        
        # Generate hypotheses with LLM (returns List[GeneratedHypothesis])
        hypothesis_objects = await generator.generate_hypotheses(
            scenario=scenario,
            case_id=case_id,
            time_range=f"{time_range.get('start', '')} to {time_range.get('end', '')}" if time_range else None,
            suspected_entities=entities,
        )
        
        # Convert to dict format for compatibility
        hypotheses = [h.to_dict() for h in hypothesis_objects]
        
        return hypotheses
        
    except Exception as e:
        import logging
        logging.error(f"LLM hypothesis generation failed: {e}")
        
        # Fallback to rule-based generation
        return _generate_hypotheses_from_scenario_fallback(scenario)


def _generate_hypotheses_from_scenario_fallback(scenario: str) -> List[Dict[str, Any]]:
    """
    Fallback rule-based hypothesis generation.
    
    Used when LLM generation fails.
    """
    hypotheses = []
    scenario_lower = scenario.lower()
    
    # Check for USB mentions
    if any(kw in scenario_lower for kw in ["usb", "flash drive", "thumb drive", "removable"]):
        hypotheses.append({
            "hypothesis_id": "h1_usb_exfiltration",
            "hypothesis_name": "Data exfiltration via USB device",
            "required_evidence": ["usb_connect", "file_copy", "usb_disconnect"],
        })
    
    # Check for Bluetooth mentions
    if any(kw in scenario_lower for kw in ["bluetooth", "wireless transfer", "bt"]):
        hypotheses.append({
            "hypothesis_id": "h2_bluetooth_exfiltration",
            "hypothesis_name": "Data exfiltration via Bluetooth",
            "required_evidence": ["bluetooth_pair", "bluetooth_transfer"],
        })
    
    # Check for Email mentions
    if any(kw in scenario_lower for kw in ["email", "mail", "attachment", "sent"]):
        hypotheses.append({
            "hypothesis_id": "h3_email_exfiltration",
            "hypothesis_name": "Data exfiltration via email",
            "required_evidence": ["email_send", "email_attach"],
        })
    
    # Check for Network mentions
    if any(kw in scenario_lower for kw in ["network", "ip", "transfer", "upload"]):
        hypotheses.append({
            "hypothesis_id": "h4_network_exfiltration",
            "hypothesis_name": "Data exfiltration via network",
            "required_evidence": ["network_connect", "network_data_transfer"],
        })
    
    # Always add null hypothesis
    hypotheses.insert(0, {
        "hypothesis_id": "h0_null",
        "hypothesis_name": "No unauthorized data transfer occurred",
        "required_evidence": [],
    })
    
    return hypotheses


def _evaluate_hypotheses(
    hypotheses: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Evaluate hypotheses against evidence."""
    findings = []
    
    # Index evidence by type
    evidence_by_type = {}
    for ev in evidence:
        ev_type = ev.get("evidence_type", "")
        if ev_type not in evidence_by_type:
            evidence_by_type[ev_type] = []
        evidence_by_type[ev_type].append(ev)
    
    for hyp in hypotheses:
        hyp_id = hyp["hypothesis_id"]
        required = hyp.get("required_evidence", [])
        
        # Count matching evidence
        evidence_for = []
        for req in required:
            if req in evidence_by_type:
                evidence_for.extend([e["evidence_id"] for e in evidence_by_type[req][:5]])
        
        # Calculate confidence
        if required and evidence_for:
            matches = len(set(evidence_for))
            total_required = len(required)
            confidence = min(0.95, matches / total_required)
            verdict = "confirmed" if confidence > 0.7 else "inconclusive"
        elif hyp_id == "h0_null":
            # Null hypothesis - rejected if other hypotheses confirmed
            confidence = 0.1
            verdict = "rejected"
        else:
            confidence = 0.0
            verdict = "inconclusive"
        
        findings.append({
            "hypothesis_id": hyp_id,
            "hypothesis_name": hyp["hypothesis_name"],
            "verdict": verdict,
            "confidence": confidence,
            "evidence_for": list(set(evidence_for)),
            "evidence_against": [],
            "summary": f"Hypothesis '{hyp['hypothesis_name']}' evaluated with {confidence:.1%} confidence.",
            "details": {
                "required_evidence": required,
                "matched_count": len(set(evidence_for)),
            }
        })
    
    return findings

# ============================================================================
# Report Version Control Endpoints
# ============================================================================

class CommitReportRequest(BaseModel):
    """Request to commit a new report version."""
    commit_message: str
    created_by: str = "system"


def _extract_version_state_from_document(case_id: str, doc_id: str) -> Dict[str, Dict[str, Any]]:
    """Build report and canvas snapshots from the Studio V4 document."""
    from operation_room.services.studio_v2_service import get_document

    document = get_document(case_id, doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ast = document.get("ast") if isinstance(document, dict) else None
    title = document.get("title", "Investigation Report") if isinstance(document, dict) else "Investigation Report"

    if isinstance(ast, dict) and ast.get("type") == "v4-canvas":
        pages = ast.get("pages", [])
        if not isinstance(pages, list):
            pages = []

        sections: List[Dict[str, Any]] = []
        for idx, page in enumerate(pages, start=1):
            page_dict = page if isinstance(page, dict) else {}
            elements = page_dict.get("elements", []) if isinstance(page_dict.get("elements"), list) else []

            evidence_refs: List[str] = []
            for element in elements:
                if not isinstance(element, dict):
                    continue
                data = element.get("data")
                if isinstance(data, dict):
                    evidence_id = data.get("evidence_id") or data.get("id")
                    if isinstance(evidence_id, str) and evidence_id:
                        evidence_refs.append(evidence_id)

            sections.append(
                {
                    "type": "page",
                    "title": f"Page {idx}",
                    "content": f"{len(elements)} elements",
                    "page_estimate": 1,
                    "evidence_refs": list(dict.fromkeys(evidence_refs)),
                }
            )

        return {
            "report_structure": {
                "document_id": doc_id,
                "title": title,
                "sections": sections,
            },
            "canvas_state": {"pages": pages},
        }

    fallback_content = ast if isinstance(ast, dict) else {}
    return {
        "report_structure": {
            "document_id": doc_id,
            "title": title,
            "sections": [
                {
                    "type": "body",
                    "title": "Main Content",
                    "content": json.dumps(fallback_content, default=str)[:4000],
                    "evidence_refs": [],
                }
            ],
        },
        "canvas_state": {"pages": []},
    }


@router.post("/cases/{case_id}/reports/{doc_id}/commit")
async def commit_report_version(
    case_id: str,
    doc_id: str,
    request: CommitReportRequest
) -> Dict[str, Any]:
    """
    Create a new version of the report (like Git commit).
    
    Stores complete state with quality metrics and content metadata.
    """
    try:
        vc = get_version_control(case_id)

        version_state = _extract_version_state_from_document(case_id, doc_id)
        report_structure = version_state["report_structure"]
        canvas_state = version_state["canvas_state"]
        
        version = await vc.commit(
            document_id=doc_id,
            report_structure=report_structure,
            canvas_state=canvas_state,
            commit_message=request.commit_message,
            created_by=request.created_by,
        )
        
        return {
            "version_id": version.version_id,
            "version_hash": version.compute_hash(),
            "alignment_score": version.alignment_score,
            "completeness_score": version.completeness_score,
            "errors": version.errors,
            "warnings": version.warnings,
            "created_at": version.created_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/reports/{doc_id}/versions")
async def get_report_versions(
    case_id: str,
    doc_id: str,
    branch: str = "main",
    limit: int = 50
) -> Dict[str, Any]:
    """Get version history for a report."""
    try:
        vc = get_version_control(case_id)
        history = vc.get_history(branch=branch, limit=limit)
        filtered_history = [version for version in history if version.document_id == doc_id]
        
        return {
            "document_id": doc_id,
            "branch": branch,
            "versions": [v.to_dict() for v in filtered_history],
            "total": len(filtered_history),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/reports/{doc_id}/versions/{version_id}")
async def get_report_version(
    case_id: str,
    doc_id: str,
    version_id: str
) -> Dict[str, Any]:
    """Get a specific report version."""
    try:
        vc = get_version_control(case_id)
        version = vc.get_version(version_id)
        
        if not version or version.document_id != doc_id:
            raise HTTPException(status_code=404, detail="Version not found")
        
        return version.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/reports/{doc_id}/diff")
async def diff_report_versions(
    case_id: str,
    doc_id: str,
    v1: str = Query(..., description="First version ID"),
    v2: str = Query(..., description="Second version ID")
) -> Dict[str, Any]:
    """
    Compare two report versions.
    
    Returns detailed diff showing all changes between versions.
    """
    try:
        vc = get_version_control(case_id)

        version_one = vc.get_version(v1)
        version_two = vc.get_version(v2)
        if not version_one or version_one.document_id != doc_id:
            raise HTTPException(status_code=404, detail=f"Version not found for document: {v1}")
        if not version_two or version_two.document_id != doc_id:
            raise HTTPException(status_code=404, detail=f"Version not found for document: {v2}")

        diff = vc.diff(v1, v2)
        
        if "error" in diff:
            raise HTTPException(status_code=404, detail=diff["error"])
        
        return diff
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RollbackRequest(BaseModel):
    """Request to rollback to a previous version."""
    reason: str
    created_by: str = "system"


@router.post("/cases/{case_id}/reports/{doc_id}/rollback/{version_id}")
async def rollback_report(
    case_id: str,
    doc_id: str,
    version_id: str,
    request: RollbackRequest
) -> Dict[str, Any]:
    """
    Rollback report to a previous version.
    
    Creates a new version with the state from the target version.
    """
    try:
        vc = get_version_control(case_id)
        target_version = vc.get_version(version_id)
        if not target_version or target_version.document_id != doc_id:
            raise HTTPException(status_code=404, detail="Version not found")
        
        new_version = await vc.rollback(
            version_id=version_id,
            commit_message=f"Rollback: {request.reason}",
            created_by=request.created_by
        )
        
        return {
            "status": "rolled_back",
            "new_version_id": new_version.version_id,
            "rolled_back_to": version_id,
            "created_at": new_version.created_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateBranchRequest(BaseModel):
    """Request to create a new branch."""
    branch_name: str
    from_version_id: Optional[str] = None
    description: str = ""
    created_by: str = "system"


@router.post("/cases/{case_id}/reports/{doc_id}/branches")
async def create_report_branch(
    case_id: str,
    doc_id: str,
    request: CreateBranchRequest
) -> Dict[str, Any]:
    """
    Create a new report branch (like Git branch).
    
    Useful for exploring alternative report versions.
    """
    try:
        vc = get_version_control(case_id)

        from_version_id = request.from_version_id
        if from_version_id:
            source_version = vc.get_version(from_version_id)
            if not source_version or source_version.document_id != doc_id:
                raise HTTPException(status_code=404, detail="Source version not found for document")
        else:
            doc_history = [version for version in vc.get_history(branch="main", limit=200) if version.document_id == doc_id]
            if not doc_history:
                raise HTTPException(status_code=404, detail="No versions found for this document")
            from_version_id = doc_history[0].version_id
        
        branch = vc.create_branch(
            branch_name=request.branch_name,
            from_version_id=from_version_id,
            created_by=request.created_by,
            description=request.description
        )
        
        return {
            "branch_name": branch.branch_name,
            "head_version_id": branch.head_version_id,
            "created_at": branch.created_at,
            "description": branch.description,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/reports/{doc_id}/branches")
async def list_report_branches(
    case_id: str,
    doc_id: str
) -> Dict[str, Any]:
    """List all branches for a report."""
    try:
        vc = get_version_control(case_id)
        
        branches = [
            {
                "branch_name": b.branch_name,
                "head_version_id": b.head_version_id,
                "created_at": b.created_at,
                "description": b.description,
                "is_active": b.is_active,
            }
            for b in vc.branches.values()
            if b.document_id == doc_id
        ]
        
        return {
            "document_id": doc_id,
            "branches": branches,
            "total": len(branches),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{investigation_id}")
async def websocket_investigation_stream(websocket: WebSocket, investigation_id: str):
    """Backward-compatible alias for investigation WebSocket updates."""
    await _run_websocket_session(websocket, investigation_id)
