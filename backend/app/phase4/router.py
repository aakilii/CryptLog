"""Phase 4 REST: expose committed Phase 2 data for analytics UI."""

from fastapi import APIRouter, Query

from app.phase4.service import fetch_parsed_logs_for_audit

router = APIRouter()


@router.get("/parsed-logs")
def get_parsed_logs(
    audit_id: str = Query(..., min_length=1, description="Phase 1 audit UUID from ledger"),
    limit: int = Query(5000, ge=1, le=20000),
):
    rows = fetch_parsed_logs_for_audit(audit_id, limit=limit)
    return {
        "ok": True,
        "audit_id": audit_id,
        "row_count": len(rows),
        "rows": rows,
    }
