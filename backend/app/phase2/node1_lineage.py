"""
Node 1: Lineage Anchoring
Create immutable pointers linking processed rows to source files
"""

import hashlib
from typing import Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import LineageAnchor
from app.db.duckdb import get_duckdb_connection


def create_immutable_pointer(source_file_hash: str, byte_offset: int) -> str:
    """
    Create immutable pointer: [Source_File_Hash] + [Byte_Offset]
    
    Args:
        source_file_hash: SHA-256 hash of source file
        byte_offset: Byte offset in source file
    
    Returns:
        Immutable pointer string
    """
    return f"{source_file_hash}:{byte_offset}"


def compute_row_hash(row_data: str | bytes) -> str:
    """
    Compute SHA-256 hash of row data.
    
    Args:
        row_data: Row content as string or bytes
    
    Returns:
        SHA-256 hex digest
    """
    if isinstance(row_data, str):
        row_data = row_data.encode('utf-8')
    
    return hashlib.sha256(row_data).hexdigest()


def anchor_lineage(
    db: Session,
    audit_id: str,
    source_file_hash: str,
    byte_offset: int,
    row_data: str | bytes,
    duckdb_row_id: Optional[int] = None
) -> LineageAnchor:
    """
    Create lineage anchor for a processed row.
    
    Node 1: Lineage Anchoring
    Creates immutable pointer: [Source_File_Hash]:[Byte_Offset]
    
    Args:
        db: Database session
        audit_id: Audit log ID from Phase 1
        source_file_hash: Source file SHA-256 hash (from audit_log.sha256_hash)
        byte_offset: Byte offset in source file
        row_data: Row content (log line)
        duckdb_row_id: Optional DuckDB row ID (lightweight option)
    
    Returns:
        LineageAnchor record
    
    Payload from Phase 1:
        {
            "status": "done",
            "audit_id": "uuid",
            "sha256": "file_hash",
            "file_path": "/worm/vault/file.log",
            "source_ip": "127.0.0.1"
        }
    """
    row_hash = compute_row_hash(row_data)
    immutable_pointer = create_immutable_pointer(source_file_hash, byte_offset)
    
    # Log payload receipt for debugging
    logger.debug(
        f"[Node1] Receiving payload: "
        f"audit_id={audit_id} "
        f"source_hash={source_file_hash[:12]}... "
        f"byte_offset={byte_offset} "
        f"row_length={len(row_data) if isinstance(row_data, str) else len(str(row_data))}"
    )
    
    anchor = LineageAnchor(
        audit_id=audit_id,
        source_file_hash=source_file_hash,
        byte_offset=byte_offset,
        row_hash=row_hash,
        duckdb_row_id=duckdb_row_id
    )
    
    db.add(anchor)
    db.commit()
    db.refresh(anchor)
    
    logger.info(
        f"[Node1] ✓ Lineage anchored: "
        f"anchor_id={anchor.id} "
        f"audit_id={audit_id} "
        f"pointer={immutable_pointer[:30]}... "
        f"row_hash={row_hash[:12]}... "
        f"byte_offset={byte_offset}"
    )
    
    return anchor


def log_to_duckdb(row_hash: str, audit_id: str, row_data: dict) -> Optional[int]:
    """
    Log row hash to DuckDB (lightweight option).
    
    Args:
        row_hash: SHA-256 hash of row
        audit_id: Audit log ID
        row_data: Row data dictionary
    
    Returns:
        DuckDB row ID if successful
    """
    try:
        conn = get_duckdb_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lineage_row_hashes (
                row_hash VARCHAR PRIMARY KEY,
                audit_id VARCHAR,
                row_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        import json
        row_data_json = json.dumps(row_data)
        
        conn.execute("""
            INSERT OR REPLACE INTO lineage_row_hashes (row_hash, audit_id, row_data)
            VALUES (?, ?, ?)
        """, [row_hash, audit_id, row_data_json])
        
        result = conn.execute("""
            SELECT rowid FROM lineage_row_hashes WHERE row_hash = ?
        """, [row_hash]).fetchone()
        
        conn.close()
        
        if result:
            return result[0]
    except Exception as e:
        logger.warning(f"[Node1] DuckDB logging failed: {e}")
    
    return None

