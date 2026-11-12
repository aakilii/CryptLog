"""
Multi-Agent API Routes — FastAPI endpoints for the automated report generation system.

This module provides REST API endpoints for:
- Triggering automated report generation
- Managing agent execution
- Monitoring pipeline progress
- Retrieving generated reports

Author: NFLIP Development Team
Version: 1.0.0
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# Note: MasterOrchestrator removed - using PipelineExecutor instead
from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
from operation_room.agents.evidence.evidence_collector import EvidenceCollectionAgent
from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent
from operation_room.agents.synthesis.synthesis_agent import SummarySynthesisAgent
from operation_room.agents.research.knowledge_base import knowledge_base, ResearchCategory
from operation_room.agents.base import registry, BaseAgentState
from operation_room.services.agent_runner import get_runner_service, RunStatus
from operation_room.services.llm_service import get_llm_service
from operation_room.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["Multi-Agent System"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AutoReportRequest(BaseModel):
    """Request to generate an automated report."""
    case_id: str = Field(..., description="Target case identifier")
    scenario: str = Field("", description="Investigation scenario or hypothesis text")
    report_type: str = Field("technical", description="Type of report: technical, executive, regulatory")
    llm_provider: str = Field("ollama", description="LLM provider: ollama or gemini")


class AutoReportResponse(BaseModel):
    """Response from automated report generation."""
    run_id: str
    case_id: str
    status: str
    report: Optional[dict] = None
    markdown: Optional[str] = None
    confidence: Optional[dict] = None
    error: Optional[str] = None


class HypothesisRequest(BaseModel):
    """Request for hypothesis analysis."""
    scenario: str = Field(..., description="Investigation scenario text")
    case_id: str = Field("", description="Optional case identifier")
    llm_provider: str = Field("ollama", description="LLM provider")


class HypothesisResponse(BaseModel):
    """Response from hypothesis analysis."""
    run_id: str
    hypotheses: List[dict]
    entities: List[dict]
    attack_vectors: List[dict]
    evidence_requirements: List[dict]


class ConfidenceRequest(BaseModel):
    """Request for confidence scoring."""
    case_id: str
    hypotheses: List[dict]
    evidence_inventory: Optional[dict] = None
    module_results: Optional[dict] = None


class ConfidenceResponse(BaseModel):
    """Response from confidence scoring."""
    run_id: str
    overall_confidence: float
    confidence_level: str
    hypothesis_confidences: List[dict]


class ResearchSearchRequest(BaseModel):
    """Request to search research methodologies."""
    query: str = Field("", description="Search query")
    category: Optional[str] = Field(None, description="Filter by category")
    module: Optional[str] = Field(None, description="Filter by module")
    hypothesis_type: Optional[str] = Field(None, description="Filter by hypothesis type")
    limit: int = Field(20, description="Maximum results")


class AgentStatusResponse(BaseModel):
    """Agent status information."""
    agent_id: str
    agent_name: str
    status: str
    metrics: dict


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/generate-report", response_model=AutoReportResponse)
async def generate_automated_report(
    request: AutoReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate an automated forensic report.
    
    This endpoint triggers the full multi-agent pipeline:
    1. Hypothesis Analysis
    2. Evidence Collection
    3. Module Evaluation
    4. Confidence Scoring
    5. Summary Synthesis
    
    The report is generated asynchronously. Use the run_id to check status.
    """
    runner = get_runner_service()
    
    # Create and start run
    run = runner.create_run(
        case_id=request.case_id,
        scenario=request.scenario,
        report_type=request.report_type,
        llm_provider=request.llm_provider or settings.LLM_PROVIDER
    )
    
    # Start async execution
    runner.start_run_async(run)
    
    return AutoReportResponse(
        run_id=run.run_id,
        case_id=request.case_id,
        status=run.status.value
    )


@router.get("/report-status/{run_id}", response_model=AutoReportResponse)
async def get_report_status(run_id: str):
    """
    Get the status of an automated report generation task.
    """
    runner = get_runner_service()
    run = runner.get_run(run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    response = AutoReportResponse(
        run_id=run_id,
        case_id=run.case_id,
        status=run.status.value
    )
    
    if run.status == RunStatus.COMPLETED and run.result:
        response.report = run.result.get("report")
        response.confidence = run.result.get("confidence")
    elif run.status == RunStatus.FAILED:
        response.error = run.error
    
    return response


@router.get("/runs")
async def list_runs(
    status: Optional[str] = None,
    case_id: Optional[str] = None,
    limit: int = 50
):
    """List all agent runs."""
    runner = get_runner_service()
    status_enum = RunStatus(status) if status else None
    runs = runner.list_runs(status=status_enum, case_id=case_id, limit=limit)
    return {"runs": [r.to_dict() for r in runs]}


@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str):
    """Cancel a running agent execution."""
    runner = get_runner_service()
    success = await runner.cancel_run(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Run not found or not running")
    return {"status": "cancelled", "run_id": run_id}


@router.get("/health")
async def agent_health():
    """Get agent system health status."""
    runner = get_runner_service()
    return runner.get_health()


@router.get("/statistics")
async def agent_statistics():
    """Get agent system statistics."""
    runner = get_runner_service()
    return runner.get_statistics()


@router.post("/analyze-hypothesis", response_model=HypothesisResponse)
async def analyze_hypothesis(request: HypothesisRequest):
    """
    Analyze a scenario and generate testable hypotheses.
    
    This endpoint runs just the Hypothesis Analysis Agent to:
    - Extract entities and relationships
    - Generate competing hypotheses
    - Identify attack vectors
    - Map evidence requirements
    """
    agent = HypothesisAnalysisAgent(llm_provider=request.llm_provider)
    result = await agent.analyze(
        scenario=request.scenario,
        case_id=request.case_id,
        llm_provider=request.llm_provider
    )
    
    return HypothesisResponse(
        run_id=result.get("run_id", ""),
        hypotheses=result.get("hypotheses", []),
        entities=result.get("entities", []),
        attack_vectors=result.get("attack_vectors", []),
        evidence_requirements=result.get("evidence_requirements", [])
    )


@router.post("/score-confidence", response_model=ConfidenceResponse)
async def score_confidence(request: ConfidenceRequest):
    """
    Compute confidence scores for hypotheses.
    
    This endpoint runs the Confidence Scoring Agent to:
    - Evaluate evidence coverage
    - Assess module agreement
    - Check temporal consistency
    - Cross-validate findings
    - Generate overall confidence
    """
    agent = ConfidenceScoringAgent()
    result = await agent.score(
        case_id=request.case_id,
        hypotheses=request.hypotheses,
        evidence_inventory=request.evidence_inventory,
        module_results=request.module_results
    )
    
    return ConfidenceResponse(
        run_id=result.get("run_id", ""),
        overall_confidence=result.get("overall_case_confidence", 0.0),
        confidence_level=result.get("overall_confidence_level", "moderate"),
        hypothesis_confidences=result.get("hypothesis_confidences", [])
    )


@router.get("/agents")
async def list_agents():
    """
    List all registered agents and their status.
    """
    return {
        "agents": registry.list_agents(),
        "metrics": registry.get_all_metrics()
    }


@router.get("/agents/{agent_id}", response_model=AgentStatusResponse)
async def get_agent_status(agent_id: str):
    """
    Get detailed status of a specific agent.
    """
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    info = agent.get_info()
    metrics = agent.get_metrics()
    
    return AgentStatusResponse(
        agent_id=info["agent_id"],
        agent_name=info["agent_name"],
        status="available",
        metrics=metrics
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH KNOWLEDGE BASE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/research/statistics")
async def get_research_statistics():
    """
    Get statistics about the research knowledge base.
    """
    return knowledge_base.get_statistics()


@router.post("/research/search")
async def search_research(request: ResearchSearchRequest):
    """
    Search the research knowledge base.
    """
    results = []
    
    if request.query:
        results = knowledge_base.search(request.query)
    elif request.category:
        try:
            cat = ResearchCategory(request.category)
            results = knowledge_base.get_by_category(cat)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category")
    elif request.module:
        results = knowledge_base.get_by_module(request.module)
    elif request.hypothesis_type:
        results = knowledge_base.get_by_hypothesis_type(request.hypothesis_type)
    else:
        # Return all if no filter
        return {"methodologies": knowledge_base.list_all()[:request.limit]}
    
    return {
        "count": len(results),
        "methodologies": [m.to_dict() for m in results[:request.limit]]
    }


@router.get("/research/methodology/{methodology_id}")
async def get_methodology(methodology_id: str):
    """
    Get details of a specific research methodology.
    """
    methodology = knowledge_base.get(methodology_id)
    if not methodology:
        raise HTTPException(status_code=404, detail="Methodology not found")
    
    return methodology.to_dict()


@router.get("/research/categories")
async def list_categories():
    """
    List all research categories with counts.
    """
    stats = knowledge_base.get_statistics()
    return {
        "categories": stats["categories"]
    }


@router.get("/research/by-category")
async def list_by_category():
    """
    List all methodologies grouped by category.
    """
    return knowledge_base.list_by_category()


@router.post("/research/recommendations")
async def get_recommendations(
    hypothesis_types: List[str] = None,
    modules: List[str] = None,
    limit: int = 10
):
    """
    Get recommended methodologies based on investigation context.
    """
    recommendations = knowledge_base.get_recommendations(
        hypothesis_types=hypothesis_types,
        modules=modules,
        limit=limit
    )
    
    return {
        "recommendations": [m.to_dict() for m in recommendations]
    }
