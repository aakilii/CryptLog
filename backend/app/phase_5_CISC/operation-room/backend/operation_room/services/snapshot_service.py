import os
import json
import duckdb
from fastapi import HTTPException
from operation_room.config import settings
from operation_room.database import get_vault_path

def freeze_evidence(case_id: str, card_id: str, table: str, pointers: list[str]) -> str:
    """Read the explicit row hashes/data from DuckDB and save to immutable artifacts folder."""
    case_dir = settings.DATA_DIR / "cases" / case_id
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_path = artifacts_dir / f"{card_id}.json"
    vault_db = get_vault_path(case_id)
    
    if not vault_db.exists():
        raise HTTPException(404, "Vault not found")

    from operation_room.database import open_vault
    con = open_vault(case_id)
    try:
        if not pointers:
            data = []
        else:
            # Simple query to fetch explicit rows by UUID/pointers
            # Prepare placeholders dynamically since pointers could be multiple 
            placeholders = ", ".join(["?"] * len(pointers))
            
            # Make sure table doesn't have SQL injection implicitly
            safe_table = ''.join(c for c in table if c.isalnum() or c == '_')
            
            # Fetch as JSON or dict
            pk_col = "tl_event_id" if safe_table == "unified_timeline" else "id"
            query = f"SELECT * FROM {safe_table} WHERE {pk_col} IN ({placeholders})"
            # Use fetchdf() to easily convert to JSON dicts
            df = con.execute(query, pointers).fetchdf()
            # Convert timestamp or native pandas types to strings safely
            data = json.loads(df.to_json(orient='records', date_format='iso'))
            
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump({
                "card_id": card_id,
                "schema_type": safe_table,
                "data": data,
                "count": len(pointers)
            }, f, indent=2)
            
        # Return path relative to case directory or absolute, we'll store relative
        return f"artifacts/{card_id}.json"
    except Exception as e:
        import logging
        logging.error(f"Failed to freeze evidence payload: {e}")
        raise HTTPException(500, f"Snapshot Engine Error: {str(e)}")
    finally:
        con.close()
