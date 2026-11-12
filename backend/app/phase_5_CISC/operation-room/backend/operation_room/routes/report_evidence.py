"""
Report Evidence API Routes - Intelligent Report Generation Phase 4.

Endpoints for:
- Storing evidence with KEY-VALUE pairs
- Retrieving evidence with different redaction modes
- Building evidence chains for narratives
- Audit trail access
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from operation_room.services.report_evidence_service import (
    get_report_evidence_service,
    RedactionMode,
    AccessPurpose,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report-evidence", tags=["Report Evidence"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class StoreEvidenceRequest(BaseModel):
    """Request to store evidence."""
    key_name: str = Field(..., description="Human-readable key name")
    category: str = Field(..., description="Evidence category (suspect, device, ip, etc.)")
    raw_value: str = Field(..., description="Actual evidence content")
    summary: str = Field(..., description="Brief AI-safe summary")
    evidence_type: str = Field(default="finding", description="Type of evidence")
    source_module: str = Field(default="manual", description="Source module")
    source_finding_id: Optional[str] = Field(None, description="Link to source finding")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence score")
    section_id: Optional[str] = Field(None, description="Report section ID")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class StoreFromFindingRequest(BaseModel):
    """Request to store evidence from a finding."""
    finding_id: str
    finding_content: str
    module_name: str
    category: str
    key_name: Optional[str] = None
    section_id: Optional[str] = None


class GetValueRequest(BaseModel):
    """Request to get evidence value."""
    key_id: str
    mode: str = Field(default="full", description="Redaction mode: full, key_only, redacted, summary")
    accessed_by: str = Field(..., description="Who is accessing")
    purpose: str = Field(default="review", description="Access purpose")
    session_id: Optional[str] = None


class CreateChainRequest(BaseModel):
    """Request to create evidence chain."""
    section_id: str
    key_ids: List[str]
    narrative_hint: str


class EvidenceKeyResponse(BaseModel):
    """Response with evidence key."""
    key_id: str
    key_name: str
    category: str
    summary: str
    evidence_type: str
    section_id: Optional[str]
    created_at: str
    ai_reference: str


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{case_id}/store")
async def store_evidence(case_id: str, request: StoreEvidenceRequest):
    """
    Store evidence with a KEY-VALUE pair.
    
    The key is safe for AI processing (summary only).
    The value contains the full evidence (for final report).
    """
    service = get_report_evidence_service(case_id)
    
    try:
        key_id = service.store_evidence(
            key_name=request.key_name,
            category=request.category,
            raw_value=request.raw_value,
            summary=request.summary,
            evidence_type=request.evidence_type,
            source_module=request.source_module,
            source_finding_id=request.source_finding_id,
            confidence=request.confidence,
            section_id=request.section_id,
            metadata=request.metadata
        )
        
        # Get the created key
        key = service.get_key(key_id)
        
        return {
            "success": True,
            "key_id": key_id,
            "ai_reference": key.to_ai_reference() if key else None,
            "message": f"Evidence stored with key: {key_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to store evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/store-from-finding")
async def store_from_finding(case_id: str, request: StoreFromFindingRequest):
    """
    Create evidence key from a module finding.
    
    Automatically generates key name and summary from the finding.
    """
    service = get_report_evidence_service(case_id)
    
    try:
        key_id = service.store_from_finding(
            finding_id=request.finding_id,
            finding_content=request.finding_content,
            module_name=request.module_name,
            category=request.category,
            key_name=request.key_name,
            section_id=request.section_id
        )
        
        key = service.get_key(key_id)
        
        return {
            "success": True,
            "key_id": key_id,
            "ai_reference": key.to_ai_reference() if key else None
        }
        
    except Exception as e:
        logger.error(f"Failed to store from finding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/key/{key_id}")
async def get_key(case_id: str, key_id: str):
    """Get evidence key metadata (no value)."""
    service = get_report_evidence_service(case_id)
    
    key = service.get_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Evidence key not found")
    
    return EvidenceKeyResponse(
        key_id=key.key_id,
        key_name=key.key_name,
        category=key.category,
        summary=key.summary,
        evidence_type=key.evidence_type,
        section_id=key.section_id,
        created_at=key.created_at.isoformat(),
        ai_reference=key.to_ai_reference()
    )


@router.post("/{case_id}/value")
async def get_value(case_id: str, request: GetValueRequest):
    """
    Get evidence value with specified redaction mode.
    
    ALWAYS logs access for audit trail.
    
    Modes:
    - full: Complete value (for final report)
    - key_only: Only key reference (for AI)
    - redacted: Placeholder only
    - summary: Summarized value
    """
    service = get_report_evidence_service(case_id)
    
    # Parse enums
    try:
        mode = RedactionMode(request.mode)
    except ValueError:
        mode = RedactionMode.FULL
    
    try:
        purpose = AccessPurpose(request.purpose)
    except ValueError:
        purpose = AccessPurpose.REVIEW
    
    value = service.get_value(
        key_id=request.key_id,
        mode=mode,
        accessed_by=request.accessed_by,
        purpose=purpose,
        session_id=request.session_id
    )
    
    if value is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    return {
        "key_id": request.key_id,
        "mode": request.mode,
        "value": value,
        "access_logged": True
    }


@router.get("/{case_id}/for-ai/{key_id}")
async def get_for_ai(
    case_id: str,
    key_id: str,
    component: str = Query(..., description="AI component name")
):
    """
    Get evidence reference for AI processing.
    
    Returns only summary/key, never raw value.
    Safe for sending to LLMs.
    """
    service = get_report_evidence_service(case_id)
    
    reference = service.get_for_ai(key_id, system_component=component)
    
    return {
        "key_id": key_id,
        "ai_reference": reference,
        "mode": "key_only"
    }


@router.get("/{case_id}/for-report/{key_id}")
async def get_for_report(
    case_id: str,
    key_id: str,
    user_id: str = Query(..., description="User generating report")
):
    """Get full evidence value for final report generation."""
    service = get_report_evidence_service(case_id)
    
    value = service.get_for_report(key_id, user_id=user_id)
    
    if value is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    return {
        "key_id": key_id,
        "value": value,
        "mode": "full"
    }


@router.get("/{case_id}/keys")
async def list_keys(
    case_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    section_id: Optional[str] = Query(None, description="Filter by section")
):
    """List evidence keys with optional filtering."""
    service = get_report_evidence_service(case_id)
    
    if category:
        keys = service.get_keys_by_category(category)
    elif section_id:
        keys = service.get_keys_by_section(section_id)
    else:
        keys = service.get_all_keys()
    
    return {
        "case_id": case_id,
        "count": len(keys),
        "keys": [
            {
                "key_id": k.key_id,
                "key_name": k.key_name,
                "category": k.category,
                "summary": k.summary,
                "ai_reference": k.to_ai_reference()
            }
            for k in keys
        ]
    }


@router.post("/{case_id}/chain")
async def create_chain(case_id: str, request: CreateChainRequest):
    """
    Create an evidence chain for narrative building.
    
    Chains link multiple evidence keys in order with a narrative hint.
    """
    service = get_report_evidence_service(case_id)
    
    try:
        chain_id = service.create_chain(
            section_id=request.section_id,
            key_ids=request.key_ids,
            narrative_hint=request.narrative_hint
        )
        
        return {
            "success": True,
            "chain_id": chain_id,
            "key_count": len(request.key_ids)
        }
        
    except Exception as e:
        logger.error(f"Failed to create chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}/chains/{section_id}")
async def get_chains(case_id: str, section_id: str):
    """Get all evidence chains for a section."""
    service = get_report_evidence_service(case_id)
    
    chains = service.get_chains_for_section(section_id)
    
    return {
        "section_id": section_id,
        "count": len(chains),
        "chains": [
            {
                "chain_id": c.chain_id,
                "keys": c.keys,
                "narrative_hint": c.narrative_hint,
                "created_at": c.created_at.isoformat()
            }
            for c in chains
        ]
    }


@router.get("/{case_id}/audit")
async def get_audit_log(
    case_id: str,
    key_id: Optional[str] = Query(None, description="Filter by key"),
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Get access audit log for evidence."""
    service = get_report_evidence_service(case_id)
    
    logs = service.get_access_log(key_id=key_id, limit=limit)
    
    return {
        "case_id": case_id,
        "count": len(logs),
        "logs": logs
    }


@router.get("/{case_id}/audit/summary")
async def get_audit_summary(case_id: str):
    """Get summary of evidence access for audit."""
    service = get_report_evidence_service(case_id)
    
    summary = service.get_audit_summary()
    
    return {
        "case_id": case_id,
        **summary
    }
