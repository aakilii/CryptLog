"""
Evidence Binding API — Phase 2.

Endpoints for querying module data, binding to report blocks,
and verifying evidence integrity.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging

from operation_room.services.binding_service import (
    list_available_queries,
    execute_binding_query,
    verify_binding_hash,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v4/studio/cases/{case_id}/bindings", tags=["Evidence Bindings"])


class VerifyRequest(BaseModel):
    module: str
    query_id: str
    expected_hash: str


@router.get("/queries")
def api_list_queries(case_id: str, module: Optional[str] = None):
    """List all available predefined queries."""
    return {"queries": list_available_queries(module)}


@router.get("/queries/{module}/{query_id}")
def api_execute_query(case_id: str, module: str, query_id: str):
    """Execute a predefined query and return data + hash."""
    result = execute_binding_query(case_id, module, query_id)
    if result.get("error"):
        return {"error": result["error"]}, 400
    return result


@router.post("/verify")
def api_verify_binding(case_id: str, req: VerifyRequest):
    """Verify an evidence binding hash against current data."""
    return verify_binding_hash(case_id, req.module, req.query_id, req.expected_hash)
