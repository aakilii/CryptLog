"""
Report Studio v2 — Document Service.

Provides document CRUD, versioning, and integrity tracking.
Uses the case DuckDB vault for storage (Postgres migration in later phase).
All writes are accompanied by SHA-256 hashes and CoC events.
"""

import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from operation_room.database import open_vault, create_vault, vault_exists
from operation_room.services.audit_service import record_coc_event

logger = logging.getLogger(__name__)

# ── Schema DDL (added to case vault) ────────────────────────────────────
STUDIO_V2_DDL = """
-- Report Studio v2 documents
CREATE TABLE IF NOT EXISTS studio_documents (
    doc_id          VARCHAR PRIMARY KEY,
    case_id         VARCHAR NOT NULL,
    title           VARCHAR NOT NULL DEFAULT 'Untitled Report',
    template        VARCHAR DEFAULT 'blank',
    ast_json        VARCHAR NOT NULL,  -- TipTap JSON AST
    content_hash    VARCHAR NOT NULL,
    status          VARCHAR DEFAULT 'DRAFT',
    created_by      VARCHAR DEFAULT 'investigator',
    created_at      TIMESTAMP DEFAULT current_timestamp,
    updated_at      TIMESTAMP DEFAULT current_timestamp
);

-- Document version snapshots
CREATE TABLE IF NOT EXISTS doc_versions (
    version_id      VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    version_num     INTEGER NOT NULL,
    ast_json        VARCHAR NOT NULL,
    content_hash    VARCHAR NOT NULL,
    change_summary  VARCHAR,
    created_by      VARCHAR DEFAULT 'investigator',
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- Render artifacts (images, SVGs, chart renders)
CREATE TABLE IF NOT EXISTS doc_artifacts (
    artifact_id     VARCHAR PRIMARY KEY,
    doc_id          VARCHAR,
    case_id         VARCHAR,
    artifact_type   VARCHAR NOT NULL,
    mime_type       VARCHAR,
    file_path       VARCHAR NOT NULL,
    file_size       BIGINT,
    content_hash    VARCHAR NOT NULL,
    created_at      TIMESTAMP DEFAULT current_timestamp
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn):
    """Create studio v2 tables if they don't exist."""
    for stmt in STUDIO_V2_DDL.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except Exception:
                pass


def _hash_ast(ast_json: str) -> str:
    """Canonicalise and hash an AST JSON string (RFC 8785 + SHA-256)."""
    try:
        obj = json.loads(ast_json)
    except Exception:
        obj = {"raw": ast_json}
    canonical = json.dumps(obj, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str).encode('utf-8')
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ═══════════════════════════════════════════════════════════════
# Document CRUD
# ═══════════════════════════════════════════════════════════════

def create_document(case_id: str, title: str = "Untitled Report",
                    template: str = "blank", initial_ast: dict = None,
                    created_by: str = "investigator") -> dict:
    """Create a new studio document."""
    doc_id = str(uuid.uuid4())
    now = _now()

    if initial_ast is None:
        initial_ast = _default_ast(title)

    ast_str = json.dumps(initial_ast)
    content_hash = _hash_ast(ast_str)

    conn = create_vault(case_id)  # auto-create vault for new cases
    try:
        _ensure_schema(conn)
        conn.execute("""
            INSERT INTO studio_documents (doc_id, case_id, title, template, ast_json, content_hash, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
        """, [doc_id, case_id, title, template, ast_str, content_hash, created_by, now, now])

        # Save initial version
        conn.execute("""
            INSERT INTO doc_versions (version_id, doc_id, version_num, ast_json, content_hash, change_summary, created_by, created_at)
            VALUES (?, ?, 1, ?, ?, 'Initial creation', ?, ?)
        """, [str(uuid.uuid4()), doc_id, ast_str, content_hash, created_by, now])

        # CoC event
        record_coc_event(
            case_id=case_id, actor=created_by,
            action="DOCUMENT_CREATED",
            target_artefact=f"studio_doc:{doc_id}",
            justification=f"Created report: {title}",
            hash_after=content_hash,
            details={"doc_id": doc_id, "title": title, "template": template}
        )

        logger.info(f"[StudioV2] Created document {doc_id}: {title}")
        return {
            "doc_id": doc_id, "case_id": case_id, "title": title,
            "template": template, "content_hash": content_hash,
            "status": "DRAFT", "created_at": now,
        }
    finally:
        conn.close()


def get_document(case_id: str, doc_id: str) -> Optional[dict]:
    """Get a document with its full AST."""
    if not vault_exists(case_id):
        return None
    conn = open_vault(case_id)
    try:
        _ensure_schema(conn)
        row = conn.execute("""
            SELECT doc_id, case_id, title, template, ast_json, content_hash, status, created_by, created_at, updated_at
            FROM studio_documents WHERE doc_id = ?
        """, [doc_id]).fetchone()
        if not row:
            return None

        version_count = conn.execute(
            "SELECT COUNT(*) FROM doc_versions WHERE doc_id = ?", [doc_id]
        ).fetchone()[0]

        return {
            "doc_id": row[0], "case_id": row[1], "title": row[2],
            "template": row[3], "ast": json.loads(row[4]),
            "content_hash": row[5], "status": row[6],
            "created_by": row[7],
            "created_at": str(row[8]) if row[8] else None,
            "updated_at": str(row[9]) if row[9] else None,
            "version_count": version_count,
        }
    finally:
        conn.close()


def update_document(case_id: str, doc_id: str, ast: dict,
                    title: str = None, save_version: bool = True,
                    change_summary: str = None,
                    actor: str = "investigator") -> dict:
    """Update a document's AST. Optionally saves a version snapshot."""
    now = _now()
    ast_str = json.dumps(ast)
    new_hash = _hash_ast(ast_str)

    conn = create_vault(case_id)  # auto-create if missing (offline → online save)
    try:
        _ensure_schema(conn)

        # Get previous hash
        prev = conn.execute("SELECT content_hash, title FROM studio_documents WHERE doc_id=?", [doc_id]).fetchone()
        if not prev:
            return {"error": "Document not found"}

        old_hash = prev[0]
        doc_title = title or prev[1]

        # Update document
        conn.execute("""
            UPDATE studio_documents SET ast_json=?, content_hash=?, title=?, updated_at=? WHERE doc_id=?
        """, [ast_str, new_hash, doc_title, now, doc_id])

        # Save version snapshot if requested
        version_num = None
        if save_version and old_hash != new_hash:
            vcount = conn.execute("SELECT COALESCE(MAX(version_num),0) FROM doc_versions WHERE doc_id=?", [doc_id]).fetchone()[0]
            version_num = vcount + 1
            conn.execute("""
                INSERT INTO doc_versions (version_id, doc_id, version_num, ast_json, content_hash, change_summary, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [str(uuid.uuid4()), doc_id, version_num, ast_str, new_hash,
                  change_summary or f"Version {version_num}", actor, now])

        # CoC event
        if old_hash != new_hash:
            record_coc_event(
                case_id=case_id, actor=actor,
                action="DOCUMENT_UPDATED",
                target_artefact=f"studio_doc:{doc_id}",
                justification=change_summary or "Document saved",
                hash_after=new_hash,
                details={"doc_id": doc_id, "version": version_num, "prev_hash": old_hash}
            )

        return {
            "doc_id": doc_id, "content_hash": new_hash,
            "version_num": version_num, "changed": old_hash != new_hash,
            "updated_at": now,
        }
    finally:
        conn.close()


def list_documents(case_id: str) -> list[dict]:
    """List all documents for a case.  Returns empty list if no vault exists."""
    if not vault_exists(case_id):
        return []
    conn = open_vault(case_id)
    try:
        _ensure_schema(conn)
        rows = conn.execute("""
            SELECT doc_id, title, template, status, content_hash, created_by, created_at, updated_at
            FROM studio_documents WHERE case_id=? ORDER BY updated_at DESC
        """, [case_id]).fetchall()
        return [{
            "doc_id": r[0], "title": r[1], "template": r[2],
            "status": r[3], "content_hash": r[4], "created_by": r[5],
            "created_at": str(r[6]) if r[6] else None,
            "updated_at": str(r[7]) if r[7] else None,
        } for r in rows]
    finally:
        conn.close()


def delete_document(case_id: str, doc_id: str, actor: str = "investigator") -> dict:
    """Soft-delete (mark as ARCHIVED)."""
    conn = open_vault(case_id)
    try:
        _ensure_schema(conn)
        conn.execute("UPDATE studio_documents SET status='ARCHIVED', updated_at=? WHERE doc_id=?", [_now(), doc_id])
        record_coc_event(case_id=case_id, actor=actor, action="DOCUMENT_ARCHIVED",
                         target_artefact=f"studio_doc:{doc_id}", justification="Document archived")
        return {"doc_id": doc_id, "status": "ARCHIVED"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Version Management
# ═══════════════════════════════════════════════════════════════

def list_versions(case_id: str, doc_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        _ensure_schema(conn)
        rows = conn.execute("""
            SELECT version_id, version_num, content_hash, change_summary, created_by, created_at
            FROM doc_versions WHERE doc_id=? ORDER BY version_num DESC
        """, [doc_id]).fetchall()
        return [{
            "version_id": r[0], "version_num": r[1], "content_hash": r[2],
            "change_summary": r[3], "created_by": r[4],
            "created_at": str(r[5]) if r[5] else None,
        } for r in rows]
    finally:
        conn.close()


def get_version(case_id: str, doc_id: str, version_id: str) -> Optional[dict]:
    conn = open_vault(case_id)
    try:
        _ensure_schema(conn)
        row = conn.execute("""
            SELECT version_id, version_num, ast_json, content_hash, change_summary, created_by, created_at
            FROM doc_versions WHERE version_id=? AND doc_id=?
        """, [version_id, doc_id]).fetchone()
        if not row:
            return None
        return {
            "version_id": row[0], "version_num": row[1],
            "ast": json.loads(row[2]), "content_hash": row[3],
            "change_summary": row[4], "created_by": row[5],
            "created_at": str(row[6]) if row[6] else None,
        }
    finally:
        conn.close()


def restore_version(case_id: str, doc_id: str, version_id: str,
                    actor: str = "investigator") -> dict:
    """Restore a document to a previous version."""
    version = get_version(case_id, doc_id, version_id)
    if not version:
        return {"error": "Version not found"}
    return update_document(
        case_id, doc_id, version["ast"],
        change_summary=f"Restored to version {version['version_num']}",
        actor=actor,
    )


# ═══════════════════════════════════════════════════════════════
# Default AST Templates
# ═══════════════════════════════════════════════════════════════

def _default_ast(title: str = "Untitled Report") -> dict:
    """Generate a default TipTap-compatible AST."""
    return {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": title}]
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Begin writing your forensic report here..."}]
            }
        ]
    }


REPORT_TEMPLATES = {
    "blank": {
        "title": "Blank Report",
        "ast": lambda t: _default_ast(t),
    },
    "technical": {
        "title": "Technical Incident Report",
        "ast": lambda t: {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": t}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Executive Summary"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Summarise the incident, severity, and key findings."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Case Overview & Scope"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Describe the systems investigated, time range, and log sources."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Event Timeline"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Chronicle the sequence of events with timestamps."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Anomaly Detection Findings"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Detail the anomalies detected plus SHAP feature contributions."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Attack Chain & Correlation"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Map the attack path using entity relationships and MITRE ATT&CK."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Data Access Analysis"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Classify CRUD operations and flag sensitive data exposure."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Network & Exfiltration"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Analyse network flows and identify data exfiltration."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Depth & Impact Assessment"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Score penetration across account, system, data, and control dimensions."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Remediation & Recommendations"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "List prioritised remediation actions."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Chain of Custody & Integrity"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Document evidence handling and hash verification status."}]},
            ]
        },
    },
    "executive": {
        "title": "Executive Summary Report",
        "ast": lambda t: {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": t}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Executive Summary"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "High-level overview for leadership."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Business Impact"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Financial, operational, and reputational impact."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Key Findings"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Top 5 findings from the investigation."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Recommended Actions"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Strategic action items for leadership."}]},
            ]
        },
    },
    "regulatory": {
        "title": "Regulatory Compliance Report",
        "ast": lambda t: {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": t}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Summary of Incident"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Compliance-focused incident summary."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Personal Data Affected"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Detail personal data exposure per regulations."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Incident Timeline"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Regulatory-format timeline of events."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Impact Assessment"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Regulated impact metrics."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Containment & Remediation"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Steps taken and planned."}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Evidence Integrity"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Hash verification and evidence handling."}]},
            ]
        },
    },
}


def get_template_ast(template: str, title: str) -> dict:
    """Generate an AST from a template."""
    t = REPORT_TEMPLATES.get(template, REPORT_TEMPLATES["blank"])
    return t["ast"](title)


def list_templates() -> list[dict]:
    return [{"id": k, "title": v["title"]} for k, v in REPORT_TEMPLATES.items()]
