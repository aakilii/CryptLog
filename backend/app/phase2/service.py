"""
Phase 2 Orchestration Service
Coordinates all 6 nodes in the Universal Translator pipeline
"""

import json
from pathlib import Path
from typing import Dict, Any, Generator, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import AuditLog
from app.phase2.node1_lineage import anchor_lineage, compute_row_hash, log_to_duckdb
from app.phase2.node2_deobfuscation import process_deobfuscation
from app.phase2.node3_drain3 import process_drain3
from app.phase2.node4_ner import process_ner_tagging
from app.phase2.node5_chronograph import process_timestamp_sync, extract_timestamp
from app.phase2.node6_staging import create_staging_entry, commit_staging, get_staging_preview


def _resolve_phase2_inputs(
    db: Session,
    audit_id: str,
    file_path: str,
    source_ip: Optional[str] = None,
) -> tuple:
    """Validate inputs and return (audit_log, file_path_obj, source_file_hash, source_ip)."""
    audit_log = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not audit_log:
        raise ValueError(f"Audit log not found: {audit_id}")

    source_file_hash = audit_log.sha256_hash

    if not file_path:
        from app.config import settings
        worm_dir = Path(settings.WORM_STORAGE_PATH)
        file_path = str(worm_dir / str(audit_id) / audit_log.filename)

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not source_ip:
        source_ip = audit_log.source_ip

    return audit_log, file_path_obj, source_file_hash, source_ip


def _count_lines(file_path_obj: Path) -> int:
    """Fast line count for progress reporting."""
    count = 0
    with open(file_path_obj, "rb") as f:
        for _ in f:
            count += 1
    return count


def process_file_phase2_stream(
    db: Session,
    audit_id: str,
    file_path: str,
    source_ip: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator that processes a file through the 6-node pipeline and yields
    progress events per line per node. Used by the SSE endpoint.

    Yields dicts like:
        {"type": "init", "total_lines": N, "audit_id": ..., "filename": ...}
        {"type": "node", "node": 1..6, "line": L, "total": N, "msg": "..."}
        {"type": "complete", "rows_processed": N, "staging_ids": [...]}
        {"type": "error", "message": "..."}
    """
    audit_log, file_path_obj, source_file_hash, source_ip = _resolve_phase2_inputs(
        db, audit_id, file_path, source_ip
    )

    total_lines = _count_lines(file_path_obj)
    yield {
        "type": "init",
        "total_lines": total_lines,
        "audit_id": audit_id,
        "filename": audit_log.filename,
        "file_hash": source_file_hash[:16] if source_file_hash else "",
    }

    staging_entries: list[str] = []
    byte_offset = 0
    processed_line = 0
    entity_counts: Dict[str, int] = {}
    template_set: set[str] = set()
    ts_normalized = 0
    ts_ambiguous = 0
    obfuscated_count = 0

    try:
        with open(file_path_obj, "rb") as f:
            for line_num, line_bytes in enumerate(f, start=1):
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    byte_offset += len(line_bytes)
                    continue

                processed_line += 1

                # ── Node 1: Lineage Anchoring ──
                row_hash = compute_row_hash(line)
                duckdb_row_id = log_to_duckdb(
                    row_hash=row_hash,
                    audit_id=audit_id,
                    row_data={"line_number": line_num, "content": line},
                )
                anchor = anchor_lineage(
                    db=db,
                    audit_id=audit_id,
                    source_file_hash=source_file_hash,
                    byte_offset=byte_offset,
                    row_data=line,
                    duckdb_row_id=duckdb_row_id,
                )
                yield {
                    "type": "node", "node": 1,
                    "line": processed_line, "total": total_lines,
                    "msg": f"Row hash {row_hash[:12]}... anchored at offset 0x{byte_offset:X}",
                }

                # ── Node 2: Recursive De-obfuscation ──
                deobf_result = process_deobfuscation(line)
                decoded_payload = deobf_result.get("decoded")
                decode_trace = deobf_result.get("trace", [])
                process_text = decoded_payload if decoded_payload else line
                if decoded_payload:
                    obfuscated_count += 1
                    n2_msg = f"Decoded {len(decode_trace)} layer(s) via {', '.join(t.get('decoder','?') for t in decode_trace if isinstance(t, dict))}"
                else:
                    entropy_val = deobf_result.get("entropy", 0)
                    n2_msg = f"Entropy {entropy_val:.2f} — cleartext, no decoding needed" if entropy_val else "Cleartext — no obfuscation detected"
                yield {
                    "type": "node", "node": 2,
                    "line": processed_line, "total": total_lines,
                    "msg": n2_msg,
                }

                # ── Node 3: Universal Translator (DRAIN3) ──
                drain3_result = process_drain3(db, process_text, audit_id)
                template_id = drain3_result.get("template_id")
                extracted_variables = drain3_result.get("variables", {})
                tpl = drain3_result.get("template", "")
                if tpl:
                    template_set.add(tpl)
                n_vars = len(extracted_variables) if extracted_variables else 0
                yield {
                    "type": "node", "node": 3,
                    "line": processed_line, "total": total_lines,
                    "msg": f"Template: \"{tpl[:60]}\" | {n_vars} variables extracted",
                }

                # ── Node 4: NER Tagging & Fallback Validation ──
                ner_result = process_ner_tagging(process_text, drain3_result.get("template"))
                ner_tags = ner_result.get("tags", {})
                tag_summary_parts = []
                for tag_type, tag_vals in ner_tags.items():
                    cnt = len(tag_vals) if isinstance(tag_vals, list) else (1 if tag_vals else 0)
                    entity_counts[tag_type] = entity_counts.get(tag_type, 0) + cnt
                    if cnt:
                        tag_summary_parts.append(f"{tag_type}:{cnt}")
                n4_msg = f"Tagged: {', '.join(tag_summary_parts)}" if tag_summary_parts else "No entities detected"
                if ner_result.get("neutralized"):
                    n4_msg += " | SQLi neutralized"
                yield {
                    "type": "node", "node": 4,
                    "line": processed_line, "total": total_lines,
                    "msg": n4_msg,
                }

                # ── Node 5: Chronograph (Timeline Sync) ──
                timestamp_str = extract_timestamp(line, extracted_variables)
                normalized_timestamp = None
                if timestamp_str:
                    timestamp_result = process_timestamp_sync(
                        db=db,
                        timestamp_str=timestamp_str,
                        source_ip=source_ip,
                        log_line=line,
                    )
                    normalized_timestamp = timestamp_result.get("normalized")
                    if normalized_timestamp:
                        ts_normalized += 1
                        n5_msg = f"Normalized to {normalized_timestamp}"
                    else:
                        ts_ambiguous += 1
                        n5_msg = f"Ambiguous format for \"{timestamp_str}\" — flagged"
                else:
                    ts_ambiguous += 1
                    n5_msg = "No timestamp found in line"
                yield {
                    "type": "node", "node": 5,
                    "line": processed_line, "total": total_lines,
                    "msg": n5_msg,
                }

                # ── Node 6: Create Staging Entry ──
                if extracted_variables is None:
                    extracted_variables = {}
                extracted_variables["original"] = line
                extracted_variables["line_number"] = line_num

                row_data = {
                    "line_number": line_num,
                    "original": line,
                    "decoded": decoded_payload,
                    "template": drain3_result.get("template"),
                    "variables": extracted_variables,
                    "ner_tags": ner_tags,
                    "timestamp": normalized_timestamp,
                }
                staging = create_staging_entry(
                    db=db,
                    audit_id=audit_id,
                    row_data=row_data,
                    lineage_anchor_id=anchor.id,
                    decoded_payload={"decoded": decoded_payload} if decoded_payload else None,
                    decode_trace=decode_trace,
                    template_id=template_id,
                    extracted_variables=extracted_variables,
                    ner_tags=ner_tags,
                    normalized_timestamp=normalized_timestamp,
                )
                staging_entries.append(staging.id)
                byte_offset += len(line_bytes)

                yield {
                    "type": "node", "node": 6,
                    "line": processed_line, "total": total_lines,
                    "msg": f"Staged as {staging.id[:8]}... (status: pending)",
                }

        logger.info(f"[Phase2] Processing complete: audit_id={audit_id} rows={len(staging_entries)}")
        total_entities = sum(entity_counts.values())
        yield {
            "type": "complete",
            "rows_processed": len(staging_entries),
            "staging_ids": staging_entries,
            "templates_learned": len(template_set),
            "entities_detected": total_entities,
            "entity_breakdown": entity_counts,
            "timestamps_normalized": ts_normalized,
            "timestamps_ambiguous": ts_ambiguous,
            "obfuscated_lines": obfuscated_count,
        }

    except Exception as e:
        logger.error(f"[Phase2] Processing failed: {e}")
        yield {"type": "error", "message": str(e)}


def process_file_phase2(
    db: Session,
    audit_id: str,
    file_path: str,
    source_ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process file through Phase 2 pipeline (all 6 nodes).
    Thin wrapper over the streaming generator.
    """
    result: Dict[str, Any] = {}
    for event in process_file_phase2_stream(db, audit_id, file_path, source_ip):
        if event["type"] == "complete":
            result = {
                "status": "staged",
                "staging_ids": event["staging_ids"],
                "rows_processed": event["rows_processed"],
                "preview_url": f"/api/phase2/preview/{event['staging_ids'][0]}" if event["staging_ids"] else None,
            }
        elif event["type"] == "error":
            raise RuntimeError(event["message"])
    return result


def get_staging_previews(db: Session, audit_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get previews of all staging entries for an audit.
    
    Args:
        db: Database session
        audit_id: Audit log ID
        limit: Maximum number of previews
    
    Returns:
        List of preview dictionaries
    """
    from app.db.models import StagingArea
    
    staging_entries = (
        db.query(StagingArea)
        .filter(StagingArea.audit_id == audit_id)
        .filter(StagingArea.status == "pending")
        .limit(limit)
        .all()
    )
    
    return [get_staging_preview(db, staging.id) for staging in staging_entries]


def commit_staging_batch(
    db: Session,
    audit_id: str,
    human_overrides: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Commit all pending staging entries for an audit in one batch.

    Uses bulk DuckDB inserts and a single Phase 3 webhook call to avoid
    the per-row overhead of commit_staging().
    """
    import hashlib as _hl
    import json as _json
    from datetime import datetime as _dt
    from app.db.models import StagingArea, AuditLog
    from app.db.duckdb import get_duckdb_connection

    staging_entries = (
        db.query(StagingArea)
        .filter(StagingArea.audit_id == audit_id)
        .filter(StagingArea.status == "pending")
        .all()
    )

    if not staging_entries:
        return {"status": "completed", "committed": 0, "failed": 0,
                "committed_ids": [], "failed_ids": []}

    audit_rows = []
    norm_rows = []
    committed_ids = []
    failed_ids: list[str] = []

    for staging in staging_entries:
        try:
            ev = _json.loads(staging.extracted_variables) if staging.extracted_variables else {}
            ner = _json.loads(staging.ner_tags) if staging.ner_tags else {}
            overrides_merged = _json.loads(staging.human_overrides) if staging.human_overrides else {}
            if human_overrides and staging.id in human_overrides:
                overrides_merged.update(human_overrides[staging.id])
                staging.human_overrides = _json.dumps(overrides_merged)
            clean = {k: v for k, v in overrides_merged.items() if not k.startswith("_")}
            ev.update(clean)

            final_data = {
                "audit_id": staging.audit_id, "row_hash": staging.row_hash,
                "extracted_variables": ev, "ner_tags": ner,
                "normalized_timestamp": staging.normalized_timestamp.isoformat() if staging.normalized_timestamp else None,
                "human_overrides": overrides_merged,
            }
            frh = _hl.sha256(_json.dumps(final_data, sort_keys=True).encode()).hexdigest()
            now = _dt.utcnow()

            audit_rows.append((staging.id, staging.audit_id, staging.row_hash, frh, now))
            norm_rows.append((
                staging.id, staging.audit_id, staging.row_hash, frh,
                staging.extracted_variables or "{}",
                staging.ner_tags or "{}",
                staging.normalized_timestamp,
                staging.human_overrides or "{}",
            ))

            staging.status = "committed"
            committed_ids.append(staging.id)
        except Exception as e:
            logger.error(f"[Phase2] Failed to prepare staging {staging.id}: {e}")
            failed_ids.append(staging.id)

    conn = get_duckdb_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_row_hashes (
                staging_id VARCHAR PRIMARY KEY,
                audit_id VARCHAR NOT NULL,
                row_hash VARCHAR NOT NULL,
                final_row_hash VARCHAR NOT NULL,
                committed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.executemany(
            "INSERT OR REPLACE INTO audit_row_hashes VALUES (?, ?, ?, ?, ?)",
            audit_rows,
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS normalized_logs (
                staging_id VARCHAR, audit_id VARCHAR, row_hash VARCHAR,
                final_row_hash VARCHAR, extracted_variables JSON, ner_tags JSON,
                normalized_timestamp TIMESTAMP, human_overrides JSON,
                committed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.executemany(
            "INSERT INTO normalized_logs (staging_id,audit_id,row_hash,final_row_hash,"
            "extracted_variables,ner_tags,normalized_timestamp,human_overrides) "
            "VALUES (?,?,?,?,?,?,?,?)",
            norm_rows,
        )
    finally:
        conn.close()

    db.commit()
    logger.info(f"[Phase2] Batch commit: {len(committed_ids)} committed, {len(failed_ids)} failed")

    # Send enriched per-row webhooks to Phase 3 so cold storage has real data
    try:
        import os
        import httpx

        base_url = os.getenv(
            "PHASE3_WEBHOOK_URL",
            "http://127.0.0.1:8000/api/phase3/phase2_webhook",
        ).rstrip("/")

        conn2 = get_duckdb_connection()
        try:
            rows = conn2.execute(
                "SELECT staging_id, audit_id, row_hash, final_row_hash, "
                "extracted_variables, ner_tags, normalized_timestamp "
                "FROM normalized_logs WHERE audit_id = ? "
                "ORDER BY committed_at DESC",
                [audit_id],
            ).fetchall()
        finally:
            conn2.close()

        with httpx.Client(timeout=5.0) as client:
            for r in rows:
                sid, aid, rh, frh, ev_json, ner_json, norm_ts = r

                ev = {}
                try:
                    ev = _json.loads(ev_json) if ev_json else {}
                except Exception:
                    pass
                ner = {}
                try:
                    ner = _json.loads(ner_json) if ner_json else {}
                except Exception:
                    pass

                user = (
                    ner.get("user", [None])[0] if isinstance(ner.get("user"), list) else ner.get("user")
                ) or ev.get("user") or ev.get("username") or "unknown"
                src = ev.get("source_type") or ev.get("facility") or ""
                notes = ev.get("original") or ev.get("template") or f"staging_id={sid}"

                payload = {
                    "Target_User": str(user),
                    "Notes": str(notes),
                    "Lineage": str(sid),
                    "audit_id": str(aid),
                    "source_type": str(src),
                    "extracted_variables": ev_json or "{}",
                    "ner_tags": ner_json or "{}",
                    "normalized_timestamp": norm_ts.isoformat() if norm_ts else None,
                    "row_hash": str(frh or rh or ""),
                    "final_row_hash": str(frh or ""),
                }
                try:
                    client.post(base_url, json=payload)
                except Exception:
                    pass

        logger.info(f"[Phase2] Sent {len(rows)} Phase 3 webhooks for audit {audit_id}")
    except Exception as exc:
        logger.warning(f"[Phase2] Phase 3 batch webhook failed: {exc}")

    return {
        "status": "completed",
        "committed": len(committed_ids),
        "failed": len(failed_ids),
        "committed_ids": committed_ids,
        "failed_ids": failed_ids,
    }

