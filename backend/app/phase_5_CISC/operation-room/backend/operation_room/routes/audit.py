"""API routes for Audit / Chain‑of‑Custody."""

from fastapi import APIRouter, HTTPException
from operation_room.services import audit_service
from operation_room.database import vault_exists

router = APIRouter(tags=["Audit"])


@router.get("/api/cases/{case_id}/chain-of-custody")
def get_chain_of_custody(case_id: str):
    """Get all chain‑of‑custody events for a case."""
    try:
        return audit_service.get_coc_events(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/api/audit-log")
def get_audit_log(limit: int = 200):
    """Read the global audit log (last N entries)."""
    return audit_service.get_global_audit_log(limit=limit)

from pydantic import BaseModel
from typing import List, Optional

class AuditEventCreate(BaseModel):
    action: str
    user_initials: Optional[str] = None
    missing_telemetry: Optional[List[str]] = None
    playbook_id: Optional[str] = None

@router.post("/api/cases/{case_id}/audit")
def log_audit_event(case_id: str, event: AuditEventCreate):
    """Log an explicit liability event like a Playbook gap waiver."""
    try:
        details = {
            "user_initials": event.user_initials,
            "playbook": event.playbook_id,
            "missing_telemetry": event.missing_telemetry
        }
        if not vault_exists(case_id):
            raise HTTPException(status_code=404, detail="Vault not found")

        event_id = audit_service.record_coc_event(
            case_id=case_id,
            actor=event.user_initials or "UNKNOWN",
            action=event.action,
            target_artefact=f"audit:{event.playbook_id or 'manual'}",
            justification="Manual audit event",
            details=details,
        )
        
        return {"status": "success", "recorded": True, "event_id": event_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit log failed: {exc}")

