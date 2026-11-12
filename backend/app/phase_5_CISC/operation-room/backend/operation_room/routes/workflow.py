"""
Workflow API Routes

API endpoints for running the complete investigation workflow.
Supports 3 execution modes:
- autopilot: AI runs all relevant modules automatically
- smart_recommendation: AI recommends modules, user approves
- run_all: Run all modules regardless of hypothesis
"""

import logging
from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from operation_room.services.investigation_workflow import (
    get_workflow_orchestrator,
    ExecutionMode
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cases/{case_id}/workflow", tags=["workflow"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class StartWorkflowRequest(BaseModel):
    """Request to start complete investigation workflow."""
    scenario: str = Field(..., description="Investigation scenario description")
    timeline_range: Optional[Dict] = Field(None, description="Timeline range constraints")
    scope: Optional[Dict] = Field(None, description="Scope constraints")
    llm_provider: str = Field("gemini", description="LLM provider to use")
    execution_mode: str = Field("autopilot", description="autopilot | smart_recommendation | run_all")
    approved_modules: Optional[List[str]] = Field(None, description="Modules to run (for smart_recommendation)")
    hypotheses: Optional[List[Dict]] = Field(None, description="Pre-generated hypotheses")
    
    class Config:
        json_schema_extra = {
            "example": {
                "scenario": "Suspected data exfiltration by insider threat. Employee accessed sensitive files after hours and large outbound transfers detected.",
                "timeline_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-01-31T23:59:59Z"
                },
                "scope": {
                    "focus_areas": ["data_access", "network_traffic", "anomalies"],
                    "actors_of_interest": ["john.doe@company.com"]
                },
                "llm_provider": "gemini",
                "execution_mode": "autopilot"
            }
        }


class ModuleRecommendationResponse(BaseModel):
    """Response with module recommendations."""
    module_name: str
    description: str
    reason: str
    relevance_score: float
    recommended: bool
    estimated_duration: str


class GetRecommendationsRequest(BaseModel):
    """Request to get module recommendations."""
    hypotheses: List[Dict] = Field(..., description="List of hypotheses to analyze")


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status."""
    investigation_id: str
    case_id: str
    scenario: str
    status: str
    current_phase: str
    findings_count: int
    report_doc_id: Optional[str]


class TargetedModuleRequest(BaseModel):
    """Request to run a targeted module with specific parameters."""
    module_name: str
    parameters: Dict = Field(default_factory=dict)
    hypotheses: List[Dict] = Field(default_factory=list)
    investigation_id: Optional[str] = None


# ─── API Routes ──────────────────────────────────────────────────────────────

@router.post("/start")
async def start_investigation_workflow(case_id: str, req: StartWorkflowRequest):
    """
    Start the complete investigation workflow.
    
    Execution Modes:
    - autopilot: AI automatically runs relevant modules based on hypotheses
    - smart_recommendation: Get recommendations first, then approve modules
    - run_all: Run all modules regardless of relevance
    
    Workflow Phases:
    1. Scenario Gathering
    2. Data Validation
    3. Hypothesis Generation
    4. Evidence Collection (uses execution mode)
    5. Finding Analysis
    6. Confidence Scoring
    7. Report Building
    """
    try:
        orchestrator = get_workflow_orchestrator(case_id)
        
        logger.info(f"Starting workflow for case {case_id} (mode: {req.execution_mode}): {req.scenario[:100]}")
        
        results = await orchestrator.run_complete_workflow(
            scenario=req.scenario,
            timeline_range=req.timeline_range,
            scope=req.scope,
            llm_provider=req.llm_provider,
            execution_mode=req.execution_mode,
            approved_modules=req.approved_modules
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations")
async def get_module_recommendations(case_id: str, req: GetRecommendationsRequest):
    """
    Get module recommendations based on hypotheses.
    
    Use this in smart_recommendation mode before starting the workflow.
    Returns a list of modules with relevance scores and reasons.
    """
    try:
        orchestrator = get_workflow_orchestrator(case_id)
        recommendations = orchestrator.get_module_recommendations(req.hypotheses)
        
        return {
            "case_id": case_id,
            "hypothesis_count": len(req.hypotheses),
            "recommendations": recommendations,
            "usage": "Approve modules by calling POST /workflow/start with approved_modules list"
        }
        
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution-modes")
async def list_execution_modes():
    """List available execution modes and their descriptions."""
    return {
        "modes": [
            {
                "id": "autopilot",
                "name": "Autopilot",
                "description": "AI automatically runs all relevant modules based on hypothesis analysis. Best for quick investigations."
            },
            {
                "id": "smart_recommendation",
                "name": "Smart Recommendation",
                "description": "AI analyzes hypotheses and recommends modules. You approve which modules to run. Best for controlled investigations."
            },
            {
                "id": "run_all",
                "name": "Run All",
                "description": "Runs all available modules regardless of hypothesis relevance. Best for comprehensive investigations."
            }
        ],
        "default": "autopilot"
    }


@router.post("/run-targeted")
async def run_targeted_module(case_id: str, req: TargetedModuleRequest):
    """
    Run a specific module with targeted parameters.
    
    Use this to re-run modules with different parameters or
    to investigate specific findings in more depth.
    """
    try:
        from operation_room.services.findings_vault import get_findings_vault
        
        orchestrator = get_workflow_orchestrator(case_id)
        vault = get_findings_vault(case_id)
        orchestrator.execution_controller.vault = vault
        
        result = await orchestrator.execution_controller.run_targeted_module(
            module_name=req.module_name,
            parameters=req.parameters,
            hypotheses=req.hypotheses
        )
        
        return {
            "module": result.module_name,
            "status": result.status,
            "findings_count": result.findings_count,
            "duration_ms": result.duration_ms,
            "findings_keys": result.findings_keys,
            "error": result.error
        }
        
    except Exception as e:
        logger.error(f"Targeted module run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{investigation_id}")
async def get_workflow_status(case_id: str, investigation_id: str):
    """Get status of a running workflow (placeholder for future async implementation)."""
    # In future: implement async workflow tracking
    return {
        "investigation_id": investigation_id,
        "case_id": case_id,
        "status": "For async tracking, check findings vault",
        "note": "Current implementation is synchronous"
    }


@router.post("/run-module/{module_name}")
async def run_single_module(
    case_id: str,
    module_name: str,
    investigation_id: Optional[str] = None,
    save_findings: bool = True
):
    """
    Run a single analysis module and optionally save findings.
    
    Available modules:
    - anomaly
    - crud
    - network
    - depth
    - timeline
    
    If save_findings=True, results are saved to findings vault with keys.
    """
    try:
        from operation_room.services.findings_vault import get_findings_vault, FindingType
        from operation_room.services.confidence_scoring import get_confidence_engine
        
        vault = get_findings_vault(case_id) if save_findings else None
        engine = get_confidence_engine(case_id) if save_findings else None
        
        result = {}
        
        if module_name == "anomaly":
            from operation_room.services.anomaly_agent import get_anomaly_summary
            result = get_anomaly_summary(case_id)
            
            if save_findings and result.get("anomalies_found", 0) > 0:
                vault.save_finding(
                    finding_key=f"ANOMALY_RUN_{investigation_id or 'manual'}",
                    finding_value={
                        "total_anomalies": result["anomalies_found"],
                        "anomaly_rate": result["anomaly_rate"],
                        "charts": result.get("charts", {})
                    },
                    finding_type=FindingType.EVIDENCE,
                    investigation_id=investigation_id,
                    source_module="anomaly"
                )
        
        elif module_name == "crud":
            from operation_room.services.crud_agent import get_crud_summary
            result = get_crud_summary(case_id)
            
            if save_findings and result.get("total_events", 0) > 0:
                vault.save_finding(
                    finding_key=f"CRUD_RUN_{investigation_id or 'manual'}",
                    finding_value=result,
                    finding_type=FindingType.METRIC,
                    investigation_id=investigation_id,
                    source_module="crud"
                )
        
        elif module_name == "network":
            from operation_room.services.network_agent import get_exfil_candidates
            result = {"exfiltration_candidates": get_exfil_candidates(case_id)}
            
            if save_findings and len(result["exfiltration_candidates"]) > 0:
                vault.save_finding(
                    finding_key=f"NETWORK_EXFIL_{investigation_id or 'manual'}",
                    finding_value=result,
                    finding_type=FindingType.EVIDENCE,
                    investigation_id=investigation_id,
                    source_module="network"
                )
        
        elif module_name == "depth":
            from operation_room.services.depth_agent import run_depth_analysis
            result = run_depth_analysis(case_id)
            
            if save_findings and result.get("impact_score"):
                vault.save_finding(
                    finding_key=f"DEPTH_RUN_{investigation_id or 'manual'}",
                    finding_value=result,
                    finding_type=FindingType.METRIC,
                    investigation_id=investigation_id,
                    source_module="depth"
                )
        
        elif module_name == "timeline":
            from operation_room.services.timeline_service import get_timeline_stats_search
            result = get_timeline_stats_search(case_id, {})
            
            if save_findings:
                vault.save_finding(
                    finding_key=f"TIMELINE_STATS_{investigation_id or 'manual'}",
                    finding_value=result,
                    finding_type=FindingType.METRIC,
                    investigation_id=investigation_id,
                    source_module="timeline"
                )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown module: {module_name}")
        
        return {
            "module": module_name,
            "result": result,
            "findings_saved": save_findings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Module execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
