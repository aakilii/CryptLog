"""
Section Generation API Routes - Intelligent Report Generation Phase 5.

Endpoints for:
- Creating generation plans
- Generating sections
- Approving/rejecting sections
- Tracking progress
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from operation_room.services.section_generation_pipeline import (
    get_generation_pipeline,
    SectionStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generation", tags=["Report Generation"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class CreatePlanRequest(BaseModel):
    """Request to create a generation plan."""
    scenario_session_id: str = Field(..., description="ID from scenario analysis")
    sections: List[dict] = Field(..., description="Sections from structure recommendation")
    auto_pilot: bool = Field(default=False, description="Auto-approve sections")


class GenerateSectionRequest(BaseModel):
    """Request to generate a section."""
    section_idx: int = Field(..., ge=0, description="Section index")
    scenario_context: dict = Field(default_factory=dict, description="Scenario context")


class ApproveSectionRequest(BaseModel):
    """Request to approve/reject a section."""
    section_idx: int = Field(..., ge=0, description="Section index")
    approved: bool = Field(..., description="Whether to approve")
    notes: str = Field(default="", description="Verification notes")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{case_id}/plan")
async def create_plan(case_id: str, request: CreatePlanRequest):
    """
    Create a generation plan for a report.
    
    The plan defines all sections to be generated and tracks progress.
    """
    pipeline = get_generation_pipeline(case_id)
    
    try:
        plan = pipeline.create_plan(
            scenario_session_id=request.scenario_session_id,
            structure_sections=request.sections,
            auto_pilot=request.auto_pilot
        )
        
        return {
            "success": True,
            "plan_id": plan.plan_id,
            "total_sections": plan.total_sections,
            "auto_pilot": plan.auto_pilot,
            "sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "level": s.level,
                    "status": s.status.value
                }
                for s in plan.sections
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to create plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/plan/{plan_id}")
async def get_plan(case_id: str, plan_id: str):
    """Get a generation plan by ID."""
    pipeline = get_generation_pipeline(case_id)
    
    plan = pipeline.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return plan.to_dict()


@router.post("/{case_id}/plan/{plan_id}/generate")
async def generate_section(
    case_id: str,
    plan_id: str,
    request: GenerateSectionRequest
):
    """
    Generate content for a single section.
    
    Includes:
    - Evidence gathering
    - Hypothesis generation
    - Chart decisions
    - Text generation
    """
    pipeline = get_generation_pipeline(case_id)
    
    try:
        section = pipeline.generate_section(
            plan_id=plan_id,
            section_idx=request.section_idx,
            scenario_context=request.scenario_context
        )
        
        return {
            "success": True,
            "section": section.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/plan/{plan_id}/approve")
async def approve_section(
    case_id: str,
    plan_id: str,
    request: ApproveSectionRequest
):
    """
    Approve or reject a generated section.
    
    Approved sections are marked as verified.
    Rejected sections need regeneration.
    """
    pipeline = get_generation_pipeline(case_id)
    
    try:
        section = pipeline.approve_section(
            plan_id=plan_id,
            section_idx=request.section_idx,
            approved=request.approved,
            notes=request.notes
        )
        
        return {
            "success": True,
            "section_id": section.section_id,
            "status": section.status.value,
            "verified": section.verified,
            "notes": section.verification_notes
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to approve section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/plan/{plan_id}/progress")
async def get_progress(case_id: str, plan_id: str):
    """Get generation progress for a plan."""
    pipeline = get_generation_pipeline(case_id)
    
    progress = pipeline.get_progress(plan_id)
    
    if "error" in progress:
        raise HTTPException(status_code=404, detail=progress["error"])
    
    return progress


@router.post("/{case_id}/plan/{plan_id}/generate-next")
async def generate_next_section(
    case_id: str,
    plan_id: str,
    scenario_context: Optional[dict] = None
):
    """
    Generate the next pending section in the plan.
    
    Automatically finds the next section that needs generation.
    """
    pipeline = get_generation_pipeline(case_id)
    
    plan = pipeline.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Find next pending section
    next_idx = None
    for idx, section in enumerate(plan.sections):
        if section.status == SectionStatus.PENDING:
            next_idx = idx
            break
    
    if next_idx is None:
        return {
            "success": True,
            "message": "All sections generated",
            "complete": True
        }
    
    try:
        section = pipeline.generate_section(
            plan_id=plan_id,
            section_idx=next_idx,
            scenario_context=scenario_context or {}
        )
        
        return {
            "success": True,
            "section": section.to_dict(),
            "complete": False,
            "remaining": sum(1 for s in plan.sections if s.status == SectionStatus.PENDING) - 1
        }
        
    except Exception as e:
        logger.error(f"Failed to generate next section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/plan/{plan_id}/auto-generate")
async def auto_generate_all(
    case_id: str,
    plan_id: str,
    scenario_context: Optional[dict] = None
):
    """
    Generate all pending sections in auto-pilot mode.
    
    Will auto-approve if plan has auto_pilot=True.
    """
    pipeline = get_generation_pipeline(case_id)
    
    plan = pipeline.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    results = []
    
    for idx, section in enumerate(plan.sections):
        if section.status != SectionStatus.PENDING:
            continue
        
        try:
            generated = pipeline.generate_section(
                plan_id=plan_id,
                section_idx=idx,
                scenario_context=scenario_context or {}
            )
            
            # Auto-approve if in auto-pilot mode
            if plan.auto_pilot:
                pipeline.approve_section(
                    plan_id=plan_id,
                    section_idx=idx,
                    approved=True,
                    notes="Auto-approved in auto-pilot mode"
                )
            
            results.append({
                "section_id": generated.section_id,
                "title": generated.title,
                "status": generated.status.value
            })
            
        except Exception as e:
            results.append({
                "section_idx": idx,
                "error": str(e)
            })
    
    return {
        "success": True,
        "generated_count": len([r for r in results if "section_id" in r]),
        "results": results,
        "progress": pipeline.get_progress(plan_id)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ALIGNMENT VERIFICATION ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

from operation_room.services.alignment_verifier import get_alignment_verifier


class VerifyAlignmentRequest(BaseModel):
    """Request to verify section alignment."""
    section_id: str
    elements: List[dict] = Field(..., description="Elements with position info")


class AutoFixRequest(BaseModel):
    """Request to auto-fix alignment issues."""
    verification_id: str


@router.post("/{case_id}/verify-alignment")
async def verify_alignment(case_id: str, request: VerifyAlignmentRequest):
    """
    Verify alignment of section elements.
    
    Checks for:
    - Overlapping elements
    - Insufficient/excessive spacing
    - Elements outside margins
    - Orphan/widow text issues
    """
    verifier = get_alignment_verifier()
    
    try:
        result = verifier.verify_section(
            section_id=request.section_id,
            elements=request.elements
        )
        
        return {
            "success": True,
            "verification_id": result.verification_id,
            "status": result.status.value,
            "element_count": result.element_count,
            "issue_count": len(result.issues),
            "issues": [i.to_dict() for i in result.issues],
            "auto_fixable_count": sum(1 for i in result.issues if i.auto_fixable)
        }
        
    except Exception as e:
        logger.error(f"Alignment verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/verification/{verification_id}")
async def get_verification(case_id: str, verification_id: str):
    """Get alignment verification result."""
    verifier = get_alignment_verifier()
    
    result = verifier.get_verification(verification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    return result.to_dict()


@router.post("/{case_id}/auto-fix")
async def auto_fix_alignment(case_id: str, request: AutoFixRequest):
    """
    Attempt to auto-fix alignment issues.
    
    Returns position adjustments for elements.
    """
    verifier = get_alignment_verifier()
    
    try:
        adjustments, remaining = verifier.auto_fix_issues(request.verification_id)
        
        return {
            "success": True,
            "adjustments": adjustments,
            "fixed_count": len(adjustments),
            "remaining_issues": [i.to_dict() for i in remaining],
            "remaining_count": len(remaining)
        }
        
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
