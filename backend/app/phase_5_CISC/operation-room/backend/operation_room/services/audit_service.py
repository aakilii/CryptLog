"""
Audit / Chain‑of‑Custody service.

Two audit layers:
  1. Per‑case CoC table inside the DuckDB vault (forensic evidence chain).
  2. Global audit_log.jsonl outside all case folders (system‑wide tamper‑evident log).
"""

import json
import uuid
import canonicaljson
from datetime import datetime, timezone
from pathlib import Path

from operation_room.config import settings
from operation_room.database import open_vault


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Per‑case Chain of Custody ────────────────────────────────────────────

def record_coc_event(
    case_id: str,
    actor: str,
    action: str,
    target_artefact: str,
    justification: str = "",
    hash_before: str | None = None,
    hash_after: str | None = None,
    details: dict | None = None,
) -> str:
    """
    Append an event to the per‑case chain_of_custody table.
    Returns the generated event_id.
    """
    event_id = str(uuid.uuid4())
    ts = _now_iso()
    conn = open_vault(case_id)
    try:
        conn.execute(
            """
            INSERT INTO chain_of_custody
                (event_id, case_id, timestamp, actor, action,
                 target_artefact, justification, hash_before, hash_after, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id, case_id, ts, actor, action,
                target_artefact, justification,
                hash_before, hash_after,
                canonicaljson.encode_canonical_json(json.loads(json.dumps(details, default=str))).decode("utf-8") if details else None,
            ],
        )
    finally:
        conn.close()

    # Also write to the global audit log
    _append_global_audit(actor, action, case_id, target_artefact, details)

    return event_id


def get_coc_events(case_id: str) -> list[dict]:
    """Retrieve all CoC events for a case, chronologically."""
    conn = open_vault(case_id)
    try:
        rows = conn.execute(
            """
            SELECT event_id, case_id, timestamp, actor, action,
                   target_artefact, justification, hash_before, hash_after, details
            FROM chain_of_custody
            WHERE case_id = ?
            ORDER BY timestamp ASC
            """,
            [case_id],
        ).fetchall()
        cols = [
            "event_id", "case_id", "timestamp", "actor", "action",
            "target_artefact", "justification", "hash_before", "hash_after", "details",
        ]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


# ── Global Audit Log ─────────────────────────────────────────────────────

def _append_global_audit(
    actor: str,
    action: str,
    case_id: str | None,
    target: str,
    details: dict | None = None,
) -> None:
    """Append a line to the global audit_log.jsonl (append‑only, tamper‑evident)."""
    entry = {
        "timestamp": _now_iso(),
        "actor": actor,
        "action": action,
        "case_id": case_id,
        "target": target,
        "details": details,
    }
    path = settings.AUDIT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def get_global_audit_log(limit: int = 200) -> list[dict]:
    """Read the last N entries from the global audit log."""
    path = settings.AUDIT_LOG_PATH
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-limit:]
    return [json.loads(line) for line in recent]
