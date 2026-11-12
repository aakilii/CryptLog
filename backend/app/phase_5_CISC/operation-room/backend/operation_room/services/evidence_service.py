"""
Evidence import & integrity service.

Orchestrates:  NLP agent query → hash computation → DuckDB storage → CoC logging.
"""

import json
import uuid
from datetime import datetime, timezone

from operation_room.database import open_vault
from operation_room.config import settings
from operation_room.utils.hashing import hash_records
from operation_room.services.nlp_agent import query_nlp_agent
from operation_room.services.audit_service import record_coc_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


MAGIC_QUERY_SOURCE = "MAGIC_QUERY"
MAX_MAGIC_QUERY_ROWS = 5000


def _parsed_logs_row_to_raw_event(row: dict, audit_id: str | None) -> dict:
    """Map Phase 4 / Magic Query parsed_logs row to raw_events schema."""
    ts = str(row.get("timestamp") or "")
    et = str(row.get("event_template") or "")
    action = (et[:200] if et else "log_event") or "log_event"
    user = str(row.get("user") or "")
    ip = str(row.get("ip_address") or "")
    proc = str(row.get("process_name") or "")
    fac = str(row.get("facility") or "")
    raw = str(row.get("raw_log") or "")
    sev = str(row.get("severity") or "")
    rid = row.get("id")
    detail = {
        "magic_query": True,
        "audit_id": audit_id,
        "original_row_id": rid,
        "event_template": et[:4096] if et else "",
        "ip_address": ip,
        "process_name": proc,
        "severity": sev,
        "facility": fac,
        "raw_log": raw[:8192] if raw else "",
    }
    return {
        "event_id": str(uuid.uuid4()),
        "source_type": MAGIC_QUERY_SOURCE,
        "timestamp": ts,
        "source_system": proc or fac or "",
        "actor": user,
        "action": action,
        "target": ip,
        "detail": detail,
    }


async def import_magic_query_rows(
    case_id: str,
    rows: list[dict],
    audit_id: str | None = None,
    justification: str = "Magic Query result import",
) -> dict:
    """
    Persist Magic Query / parsed_logs rows into raw_events with the same hash + CoC path as Phase 3 import.
    """
    if len(rows) > MAX_MAGIC_QUERY_ROWS:
        raise ValueError(f"At most {MAX_MAGIC_QUERY_ROWS} rows per import")
    if len(rows) < 1:
        raise ValueError("At least one row is required")

    batch_id = str(uuid.uuid4())
    actor = "analyst"
    now = _now_iso()

    records = [_parsed_logs_row_to_raw_event(dict(r), audit_id) for r in rows]

    payload_bytes = json.dumps(records, sort_keys=True, default=str).encode("utf-8")
    hash_value = hash_records(records, settings.HASH_ALGORITHM)
    byte_size = len(payload_bytes)

    day = now[:10]
    artefact_name = f"magic_query_{day}_{batch_id[:8]}"

    conn = open_vault(case_id)
    try:
        with conn.transaction():
            for rec in records:
                conn.execute(
                    """
                    INSERT INTO raw_events
                        (event_id, case_id, import_batch_id, source_type,
                         timestamp, source_system, actor, action, target, detail, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        rec.get("event_id", str(uuid.uuid4())),
                        case_id,
                        batch_id,
                        rec.get("source_type", MAGIC_QUERY_SOURCE),
                        rec.get("timestamp"),
                        rec.get("source_system"),
                        rec.get("actor"),
                        rec.get("action"),
                        rec.get("target"),
                        json.dumps(rec.get("detail", {})),
                        now,
                    ],
                )

            hash_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO evidence_hashes
                    (hash_id, case_id, import_batch_id, artefact_name, artefact_type,
                     hash_algorithm, hash_value, record_count, byte_size,
                     created_at, created_by)
                VALUES (?, ?, ?, ?, 'MAGIC_QUERY_RESULT', ?, ?, ?, ?, ?, ?)
                """,
                [
                    hash_id,
                    case_id,
                    batch_id,
                    artefact_name,
                    settings.HASH_ALGORITHM.upper().replace("SHA", "SHA-"),
                    hash_value,
                    len(records),
                    byte_size,
                    now,
                    actor,
                ],
            )
    finally:
        conn.close()

    coc_id = record_coc_event(
        case_id=case_id,
        actor=actor,
        action="IMPORT",
        target_artefact=artefact_name,
        justification=justification,
        hash_after=hash_value,
        details={
            "batch_id": batch_id,
            "source_type": MAGIC_QUERY_SOURCE,
            "record_count": len(records),
            "byte_size": byte_size,
            "audit_id": audit_id,
        },
    )

    return {
        "import_batch_id": batch_id,
        "artefact_name": artefact_name,
        "record_count": len(records),
        "byte_size": byte_size,
        "hash_algorithm": settings.HASH_ALGORITHM.upper().replace("SHA", "SHA-"),
        "hash_value": hash_value,
        "coc_event_id": coc_id,
        "message": f"Imported {len(records)} Magic Query rows into case vault.",
    }


async def import_evidence(case_id: str, data: dict) -> dict:
    """
    Full import pipeline:
      1. Query NLP agent for log records.
      2. Compute SHA‑256 hash of the result set.
      3. Insert records into raw_events.
      4. Store hash in evidence_hashes.
      5. Record chain‑of‑custody event.
    """
    batch_id = str(uuid.uuid4())
    actor = "analyst"
    now = _now_iso()

    # ① Query the NLP agent
    agent_output = await query_nlp_agent(
        source_type=data["source_type"],
        time_start=data["time_start"],
        time_end=data["time_end"],
        target_actors=data.get("target_actors"),
        target_systems=data.get("target_systems"),
        query_text=data.get("query_text", ""),
    )

    # Accept both list-based and dict-based NLP agent responses.
    records: list[dict]
    if isinstance(agent_output, list):
        raw_records = agent_output
    elif isinstance(agent_output, dict):
        maybe_records = agent_output.get("records")
        raw_records = maybe_records if isinstance(maybe_records, list) else []
    else:
        raw_records = []

    records = []
    for rec in raw_records:
        if isinstance(rec, dict):
            records.append(rec)

    if not records:
        # No data found — record it and return
        coc_id = record_coc_event(
            case_id=case_id,
            actor=actor,
            action="NO_DATA_FOUND",
            target_artefact=f"query:{data['source_type']}",
            justification=data.get("justification", ""),
            details=data,
        )
        return {
            "import_batch_id": batch_id,
            "artefact_name": f"{data['source_type']}_logs",
            "record_count": 0,
            "byte_size": 0,
            "hash_algorithm": settings.HASH_ALGORITHM.upper(),
            "hash_value": "",
            "coc_event_id": coc_id,
            "message": "No records returned by the NLP agent for the given parameters.",
        }

    # ② Compute hash
    payload_bytes = json.dumps(records, sort_keys=True, default=str).encode("utf-8")
    hash_value = hash_records(records, settings.HASH_ALGORITHM)
    byte_size = len(payload_bytes)

    # ③ Insert into raw_events
    artefact_name = f"{data['source_type']}_{data['time_start'][:10]}_to_{data['time_end'][:10]}"

    conn = open_vault(case_id)
    try:
        with conn.transaction():
            for rec in records:
                conn.execute(
                    """
                    INSERT INTO raw_events
                        (event_id, case_id, import_batch_id, source_type,
                         timestamp, source_system, actor, action, target, detail, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        rec.get("event_id", str(uuid.uuid4())),
                        case_id,
                        batch_id,
                        rec.get("source_type", data["source_type"]),
                        rec.get("timestamp"),
                        rec.get("source_system"),
                        rec.get("actor"),
                        rec.get("action"),
                        rec.get("target"),
                        json.dumps(rec.get("detail", {})),
                        now,
                    ],
                )

            # ④ Store hash
            hash_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO evidence_hashes
                    (hash_id, case_id, import_batch_id, artefact_name, artefact_type,
                     hash_algorithm, hash_value, record_count, byte_size,
                     created_at, created_by)
                VALUES (?, ?, ?, ?, 'QUERY_RESULT', ?, ?, ?, ?, ?, ?)
                """,
                [
                    hash_id, case_id, batch_id, artefact_name,
                    settings.HASH_ALGORITHM.upper().replace("SHA", "SHA-"),
                    hash_value, len(records), byte_size,
                    now, actor,
                ],
            )
    finally:
        conn.close()

    # ⑤ Chain of custody
    coc_id = record_coc_event(
        case_id=case_id,
        actor=actor,
        action="IMPORT",
        target_artefact=artefact_name,
        justification=data.get("justification", "Evidence collection"),
        hash_after=hash_value,
        details={
            "batch_id": batch_id,
            "source_type": data["source_type"],
            "record_count": len(records),
            "byte_size": byte_size,
        },
    )

    return {
        "import_batch_id": batch_id,
        "artefact_name": artefact_name,
        "record_count": len(records),
        "byte_size": byte_size,
        "hash_algorithm": settings.HASH_ALGORITHM.upper().replace("SHA", "SHA-"),
        "hash_value": hash_value,
        "coc_event_id": coc_id,
        "message": f"Successfully imported {len(records)} records.",
    }


def list_evidence(case_id: str) -> list[dict]:
    """Return all evidence hash records for a case."""
    conn = open_vault(case_id)
    try:
        rows = conn.execute(
            """
            SELECT hash_id, case_id, import_batch_id, artefact_name, artefact_type,
                   hash_algorithm, hash_value, record_count, byte_size,
                   created_at, created_by
            FROM evidence_hashes
            WHERE case_id = ?
            ORDER BY created_at ASC
            """,
            [case_id],
        ).fetchall()
        cols = [
            "hash_id", "case_id", "import_batch_id", "artefact_name", "artefact_type",
            "hash_algorithm", "hash_value", "record_count", "byte_size",
            "created_at", "created_by",
        ]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            for k in ("created_at",):
                if d.get(k) and not isinstance(d[k], str):
                    d[k] = str(d[k])
            results.append(d)
        return results
    finally:
        conn.close()


def verify_evidence_hash(case_id: str, hash_id: str) -> dict:
    """Re-compute the hash of a stored artefact and compare."""
    conn = open_vault(case_id)
    try:
        row = conn.execute(
            "SELECT artefact_name, hash_algorithm, hash_value, import_batch_id FROM evidence_hashes WHERE hash_id = ?",
            [hash_id],
        ).fetchone()
        if not row:
            raise ValueError(f"Hash record {hash_id} not found")

        artefact_name, algo, stored_hash, import_batch_id = row

        # Re-read only raw_events from the original import batch.
        # Fallback for legacy rows that predate import_batch_id linkage.
        if import_batch_id:
            events = conn.execute(
                """
                SELECT event_id, source_type, timestamp, source_system,
                       actor, action, target, detail
                FROM raw_events
                WHERE case_id = ? AND import_batch_id = ?
                ORDER BY timestamp ASC
                """,
                [case_id, import_batch_id],
            ).fetchall()
        else:
            events = conn.execute(
                """
                SELECT event_id, source_type, timestamp, source_system,
                       actor, action, target, detail
                FROM raw_events
                WHERE case_id = ?
                ORDER BY timestamp ASC
                """,
                [case_id],
            ).fetchall()

        cols = ["event_id", "source_type", "timestamp", "source_system",
                "actor", "action", "target", "detail"]
        records = []
        for ev in events:
            d = dict(zip(cols, ev))
            for k, v in d.items():
                if v is not None and not isinstance(v, (str, int, float)):
                    d[k] = str(v)
            records.append(d)

        computed = hash_records(records, algo.lower().replace("sha-", "sha").replace("-", ""))
        match = computed == stored_hash

        # Record the verification in CoC
        record_coc_event(
            case_id=case_id,
            actor="analyst",
            action="VERIFY_HASH",
            target_artefact=artefact_name,
            justification="Integrity verification",
            hash_before=stored_hash,
            hash_after=computed,
            details={
                "match": match,
                "import_batch_id": import_batch_id,
                "legacy_scope": import_batch_id is None,
            },
        )

        return {
            "hash_id": hash_id,
            "artefact_name": artefact_name,
            "stored_hash": stored_hash,
            "computed_hash": computed,
            "match": match,
            "message": "Integrity verified — hashes match." if match else "INTEGRITY VIOLATION — hashes do NOT match!",
        }
    finally:
        conn.close()
