"""
Depth & Impact Assessment API routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/cases/{case_id}/depth", tags=["depth"])


class RunDepthRequest(BaseModel):
    weights: dict = {"account": 0.25, "system": 0.25, "data": 0.30, "control": 0.20}
    llm_provider: str = "ollama"


class NarrativeRequest(BaseModel):
    llm_provider: str = "ollama"
    run_id: Optional[str] = None


@router.get("")
async def get_depth_overview(case_id: str):
    """Get depth analysis overview with scores in frontend-expected format."""
    from operation_room.services.depth_agent import run_depth_analysis
    try:
        result = run_depth_analysis(case_id)
        
        # Transform to frontend-expected format (scores in 0-10 scale)
        dimensions = result.get("dimensions", {})
        impact = result.get("impact_score", {})
        
        return {
            # Frontend uses these field names (0-10 scale)
            "account_depth": dimensions.get("account", 0),
            "system_depth": dimensions.get("system", 0),
            "data_depth": dimensions.get("data", 0),
            "control_depth": dimensions.get("control", 0),
            "overall_severity": impact.get("overall", 0),
            "severity_label": impact.get("level", "MINIMAL"),
            "level": impact.get("level", "MINIMAL"),
            "metrics": result.get("metrics", {}),
            "run_id": result.get("run_id"),
            "status": result.get("status", "completed")
        }
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/findings")
async def get_depth_findings(case_id: str):
    """Get depth analysis findings."""
    from operation_room.services.depth_agent import run_depth_analysis
    try:
        result = run_depth_analysis(case_id)
        metrics = result.get("metrics", {})
        impact = result.get("impact_score", {})
        dimensions = result.get("dimensions", {})
        
        # Generate findings based on metrics
        findings = []
        
        if metrics.get("affected_users", 0) > 0:
            findings.append({
                "id": "users-affected",
                "title": f"{metrics['affected_users']} Users Affected",
                "description": f"Analysis detected activity from {metrics['affected_users']} unique users",
                "severity": "high" if metrics['affected_users'] > 10 else "medium",
                "dimension": "account"
            })
        
        if metrics.get("affected_systems", 0) > 0:
            findings.append({
                "id": "systems-touched",
                "title": f"{metrics['affected_systems']} Systems Accessed",
                "description": f"Activity detected across {metrics['affected_systems']} different systems",
                "severity": "high" if metrics['affected_systems'] > 5 else "medium",
                "dimension": "system"
            })
        
        if metrics.get("total_events", 0) > 0:
            findings.append({
                "id": "event-volume",
                "title": f"{metrics['total_events']} Total Events",
                "description": f"High volume of activity with {metrics['total_events']} recorded events",
                "severity": "critical" if metrics['total_events'] > 1000 else "high" if metrics['total_events'] > 100 else "medium",
                "dimension": "data"
            })
        
        if impact.get("level") in ["HIGH", "CRITICAL"]:
            findings.append({
                "id": "overall-impact",
                "title": f"Overall Impact: {impact.get('level')}",
                "description": f"Combined impact score of {impact.get('overall', 0):.1f}/10 indicates significant breach depth",
                "severity": "critical" if impact.get("level") == "CRITICAL" else "high",
                "dimension": "control"
            })
        
        return {"findings": findings, "count": len(findings)}
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        return {"findings": [], "count": 0}


@router.post("/run")
async def run_depth(case_id: str, body: RunDepthRequest):
    from operation_room.services.depth_agent import run_depth_analysis
    try:
        return run_depth_analysis(case_id, weights=body.weights, llm_provider=body.llm_provider)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/results")
async def get_results(case_id: str, run_id: Optional[str] = None):
    """Get depth results in frontend-expected format."""
    from operation_room.services.depth_agent import run_depth_analysis
    try:
        result = run_depth_analysis(case_id)
        
        # Transform to frontend-expected format (scores in 0-10 scale)
        dimensions = result.get("dimensions", {})
        impact = result.get("impact_score", {})
        
        return {
            # Frontend uses these field names (0-10 scale)
            "account_depth": dimensions.get("account", 0),
            "system_depth": dimensions.get("system", 0),
            "data_depth": dimensions.get("data", 0),
            "control_depth": dimensions.get("control", 0),
            "overall_severity": impact.get("overall", 0),
            "severity_label": impact.get("level", "MINIMAL"),
            "level": impact.get("level", "MINIMAL"),
            "metrics": result.get("metrics", {}),
            "run_id": result.get("run_id"),
            "status": result.get("status", "completed")
        }
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/details")
async def get_details(case_id: str, run_id: Optional[str] = None, dimension: Optional[str] = None):
    from operation_room.services.depth_agent import get_depth_details
    try:
        return get_depth_details(case_id, run_id, dimension)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.post("/narrative")
async def gen_narrative(case_id: str, body: NarrativeRequest):
    from operation_room.services.depth_agent import generate_impact_narrative
    try:
        return generate_impact_narrative(case_id, run_id=body.run_id, llm_provider=body.llm_provider)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/narrative")
async def get_narrative(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.depth_agent import get_impact_narrative
    try:
        return get_impact_narrative(case_id, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/runs")
async def list_runs(case_id: str):
    from operation_room.services.depth_agent import get_depth_runs
    try:
        return get_depth_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
