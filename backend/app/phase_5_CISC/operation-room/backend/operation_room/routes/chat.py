"""
Chat API Routes

FastAPI routes for the conversational investigation intake system.
Handles chat sessions, message processing, and hypothesis generation.
"""

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from operation_room.services.chat_service import (
    ChatService,
    ChatSession,
    ChatPhase,
    InvestigationContext
)
from operation_room.services.investigation_audit import InvestigationAuditService as AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases/{case_id}/chat", tags=["chat"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class StartChatRequest(BaseModel):
    """Request to start a new chat session."""
    investigation_id: Optional[str] = None
    initial_scenario: Optional[str] = None


class StartChatResponse(BaseModel):
    """Response from starting a chat session."""
    session_id: str
    investigation_id: Optional[str] = None
    phase: str
    welcome_message: str
    suggested_prompts: List[str]


class SendMessageRequest(BaseModel):
    """Request to send a message in a chat session."""
    message: str
    session_id: str


class MessageResponse(BaseModel):
    """Response from sending a message."""
    session_id: str
    phase: str
    response: str
    context_completeness: float
    extracted_context: Dict[str, Any]
    suggested_prompts: List[str]
    hypotheses: Optional[List[Dict[str, Any]]] = None
    ready_for_analysis: bool = False


class ChatHistoryResponse(BaseModel):
    """Response with chat history."""
    session_id: str
    messages: List[Dict[str, Any]]
    current_phase: str
    context: Dict[str, Any]


class HypothesisApprovalRequest(BaseModel):
    """Request to approve/modify hypotheses."""
    session_id: str
    approved_hypotheses: List[str]  # List of hypothesis IDs to approve
    modified_hypotheses: Optional[List[Dict[str, Any]]] = None
    custom_hypotheses: Optional[List[Dict[str, Any]]] = None


class HypothesisApprovalResponse(BaseModel):
    """Response from hypothesis approval."""
    session_id: str
    investigation_id: str
    approved_count: int
    total_hypotheses: int
    ready_for_execution: bool
    next_steps: List[str]


class ExecutionModeRequest(BaseModel):
    """Request to set execution mode."""
    session_id: str
    mode: str = Field(..., description="autopilot | smart_recommendation | run_all")


# ============================================================================
# ROUTES
# ============================================================================

@router.post("/start", response_model=StartChatResponse)
async def start_chat_session(
    case_id: str = Path(..., description="Case ID"),
    request: StartChatRequest = None
):
    """
    Start a new chat session for investigation intake.
    
    Creates a new conversational session that guides the user through
    providing investigation context (scenario, timeline, scope, actors).
    """
    try:
        chat_service = ChatService(case_id)
        
        # Create new session
        session = await chat_service.create_session(
            investigation_id=request.investigation_id if request else None
        )
        
        # Generate welcome message
        welcome = await chat_service.generate_welcome_message(session)
        
        # Log to audit
        try:
            audit = AuditService(case_id)
            audit.log_session_start(session.investigation_id, {
                "session_id": session.session_id,
                "initial_scenario": request.initial_scenario if request else None
            })
        except Exception as e:
            logger.warning(f"Audit logging failed: {e}")
        
        # If initial scenario provided, process it
        if request and request.initial_scenario:
            result = await chat_service.process_message(
                session.session_id,
                request.initial_scenario
            )
            return StartChatResponse(
                session_id=session.session_id,
                investigation_id=session.investigation_id,
                phase=result["phase"],
                welcome_message=result["response"],
                suggested_prompts=result.get("suggested_prompts", [])
            )
        
        return StartChatResponse(
            session_id=session.session_id,
            investigation_id=session.investigation_id,
            phase=session.phase.value,
            welcome_message=welcome["message"],
            suggested_prompts=welcome.get("prompts", [
                "I'm investigating a potential data breach...",
                "We noticed suspicious login activity...",
                "There's been unauthorized file access..."
            ])
        )
        
    except Exception as e:
        logger.error(f"Error starting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message", response_model=MessageResponse)
async def send_chat_message(
    case_id: str = Path(..., description="Case ID"),
    request: SendMessageRequest = None
):
    """
    Send a message in an existing chat session.
    
    The AI will:
    1. Extract context from the message
    2. Ask clarifying questions if needed
    3. Progress through phases (scenario → timeline → scope → actors)
    4. Generate hypotheses when ready
    """
    try:
        chat_service = ChatService(case_id)
        
        result = await chat_service.process_message(
            request.session_id,
            request.message
        )
        
        # Log to audit
        try:
            audit = AuditService(case_id)
            session = chat_service.get_session(request.session_id)
            if session:
                audit.log_chat_message(
                    role="user",
                    content=request.message[:500],
                    session_id=request.session_id,
                    investigation_id=session.investigation_id
                )
        except Exception as e:
            logger.warning(f"Audit logging failed: {e}")
        
        return MessageResponse(
            session_id=request.session_id,
            phase=result["phase"],
            response=result["response"],
            context_completeness=result.get("context_completeness", 0),
            extracted_context=result.get("extracted_context", {}),
            suggested_prompts=result.get("suggested_prompts", []),
            hypotheses=result.get("hypotheses"),
            ready_for_analysis=result.get("ready_for_analysis", False)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    case_id: str = Path(..., description="Case ID"),
    session_id: str = Path(..., description="Session ID"),
    limit: int = Query(50, description="Max messages to return")
):
    """
    Get chat history for a session.
    """
    try:
        chat_service = ChatService(case_id)
        
        session = chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        history = await chat_service.get_message_history(session_id, limit)
        
        return ChatHistoryResponse(
            session_id=session_id,
            messages=history,
            current_phase=session.phase.value,
            context=session.context.to_dict() if session.context else {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{session_id}")
async def get_investigation_context(
    case_id: str = Path(..., description="Case ID"),
    session_id: str = Path(..., description="Session ID")
):
    """
    Get the extracted investigation context for a session.
    """
    try:
        chat_service = ChatService(case_id)
        
        session = chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        context = session.context
        
        return {
            "session_id": session_id,
            "investigation_id": session.investigation_id,
            "phase": session.phase.value,
            "context": context.to_dict() if context else {},
            "completeness_score": context.completeness_score() if context else 0,
            "missing_fields": _get_missing_fields(context) if context else [],
            "hypotheses": session.hypotheses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hypotheses/approve", response_model=HypothesisApprovalResponse)
async def approve_hypotheses(
    case_id: str = Path(..., description="Case ID"),
    request: HypothesisApprovalRequest = None
):
    """
    Approve, modify, or add hypotheses for the investigation.
    
    After chat intake is complete, this endpoint allows the user to:
    1. Approve AI-generated hypotheses
    2. Modify existing hypotheses
    3. Add custom hypotheses
    """
    try:
        chat_service = ChatService(case_id)
        
        session = chat_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Process approvals
        approved = []
        
        # Handle approved hypotheses
        for hyp_id in request.approved_hypotheses:
            for hyp in session.hypotheses:
                if hyp.get("id") == hyp_id:
                    hyp["status"] = "approved"
                    approved.append(hyp)
        
        # Handle modified hypotheses
        if request.modified_hypotheses:
            for mod_hyp in request.modified_hypotheses:
                for i, hyp in enumerate(session.hypotheses):
                    if hyp.get("id") == mod_hyp.get("id"):
                        session.hypotheses[i] = {**hyp, **mod_hyp, "status": "approved"}
                        approved.append(session.hypotheses[i])
        
        # Handle custom hypotheses
        if request.custom_hypotheses:
            for custom in request.custom_hypotheses:
                custom["id"] = f"custom_{len(session.hypotheses)}"
                custom["status"] = "approved"
                custom["source"] = "user"
                session.hypotheses.append(custom)
                approved.append(custom)
        
        # Update session
        session.phase = ChatPhase.READY_FOR_ANALYSIS
        await chat_service.save_session(session)
        
        # Log to audit
        try:
            audit = AuditService(case_id)
            audit.log_hypothesis_approved(
                hypotheses=approved,
                investigation_id=session.investigation_id
            )
        except Exception as e:
            logger.warning(f"Audit logging failed: {e}")
        
        return HypothesisApprovalResponse(
            session_id=request.session_id,
            investigation_id=session.investigation_id,
            approved_count=len(approved),
            total_hypotheses=len(session.hypotheses),
            ready_for_execution=True,
            next_steps=[
                "Select execution mode (autopilot, smart_recommendation, or run_all)",
                "Start module execution with /api/cases/{case_id}/workflow/start",
                "Monitor progress with /api/cases/{case_id}/workflow/status"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving hypotheses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execution-mode")
async def set_execution_mode(
    case_id: str = Path(..., description="Case ID"),
    request: ExecutionModeRequest = None
):
    """
    Set the module execution mode for the investigation.
    
    Modes:
    - autopilot: AI runs all relevant modules automatically
    - smart_recommendation: AI recommends modules, user approves
    - run_all: Run all modules regardless of hypothesis
    """
    valid_modes = ["autopilot", "smart_recommendation", "run_all"]
    if request.mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {valid_modes}"
        )
    
    try:
        chat_service = ChatService(case_id)
        
        session = chat_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Store execution mode in session
        session.execution_mode = request.mode
        chat_service._save_session(session)
        
        # Determine which modules to run based on mode
        recommended_modules = _recommend_modules(session, request.mode)
        
        return {
            "session_id": request.session_id,
            "investigation_id": session.investigation_id,
            "execution_mode": request.mode,
            "recommended_modules": recommended_modules,
            "message": _get_mode_message(request.mode),
            "next_endpoint": f"/api/cases/{case_id}/workflow/start"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting execution mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_chat_sessions(
    case_id: str = Path(..., description="Case ID"),
    active_only: bool = Query(True, description="Only return active sessions")
):
    """
    List all chat sessions for a case.
    """
    try:
        chat_service = ChatService(case_id)
        sessions = await chat_service.list_sessions(active_only=active_only)
        
        return {
            "case_id": case_id,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "investigation_id": s.investigation_id,
                    "phase": s.phase.value,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "context_completeness": s.context.completeness_score() if s.context else 0
                }
                for s in sessions
            ],
            "total": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_missing_fields(context: InvestigationContext) -> List[str]:
    """Get list of missing context fields."""
    missing = []
    if not context.scenario:
        missing.append("scenario")
    if not context.timeline_start:
        missing.append("timeline")
    if not context.actors:
        missing.append("actors")
    if not context.systems:
        missing.append("systems")
    if not context.scope:
        missing.append("scope")
    return missing


def _recommend_modules(session: ChatSession, mode: str) -> List[Dict[str, Any]]:
    """Recommend modules based on hypotheses and execution mode."""
    
    # Module capabilities
    module_map = {
        "anomaly": {
            "name": "Anomaly Detection",
            "description": "Statistical analysis of event patterns",
            "relevant_for": ["suspicious_activity", "insider_threat", "policy_violation"]
        },
        "network": {
            "name": "Network Analysis",
            "description": "Network flow and connection analysis",
            "relevant_for": ["data_exfiltration", "lateral_movement", "external_attack"]
        },
        "crud": {
            "name": "CRUD Analysis",
            "description": "Create/Read/Update/Delete operation tracking",
            "relevant_for": ["data_theft", "unauthorized_access", "data_modification"]
        },
        "depth": {
            "name": "Depth Analysis",
            "description": "Access depth and permission escalation",
            "relevant_for": ["privilege_escalation", "deep_access", "permission_abuse"]
        },
        "timeline": {
            "name": "Timeline Analysis",
            "description": "Temporal pattern and sequence analysis",
            "relevant_for": ["all"]  # Always relevant
        },
        "correlation": {
            "name": "Correlation Analysis",
            "description": "Cross-module pattern correlation",
            "relevant_for": ["all"]  # Always relevant
        }
    }
    
    if mode == "run_all":
        # Return all modules
        return [
            {"module": k, **v, "recommended": True, "reason": "Run All mode"}
            for k, v in module_map.items()
        ]
    
    # Determine relevant modules based on hypotheses
    recommended = []
    hypothesis_types = set()
    
    for hyp in session.hypotheses:
        if hyp.get("status") == "approved":
            hyp_type = hyp.get("type", "").lower()
            hypothesis_types.add(hyp_type)
    
    for module_id, module_info in module_map.items():
        relevant_for = module_info["relevant_for"]
        
        if "all" in relevant_for:
            recommended.append({
                "module": module_id,
                **module_info,
                "recommended": True,
                "reason": "Relevant for all investigations"
            })
        else:
            # Check if any hypothesis type matches
            for hyp_type in hypothesis_types:
                if any(r in hyp_type for r in relevant_for):
                    recommended.append({
                        "module": module_id,
                        **module_info,
                        "recommended": True,
                        "reason": f"Relevant for hypothesis type: {hyp_type}"
                    })
                    break
            else:
                if mode == "autopilot":
                    # Skip non-relevant modules in autopilot
                    pass
                else:
                    # In smart_recommendation, show but don't recommend
                    recommended.append({
                        "module": module_id,
                        **module_info,
                        "recommended": False,
                        "reason": "Not directly related to hypotheses"
                    })
    
    return recommended


def _get_mode_message(mode: str) -> str:
    """Get user-friendly message for execution mode."""
    messages = {
        "autopilot": "Autopilot mode enabled. AI will automatically run relevant modules and generate findings.",
        "smart_recommendation": "Smart Recommendation mode enabled. AI will recommend modules for your approval before running.",
        "run_all": "Run All mode enabled. All analysis modules will be executed regardless of hypothesis relevance."
    }
    return messages.get(mode, "Mode set successfully.")
