"""
Version Diff Service — Phase 3.

Provides AST-level diff between document versions,
comment management, and collaboration session tracking.
"""

import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════
# AST Diff Engine
# ═══════════════════════════════════════════════════════════════

def _flatten_text(ast: dict) -> list[str]:
    """Flatten an AST into text lines for diff comparison."""
    lines = []

    def walk(node, depth=0):
        if not node:
            return
        ntype = node.get("type", "")
        attrs = node.get("attrs", {})

        if ntype == "heading":
            level = attrs.get("level", 1)
            text = _extract_text(node)
            lines.append(f"{'#' * level} {text}")
        elif ntype == "paragraph":
            text = _extract_text(node)
            if text.strip():
                lines.append(text)
            else:
                lines.append("")
        elif ntype == "bulletList":
            for item in node.get("content", []):
                text = _extract_text(item)
                lines.append(f"• {text}")
        elif ntype == "orderedList":
            for i, item in enumerate(node.get("content", []), 1):
                text = _extract_text(item)
                lines.append(f"{i}. {text}")
        elif ntype == "codeBlock":
            text = _extract_text(node)
            lines.append(f"```\n{text}\n```")
        elif ntype == "blockquote":
            text = _extract_text(node)
            lines.append(f"> {text}")
        elif ntype == "table":
            lines.append("[TABLE]")
        elif ntype == "horizontalRule":
            lines.append("---")
        elif ntype == "doc":
            for child in node.get("content", []):
                walk(child, depth)
        else:
            for child in node.get("content", []):
                walk(child, depth + 1)

    walk(ast)
    return lines


def _extract_text(node: dict) -> str:
    """Extract plain text from an AST node."""
    if not node:
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = []
    for child in node.get("content", []):
        parts.append(_extract_text(child))
    return "".join(parts)


def compute_diff(version_a_ast: dict, version_b_ast: dict) -> dict:
    """Compute a line-level diff between two AST versions."""
    lines_a = _flatten_text(version_a_ast)
    lines_b = _flatten_text(version_b_ast)

    # Simple LCS-based diff
    changes = []
    i, j = 0, 0
    while i < len(lines_a) or j < len(lines_b):
        if i < len(lines_a) and j < len(lines_b) and lines_a[i] == lines_b[j]:
            changes.append({"type": "equal", "content": lines_a[i]})
            i += 1
            j += 1
        elif j < len(lines_b) and (i >= len(lines_a) or lines_a[i] != lines_b[j]):
            changes.append({"type": "added", "content": lines_b[j]})
            j += 1
        else:
            changes.append({"type": "removed", "content": lines_a[i]})
            i += 1

    stats = {
        "added": sum(1 for c in changes if c["type"] == "added"),
        "removed": sum(1 for c in changes if c["type"] == "removed"),
        "unchanged": sum(1 for c in changes if c["type"] == "equal"),
    }

    return {"changes": changes, "stats": stats}


def diff_versions(case_id: str, doc_id: str,
                  version_a_id: str, version_b_id: str) -> dict:
    """Diff two saved document versions."""
    conn = open_vault(case_id)
    try:
        row_a = conn.execute(
            "SELECT ast_json, version_num FROM doc_versions WHERE version_id=? AND doc_id=?",
            [version_a_id, doc_id]
        ).fetchone()
        row_b = conn.execute(
            "SELECT ast_json, version_num FROM doc_versions WHERE version_id=? AND doc_id=?",
            [version_b_id, doc_id]
        ).fetchone()

        if not row_a or not row_b:
            return {"error": "Version not found"}

        ast_a = json.loads(row_a[0])
        ast_b = json.loads(row_b[0])
        diff = compute_diff(ast_a, ast_b)

        return {
            "doc_id": doc_id,
            "version_a": {"id": version_a_id, "num": row_a[1]},
            "version_b": {"id": version_b_id, "num": row_b[1]},
            **diff,
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Comments System
# ═══════════════════════════════════════════════════════════════

COMMENTS_DDL = """
CREATE TABLE IF NOT EXISTS doc_comments (
    comment_id   VARCHAR PRIMARY KEY,
    doc_id       VARCHAR NOT NULL,
    parent_id    VARCHAR,
    author       VARCHAR DEFAULT 'investigator',
    content      VARCHAR NOT NULL,
    anchor_from  INTEGER,
    anchor_to    INTEGER,
    anchor_text  VARCHAR,
    status       VARCHAR DEFAULT 'open',
    created_at   TIMESTAMP DEFAULT current_timestamp,
    resolved_at  TIMESTAMP
);
"""


def _ensure_comments_schema(conn):
    try:
        conn.execute(COMMENTS_DDL)
    except Exception:
        pass


def add_comment(case_id: str, doc_id: str, content: str,
                author: str = "investigator",
                anchor_from: int = None, anchor_to: int = None,
                anchor_text: str = None, parent_id: str = None) -> dict:
    """Add a comment or reply to a document."""
    comment_id = str(uuid.uuid4())
    now = _now()
    conn = open_vault(case_id)
    try:
        _ensure_comments_schema(conn)
        conn.execute("""
            INSERT INTO doc_comments (comment_id, doc_id, parent_id, author, content,
                                      anchor_from, anchor_to, anchor_text, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """, [comment_id, doc_id, parent_id, author, content,
              anchor_from, anchor_to, anchor_text, now])
        return {
            "comment_id": comment_id, "doc_id": doc_id,
            "author": author, "content": content, "status": "open",
            "created_at": now,
        }
    finally:
        conn.close()


def list_comments(case_id: str, doc_id: str) -> list[dict]:
    """List all comments for a document (threaded)."""
    conn = open_vault(case_id)
    try:
        _ensure_comments_schema(conn)
        rows = conn.execute("""
            SELECT comment_id, doc_id, parent_id, author, content,
                   anchor_from, anchor_to, anchor_text, status, created_at, resolved_at
            FROM doc_comments WHERE doc_id=? ORDER BY created_at ASC
        """, [doc_id]).fetchall()

        comments = []
        for r in rows:
            comments.append({
                "comment_id": r[0], "doc_id": r[1], "parent_id": r[2],
                "author": r[3], "content": r[4],
                "anchor_from": r[5], "anchor_to": r[6], "anchor_text": r[7],
                "status": r[8],
                "created_at": str(r[9]) if r[9] else None,
                "resolved_at": str(r[10]) if r[10] else None,
            })
        return comments
    finally:
        conn.close()


def resolve_comment(case_id: str, doc_id: str, comment_id: str) -> dict:
    """Resolve a comment."""
    conn = open_vault(case_id)
    try:
        _ensure_comments_schema(conn)
        conn.execute(
            "UPDATE doc_comments SET status='resolved', resolved_at=? WHERE comment_id=? AND doc_id=?",
            [_now(), comment_id, doc_id]
        )
        return {"comment_id": comment_id, "status": "resolved"}
    finally:
        conn.close()


def delete_comment(case_id: str, doc_id: str, comment_id: str) -> dict:
    """Delete a comment."""
    conn = open_vault(case_id)
    try:
        _ensure_comments_schema(conn)
        conn.execute("DELETE FROM doc_comments WHERE comment_id=? AND doc_id=?",
                     [comment_id, doc_id])
        return {"comment_id": comment_id, "deleted": True}
    finally:
        conn.close()
