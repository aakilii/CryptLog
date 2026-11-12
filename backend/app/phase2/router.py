"""
Phase 2 API Router
REST endpoints for Universal Translator pipeline
"""

import json
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.session import SessionLocal
from app.phase2.service import (
    process_file_phase2,
    process_file_phase2_stream,
    get_staging_previews,
    commit_staging_batch,
    get_staging_preview,
    commit_staging,
)
from app.phase2.node6_staging import (
    get_staging_preview as get_preview,
    confirm_staging,
    reject_staging,
    query_staging,
    get_staging_statistics,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class Phase2ProcessRequest(BaseModel):
    audit_id: str
    file_path: str
    source_ip: Optional[str] = None


class CommitRequest(BaseModel):
    human_overrides: Optional[dict] = None
    confirm: bool = True


class ConfirmRequest(BaseModel):
    human_overrides: Optional[dict] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/process")
async def process_phase2(
    request: Phase2ProcessRequest,
    db: Session = Depends(get_db)
):
    """
    Process file through Phase 2 pipeline (all 6 nodes).
    
    Triggers:
    - Node 1: Lineage Anchoring
    - Node 2: Recursive De-obfuscation
    - Node 3: DRAIN3 Template Extraction
    - Node 4: NER Tagging
    - Node 5: Timestamp Sync
    - Node 6: Staging Area Creation
    
    Returns staging IDs for human review.
    """
    try:
        result = process_file_phase2(
            db=db,
            audit_id=request.audit_id,
            file_path=request.file_path,
            source_ip=request.source_ip
        )
        return result
    except ValueError as e:
        logger.error(f"[Phase2 Router] ValueError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"[Phase2 Router] FileNotFoundError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"[Phase2 Router] Unhandled error: {e}")
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/process-stream")
async def process_phase2_stream(
    audit_id: str,
    file_path: str = "",
    source_ip: Optional[str] = None,
):
    """
    SSE endpoint that streams per-node, per-line progress while running
    the full Phase 2 pipeline.  The frontend connects with EventSource.

    If staging rows already exist for this audit (e.g. AUTO_TRIGGER_PHASE2
    already ran), emits a fast "already_processed" event instead.
    """
    sse_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    def _generate():
        import os
        db = SessionLocal()
        try:
            from app.db.models import StagingArea

            auto_on = os.getenv("AUTO_TRIGGER_PHASE2", "true").lower() not in {
                "0", "false", "no", "off",
            }

            existing = (
                db.query(StagingArea)
                .filter(StagingArea.audit_id == audit_id)
                .count()
            )
            if existing > 0:
                yield f"data: {json.dumps({'type': 'already_processed', 'rows': existing, 'audit_id': audit_id})}\n\n"
                return

            if auto_on:
                for attempt in range(60):
                    time.sleep(2)
                    db.expire_all()
                    existing = (
                        db.query(StagingArea)
                        .filter(StagingArea.audit_id == audit_id)
                        .count()
                    )
                    if existing > 0:
                        yield f"data: {json.dumps({'type': 'already_processed', 'rows': existing, 'audit_id': audit_id})}\n\n"
                        return
                    pct = min(99, int((attempt + 1) / 60 * 100))
                    yield f"data: {json.dumps({'type': 'progress', 'percent': pct, 'message': f'Phase 2 processing in progress... ({attempt+1})'})}\n\n"

            for event in process_file_phase2_stream(db, audit_id, file_path, source_ip):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get("/preview/{staging_id}")
async def preview_staging(
    staging_id: str,
    db: Session = Depends(get_db)
):
    """
    Get preview of staged data for human review.
    
    Returns processed data with all node outputs.
    """
    try:
        preview = get_staging_preview(db, staging_id)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview/audit/{audit_id}")
async def preview_audit_staging(
    audit_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get previews of all staging entries for an audit.
    
    Returns list of previews for human review.
    """
    try:
        previews = get_staging_previews(db, audit_id, limit=limit)
        return {
            "audit_id": audit_id,
            "count": len(previews),
            "previews": previews
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commit/{staging_id}")
async def commit_single_staging(
    staging_id: str,
    request: CommitRequest,
    db: Session = Depends(get_db)
):
    """
    Commit single staging entry with human overrides.
    
    Implements "Confirm & Push Database" workflow:
    1. Takes final row hash (after human overrides)
    2. Writes to SQLite Audit Ledger
    3. Moves data from Staging → DuckDB Main Table
    4. Sends background signal to Phase 3
    
    This is the single action that combines confirmation and commit.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Commit confirmation required"
        )
    
    try:
        result = commit_staging(
            db=db,
            staging_id=staging_id,
            human_overrides=request.human_overrides
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commit/audit/{audit_id}")
async def commit_audit_staging(
    audit_id: str,
    request: CommitRequest,
):
    """
    Commit all staging entries for an audit.

    Batch commit with human overrides.
    """
    import asyncio

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Commit confirmation required"
        )

    def _run():
        db = SessionLocal()
        try:
            return commit_staging_batch(
                db=db,
                audit_id=audit_id,
                human_overrides=request.human_overrides,
            )
        finally:
            db.close()

    try:
        result = await asyncio.to_thread(_run)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm/{staging_id}")
async def confirm_single_staging(
    staging_id: str,
    request: ConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Confirm staging entry (pending -> confirmed).
    
    Marks entry as confirmed for review, does not commit to DuckDB.
    """
    try:
        result = confirm_staging(
            db=db,
            staging_id=staging_id,
            human_overrides=request.human_overrides
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject/{staging_id}")
async def reject_single_staging(
    staging_id: str,
    request: RejectRequest,
    db: Session = Depends(get_db)
):
    """
    Reject staging entry.
    
    Marks entry as rejected, prevents commit.
    """
    try:
        result = reject_staging(
            db=db,
            staging_id=staging_id,
            reason=request.reason
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query")
async def query_staging_entries(
    audit_id: Optional[str] = None,
    status: Optional[str] = None,
    has_template: Optional[bool] = None,
    has_ner_tags: Optional[bool] = None,
    has_timestamp: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Query staging entries with filters.
    
    Filters:
    - audit_id: Filter by audit ID
    - status: Filter by status (pending, confirmed, committed, rejected)
    - has_template: Filter by template presence
    - has_ner_tags: Filter by NER tags presence
    - has_timestamp: Filter by timestamp presence
    - limit: Maximum results (default: 100)
    - offset: Offset for pagination (default: 0)
    """
    try:
        result = query_staging(
            db=db,
            audit_id=audit_id,
            status=status,
            has_template=has_template,
            has_ner_tags=has_ner_tags,
            has_timestamp=has_timestamp,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics(
    audit_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get statistics for staging entries.
    
    Returns:
    - Total count
    - Status breakdown
    - Feature presence counts
    - Percentages
    """
    try:
        stats = get_staging_statistics(db=db, audit_id=audit_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

