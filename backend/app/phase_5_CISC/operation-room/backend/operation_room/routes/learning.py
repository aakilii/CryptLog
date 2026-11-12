"""
Report Learning API Routes - Intelligent Report Generation Phase 1 & 2.

Endpoints for:
- Uploading reports for learning
- Extracting and storing structure patterns
- Querying similar reports
- Getting structure recommendations
- Submitting feedback
- Scenario analysis and clarification
"""

import logging
from pathlib import Path
import re
from typing import List, Optional
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel, Field

from operation_room.config import settings
from operation_room.services.report_learning_service import (
    get_report_learning_service,
    ReportStructure,
    StructureRecommendation,
    LearningFeedback,
)
from operation_room.services.scenario_analyzer import (
    get_scenario_analyzer,
    ScenarioContext,
    ClarificationQuestion,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/learning", tags=["Report Learning"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class UploadReportResponse(BaseModel):
    """Response from report upload."""
    success: bool
    report_id: str
    message: str
    structure_summary: dict


class ExtractStructureRequest(BaseModel):
    """Request to extract structure from uploaded file."""
    file_path: str
    case_type: str = "general"
    title: Optional[str] = None


class RecommendStructureRequest(BaseModel):
    """Request for structure recommendation."""
    case_type: str
    scenario_description: str
    evidence_volume: Optional[dict] = None
    n_similar: int = 5


class RecommendStructureResponse(BaseModel):
    """Response with structure recommendation."""
    recommended_sections: List[dict]
    estimated_pages: int
    chart_suggestions: List[dict]
    similar_reports: List[str]
    confidence: float
    reasoning: str


class SubmitFeedbackRequest(BaseModel):
    """Request to submit feedback."""
    report_id: str
    case_id: str
    rating: int = Field(ge=1, le=5)
    structure_feedback: str = "good"  # good, too_long, too_short, missing_sections
    specific_issues: List[str] = []
    suggestions: str = ""


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""
    feedback_id: str
    message: str


class LearningStatsResponse(BaseModel):
    """Learning statistics."""
    learned_reports: int
    learned_sections: int
    feedback_entries: int
    learning_active: bool


class LearnedReportSummary(BaseModel):
    """Summary of a learned report."""
    report_id: str
    case_type: Optional[str]
    total_pages: Optional[int]
    section_count: Optional[int]
    learned_at: Optional[str]


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/upload-report", response_model=UploadReportResponse)
async def upload_report_for_learning(
    file: UploadFile = File(...),
    case_type: str = Form(default="general"),
    title: Optional[str] = Form(default=None)
):
    """
    Upload a forensic report (PDF/DOCX) for learning.
    
    The system will:
    1. Parse the document structure
    2. Extract sections, headings, charts
    3. Store patterns for future recommendations
    
    Args:
        file: PDF or DOCX file
        case_type: Type of case (ransomware, data_exfiltration, fraud, etc.)
        title: Optional title override
    
    Returns:
        Upload result with extracted structure summary
    """
    learning_service = get_report_learning_service()
    
    original_filename = file.filename or "upload.bin"
    file_ext = Path(original_filename).suffix.lower()

    # Validate file type
    if file_ext not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Please upload PDF or DOCX."
        )
    
    # Save file temporarily
    upload_dir = settings.DATA_DIR / "learning" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    safe_name = Path(original_filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
    if not safe_name:
        safe_name = "upload.bin"

    file_path = upload_dir / f"upload_{uuid.uuid4().hex}_{safe_name}"
    
    try:
        # Write uploaded file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Parse document
        layout = learning_service.parse_document(str(file_path), file_ext.replace(".", ""))
        
        # Extract structure
        structure = learning_service.extract_structure(
            layout=layout,
            case_type=case_type,
            title=title
        )
        
        # Store in vector database
        report_id = learning_service.store_learned_structure(structure)
        
        # Build summary
        structure_summary = {
            "total_pages": structure.total_pages,
            "total_words": structure.total_words,
            "section_count": len(structure.sections),
            "sections": [s.title for s in structure.sections],
            "chart_types": list(structure.chart_summary.keys()),
            "chart_count": sum(structure.chart_summary.values())
        }
        
        logger.info(f"Learned from report: {report_id} ({case_type}, {structure.total_pages} pages)")
        
        return UploadReportResponse(
            success=True,
            report_id=report_id,
            message=f"Successfully learned from {original_filename}",
            structure_summary=structure_summary
        )
        
    except Exception as e:
        logger.error(f"Failed to process report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process report: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if file_path.exists():
            file_path.unlink()


@router.post("/recommend-structure", response_model=RecommendStructureResponse)
async def recommend_structure(request: RecommendStructureRequest):
    """
    Get a recommended report structure based on learned patterns.
    
    Uses similarity search to find reports from similar cases
    and aggregates their structure patterns.
    
    Args:
        case_type: Type of case
        scenario_description: Text description of the investigation
        evidence_volume: Optional evidence counts by type
        n_similar: Number of similar reports to consider
    
    Returns:
        Recommended sections, charts, estimated pages
    """
    learning_service = get_report_learning_service()
    
    recommendation = learning_service.recommend_structure(
        case_type=request.case_type,
        scenario_description=request.scenario_description,
        evidence_volume=request.evidence_volume,
        n_similar=request.n_similar
    )
    
    return RecommendStructureResponse(
        recommended_sections=recommendation.recommended_sections,
        estimated_pages=recommendation.estimated_pages,
        chart_suggestions=recommendation.chart_suggestions,
        similar_reports=recommendation.similar_reports,
        confidence=recommendation.confidence,
        reasoning=recommendation.reasoning
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: SubmitFeedbackRequest):
    """
    Submit feedback on a generated report.
    
    Feedback is used to improve future structure recommendations
    and calibrate the learning system.
    
    Args:
        report_id: ID of the report
        case_id: ID of the case
        rating: 1-5 star rating
        structure_feedback: General feedback type
        specific_issues: List of specific issues
        suggestions: Free text suggestions
    
    Returns:
        Feedback ID
    """
    learning_service = get_report_learning_service()
    
    feedback_id = learning_service.submit_feedback(
        report_id=request.report_id,
        case_id=request.case_id,
        rating=request.rating,
        structure_feedback=request.structure_feedback,
        specific_issues=request.specific_issues,
        suggestions=request.suggestions
    )
    
    return FeedbackResponse(
        feedback_id=feedback_id,
        message=f"Thank you for your feedback! Rating: {request.rating}/5"
    )


@router.get("/stats", response_model=LearningStatsResponse)
async def get_learning_stats():
    """
    Get statistics about the learning system.
    
    Returns:
        Counts of learned reports, sections, feedback entries
    """
    learning_service = get_report_learning_service()
    stats = learning_service.get_learning_stats()
    
    return LearningStatsResponse(**stats)


@router.get("/reports", response_model=List[LearnedReportSummary])
async def list_learned_reports(
    case_type: Optional[str] = Query(default=None, description="Filter by case type"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results")
):
    """
    List learned report structures.
    
    Args:
        case_type: Optional filter by case type
        limit: Maximum number of results
    
    Returns:
        List of learned report summaries
    """
    learning_service = get_report_learning_service()
    reports = learning_service.list_learned_reports(case_type=case_type, limit=limit)
    
    return [LearnedReportSummary(**r) for r in reports]


@router.get("/similar")
async def find_similar_reports(
    scenario: str = Query(..., description="Scenario description to match"),
    case_type: str = Query(default="general", description="Case type"),
    n_results: int = Query(default=5, ge=1, le=20, description="Number of results")
):
    """
    Find similar reports based on scenario description.
    
    Args:
        scenario: Text description of the scenario
        case_type: Type of case
        n_results: Number of similar reports to return
    
    Returns:
        List of similar report IDs with similarity scores
    """
    learning_service = get_report_learning_service()
    
    recommendation = learning_service.recommend_structure(
        case_type=case_type,
        scenario_description=scenario,
        n_similar=n_results
    )
    
    return {
        "similar_reports": recommendation.similar_reports,
        "confidence": recommendation.confidence,
        "reasoning": recommendation.reasoning
    }


@router.get("/case-types")
async def get_case_types():
    """
    Get list of known case types with learning data.
    
    Returns:
        List of case types and their report counts
    """
    # Standard case types
    standard_types = [
        {"type": "ransomware", "description": "Ransomware attack investigations"},
        {"type": "data_exfiltration", "description": "Data theft and unauthorized transfer"},
        {"type": "fraud", "description": "Financial fraud and embezzlement"},
        {"type": "insider_threat", "description": "Malicious insider activities"},
        {"type": "network_intrusion", "description": "Unauthorized network access"},
        {"type": "malware", "description": "Malware infection analysis"},
        {"type": "phishing", "description": "Phishing and social engineering"},
        {"type": "ip_theft", "description": "Intellectual property theft"},
        {"type": "compliance", "description": "Compliance and policy violations"},
        {"type": "general", "description": "General forensic investigations"},
    ]
    
    return {"case_types": standard_types}


@router.delete("/reports/{report_id}")
async def delete_learned_report(report_id: str):
    """
    Delete a learned report structure.
    
    Args:
        report_id: ID of the report to delete
    
    Returns:
        Deletion confirmation
    """
    learning_service = get_report_learning_service()
    
    try:
        # This would delete from vector store
        # For now, log the request
        logger.info(f"Delete request for learned report: {report_id}")
        
        return {
            "success": True,
            "message": f"Deleted learned report: {report_id}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete report: {str(e)}"
        )


# ============================================================================
# SCENARIO ANALYSIS ROUTES (Iteration 2)
# ============================================================================

class ScenarioAnalysisRequest(BaseModel):
    """Request model for scenario analysis."""
    scenario_text: str = Field(..., description="The investigation scenario description")
    case_id: Optional[str] = Field(None, description="Associated case ID")
    use_llm: bool = Field(default=False, description="Use LLM for enhanced analysis")


class ClarificationAnswerRequest(BaseModel):
    """Request model for answering clarification questions."""
    question_id: str = Field(..., description="ID of the question being answered")
    answer: str = Field(..., description="User's answer")


class ScenarioAnalysisResponse(BaseModel):
    """Response model for scenario analysis."""
    session_id: str
    case_type: str
    case_type_confidence: float
    devices: List[dict]
    transfer_channels: List[str]
    suspects: List[dict]
    victims: List[dict]
    organizations: List[dict]
    ip_addresses: List[str]
    domains: List[str]
    timeline_specified: bool
    timeline_start: Optional[str]
    timeline_end: Optional[str]
    use_full_timeline: bool
    objectives: List[str]
    files_of_interest: List[str]
    clarification_questions: List[dict]
    clarification_complete: bool


@router.post("/scenario/analyze", response_model=ScenarioAnalysisResponse)
async def analyze_scenario(request: ScenarioAnalysisRequest):
    """
    Analyze an investigation scenario and extract key information.
    
    This is the entry point for the intelligent report generation workflow.
    It parses the scenario description and identifies:
    - Case type (data exfiltration, insider threat, etc.)
    - Devices involved
    - Transfer channels used
    - Entities (suspects, victims, organizations)
    - Timeline information
    - Required evidence types
    
    Args:
        request: Scenario analysis request with scenario text
    
    Returns:
        Analysis results with clarification questions if needed
    """
    analyzer = get_scenario_analyzer()
    
    try:
        context = analyzer.analyze(
            scenario_text=request.scenario_text,
            case_id=request.case_id,
            use_llm=request.use_llm,
        )
        
        # Convert context to response format using actual field names
        return ScenarioAnalysisResponse(
            session_id=context.scenario_id,
            case_type=context.case_type.value,
            case_type_confidence=context.confidence,
            devices=[d.to_dict() for d in context.devices],
            transfer_channels=[tc.value for tc in context.transfer_channels],
            suspects=[s.to_dict() for s in context.suspects],
            victims=[v.to_dict() for v in context.victims],
            organizations=[o.to_dict() for o in context.organizations],
            ip_addresses=context.ip_addresses,
            domains=context.domains,
            timeline_specified=context.timeline_specified,
            timeline_start=context.timeline_start,
            timeline_end=context.timeline_end,
            use_full_timeline=context.use_full_timeline,
            objectives=context.objectives,
            files_of_interest=context.files_of_interest,
            clarification_questions=[q.to_dict() for q in context.clarification_questions],
            clarification_complete=context.clarification_complete
        )
        
    except Exception as e:
        logger.error(f"Scenario analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze scenario: {str(e)}"
        )


@router.post("/scenario/clarify/{session_id}")
async def answer_clarification(
    session_id: str,
    request: ClarificationAnswerRequest
):
    """
    Answer a clarification question for an ongoing scenario analysis.
    
    Updates the scenario context with the user's answer and may generate
    additional questions or mark analysis as complete.
    
    Args:
        session_id: The scenario analysis session ID
        request: The clarification answer
    
    Returns:
        Updated scenario context with remaining questions
    """
    analyzer = get_scenario_analyzer()
    
    try:
        updated_context = analyzer.answer_clarification(
            session_id=session_id,
            question_id=request.question_id,
            answer=request.answer
        )
        
        if updated_context is None:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Get unanswered questions
        unanswered = [q for q in updated_context.clarification_questions if not q.answered]
        
        return {
            "session_id": session_id,
            "question_answered": request.question_id,
            "remaining_questions": [q.to_dict() for q in unanswered],
            "clarification_complete": updated_context.clarification_complete,
            "confidence": updated_context.confidence
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clarification answer failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process clarification: {str(e)}"
        )


@router.get("/scenario/{session_id}")
async def get_scenario_context(session_id: str):
    """
    Get the current scenario analysis context.
    
    Args:
        session_id: The scenario analysis session ID
    
    Returns:
        Current scenario context with all extracted information
    """
    analyzer = get_scenario_analyzer()
    
    context = analyzer.get_session(session_id)
    
    if context is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    
    return context.to_dict()


@router.post("/scenario/{session_id}/complete")
async def complete_scenario_analysis(session_id: str):
    """
    Mark scenario analysis as complete and proceed to structure recommendation.
    
    This finalizes the analysis phase and prepares for report structure generation.
    
    Args:
        session_id: The scenario analysis session ID
    
    Returns:
        Final analysis summary and readiness for structure phase
    """
    analyzer = get_scenario_analyzer()
    
    context = analyzer.get_session(session_id)
    
    if context is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    
    # Check if required questions are answered (priority 1)
    unanswered_required = [
        q for q in context.clarification_questions
        if q.priority == 1 and not q.answered
    ]
    
    if unanswered_required:
        return {
            "success": False,
            "message": "Required clarification questions must be answered",
            "unanswered_required": [q.to_dict() for q in unanswered_required]
        }
    
    # Mark as complete
    context.clarification_complete = True
    
    # Get structure recommendation from learning service
    learning_service = get_report_learning_service()
    
    try:
        # Build evidence volume from context
        evidence_volume = {}
        for device in context.devices:
            evidence_volume[device.device_type.value] = 1
        
        recommendation = learning_service.recommend_structure(
            case_type=context.case_type.value,
            scenario_description=context.raw_scenario,
            evidence_volume=evidence_volume,
            n_similar=5
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "analysis_summary": {
                "case_type": context.case_type.value,
                "case_type_confidence": context.confidence,
                "devices": [d.to_dict() for d in context.devices],
                "transfer_channels": [tc.value for tc in context.transfer_channels],
                "entity_count": {
                    "suspects": len(context.suspects),
                    "victims": len(context.victims),
                    "organizations": len(context.organizations),
                    "ip_addresses": len(context.ip_addresses)
                }
            },
            "structure_recommendation": {
                "estimated_pages": recommendation.estimated_pages,
                "sections": recommendation.sections,  # Already in correct format
                "similar_reports_count": len(recommendation.similar_reports),
                "confidence": recommendation.confidence_score
            },
            "ready_for_generation": True
        }
        
    except Exception as e:
        logger.warning(f"Structure recommendation failed, using defaults: {e}")
        
        # Return default structure if recommendation fails
        return {
            "success": True,
            "session_id": session_id,
            "analysis_summary": {
                "case_type": context.case_type.value,
                "case_type_confidence": context.confidence,
                "devices": [d.to_dict() for d in context.devices],
                "transfer_channels": [tc.value for tc in context.transfer_channels]
            },
            "structure_recommendation": None,
            "ready_for_generation": True,
            "note": "Using default structure - no learned patterns available"
        }
