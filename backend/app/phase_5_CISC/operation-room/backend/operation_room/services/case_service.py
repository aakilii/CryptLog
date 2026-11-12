"""
Case management service.

Handles case creation, retrieval, update and listing.
Each case gets its own DuckDB vault file under data/cases/{case_id}/.
"""

import json
import uuid
from datetime import datetime, timezone

from operation_room.database import create_vault, open_vault, vault_exists, close_vault
from operation_room.config import settings
from operation_room.services.audit_service import record_coc_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_cases() -> list[dict]:
    """Return summary data for every case."""
    cases_dir = settings.CASES_DIR
    summaries = []
    if not cases_dir.exists():
        return summaries

    for child in sorted(cases_dir.iterdir()):
        if child.is_dir() and vault_exists(child.name):
            try:
                info = get_case(child.name)
                summaries.append({
                    "case_id": info["case_id"],
                    "title": info["title"],
                    "priority": info["priority"],
                    "status": info["status"],
                    "lead_investigator": info["lead_investigator"],
                    "created_at": info["created_at"],
                    "evidence_count": info.get("evidence_count", 0),
                })
            except ValueError as e:
                # Vault exists but missing metadata or case_id doesn't match
                continue
            except Exception as e:
                # Unexpected error, skip silently
                continue
    return summaries


def create_case(data: dict) -> dict:
    """Create a new case: vault + metadata + scope + CoC event."""
    case_id = str(uuid.uuid4())
    conn = create_vault(case_id)
    now = _now_iso()

    try:
        with conn.transaction():
            # Insert case metadata
            conn.execute(
                """
                INSERT INTO case_metadata
                    (case_id, title, description, classification, priority,
                     status, lead_investigator, suspects, investigation_reason,
                     log_sources, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
                """,
                [
                    case_id,
                    data["title"],
                    data.get("description", ""),
                    data.get("classification", "UNCLASSIFIED"),
                    data.get("priority", "MEDIUM"),
                    data.get("lead_investigator", "analyst"),
                    json.dumps(data.get("suspects", [])),
                    data.get("investigation_reason", ""),
                    json.dumps(data.get("log_sources", [])),
                    now, now,
                ],
            )

            # Insert scope entries
            for entry in data.get("scope", []):
                scope_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO scope_definition
                        (scope_id, case_id, source_type, time_start, time_end,
                         target_actors, target_systems, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        scope_id, case_id,
                        entry["source_type"],
                        entry.get("time_start"),
                        entry.get("time_end"),
                        json.dumps(entry.get("target_actors", [])),
                        json.dumps(entry.get("target_systems", [])),
                        now,
                    ],
                )
    finally:
        conn.close()

    # Record chain‑of‑custody
    record_coc_event(
        case_id=case_id,
        actor=data.get("lead_investigator", "analyst"),
        action="CASE_CREATED",
        target_artefact="case_metadata",
        justification=data.get("investigation_reason", "New investigation"),
    )

    return get_case(case_id)


def get_case(case_id: str) -> dict:
    """Retrieve full case detail."""
    conn = open_vault(case_id)
    try:
        try:
            result = conn.execute(
                "SELECT * FROM case_metadata WHERE case_id = ?", [case_id]
            )
        except Exception:
            raise ValueError(f"Case {case_id} not found in vault (no case_metadata table)")
        row = result.fetchone()
        if not row:
            raise ValueError(f"Case {case_id} not found in vault")
        desc = result.description if hasattr(result, "description") else conn.description
        if not desc:
            raise ValueError(f"Case {case_id}: could not read column metadata from vault")
        cols = [d[0] for d in desc]
        case = dict(zip(cols, row))

        # Parse JSON fields
        for field in ("suspects", "log_sources"):
            val = case.get(field, "[]")
            case[field] = json.loads(val) if isinstance(val, str) else (val or [])

        # Stringify timestamps
        for field in ("created_at", "updated_at"):
            if case.get(field) and not isinstance(case[field], str):
                case[field] = str(case[field])

        # Count evidence and CoC entries (tables may not exist in older vaults)
        ev_count = 0
        coc_count = 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM evidence_hashes WHERE case_id = ?", [case_id]
            ).fetchone()
            ev_count = row[0] if row else 0
        except Exception:
            pass
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM chain_of_custody WHERE case_id = ?", [case_id]
            ).fetchone()
            coc_count = row[0] if row else 0
        except Exception:
            pass
        case["evidence_count"] = ev_count
        case["coc_count"] = coc_count

        return case
    finally:
        conn.close()


def update_case(case_id: str, data: dict) -> dict:
    """Update mutable case fields."""
    conn = open_vault(case_id)
    now = _now_iso()
    try:
        sets = []
        vals = []
        for field in ("title", "description", "classification", "priority", "status", "investigation_reason"):
            if data.get(field) is not None:
                sets.append(f"{field} = ?")
                vals.append(data[field])
        for field in ("suspects", "log_sources"):
            if data.get(field) is not None:
                sets.append(f"{field} = ?")
                vals.append(json.dumps(data[field]))
        if not sets:
            return get_case(case_id)
        sets.append("updated_at = ?")
        vals.append(now)
        vals.append(case_id)
        with conn.transaction():
            conn.execute(
                f"UPDATE case_metadata SET {', '.join(sets)} WHERE case_id = ?",
                vals,
            )
    finally:
        conn.close()

    record_coc_event(
        case_id=case_id,
        actor="analyst",
        action="CASE_UPDATED",
        target_artefact="case_metadata",
        justification="Case parameters updated",
        details=data,
    )
    return get_case(case_id)


def delete_case(case_id: str) -> None:
    """Hard delete a case and all its files from the disk."""
    import shutil
    case_dir = settings.CASES_DIR / case_id
    if not case_dir.exists():
        raise FileNotFoundError(f"Case {case_id} not found.")
    
    # Must explicitly disconnect DuckDB or Windows will block rmtree
    close_vault(case_id)
    
    try:
        shutil.rmtree(case_dir, ignore_errors=False)
    except Exception as e:
        raise ValueError(f"Failed to delete case directory: {e}")

