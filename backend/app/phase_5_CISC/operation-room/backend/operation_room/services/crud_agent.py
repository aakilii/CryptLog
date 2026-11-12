"""
CRUD Analysis Agent Service
Provides data access pattern analysis, sensitivity scoring, and privilege detection.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from operation_room.database import open_vault
from operation_room.config import settings

logger = logging.getLogger(__name__)


def _get_table_names(conn) -> List[str]:
    """Get table names using DuckDB SHOW TABLES."""
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        return [t[0] for t in tables]
    except:
        return []


def run_crud_analysis(
    case_id: str,
    source_filters: List[str] = None,
    sensitivity_threshold: str = "LOW",
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute CRUD data access analysis."""
    run_id = f"crud-{uuid.uuid4().hex[:8]}"
    
    conn = open_vault(case_id)
    try:
        # Check for crud_events, unified_timeline, or timeline table
        table_names = _get_table_names(conn)
        
        if 'crud_events' in table_names:
            table = 'crud_events'
        elif 'unified_timeline' in table_names:
            table = 'unified_timeline'
        elif 'timeline' in table_names:
            table = 'timeline'
        else:
            return {
                "run_id": run_id,
                "status": "completed",
                "message": "No CRUD data found. Import data access logs first.",
                "total_events": 0,
                "high_risk_events": 0
            }
        
        # Get event statistics
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
        # Try to count high-risk operations
        try:
            if table == 'crud_events':
                high_risk = conn.execute("""
                SELECT COUNT(*) FROM crud_events 
                WHERE operation IN ('DELETE', 'UPDATE', 'DROP', 'TRUNCATE')
                OR sensitivity IN ('HIGH', 'CRITICAL')
                """).fetchone()[0]
            else:
                high_risk = conn.execute(f"""
                SELECT COUNT(*) FROM {table} 
                WHERE action IN ('DELETE', 'UPDATE', 'DROP', 'TRUNCATE', 'modify', 'delete', 'EXPORT', 'FILE_WRITE')
                OR severity IN ('HIGH', 'CRITICAL')
                """).fetchone()[0]
        except:
            high_risk = 0
        
        # Store run info
        _ensure_crud_runs_table(conn)
        conn.execute("""
            INSERT INTO crud_runs (run_id, started_at, completed_at, total_events, high_risk_count, crud_counts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [run_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), total, high_risk, "{}"])
        
        return {
            "run_id": run_id,
            "status": "completed",
            "total_events": total,
            "high_risk_events": high_risk,
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        conn.close()


def _ensure_crud_runs_table(conn):
    """Ensure crud_runs table exists."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crud_runs (
                run_id VARCHAR PRIMARY KEY,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                total_events INT DEFAULT 0,
                high_risk_count INT DEFAULT 0,
                crud_counts VARCHAR DEFAULT '{}'
            )
        """)
    except Exception as e:
        logger.warning(f"Error creating crud_runs table: {e}")


def get_crud_events(
    case_id: str,
    run_id: Optional[str] = None,
    high_risk_only: bool = False,
    sensitivity: Optional[str] = None,
    crud_type: Optional[str] = None,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Get CRUD event records."""
    conn = open_vault(case_id)
    try:
        # Determine table
        table_names = _get_table_names(conn)
        
        if 'crud_events' in table_names:
            table = 'crud_events'
        elif 'unified_timeline' in table_names:
            table = 'unified_timeline'
        elif 'timeline' in table_names:
            table = 'timeline'
        else:
            return []
        
        where_clauses = ["1=1"]
        
        if high_risk_only:
            if table == 'crud_events':
                where_clauses.append("(crud_type IN ('DELETE', 'UPDATE', 'DROP') OR sensitivity IN ('HIGH', 'CRITICAL') OR is_high_risk = true)")
            else:
                where_clauses.append("(action IN ('DELETE', 'UPDATE', 'DROP', 'delete', 'modify', 'EXPORT', 'FILE_WRITE') OR severity IN ('HIGH', 'CRITICAL'))")
        
        if sensitivity and table == 'crud_events':
            where_clauses.append(f"sensitivity = '{sensitivity}'")
        elif sensitivity and table in ('unified_timeline', 'timeline'):
            where_clauses.append(f"severity = '{sensitivity}'")
        
        if crud_type:
            if table == 'crud_events':
                where_clauses.append(f"crud_type = '{crud_type}'")
            else:
                where_clauses.append(f"action = '{crud_type}'")
        
        # Determine timestamp column based on table
        if table == 'crud_events':
            ts_col = 'normalised_ts'
        elif table == 'unified_timeline':
            ts_col = 'normalised_ts'
        else:  # timeline table
            ts_col = 'timestamp'
        
        query = f"""
        SELECT * FROM {table}
        WHERE {" AND ".join(where_clauses)}
        ORDER BY {ts_col} DESC
        LIMIT {limit}
        """
        
        results = conn.execute(query).fetchall()
        columns = [d[0] for d in conn.description] if conn.description else []
        
        return [dict(zip(columns, row)) for row in results]
    except Exception as e:
        logger.error(f"Error getting CRUD events: {e}")
        return []
    finally:
        conn.close()


def get_crud_summary(case_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get CRUD analysis summary."""
    conn = open_vault(case_id)
    try:
        table_names = _get_table_names(conn)
        
        if 'crud_events' in table_names:
            table = 'crud_events'
        elif 'unified_timeline' in table_names:
            table = 'unified_timeline'
        elif 'timeline' in table_names:
            table = 'timeline'
        else:
            return {"total": 0, "by_operation": {}, "by_sensitivity": {}}
        
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
        # Operation breakdown - use crud_type for crud_events, action for timeline tables
        if table == 'crud_events':
            op_col = 'crud_type'
        else:
            op_col = 'action'
        
        try:
            ops = conn.execute(f"SELECT {op_col}, COUNT(*) FROM {table} GROUP BY {op_col} ORDER BY 2 DESC").fetchall()
            by_operation = {str(row[0]): row[1] for row in ops if row[0]}
        except:
            by_operation = {}
        
        # Sensitivity/severity breakdown
        try:
            sev_col = 'sensitivity' if table == 'crud_events' else 'severity'
            sevs = conn.execute(f"SELECT {sev_col}, COUNT(*) FROM {table} WHERE {sev_col} IS NOT NULL GROUP BY {sev_col}").fetchall()
            by_sensitivity = {str(row[0]): row[1] for row in sevs if row[0]}
        except:
            by_sensitivity = {}
        
        return {
            "total": total,
            "by_operation": by_operation,
            "by_sensitivity": by_sensitivity
        }
    finally:
        conn.close()


def get_crud_runs(case_id: str) -> List[Dict[str, Any]]:
    """List past CRUD analysis runs."""
    return []


def get_crud_search(
    case_id: str,
    payload: Dict[str, Any],
    limit: int = 500,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Search CRUD events with filters."""
    return get_crud_events(case_id, limit=limit)


def get_crud_stats_search(
    case_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Get CRUD event statistics."""
    return get_crud_summary(case_id)


def get_crud_distinct(case_id: str, field_name: str) -> List[str]:
    """Get distinct values for a field."""
    allowed_fields = ['operation', 'action', 'user', 'actor', 'target', 'sensitivity', 'crud_type']
    if field_name not in allowed_fields:
        raise ValueError(f"Field {field_name} not allowed")
    
    conn = open_vault(case_id)
    try:
        table_names = _get_table_names(conn)
        
        if 'crud_events' in table_names:
            table = 'crud_events'
        elif 'unified_timeline' in table_names:
            table = 'unified_timeline'
        elif 'timeline' in table_names:
            table = 'timeline'
        else:
            return []
        
        # Map field name based on table
        actual_field = field_name
        if table == 'crud_events':
            if field_name == 'operation':
                actual_field = 'crud_type'
            elif field_name == 'target':
                actual_field = 'target_object'
        elif table in ('unified_timeline', 'timeline'):
            if field_name == 'operation':
                actual_field = 'action'
        
        try:
            results = conn.execute(f"SELECT DISTINCT {actual_field} FROM {table} WHERE {actual_field} IS NOT NULL LIMIT 1000").fetchall()
            return [str(r[0]) for r in results]
        except:
            return []
    finally:
        conn.close()
