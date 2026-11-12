"""API routes for Case management."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from operation_room.models.case import CaseCreate, CaseUpdate
from operation_room.services import case_service
from operation_room.config import settings
from operation_room.database import open_vault, get_vault_path
import duckdb

router = APIRouter(prefix="/api/cases", tags=["Cases"])

@router.get("/{case_id}/preflight-check")
def preflight_check(case_id: str):
    """Execute a lightning-fast SELECT DISTINCT source_system FROM raw_events. Return known schemas."""
    vault_db = get_vault_path(case_id)
    if not vault_db.exists():
        raise HTTPException(404, detail="Vault not found")
        
    con = open_vault(case_id)
    try:
        results = con.execute("SELECT DISTINCT source_system FROM raw_events").fetchall()
        return {"source_systems": [r[0] for r in results if r[0]]}
    except duckdb.CatalogException:
        # Table might not exist if empty case
        return {"source_systems": []}
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    finally:
        con.close()

@router.post("/{case_id}/export")
def generate_export_bundle(case_id: str):
    """Gathers PDF, Canvas AST, artifacts. Generates manifest, hashes via SHA-256 and zips."""
    from operation_room.services.export_manifest import generate_cryptographic_export
    try:
        zip_path = generate_cryptographic_export(case_id)
        # Return the actual file for download
        return FileResponse(zip_path, media_type="application/zip", filename=f"export_{case_id}.zip")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("")
def list_cases():
    """List all cases (dashboard summary)."""
    return case_service.list_cases()


@router.post("", status_code=201)
def create_case(payload: CaseCreate):
    """Create a new forensic case and initialise its vault."""
    data = payload.model_dump()
    data["scope"] = [s.model_dump() for s in payload.scope]
    return case_service.create_case(data)


@router.get("/{case_id}")
def get_case(case_id: str):
    """Get full case detail."""
    try:
        return case_service.get_case(case_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/{case_id}")
def update_case(case_id: str, payload: CaseUpdate):
    """Update mutable case fields."""
    try:
        data = payload.model_dump(exclude_none=True)
        return case_service.update_case(case_id, data)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str):
    """Archive a case (soft delete)."""
    try:
        case_service.delete_case(case_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

# Phase 1: Security Governance - Claim Approval Role Guarding
from fastapi import Request
from pydantic import BaseModel
from operation_room.services.audit_service import record_coc_event

class ClaimUpdate(BaseModel):
    status: str
    reason: str | None = None

@router.patch("/{case_id}/claims/approve-all")
def approve_all_claims(case_id: str, req: Request):
    """Cockpit: Approve all drafts in active layout."""
    role = req.headers.get("X-User-Role", "JUNIOR_ANALYST")
    if role != "LEAD_INVESTIGATOR":
        raise HTTPException(403, detail="Only LEAD_INVESTIGATOR can perform bulk claim approvals.")
    
    # Normally this would update DuckDB rows or physical AST storage directly.
    return {"status": "success", "message": "All eligible claims approved."}


@router.patch("/{case_id}/claims/{claim_id}")
def approve_single_claim(case_id: str, claim_id: str, payload: ClaimUpdate, req: Request):
    """Cockpit: Explicit lead investigator sign-off or dispute on a single narrative claim."""
    role = req.headers.get("X-User-Role", "JUNIOR_ANALYST")
    
    if payload.status == "approved" and role != "LEAD_INVESTIGATOR":
        raise HTTPException(403, detail="Only LEAD_INVESTIGATOR can approve individual claims.")

    action = "CLAIM_DISPUTED" if payload.status == "disputed" else "CLAIM_APPROVED" if payload.status == "approved" else "CLAIM_UPDATED"

    # Persist the Dispute/Approval Audit Trail
    record_coc_event(
        case_id=case_id,
        actor=role,
        action=action,
        target_artefact=f"claim_{claim_id}",
        justification=payload.reason or "State updated.",
        hash_before=None,
        hash_after=None,
        details={"claim_id": claim_id, "new_status": payload.status}
    )

    return {"status": "success", "claim_id": claim_id, "new_state": payload.status}
