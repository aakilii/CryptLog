"""
Node 6: Human-in-the-Loop Commit
Staging area with preview and human overrides
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.core.logging import logger
from app.db.models import StagingArea, AuditLog, LineageAnchor, TemplateRegistry
from app.db.duckdb import get_duckdb_connection


def create_staging_entry(
    db: Session,
    audit_id: str,
    row_data: Dict[str, Any],
    lineage_anchor_id: Optional[str] = None,
    decoded_payload: Optional[Dict] = None,
    decode_trace: Optional[List] = None,
    template_id: Optional[str] = None,
    extracted_variables: Optional[Dict] = None,
    ner_tags: Optional[Dict] = None,
    normalized_timestamp: Optional[datetime | str] = None
) -> StagingArea:
    """
    Create staging area entry for human review.
    
    Args:
        db: Database session
        audit_id: Audit log ID
        row_data: Processed row data
        lineage_anchor_id: Lineage anchor ID
        decoded_payload: Decoded payload from Node 2
        decode_trace: Decode trace array
        template_id: Template ID from Node 3
        extracted_variables: Extracted variables
        ner_tags: NER tags from Node 4
        normalized_timestamp: Normalized timestamp from Node 5
    
    Returns:
        StagingArea record
    """
    # Convert datetime objects to ISO strings for JSON serialization
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    # Create a serializable copy of row_data
    serializable_data = {}
    for key, value in row_data.items():
        if isinstance(value, datetime):
            serializable_data[key] = value.isoformat()
        else:
            serializable_data[key] = value
    
    row_hash = hashlib.sha256(json.dumps(serializable_data, sort_keys=True).encode()).hexdigest()
    
    # Convert normalized_timestamp string to datetime if provided
    timestamp_dt = None
    if normalized_timestamp:
        try:
            if isinstance(normalized_timestamp, str):
                timestamp_dt = datetime.fromisoformat(normalized_timestamp.replace('Z', '+00:00'))
            elif isinstance(normalized_timestamp, datetime):
                timestamp_dt = normalized_timestamp
        except Exception as e:
            logger.warning(f"[Node6] Failed to parse timestamp {normalized_timestamp}: {e}")
    
    staging = StagingArea(
        audit_id=audit_id,
        row_hash=row_hash,
        immutable_pointer=lineage_anchor_id,
        decoded_payload=json.dumps(decoded_payload) if decoded_payload else None,
        decode_trace=json.dumps(decode_trace) if decode_trace else None,
        template_id=template_id,
        extracted_variables=json.dumps(extracted_variables) if extracted_variables else None,
        ner_tags=json.dumps(ner_tags) if ner_tags else None,
        normalized_timestamp=timestamp_dt
    )
    
    db.add(staging)
    db.commit()
    db.refresh(staging)
    
    logger.info(f"[Node6] Staging entry created: staging_id={staging.id} audit_id={audit_id}")
    
    return staging


def get_staging_preview(
    db: Session,
    staging_id: str,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Get enhanced preview of staged data for human review.
    
    Args:
        db: Database session
        staging_id: Staging area ID
        include_metadata: Include lineage, template, and audit metadata
    
    Returns:
        Enhanced preview data dictionary with all node outputs
    """
    staging = db.query(StagingArea).filter(StagingArea.id == staging_id).first()
    
    if not staging:
        raise ValueError(f"Staging entry not found: {staging_id}")
    
    # Base preview data
    preview = {
        "staging_id": staging.id,
        "audit_id": staging.audit_id,
        "row_hash": staging.row_hash,
        "status": staging.status,
        "decoded_payload": json.loads(staging.decoded_payload) if staging.decoded_payload else None,
        "decode_trace": json.loads(staging.decode_trace) if staging.decode_trace else None,
        "extracted_variables": json.loads(staging.extracted_variables) if staging.extracted_variables else None,
        "ner_tags": json.loads(staging.ner_tags) if staging.ner_tags else None,
        "normalized_timestamp": staging.normalized_timestamp.isoformat() if staging.normalized_timestamp else None,
        "human_overrides": json.loads(staging.human_overrides) if staging.human_overrides else None,
        "created_at": staging.created_at.isoformat() if staging.created_at else None,
        "immutable_pointer": staging.immutable_pointer
    }
    
    # Add metadata if requested
    if include_metadata:
        # Lineage anchor info
        if staging.immutable_pointer:
            lineage = db.query(LineageAnchor).filter(LineageAnchor.id == staging.immutable_pointer).first()
            if lineage:
                preview["lineage"] = {
                    "lineage_id": lineage.id,
                    "source_file_hash": lineage.source_file_hash,
                    "byte_offset": lineage.byte_offset,
                    "row_hash": lineage.row_hash,
                    "duckdb_row_id": lineage.duckdb_row_id
                }
        
        # Template info
        if staging.template_id:
            template = db.query(TemplateRegistry).filter(TemplateRegistry.id == staging.template_id).first()
            if template:
                preview["template"] = {
                    "template_id": template.id,
                    "template": template.template,
                    "cache_key": template.cache_key,
                    "match_count": template.match_count,
                    "last_seen": template.last_seen.isoformat() if template.last_seen else None
                }
        
        # Audit log info
        audit_log = db.query(AuditLog).filter(AuditLog.id == staging.audit_id).first()
        if audit_log:
            preview["audit"] = {
                "audit_id": audit_log.id,
                "filename": audit_log.filename,
                "sha256_hash": audit_log.sha256_hash,
                "source_ip": audit_log.source_ip,
                "upload_time": audit_log.upload_time.isoformat() if audit_log.upload_time else None
            }
        
        # Processing statistics
        preview["processing_stats"] = {
            "has_decoded_payload": staging.decoded_payload is not None,
            "has_template": staging.template_id is not None,
            "has_ner_tags": staging.ner_tags is not None,
            "has_timestamp": staging.normalized_timestamp is not None,
            "has_overrides": staging.human_overrides is not None,
            "variable_count": len(preview["extracted_variables"]) if preview["extracted_variables"] else 0,
            "ner_tag_count": sum(len(v) if isinstance(v, list) else 1 for v in preview["ner_tags"].values()) if preview["ner_tags"] else 0
        }
    
    return preview


def confirm_staging(
    db: Session,
    staging_id: str,
    human_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Confirm staging entry (pending -> confirmed).
    Does not commit to DuckDB, just marks as confirmed for review.
    
    Args:
        db: Database session
        staging_id: Staging area ID
        human_overrides: Human corrections/overrides (saved but not applied yet)
    
    Returns:
        Confirmation result
    """
    staging = db.query(StagingArea).filter(StagingArea.id == staging_id).first()
    
    if not staging:
        raise ValueError(f"Staging entry not found: {staging_id}")
    
    if staging.status == "committed":
        raise ValueError(f"Staging entry already committed: {staging_id}")
    
    # Save human overrides
    if human_overrides:
        staging.human_overrides = json.dumps(human_overrides)
    
    # Mark as confirmed
    staging.status = "confirmed"
    db.commit()
    db.refresh(staging)
    
    logger.info(f"[Node6] Staging entry confirmed: staging_id={staging_id}")
    
    return {
        "status": "confirmed",
        "staging_id": staging_id,
        "has_overrides": human_overrides is not None
    }


def reject_staging(
    db: Session,
    staging_id: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reject staging entry (mark as rejected, don't commit).
    
    Args:
        db: Database session
        staging_id: Staging area ID
        reason: Optional rejection reason
    
    Returns:
        Rejection result
    """
    staging = db.query(StagingArea).filter(StagingArea.id == staging_id).first()
    
    if not staging:
        raise ValueError(f"Staging entry not found: {staging_id}")
    
    if staging.status == "committed":
        raise ValueError(f"Cannot reject already committed entry: {staging_id}")
    
    # Mark as rejected
    staging.status = "rejected"
    
    # Store rejection reason in human_overrides
    if reason:
        overrides = json.loads(staging.human_overrides) if staging.human_overrides else {}
        overrides["_rejection_reason"] = reason
        staging.human_overrides = json.dumps(overrides)
    
    db.commit()
    db.refresh(staging)
    
    logger.info(f"[Node6] Staging entry rejected: staging_id={staging_id}, reason={reason}")
    
    return {
        "status": "rejected",
        "staging_id": staging_id,
        "reason": reason
    }


def commit_staging(
    db: Session,
    staging_id: str,
    human_overrides: Optional[Dict[str, Any]] = None,
    validate: bool = True
) -> Dict[str, Any]:
    """
    Commit staged data to DuckDB main table with human overrides.
    
    This function implements the "Confirm & Push Database" workflow:
    1. Takes final row hash (after human overrides)
    2. Writes to SQLite Audit Ledger
    3. Moves data from Staging → DuckDB Main Table
    4. Sends background signal to Phase 3
    
    Args:
        db: Database session
        staging_id: Staging area ID
        human_overrides: Human corrections/overrides (applied during commit)
        validate: Validate data before committing
    
    Returns:
        Commit result with Phase 3 signal
    """
    staging = db.query(StagingArea).filter(StagingArea.id == staging_id).first()
    
    if not staging:
        raise ValueError(f"Staging entry not found: {staging_id}")
    
    if staging.status == "committed":
        raise ValueError(f"Staging entry already committed: {staging_id}")
    
    # Validation
    if validate:
        if not staging.extracted_variables and not staging.ner_tags:
            logger.warning(f"[Node6] Staging entry has no extracted data: {staging_id}")
        
        if staging.status == "rejected":
            raise ValueError(f"Cannot commit rejected entry: {staging_id}")
    
    # Apply human overrides (merge with existing if any)
    existing_overrides = json.loads(staging.human_overrides) if staging.human_overrides else {}
    if human_overrides:
        existing_overrides.update(human_overrides)
        staging.human_overrides = json.dumps(existing_overrides)
        db.commit()
    
    # Get final row hash (after overrides)
    extracted_vars = json.loads(staging.extracted_variables) if staging.extracted_variables else {}
    ner_tags_data = json.loads(staging.ner_tags) if staging.ner_tags else {}
    
    # Apply overrides to extracted data
    if existing_overrides:
        # Remove internal fields
        clean_overrides = {k: v for k, v in existing_overrides.items() if not k.startswith("_")}
        extracted_vars.update(clean_overrides)
    
    final_data = {
        "audit_id": staging.audit_id,
        "row_hash": staging.row_hash,
        "extracted_variables": extracted_vars,
        "ner_tags": ner_tags_data,
        "normalized_timestamp": staging.normalized_timestamp.isoformat() if staging.normalized_timestamp else None,
        "human_overrides": existing_overrides
    }
    
    final_row_hash = hashlib.sha256(
        json.dumps(final_data, sort_keys=True).encode()
    ).hexdigest()
    
    # Step 1: Write Final Row Hash to SQLite Audit Ledger
    audit_log = db.query(AuditLog).filter(AuditLog.id == staging.audit_id).first()
    if audit_log:
        # Store final row hash in SQLite Audit Ledger for tamper-evident audit trail
        # This creates an immutable link between the processed row and the source file
        # We use DuckDB to store the audit row hashes table (lightweight, fast)
        try:
            conn = get_duckdb_connection()
            
            # Create audit_row_hashes table in DuckDB (acts as SQLite Audit Ledger extension)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_row_hashes (
                    staging_id VARCHAR PRIMARY KEY,
                    audit_id VARCHAR NOT NULL,
                    row_hash VARCHAR NOT NULL,
                    final_row_hash VARCHAR NOT NULL,
                    committed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Write final row hash to audit ledger
            conn.execute("""
                INSERT OR REPLACE INTO audit_row_hashes (
                    staging_id, audit_id, row_hash, final_row_hash, committed_at
                ) VALUES (?, ?, ?, ?, ?)
            """, [
                staging.id,
                staging.audit_id,
                staging.row_hash,
                final_row_hash,
                datetime.utcnow()
            ])
            
            conn.close()
            
            logger.info(
                f"[Node6] Final row hash written to SQLite Audit Ledger: "
                f"audit_id={staging.audit_id}, final_row_hash={final_row_hash[:16]}..."
            )
        except Exception as e:
            logger.error(f"[Node6] Failed to write to audit ledger: {e}")
            # Don't fail the commit if audit ledger write fails, but log it
    
    # Move to DuckDB main table
    try:
        conn = get_duckdb_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS normalized_logs (
                staging_id VARCHAR,
                audit_id VARCHAR,
                row_hash VARCHAR,
                final_row_hash VARCHAR,
                extracted_variables JSON,
                ner_tags JSON,
                normalized_timestamp TIMESTAMP,
                human_overrides JSON,
                committed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            INSERT INTO normalized_logs (
                staging_id, audit_id, row_hash, final_row_hash,
                extracted_variables, ner_tags, normalized_timestamp, human_overrides
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            staging.id,
            staging.audit_id,
            staging.row_hash,
            final_row_hash,
            staging.extracted_variables or "{}",
            staging.ner_tags or "{}",
            staging.normalized_timestamp,
            staging.human_overrides or "{}"
        ])
        
        conn.close()
        
        # Step 2: Mark as committed
        staging.status = "committed"
        db.commit()
        
        logger.info(f"[Node6] Staging entry committed: staging_id={staging_id}")
        
        # Step 3: Send Background Signal to Phase 3
        phase3_signal = _signal_phase3(
            staging_id=staging_id,
            audit_id=staging.audit_id,
            final_row_hash=final_row_hash,
            committed_at=datetime.utcnow()
        )
        
        return {
            "status": "success",
            "staging_id": staging_id,
            "final_row_hash": final_row_hash,
            "committed_at": datetime.utcnow().isoformat(),
            "has_overrides": bool(existing_overrides),
            "phase3_signal": phase3_signal
        }
    except Exception as e:
        logger.error(f"[Node6] Commit failed: {e}")
        db.rollback()
        raise


def _signal_phase3(
    staging_id: str,
    audit_id: str,
    final_row_hash: str,
    committed_at: datetime
) -> Dict[str, Any]:
    """
    Send background signal to Phase 3 after successful commit.
    
    This is a background notification that Phase 2 processing is complete
    and data is ready for Phase 3 (analytics, reporting, etc.).
    
    Args:
        staging_id: Staging entry ID
        audit_id: Audit log ID
        final_row_hash: Final row hash after human overrides
        committed_at: Commit timestamp
    
    Returns:
        Phase 3 signal metadata
    """
    signal = {
        "event": "phase2_commit_complete",
        "staging_id": staging_id,
        "audit_id": audit_id,
        "final_row_hash": final_row_hash,
        "committed_at": committed_at.isoformat(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Log the signal (in production, this could be:
    # - Sent to a message queue (RabbitMQ, Kafka, etc.)
    # - Written to a Phase 3 trigger table
    # - Sent via webhook/HTTP callback
    # - Stored in a Phase 3 notification queue
    logger.info(
        f"[Node6] Phase 3 signal sent: staging_id={staging_id}, "
        f"audit_id={audit_id}, final_row_hash={final_row_hash[:16]}..."
    )

    # Wire to Phase 3 webhook (default: same backend, mounted at /api/phase3)
    try:
        import os
        import httpx

        base_url = os.getenv("PHASE3_WEBHOOK_URL", "http://127.0.0.1:8000/api/phase3/phase2_webhook").rstrip("/")

        # Read back the committed row from DuckDB so Phase 3 gets full data
        ev_json = "{}"
        ner_json = "{}"
        norm_ts = None
        try:
            conn = get_duckdb_connection()
            row = conn.execute(
                "SELECT extracted_variables, ner_tags, normalized_timestamp "
                "FROM normalized_logs WHERE staging_id = ? LIMIT 1",
                [staging_id],
            ).fetchone()
            conn.close()
            if row:
                ev_json = row[0] if row[0] else "{}"
                ner_json = row[1] if row[1] else "{}"
                norm_ts = row[2].isoformat() if row[2] else None
        except Exception as read_exc:
            logger.warning(f"[Node6] Could not read committed row for Phase 3 enrichment: {read_exc}")

        ev = {}
        try:
            ev = json.loads(ev_json) if ev_json and ev_json != "{}" else {}
        except Exception:
            pass
        ner = {}
        try:
            ner = json.loads(ner_json) if ner_json and ner_json != "{}" else {}
        except Exception:
            pass

        user = (
            ner.get("user", [None])[0] if isinstance(ner.get("user"), list) else ner.get("user")
        ) or ev.get("user") or ev.get("username") or "unknown"
        src = ev.get("source_type") or ev.get("facility") or ""
        notes = ev.get("original") or ev.get("template") or (
            f"staging_id={staging_id} audit_id={audit_id}"
        )

        payload = {
            "Target_User": str(user),
            "Notes": str(notes),
            "Lineage": staging_id,
            "audit_id": audit_id,
            "source_type": str(src),
            "extracted_variables": ev_json,
            "ner_tags": ner_json,
            "normalized_timestamp": norm_ts,
            "row_hash": final_row_hash,
            "final_row_hash": final_row_hash,
        }
        with httpx.Client(timeout=5.0) as client:
            r = client.post(base_url, json=payload)
            r.raise_for_status()
        signal["phase3_webhook"] = {"ok": True, "url": base_url}
    except Exception as exc:
        signal["phase3_webhook"] = {"ok": False, "error": str(exc)}
    
    return signal


def query_staging(
    db: Session,
    audit_id: Optional[str] = None,
    status: Optional[str] = None,
    has_template: Optional[bool] = None,
    has_ner_tags: Optional[bool] = None,
    has_timestamp: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Query staging entries with filters.
    
    Args:
        db: Database session
        audit_id: Filter by audit ID
        status: Filter by status (pending, confirmed, committed, rejected)
        has_template: Filter by template presence
        has_ner_tags: Filter by NER tags presence
        has_timestamp: Filter by timestamp presence
        limit: Maximum results
        offset: Offset for pagination
    
    Returns:
        Query results with metadata
    """
    query = db.query(StagingArea)
    
    # Apply filters
    if audit_id:
        query = query.filter(StagingArea.audit_id == audit_id)
    
    if status:
        query = query.filter(StagingArea.status == status)
    
    if has_template is not None:
        if has_template:
            query = query.filter(StagingArea.template_id.isnot(None))
        else:
            query = query.filter(StagingArea.template_id.is_(None))
    
    if has_ner_tags is not None:
        if has_ner_tags:
            query = query.filter(StagingArea.ner_tags.isnot(None))
        else:
            query = query.filter(StagingArea.ner_tags.is_(None))
    
    if has_timestamp is not None:
        if has_timestamp:
            query = query.filter(StagingArea.normalized_timestamp.isnot(None))
        else:
            query = query.filter(StagingArea.normalized_timestamp.is_(None))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    entries = query.order_by(StagingArea.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(entries),
        "entries": [
            {
                "staging_id": e.id,
                "audit_id": e.audit_id,
                "status": e.status,
                "has_template": e.template_id is not None,
                "has_ner_tags": e.ner_tags is not None,
                "has_timestamp": e.normalized_timestamp is not None,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in entries
        ]
    }


def get_staging_statistics(
    db: Session,
    audit_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get statistics for staging entries.
    
    Args:
        db: Database session
        audit_id: Filter by audit ID (optional)
    
    Returns:
        Statistics dictionary
    """
    query = db.query(StagingArea)
    
    if audit_id:
        query = query.filter(StagingArea.audit_id == audit_id)
    
    total = query.count()
    
    # Status breakdown
    status_counts = (
        db.query(StagingArea.status, func.count(StagingArea.id))
        .group_by(StagingArea.status)
    )
    if audit_id:
        status_counts = status_counts.filter(StagingArea.audit_id == audit_id)
    
    status_breakdown = {status: count for status, count in status_counts.all()}
    
    # Feature presence
    has_template_count = query.filter(StagingArea.template_id.isnot(None)).count()
    has_ner_count = query.filter(StagingArea.ner_tags.isnot(None)).count()
    has_timestamp_count = query.filter(StagingArea.normalized_timestamp.isnot(None)).count()
    has_overrides_count = query.filter(StagingArea.human_overrides.isnot(None)).count()
    
    return {
        "total": total,
        "status_breakdown": status_breakdown,
        "feature_presence": {
            "has_template": has_template_count,
            "has_ner_tags": has_ner_count,
            "has_timestamp": has_timestamp_count,
            "has_overrides": has_overrides_count
        },
        "percentages": {
            "with_template": (has_template_count / total * 100) if total > 0 else 0,
            "with_ner_tags": (has_ner_count / total * 100) if total > 0 else 0,
            "with_timestamp": (has_timestamp_count / total * 100) if total > 0 else 0,
            "with_overrides": (has_overrides_count / total * 100) if total > 0 else 0
        }
    }

