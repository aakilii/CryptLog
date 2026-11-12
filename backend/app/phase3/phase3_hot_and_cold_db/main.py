from __future__ import annotations

import asyncio
import os
import uuid
import datetime as dt
from pathlib import Path
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from .janitor import JanitorFlags, run_janitor_loop
from .privacy import apply_redactions, compute_privacy_confidence, is_privacy_bypass_enabled
from .schemas import (
    ExtendRequest,
    GraphQLQueryRequest,
    LockRequest,
    Phase2Payload,
    QueryLogsRequest,
    RemoveRequest,
)
from .storage import (
    StorageConfig,
    commit_cold,
    connect_hot,
    ensure_dirs,
    extend_lineage,
    insert_hot_event,
    lock_lineage,
    query_cold,
    query_hot,
    remove_lineage,
    remove_lineage_s3,
    rollback_cold,
    stage_to_cold,
)
from .vectorize import embed


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _cfg() -> StorageConfig:
    hot_db_path = os.getenv("PHASE3_HOT_DB_PATH", "data/phase3_hot.duckdb")
    cold_dir = os.getenv("PHASE3_COLD_DIR", "data/phase3_cold")
    ttl_seconds = int(os.getenv("PHASE3_TTL_SECONDS", "30"))
    return StorageConfig(hot_db_path=hot_db_path, cold_dir=cold_dir, ttl_seconds=ttl_seconds)


new_app = FastAPI(title="Phase 3: Forensic Storage Gateway")
_config = _cfg()
ensure_dirs(_config)
_hot = connect_hot(_config)
_janitor_flags = JanitorFlags(notified_20=set(), notified_10=set(), notified_0=set())


@new_app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(run_janitor_loop(_hot, _janitor_flags))


async def _ingest(payload: Dict[str, Any]) -> Dict[str, Any]:
    lineage = str(payload.get("Lineage") or "").strip()
    if not lineage:
        raise HTTPException(status_code=400, detail="Lineage is required")

    target_user = str(payload.get("Target_User") or "").strip()
    notes = str(payload.get("Notes") or "")
    audit_id = str(payload.get("audit_id") or "")
    source_type = str(payload.get("source_type") or "")
    extracted_variables = str(payload.get("extracted_variables") or "{}")
    ner_tags = str(payload.get("ner_tags") or "{}")
    normalized_timestamp_str = payload.get("normalized_timestamp")
    row_hash = str(payload.get("row_hash") or payload.get("final_row_hash") or "")

    created_at = _now_utc()

    normalized_timestamp = None
    if normalized_timestamp_str:
        try:
            normalized_timestamp = dt.datetime.fromisoformat(str(normalized_timestamp_str))
        except Exception:
            pass

    if is_privacy_bypass_enabled():
        notes_redacted = notes
        redactions = 0
    else:
        notes_redacted, redactions = apply_redactions(notes)

    privacy_conf = compute_privacy_confidence(redactions)
    vector = embed(notes_redacted)

    event_id = uuid.uuid4().hex
    ttl_seconds = _config.ttl_seconds

    stage_path = None
    try:
        stage_path = stage_to_cold(
            _config,
            {
                "Target_User": target_user,
                "Notes": notes,
                "Notes_Redacted": notes_redacted,
                "Lineage": lineage,
                "audit_id": audit_id,
                "source_type": source_type,
                "extracted_variables": extracted_variables,
                "ner_tags": ner_tags,
                "normalized_timestamp": normalized_timestamp,
                "row_hash": row_hash,
                "created_at": created_at,
            },
        )

        insert_hot_event(
            _hot,
            lineage=lineage,
            target_user=target_user,
            notes=notes,
            notes_redacted=notes_redacted,
            vector=vector,
            created_at=created_at,
            ttl_seconds=ttl_seconds,
            pii_redactions=redactions,
            privacy_confidence=privacy_conf,
            audit_id=audit_id,
            source_type=source_type,
            extracted_variables=extracted_variables,
            ner_tags=ner_tags,
            normalized_timestamp=normalized_timestamp,
            row_hash=row_hash,
        )

        cold_ref = commit_cold(_config, lineage)
        return {
            "ok": True,
            "event_id": event_id,
            "lineage": lineage,
            "hot_db": _config.hot_db_path,
            "cold_object": cold_ref,
            "pii_redactions": redactions,
            "privacy_confidence": privacy_conf,
        }
    except HTTPException:
        if lineage:
            rollback_cold(_config, lineage)
        raise
    except Exception as e:
        if lineage:
            rollback_cold(_config, lineage)
        raise HTTPException(status_code=500, detail=f"Phase 3 ingest failed: {e}") from e


@new_app.post("/phase2_webhook")
async def phase2_webhook(req: Phase2Payload, bg: BackgroundTasks):
    bg.add_task(_ingest, req.model_dump())
    return {"ok": True, "status": "accepted"}


@new_app.post("/lock_file")
async def lock_file(req: LockRequest):
    lock_lineage(_hot, req.Lineage)
    return {"ok": True, "status": "locked", "lineage": req.Lineage}


@new_app.post("/extend")
async def extend(req: ExtendRequest):
    extend_lineage(_hot, req.Lineage, req.seconds)
    for s in (_janitor_flags.notified_20, _janitor_flags.notified_10, _janitor_flags.notified_0):
        s.discard(req.Lineage)
    return {"ok": True, "status": "extended", "lineage": req.Lineage, "seconds": req.seconds}


@new_app.post("/remove")
async def remove(req: RemoveRequest):
    remove_lineage(_hot, req.Lineage)
    remove_lineage_s3(req.Lineage)
    for s in (_janitor_flags.notified_20, _janitor_flags.notified_10, _janitor_flags.notified_0):
        s.discard(req.Lineage)
    return {"ok": True, "status": "removed", "lineage": req.Lineage}


@new_app.post("/graphql_query")
async def graphql_query(req: GraphQLQueryRequest):
    if req.depth > 4:
        raise HTTPException(status_code=429, detail="Query depth exceeds safety limit (max=4).")

    limit = max(1, min(int(req.limit), 10000))
    offset = max(0, int(req.offset))
    target = (req.Target_User or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target_User is required")

    data = query_cold(_config, target_user=target, limit=limit, offset=offset)
    return {"ok": True, "status": "Rehydration Success", "depth": req.depth, "count": len(data), "data": data}


@new_app.get("/query-logs")
async def query_logs_endpoint(
    source_type: str = Query(default="", description="Filter by log source type"),
    time_start: str = Query(default="", description="ISO-8601 start timestamp"),
    time_end: str = Query(default="", description="ISO-8601 end timestamp"),
    target_user: str = Query(default="", description="Filter by target user"),
    limit: int = Query(default=5000, ge=1, le=20000),
    offset: int = Query(default=0, ge=0),
):
    """
    Query both hot DuckDB and cold Parquet storage with flexible filters.
    Used by the Operation Room import to pull processed logs.
    Merges results, deduplicates by Lineage, and returns up to `limit` rows.
    """
    kw = dict(target_user=target_user, source_type=source_type,
              time_start=time_start, time_end=time_end,
              limit=limit, offset=offset)

    hot_data = query_hot(_hot, **kw)
    cold_data = query_cold(_config, **kw)

    seen: set[str] = set()
    merged: list[dict] = []
    for row in hot_data + cold_data:
        lineage = row.get("Lineage", "")
        if lineage and lineage in seen:
            continue
        seen.add(lineage)
        merged.append(row)

    merged.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    page = merged[offset:offset + limit] if offset else merged[:limit]
    return {"ok": True, "count": len(page), "data": page}


@new_app.get("/health")
async def health():
    from .s3_client import is_s3_enabled

    return {
        "ok": True,
        "phase": 3,
        "hot_db_path": _config.hot_db_path,
        "cold_dir": _config.cold_dir,
        "ttl_seconds": _config.ttl_seconds,
        "s3_enabled": is_s3_enabled(),
        "s3_bucket": os.getenv("S3_BUCKET_NAME", ""),
    }
