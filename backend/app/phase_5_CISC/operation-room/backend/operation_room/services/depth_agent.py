"""
Depth Analysis Agent Service
Provides impact assessment, scope analysis, and damage calculations.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from operation_room.database import open_vault
from operation_room.config import settings

logger = logging.getLogger(__name__)


def run_depth_analysis(
    case_id: str,
    weights: Dict[str, float] = None,
    llm_provider: str = "ollama",
    source_filters: List[str] = None,
    focus_entities: List[str] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute depth/impact analysis."""
    run_id = f"depth-{uuid.uuid4().hex[:8]}"
    
    # Default weights if not provided
    if weights is None:
        weights = {"account": 0.25, "system": 0.25, "data": 0.30, "control": 0.20}
    
    conn = open_vault(case_id)
    try:
        # Get entity counts from various tables using SHOW TABLES (DuckDB compatible)
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        metrics = {
            "affected_users": 0,
            "affected_systems": 0,
            "affected_files": 0,
            "total_events": 0
        }
        
        # Count from unified_timeline if exists
        if 'unified_timeline' in table_names:
            try:
                metrics["total_events"] = conn.execute("SELECT COUNT(*) FROM unified_timeline").fetchone()[0]
                metrics["affected_users"] = conn.execute("SELECT COUNT(DISTINCT actor) FROM unified_timeline WHERE actor IS NOT NULL").fetchone()[0]
                metrics["affected_systems"] = conn.execute("SELECT COUNT(DISTINCT source_system) FROM unified_timeline WHERE source_system IS NOT NULL").fetchone()[0]
                metrics["affected_files"] = conn.execute("SELECT COUNT(DISTINCT target) FROM unified_timeline WHERE target IS NOT NULL").fetchone()[0]
            except Exception as e:
                logger.warning(f"Error counting unified_timeline metrics: {e}")
        # Fallback to timeline
        elif 'timeline' in table_names:
            try:
                metrics["total_events"] = conn.execute("SELECT COUNT(*) FROM timeline").fetchone()[0]
                metrics["affected_users"] = conn.execute("SELECT COUNT(DISTINCT actor) FROM timeline WHERE actor IS NOT NULL").fetchone()[0]
                metrics["affected_systems"] = conn.execute("SELECT COUNT(DISTINCT target) FROM timeline WHERE target IS NOT NULL").fetchone()[0]
            except Exception as e:
                logger.warning(f"Error counting timeline metrics: {e}")
        
        # Count from raw_events if timeline is empty
        if metrics["total_events"] == 0 and 'raw_events' in table_names:
            try:
                metrics["total_events"] = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
            except:
                pass
        
        # Calculate dimension scores
        dimension_scores = _calculate_dimension_scores(metrics, weights)
        impact_score = _calculate_impact_score(metrics, weights)
        
        # Store run in database
        _ensure_depth_runs_table(conn)
        conn.execute("""
            INSERT INTO depth_runs (run_id, started_at, completed_at, account_depth, system_depth, data_depth, control_depth, overall_severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            run_id, 
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            dimension_scores.get("account", 0),
            dimension_scores.get("system", 0),
            dimension_scores.get("data", 0),
            dimension_scores.get("control", 0),
            impact_score["overall"]
        ])
        
        return {
            "run_id": run_id,
            "status": "completed",
            "metrics": metrics,
            "dimensions": dimension_scores,
            "impact_score": impact_score,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    finally:
        conn.close()


def _ensure_depth_runs_table(conn):
    """Ensure depth_runs table exists with proper schema."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS depth_runs (
                run_id VARCHAR PRIMARY KEY,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                account_depth FLOAT DEFAULT 0,
                system_depth FLOAT DEFAULT 0,
                data_depth FLOAT DEFAULT 0,
                control_depth FLOAT DEFAULT 0,
                overall_severity FLOAT DEFAULT 0
            )
        """)
    except Exception as e:
        logger.warning(f"Error creating depth_runs table: {e}")


def _calculate_dimension_scores(metrics: Dict[str, int], weights: Dict[str, float]) -> Dict[str, float]:
    """Calculate scores for each depth dimension."""
    total_events = max(metrics.get("total_events", 0), 1)
    affected_users = metrics.get("affected_users", 0)
    affected_systems = metrics.get("affected_systems", 0)
    affected_files = metrics.get("affected_files", 0)
    
    # Account depth - based on unique users affected
    account_depth = min(affected_users / 5, 10)
    
    # System depth - based on systems touched
    system_depth = min(affected_systems / 3, 10)
    
    # Data depth - based on files/targets accessed
    data_depth = min(affected_files / 20, 10)
    
    # Control depth - based on event density (events per user)
    events_per_user = total_events / max(affected_users, 1)
    control_depth = min(events_per_user / 10, 10)
    
    return {
        "account": round(account_depth, 2),
        "system": round(system_depth, 2),
        "data": round(data_depth, 2),
        "control": round(control_depth, 2)
    }


def _calculate_impact_score(metrics: Dict[str, int], weights: Dict[str, float] = None) -> Dict[str, Any]:
    """Calculate overall impact score based on metrics."""
    if weights is None:
        weights = {"account": 0.25, "system": 0.25, "data": 0.30, "control": 0.20}
    
    # Simple scoring algorithm
    user_impact = min(metrics.get("affected_users", 0) / 10, 10)
    system_impact = min(metrics.get("affected_systems", 0) / 5, 10)
    event_impact = min(metrics.get("total_events", 0) / 1000, 10)
    
    overall = (
        user_impact * weights.get("account", 0.25) + 
        system_impact * weights.get("system", 0.25) + 
        event_impact * weights.get("data", 0.30) +
        min(metrics.get("affected_files", 0) / 50, 10) * weights.get("control", 0.20)
    )
    
    if overall >= 8:
        level = "CRITICAL"
    elif overall >= 6:
        level = "HIGH"
    elif overall >= 4:
        level = "MEDIUM"
    elif overall >= 2:
        level = "LOW"
    else:
        level = "MINIMAL"
    
    return {
        "overall": round(overall, 2),
        "level": level,
        "breakdown": {
            "user_impact": round(user_impact, 2),
            "system_impact": round(system_impact, 2),
            "event_impact": round(event_impact, 2)
        }
    }


def get_depth_results(
    case_id: str,
    run_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    min_impact: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Get depth analysis results."""
    conn = open_vault(case_id)
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        results = []
        
        # Determine which table to use
        table = None
        ts_col = 'timestamp'
        if 'unified_timeline' in table_names:
            table = 'unified_timeline'
            ts_col = 'normalised_ts'
        elif 'timeline' in table_names:
            table = 'timeline'
            ts_col = 'timestamp'
        
        # Analyze users
        if table:
            try:
                users = conn.execute(f"""
                SELECT 
                    actor as entity,
                    'user' as entity_type,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT action) as action_types,
                    MIN({ts_col}) as first_seen,
                    MAX({ts_col}) as last_seen
                FROM {table}
                WHERE actor IS NOT NULL
                GROUP BY actor
                ORDER BY event_count DESC
                LIMIT 50
                """).fetchall()
                
                for row in users:
                    impact = min(row[2] / 100, 10)
                    results.append({
                        "entity": row[0],
                        "entity_type": row[1],
                        "event_count": row[2],
                        "action_types": row[3],
                        "first_seen": str(row[4]) if row[4] else None,
                        "last_seen": str(row[5]) if row[5] else None,
                        "impact_score": round(impact, 2)
                    })
            except Exception as e:
                logger.warning(f"Error analyzing users: {e}")
        
        # Filter by entity type if specified
        if entity_type:
            results = [r for r in results if r["entity_type"] == entity_type]
        
        # Filter by minimum impact
        if min_impact:
            results = [r for r in results if r.get("impact_score", 0) >= min_impact]
        
        return results
    finally:
        conn.close()


def get_depth_summary(case_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get depth analysis summary."""
    result = run_depth_analysis(case_id)
    return {
        "metrics": result.get("metrics", {}),
        "impact_score": result.get("impact_score", {}),
        "status": "completed"
    }


def get_depth_runs(case_id: str) -> List[Dict[str, Any]]:
    """List past depth analysis runs."""
    conn = open_vault(case_id)
    try:
        _ensure_depth_runs_table(conn)
        rows = conn.execute("""
            SELECT run_id, started_at, completed_at, account_depth, system_depth, data_depth, control_depth, overall_severity
            FROM depth_runs
            ORDER BY started_at DESC
            LIMIT 20
        """).fetchall()
        return [
            {
                "run_id": r[0],
                "started_at": str(r[1]) if r[1] else None,
                "completed_at": str(r[2]) if r[2] else None,
                "account_depth": r[3] or 0,
                "system_depth": r[4] or 0,
                "data_depth": r[5] or 0,
                "control_depth": r[6] or 0,
                "overall_severity": r[7] or 0
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"Error getting depth runs: {e}")
        return []
    finally:
        conn.close()


def get_depth_details(case_id: str, run_id: Optional[str] = None, dimension: Optional[str] = None) -> Dict[str, Any]:
    """Get detailed depth analysis for a dimension."""
    result = run_depth_analysis(case_id)
    dimensions = result.get("dimensions", {})
    
    if dimension:
        return {
            "dimension": dimension,
            "score": dimensions.get(dimension, 0),
            "details": _get_dimension_details(case_id, dimension)
        }
    
    return {
        "dimensions": dimensions,
        "details": {
            "account": _get_dimension_details(case_id, "account"),
            "system": _get_dimension_details(case_id, "system"),
            "data": _get_dimension_details(case_id, "data"),
            "control": _get_dimension_details(case_id, "control")
        }
    }


def _get_dimension_details(case_id: str, dimension: str) -> List[Dict[str, Any]]:
    """Get specific details for a dimension."""
    conn = open_vault(case_id)
    try:
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        table_names = [t[0] for t in tables]
        
        timeline_table = "unified_timeline" if "unified_timeline" in table_names else "timeline"
        if timeline_table not in table_names:
            return []
        
        if dimension == "account":
            rows = conn.execute(f"""
                SELECT actor, COUNT(*) as events FROM {timeline_table}
                WHERE actor IS NOT NULL GROUP BY actor ORDER BY events DESC LIMIT 10
            """).fetchall()
            return [{"entity": r[0], "events": r[1]} for r in rows]
        elif dimension == "system":
            rows = conn.execute(f"""
                SELECT source_system, COUNT(*) as events FROM {timeline_table}
                WHERE source_system IS NOT NULL GROUP BY source_system ORDER BY events DESC LIMIT 10
            """).fetchall()
            return [{"system": r[0], "events": r[1]} for r in rows]
        elif dimension == "data":
            rows = conn.execute(f"""
                SELECT target, COUNT(*) as accesses FROM {timeline_table}
                WHERE target IS NOT NULL GROUP BY target ORDER BY accesses DESC LIMIT 10
            """).fetchall()
            return [{"target": r[0], "accesses": r[1]} for r in rows]
        else:  # control
            rows = conn.execute(f"""
                SELECT action, COUNT(*) as count FROM {timeline_table}
                WHERE action IS NOT NULL GROUP BY action ORDER BY count DESC LIMIT 10
            """).fetchall()
            return [{"action": r[0], "count": r[1]} for r in rows]
    except Exception as e:
        logger.warning(f"Error getting dimension details: {e}")
        return []
    finally:
        conn.close()


def generate_impact_narrative(case_id: str, run_id: Optional[str] = None, llm_provider: str = "gemini") -> Dict[str, Any]:
    """Generate AI narrative for impact assessment."""
    import asyncio
    from operation_room.services.llm_provider import get_llm
    
    result = run_depth_analysis(case_id)
    metrics = result.get("metrics", {})
    dimensions = result.get("dimensions", {})
    impact = result.get("impact_score", {})
    
    prompt = f"""Generate a brief impact assessment narrative for a forensic investigation:

Metrics:
- Total Events: {metrics.get('total_events', 0)}
- Affected Users: {metrics.get('affected_users', 0)}
- Affected Systems: {metrics.get('affected_systems', 0)}
- Affected Files: {metrics.get('affected_files', 0)}

Dimension Scores (0-10):
- Account Depth: {dimensions.get('account', 0)}
- System Depth: {dimensions.get('system', 0)}
- Data Depth: {dimensions.get('data', 0)}
- Control Depth: {dimensions.get('control', 0)}

Overall Severity: {impact.get('level', 'UNKNOWN')} ({impact.get('overall', 0)}/10)

Write a 2-3 paragraph professional assessment of the potential impact and recommended immediate actions."""

    try:
        llm = get_llm(provider=llm_provider)
        # Run async generate in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            narrative = loop.run_until_complete(llm.generate(prompt, system="You are a forensic analyst providing impact assessments."))
        finally:
            loop.close()
        
        return {
            "status": "completed",
            "narrative": narrative if isinstance(narrative, str) else str(narrative),
            "metrics": metrics,
            "impact": impact
        }
    except Exception as e:
        logger.error(f"Error generating narrative: {e}")
        return {
            "status": "error",
            "error": str(e),
            "narrative": f"Impact assessment: {impact.get('level', 'UNKNOWN')} severity. {metrics.get('total_events', 0)} events analyzed affecting {metrics.get('affected_users', 0)} users across {metrics.get('affected_systems', 0)} systems."
        }


def get_impact_narrative(case_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get cached impact narrative or generate new one."""
    # For now, always generate fresh
    return generate_impact_narrative(case_id, run_id)


def get_affected_entities(
    case_id: str,
    entity_type: str = "all"
) -> List[Dict[str, Any]]:
    """Get list of affected entities."""
    results = get_depth_results(case_id)
    
    if entity_type != "all":
        results = [r for r in results if r.get("entity_type") == entity_type]
    
    return results


def get_depth_search(
    case_id: str,
    payload: Dict[str, Any],
    limit: int = 500,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Search depth results with filters."""
    return get_depth_results(case_id)[:limit]


def get_depth_distinct(case_id: str, field_name: str) -> List[str]:
    """Get distinct values for a field."""
    allowed_fields = ['entity_type', 'actor', 'target', 'action']
    if field_name not in allowed_fields:
        raise ValueError(f"Field {field_name} not allowed")
    
    conn = open_vault(case_id)
    try:
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'timeline' not in table_names:
            return []
        
        if field_name == 'entity_type':
            return ['user', 'system', 'file', 'process']
        
        try:
            results = conn.execute(f"SELECT DISTINCT {field_name} FROM timeline WHERE {field_name} IS NOT NULL LIMIT 1000").fetchall()
            return [str(r[0]) for r in results]
        except:
            return []
    finally:
        conn.close()
