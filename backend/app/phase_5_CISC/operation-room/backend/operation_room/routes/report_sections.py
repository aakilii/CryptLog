"""
Report Section API Routes

API endpoints for section-by-section report generation and approval.
"""

import logging
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from operation_room.services.section_report_service import (
    get_section_report_service,
    SectionType,
    SectionStatus
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cases/{case_id}/report-sections", tags=["report-sections"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class InitDraftRequest(BaseModel):
    """Request to initialize a new report draft."""
    title: str = Field(..., description="Report title")
    investigation_id: str = Field(..., description="Investigation ID")
    section_types: Optional[List[str]] = Field(None, description="Specific section types to include")
    metadata: Optional[Dict] = Field(None, description="Additional metadata (scenario, timeline, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Forensic Investigation Report - Data Exfiltration",
                "investigation_id": "inv_abc123",
                "section_types": ["executive_summary", "findings", "recommendations"],
                "metadata": {
                    "scenario": "Suspected insider data theft",
                    "severity": "high"
                }
            }
        }


class GenerateSectionRequest(BaseModel):
    """Request to generate a section."""
    section_id: str = Field(..., description="Section ID to generate")
    context: Optional[Dict] = Field(None, description="Additional context for generation")
    regenerate: bool = Field(False, description="Whether to regenerate (uses revision notes)")


class ApproveSectionRequest(BaseModel):
    """Request to approve a section."""
    section_id: str = Field(..., description="Section ID to approve")
    approved_by: str = Field(..., description="Who is approving")
    edits: Optional[str] = Field(None, description="Manual edits to content (optional)")


class RequestRevisionRequest(BaseModel):
    """Request to request revision of a section."""
    section_id: str = Field(..., description="Section ID to revise")
    revision_notes: str = Field(..., description="Feedback for revision")


class SectionResponse(BaseModel):
    """Response with section details."""
    section_id: str
    section_type: str
    title: str
    order: int
    status: str
    content: str
    key_references: Dict[str, str]
    revision_count: int
    generated_at: Optional[str]
    approved_at: Optional[str]
    approved_by: Optional[str]


# ─── API Routes ──────────────────────────────────────────────────────────────

@router.post("/drafts/init")
async def initialize_draft(case_id: str, req: InitDraftRequest):
    """
    Initialize a new report draft with sections.
    
    By default includes all section types, but you can specify which ones to include.
    """
    try:
        service = get_section_report_service(case_id, req.investigation_id)
        
        # Convert string section types to enum
        section_types = None
        if req.section_types:
            section_types = [SectionType(st) for st in req.section_types]
        
        draft = service.initialize_draft(
            title=req.title,
            section_types=section_types,
            metadata=req.metadata
        )
        
        return {
            "draft_id": draft.draft_id,
            "title": draft.title,
            "case_id": draft.case_id,
            "investigation_id": draft.investigation_id,
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_type": s.section_type.value,
                    "title": s.title,
                    "order": s.order,
                    "status": s.status.value
                }
                for s in draft.sections
            ],
            "created_at": draft.created_at
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}")
async def get_draft(case_id: str, draft_id: str, investigation_id: str):
    """Get a report draft by ID."""
    try:
        service = get_section_report_service(case_id, investigation_id)
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        return {
            "draft_id": draft.draft_id,
            "title": draft.title,
            "case_id": draft.case_id,
            "investigation_id": draft.investigation_id,
            "status": draft.status,
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_type": s.section_type.value,
                    "title": s.title,
                    "order": s.order,
                    "status": s.status.value,
                    "content": s.content,
                    "key_references": s.key_references,
                    "revision_count": s.revision_count,
                    "generated_at": s.generated_at,
                    "approved_at": s.approved_at
                }
                for s in draft.sections
            ],
            "created_at": draft.created_at,
            "updated_at": draft.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}/progress")
async def get_draft_progress(case_id: str, draft_id: str, investigation_id: str):
    """Get progress summary for a draft."""
    try:
        service = get_section_report_service(case_id, investigation_id)
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        progress = service.get_draft_progress()
        
        # Format next section for response
        next_section = progress.get("next_section")
        if next_section:
            progress["next_section"] = {
                "section_id": next_section.section_id,
                "section_type": next_section.section_type.value,
                "title": next_section.title,
                "status": next_section.status.value
            }
        
        return progress
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/sections/generate")
async def generate_section(case_id: str, draft_id: str, req: GenerateSectionRequest):
    """
    Generate content for a specific section using LLM.
    
    The generated content will reference findings using keys.
    """
    try:
        service = get_section_report_service(case_id, req.context.get("investigation_id", "") if req.context else "")
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        if draft.investigation_id:
            service = get_section_report_service(case_id, draft.investigation_id)
            service.current_draft = draft
        
        section = await service.generate_section(
            section_id=req.section_id,
            context=req.context,
            regenerate=req.regenerate
        )
        
        return {
            "section_id": section.section_id,
            "section_type": section.section_type.value,
            "title": section.title,
            "status": section.status.value,
            "content": section.content,
            "content_with_keys": section.content_with_keys,
            "key_references": section.key_references,
            "revision_count": section.revision_count,
            "generated_at": section.generated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/sections/approve")
async def approve_section(case_id: str, draft_id: str, req: ApproveSectionRequest):
    """
    Approve a section (optionally with manual edits).
    
    Once approved, the section will be included in the final report.
    """
    try:
        service = get_section_report_service(case_id, "")
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        if draft.investigation_id and service is not None:
            service = get_section_report_service(case_id, draft.investigation_id)
            service.current_draft = draft

        section = service.approve_section(
            section_id=req.section_id,
            approved_by=req.approved_by,
            edits=req.edits
        )
        
        return {
            "section_id": section.section_id,
            "status": section.status.value,
            "approved_at": section.approved_at,
            "approved_by": section.approved_by,
            "message": f"Section '{section.title}' approved"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/sections/revise")
async def request_section_revision(case_id: str, draft_id: str, req: RequestRevisionRequest):
    """
    Request revision of a section with feedback.
    
    The feedback will be used when regenerating the section.
    """
    try:
        service = get_section_report_service(case_id, "")
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        if draft.investigation_id and service is not None:
            service = get_section_report_service(case_id, draft.investigation_id)
            service.current_draft = draft

        section = service.request_revision(
            section_id=req.section_id,
            revision_notes=req.revision_notes
        )
        
        return {
            "section_id": section.section_id,
            "status": section.status.value,
            "revision_notes": section.revision_notes,
            "message": f"Revision requested for '{section.title}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to request revision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/sections/{section_id}/skip")
async def skip_section(case_id: str, draft_id: str, section_id: str):
    """Skip a section (won't be included in final report)."""
    try:
        service = get_section_report_service(case_id, "")
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        if draft.investigation_id and service is not None:
            service = get_section_report_service(case_id, draft.investigation_id)
            service.current_draft = draft

        section = service.skip_section(section_id)
        
        return {
            "section_id": section.section_id,
            "status": section.status.value,
            "message": f"Section '{section.title}' skipped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/export")
async def export_draft_to_studio(case_id: str, draft_id: str, investigation_id: str):
    """
    Export approved draft to Report Studio canvas format.
    
    Returns TipTap-compatible canvas AST that can be loaded into the editor.
    """
    try:
        service = get_section_report_service(case_id, investigation_id)
        draft = service.load_draft(draft_id)
        
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
        
        export_result = service.export_to_studio()
        
        return {
            "draft_id": export_result["draft_id"],
            "canvas": export_result["canvas"],
            "key_map": export_result["key_map"],
            "exported_at": export_result["exported_at"],
            "message": "Draft exported to Report Studio format"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/section-types")
async def list_section_types():
    """List all available section types."""
    return {
        "section_types": [
            {
                "id": st.value,
                "name": st.value.replace("_", " ").title()
            }
            for st in SectionType
        ]
    }
