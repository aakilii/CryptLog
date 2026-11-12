"""Load committed normalized logs from DuckDB and map to Phase 4 / Magic Query schema."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.db.duckdb import get_duckdb_connection

_SEVERITY_RE = re.compile(r"\b(ERROR|WARN|INFO|DEBUG|FATAL|CRITICAL)\b", re.I)


def _parse_json_obj(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _infer_severity(text: str) -> str:
    m = _SEVERITY_RE.search(text or "")
    if m:
        return m.group(1).upper()
    return "INFO"


def _first_str(d: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _map_normalized_row(
    idx: int,
    extracted_variables_raw: Any,
    ner_tags_raw: Any,
    normalized_timestamp: Any,
) -> Dict[str, Any]:
    ev = _parse_json_obj(extracted_variables_raw)
    ner = _parse_json_obj(ner_tags_raw)

    raw_log = str(ev.get("original") or "")
    ips: List[str] = list(ner.get("ip_addresses") or [])
    ip_address = ips[0] if ips else ""

    event_template = _first_str(ev, ["template", "event_template"]) or (
        (raw_log[:240] + "…") if len(raw_log) > 240 else raw_log
    )
    if not event_template:
        event_template = "log_event"

    user = _first_str(ev, ["user", "username", "USER", "uid"])
    process_name = _first_str(ev, ["process", "process_name", "proc", "daemon"])

    if normalized_timestamp is None:
        ts = ""
    elif isinstance(normalized_timestamp, datetime):
        ts = normalized_timestamp.isoformat()
    else:
        ts = str(normalized_timestamp)

    severity = _infer_severity(raw_log)
    facility = _first_str(ev, ["facility", "syslog_facility"]) or "forensic"

    return {
        "id": idx,
        "timestamp": ts,
        "event_template": event_template,
        "ip_address": ip_address,
        "process_name": process_name,
        "user": user or "unknown",
        "severity": severity,
        "facility": facility,
        "raw_log": raw_log,
    }


def fetch_parsed_logs_for_audit(audit_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    """
    Return rows in Magic Query / Phase 4 UI shape from DuckDB normalized_logs.
    """
    audit_id = (audit_id or "").strip()
    if not audit_id:
        return []

    cap = max(1, min(int(limit), 20_000))
    try:
        conn = get_duckdb_connection()
    except Exception as e:
        logger.warning(f"[Phase4] DuckDB connect failed: {e}")
        return []

    try:
        rows = conn.execute(
            """
            SELECT staging_id, audit_id, extracted_variables, ner_tags, normalized_timestamp
            FROM normalized_logs
            WHERE audit_id = ?
            ORDER BY committed_at DESC
            LIMIT ?
            """,
            [audit_id, cap],
        ).fetchall()
    except Exception as e:
        logger.warning(f"[Phase4] normalized_logs query failed: {e}")
        conn.close()
        return []

    conn.close()

    out: List[Dict[str, Any]] = []
    for i, (_, _, ev, nt, nts) in enumerate(rows, start=1):
        out.append(_map_normalized_row(i, ev, nt, nts))
    return out
