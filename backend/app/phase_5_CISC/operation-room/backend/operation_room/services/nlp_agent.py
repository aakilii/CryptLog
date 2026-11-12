"""
NLP Agent — queries Phase 3 cold storage (S3 Parquet) for log records.

Replaces the original stub. When the Operation Room import form is submitted,
this function calls GET /api/phase3/query-logs with the user's filters
(source type, time range, actors, systems) and maps the returned rows into
the raw_events schema expected by evidence_service.import_evidence.
"""

import json
import uuid
import logging

import httpx

from operation_room.config import settings

logger = logging.getLogger(__name__)


def _map_phase3_row(row: dict, source_type: str) -> dict:
    """Map a Phase 3 cold-storage row to Operation Room raw_events shape."""
    ev = {}
    ev_json = row.get("extracted_variables", "{}")
    if isinstance(ev_json, str):
        try:
            ev = json.loads(ev_json)
        except Exception:
            ev = {}

    ner = {}
    ner_json = row.get("ner_tags", "{}")
    if isinstance(ner_json, str):
        try:
            ner = json.loads(ner_json)
        except Exception:
            ner = {}

    actor = ev.get("user", ev.get("User", ""))
    if not actor and ner.get("emails"):
        actor = ner["emails"][0] if isinstance(ner["emails"], list) else str(ner["emails"])

    action = ev.get("action", ev.get("Action", ""))
    target = ev.get("target", ev.get("Target", ""))
    source_system = ev.get("source_system", ev.get("host", ""))
    ip = ""
    if ner.get("ips"):
        ip = ner["ips"][0] if isinstance(ner["ips"], list) else str(ner["ips"])

    detail = {
        "extracted_variables": ev,
        "ner_tags": ner,
        "lineage": row.get("Lineage", ""),
        "audit_id": row.get("audit_id", ""),
        "row_hash": row.get("row_hash", ""),
        "source_ip": ip,
        "raw_notes": row.get("Notes", ""),
    }

    return {
        "event_id": str(uuid.uuid4()),
        "source_type": source_type or row.get("source_type", "LOG"),
        "timestamp": row.get("normalized_timestamp") or row.get("created_at"),
        "source_system": source_system,
        "actor": actor,
        "action": action,
        "target": target,
        "detail": detail,
    }


async def query_nlp_agent(
    source_type: str = "",
    time_start: str = "",
    time_end: str = "",
    target_actors: list | None = None,
    target_systems: list | None = None,
    query_text: str = "",
    **kwargs,
) -> dict:
    """
    Query Phase 3 hot + cold storage for log records matching the given filters.
    Returns a dict with 'records' list matching the raw_events schema.
    """
    base = settings.PHASE3_API_BASE.rstrip("/")
    url = f"{base}/query-logs"

    params: dict[str, str | int] = {
        "limit": 5000,
        "offset": 0,
    }
    if time_start:
        params["time_start"] = time_start
    if time_end:
        params["time_end"] = time_end
    if target_actors:
        params["target_user"] = target_actors[0]

    # First try with all filters; if nothing comes back, retry without
    # source_type since Phase 2 may not have populated it.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if source_type:
                params["source_type"] = source_type
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

            if not body.get("data") and source_type:
                params.pop("source_type", None)
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()

            if not body.get("data") and "target_user" in params:
                params.pop("target_user", None)
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
    except Exception as exc:
        logger.error(f"Phase 3 query-logs failed: {exc}")
        return {
            "success": False,
            "query": query_text,
            "records": [],
            "message": f"Failed to query Phase 3 storage: {exc}",
        }

    raw_rows = body.get("data", [])
    records = [_map_phase3_row(r, source_type) for r in raw_rows]

    return {
        "success": True,
        "query": query_text,
        "records": records,
        "message": f"Retrieved {len(records)} records from Phase 3 storage.",
    }
