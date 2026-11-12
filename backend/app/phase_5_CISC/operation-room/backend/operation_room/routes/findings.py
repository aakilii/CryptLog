"""
Findings Vault API Routes

Endpoints for managing investigation findings as key-value pairs.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from operation_room.services.findings_vault import get_findings_vault, FindingType
from operation_room.services.confidence_scoring import get_confidence_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cases/{case_id}/findings", tags=["findings"])


# ─── Request/Response Models ─────────────────────────────────────────────────

class SaveFindingRequest(BaseModel):
    """Request to save a finding."""
    finding_key: str = Field(..., description="Unique key for this finding")
    finding_value: dict = Field(..., description="The actual data")
    finding_type: str = Field(..., description="Type of finding (hypothesis, evidence, metric, etc.)")
    investigation_id: Optional[str] = Field(None, description="Investigation session ID")
    source_module: Optional[str] = Field(None, description="Module that generated this")
    source_data_path: Optional[str] = Field(None, description="Data provenance path")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    verified: bool = Field(False, description="Whether verified")
    auto_calculate_confidence: bool = Field(True, description="Auto-calculate confidence score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "finding_key": "ACTOR_TOP_SUSPICIOUS",
                "finding_value": {
                    "actor": "john.doe@company.com",
                    "anomaly_score": 0.89,
                    "event_count": 147,
                    "suspicious_actions": ["bulk_download", "after_hours_access"]
                },
                "finding_type": "evidence",
                "investigation_id": "inv-123",
                "source_module": "anomaly",
                "source_data_path": "anomaly_scores.actor",
                "metadata": {"run_id": "run-456"},
                "verified": False,
                "auto_calculate_confidence": True
            }
        }


class FindingResponse(BaseModel):
    """Response with finding details."""
    finding_id: str
    finding_key: str
    finding_value: dict
    finding_type: str
    confidence_score: float
    confidence_level: str
    verified: bool
    source_module: Optional[str]
    created_at: str
    updated_at: str


class FindingsSummaryResponse(BaseModel):
    """Summary of all findings."""
    total_findings: int
    verified_count: int
    avg_confidence: float
    max_confidence: float
    min_confidence: float
    by_type: List[dict]
    by_module: List[dict]


# ─── API Routes ──────────────────────────────────────────────────────────────

@router.post("/save")
async def save_finding(case_id: str, req: SaveFindingRequest):
    """
    Save a finding to the vault.
    
    Automatically calculates confidence score unless disabled.
    """
    try:
        vault = get_findings_vault(case_id)
        
        # Calculate confidence if requested
        confidence_score = 0.5
        confidence_level = "MODERATE"
        
        if req.auto_calculate_confidence:
            engine = get_confidence_engine(case_id)
            factors = engine.calculate_confidence(
                finding_key=req.finding_key,
                finding_value=req.finding_value,
                finding_type=req.finding_type,
                source_module=req.source_module,
                metadata=req.metadata,
                investigation_id=req.investigation_id
            )
            confidence_score = factors.calculate_overall()
            confidence_level = factors.get_confidence_level()
        
        # Save finding
        finding_id = vault.save_finding(
            finding_key=req.finding_key,
            finding_value=req.finding_value,
            finding_type=req.finding_type,
            investigation_id=req.investigation_id,
            confidence_score=confidence_score,
            source_module=req.source_module,
            source_data_path=req.source_data_path,
            metadata=req.metadata,
            verified=req.verified
        )
        
        return {
            "status": "success",
            "finding_id": finding_id,
            "finding_key": req.finding_key,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level
        }
        
    except Exception as e:
        logger.error(f"Error saving finding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get/{finding_key}")
async def get_finding(
    case_id: str,
    finding_key: str,
    investigation_id: Optional[str] = Query(None)
):
    """Get a finding by its key."""
    try:
        vault = get_findings_vault(case_id)
        finding = vault.get_finding(finding_key, investigation_id)
        
        if not finding:
            raise HTTPException(status_code=404, detail=f"Finding {finding_key} not found")
        
        return finding
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting finding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_findings(
    case_id: str,
    investigation_id: Optional[str] = Query(None),
    finding_type: Optional[str] = Query(None),
    verified_only: bool = Query(False),
    min_confidence: float = Query(0.0)
):
    """List all findings matching criteria."""
    try:
        vault = get_findings_vault(case_id)
        findings = vault.get_all_findings(
            investigation_id=investigation_id,
            finding_type=finding_type,
            verified_only=verified_only,
            min_confidence=min_confidence
        )
        
        return {
            "total": len(findings),
            "findings": findings
        }
        
    except Exception as e:
        logger.error(f"Error listing findings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_findings_summary(
    case_id: str,
    investigation_id: Optional[str] = Query(None)
):
    """Get summary statistics about findings."""
    try:
        vault = get_findings_vault(case_id)
        summary = vault.get_findings_summary(investigation_id)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify/{finding_key}")
async def verify_finding(
    case_id: str,
    finding_key: str,
    investigation_id: Optional[str] = Query(None)
):
    """Mark a finding as verified."""
    try:
        vault = get_findings_vault(case_id)
        success = vault.verify_finding(finding_key, investigation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Finding {finding_key} not found")
        
        return {"status": "verified", "finding_key": finding_key}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying finding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate-confidence")
async def recalculate_all_confidences(
    case_id: str,
    investigation_id: Optional[str] = Query(None)
):
    """
    Recalculate confidence scores for all findings.
    
    Useful when new findings are added that might corroborate existing ones.
    """
    try:
        engine = get_confidence_engine(case_id)
        updated_count = engine.recalculate_all_confidences(investigation_id)
        
        return {
            "status": "success",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error recalculating confidences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{finding_key}")
async def delete_finding(
    case_id: str,
    finding_key: str,
    investigation_id: Optional[str] = Query(None)
):
    """Delete a finding."""
    try:
        vault = get_findings_vault(case_id)
        success = vault.delete_finding(finding_key, investigation_id)
        
        return {"status": "deleted", "finding_key": finding_key}
        
    except Exception as e:
        logger.error(f"Error deleting finding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-module/{source_module}")
async def get_findings_by_module(
    case_id: str,
    source_module: str,
    investigation_id: Optional[str] = Query(None)
):
    """Get all findings from a specific module."""
    try:
        vault = get_findings_vault(case_id)
        findings = vault.get_findings_by_module(source_module, investigation_id)
        
        return {
            "source_module": source_module,
            "total": len(findings),
            "findings": findings
        }
        
    except Exception as e:
        logger.error(f"Error getting findings by module: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
