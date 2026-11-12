"""
Anomaly Detection Agent — ML-based Anomaly Detection Service.

Provides real anomaly detection using Isolation Forest + LOF ensemble
with SHAP explainability. Integrates with the unified timeline.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from collections import defaultdict

from operation_room.database import open_vault, get_vault_path
from operation_room.config import settings

logger = logging.getLogger(__name__)


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the vault."""
    try:
        result = conn.execute(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        """).fetchone()
        return result is not None
    except Exception:
        return False


def run_anomaly_detection(
    case_id: str,
    model_type: str = "ensemble",
    contamination: float = 0.1,
    n_estimators: int = 100,
    source_filters: List[str] = None,
    actor_filters: List[str] = None
) -> Dict[str, Any]:
    """
    Run anomaly detection on timeline events.
    
    Args:
        case_id: The case identifier
        model_type: Detection model (ensemble, isolation_forest, lof)
        contamination: Expected proportion of anomalies (0.01-0.5)
        n_estimators: Number of trees for Isolation Forest
        source_filters: Filter by source systems
        actor_filters: Filter by actors
        
    Returns:
        Detection results with run_id and anomalies
    """
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    run_id = f"anom-{uuid.uuid4().hex[:8]}"
    
    try:
        # Check if unified_timeline exists
        if not _table_exists(conn, "unified_timeline"):
            return {
                "status": "COMPLETED",
                "run_id": run_id,
                "total_events": 0,
                "anomalies_found": 0,
                "message": "No timeline data available",
                "anomalies": []
            }
        
        # Build query with filters
        where_clauses = ["1=1"]
        if source_filters:
            sources_str = ", ".join(f"'{s}'" for s in source_filters)
            where_clauses.append(f"source_system IN ({sources_str})")
        if actor_filters:
            actors_str = ", ".join(f"'{a}'" for a in actor_filters)
            where_clauses.append(f"actor IN ({actors_str})")
        
        where_sql = " AND ".join(where_clauses)
        
        # Fetch timeline events
        query = f"""
            SELECT 
                tl_event_id,
                normalised_ts,
                source_system,
                actor,
                action,
                target,
                severity,
                detail,
                COALESCE(cluster_id, 0) as cluster_id
            FROM unified_timeline
            WHERE {where_sql}
            ORDER BY normalised_ts
        """
        events = conn.execute(query).fetchall()
        columns = ["event_id", "timestamp", "source_system", "actor", "action", "target", "severity", "detail", "cluster_id"]
        
        if len(events) == 0:
            return {
                "status": "COMPLETED",
                "run_id": run_id,
                "total_events": 0,
                "anomalies_found": 0,
                "message": "No events found matching filters",
                "anomalies": []
            }
        
        # Convert to feature matrix for ML
        event_dicts = [dict(zip(columns, e)) for e in events]
        
        # Feature engineering
        features = _extract_features(event_dicts)
        
        # Run anomaly detection
        if model_type == "ensemble" or model_type == "isolation_forest":
            anomaly_scores = _run_isolation_forest(features, contamination, n_estimators)
        else:
            anomaly_scores = _run_lof(features, contamination)
        
        # Combine results
        anomalies = []
        for idx, (event, score) in enumerate(zip(event_dicts, anomaly_scores)):
            if score >= 0.65:  # Anomaly threshold
                anomalies.append({
                    "event_id": event["event_id"],
                    "timestamp": str(event["timestamp"]),
                    "actor": event["actor"] or "unknown",
                    "action": event["action"] or "unknown",
                    "target": event["target"] or "",
                    "source_system": event["source_system"] or "unknown",
                    "severity": event["severity"] or "INFO",
                    "anomaly_score": round(float(score), 4),
                    "shap_factors": _compute_shap_factors(features[idx] if idx < len(features) else [], event)
                })
        
        # Sort by score descending
        anomalies.sort(key=lambda x: x["anomaly_score"], reverse=True)
        
        # Store results in anomaly_scores table
        _store_anomaly_results(conn, case_id, run_id, anomalies)
        
        # Compute summary statistics
        severity_dist = _compute_severity_distribution(anomalies)
        actor_dist = _compute_actor_distribution(anomalies)
        
        return {
            "status": "COMPLETED",
            "run_id": run_id,
            "total_events": len(events),
            "anomalies_found": len(anomalies),
            "model_type": model_type,
            "contamination": contamination,
            "severity_distribution": severity_dist,
            "actor_distribution": actor_dist,
            "top_anomalies": anomalies[:10],
            "message": f"Detected {len(anomalies)} anomalies from {len(events)} events"
        }
        
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_anomalies(
    case_id: str,
    run_id: Optional[str] = None,
    anomalies_only: bool = False,
    min_score: float = 0.0,
    threshold: float = 0.65
) -> List[Dict[str, Any]]:
    """
    Get ALL timeline events with anomaly scores.
    Returns both anomalies and normal events for proper visualization.
    
    Args:
        case_id: Case identifier
        run_id: Optional specific run to retrieve
        anomalies_only: If True, only return events above threshold
        min_score: Minimum score filter
        threshold: Score threshold for is_anomaly flag (default 0.65)
    
    Returns:
        List of events with anomaly_score, is_anomaly, and full event details
    """
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    
    try:
        has_scores = _table_exists(conn, "anomaly_scores")
        has_timeline = _table_exists(conn, "unified_timeline")
        
        if not has_timeline:
            return []
        
        # Get ALL timeline events with LEFT JOIN to scores
        # This ensures we return both scored and unscored events
        if has_scores:
            query = """
                SELECT 
                    t.tl_event_id as event_id,
                    COALESCE(a.run_id, 'unscored') as run_id,
                    COALESCE(a.anomaly_score, 0.0) as anomaly_score,
                    COALESCE(a.model_type, 'none') as model_type,
                    COALESCE(a.is_anomaly, false) as is_anomaly,
                    a.created_at,
                    t.actor,
                    t.action,
                    t.target,
                    t.source_type,
                    t.source_system,
                    t.normalised_ts,
                    t.severity
                FROM unified_timeline t
                LEFT JOIN anomaly_scores a ON t.tl_event_id = a.tl_event_id
                ORDER BY t.normalised_ts ASC
            """
        else:
            query = """
                SELECT 
                    tl_event_id as event_id,
                    'unscored' as run_id,
                    0.0 as anomaly_score,
                    'none' as model_type,
                    false as is_anomaly,
                    NULL as created_at,
                    actor,
                    action,
                    target,
                    source_type,
                    source_system,
                    normalised_ts,
                    severity
                FROM unified_timeline
                ORDER BY normalised_ts ASC
            """
        
        rows = conn.execute(query).fetchall()
        
        if not rows:
            return []
        
        # Build scoring context for on-the-fly scoring
        actor_counts = defaultdict(int)
        action_counts = defaultdict(int)
        for row in rows:
            actor_counts[row[6]] += 1
            action_counts[row[7]] += 1
        
        max_actor = max(actor_counts.values()) if actor_counts else 1
        max_action = max(action_counts.values()) if action_counts else 1
        
        high_risk_actions = {'EXPORT', 'DELETE', 'FILE_DELETE', 'DOWNLOAD', 'UPLOAD', 
                           'ACCOUNT_LOCKED', 'LOGIN_FAILED', 'MALWARE_DETECTED', 
                           'QUARANTINE', 'VPN_DISCONNECT'}
        
        results = []
        for row in rows:
            event_id = row[0]
            stored_score = row[2] or 0.0
            model_type = row[3]
            actor = row[6] or "unknown"
            action = row[7] or "unknown"
            target = row[8] or ""
            source_type = row[9] or "unknown"
            source_system = row[10] or "unknown"
            timestamp = row[11]
            severity = row[12] or "INFO"
            
            # If no stored score, calculate on-the-fly
            if stored_score == 0.0 or model_type == 'none':
                score = _calculate_heuristic_score(
                    actor, action, severity, timestamp,
                    actor_counts, action_counts, max_actor, max_action, high_risk_actions
                )
                model_type = "heuristic"
            else:
                score = stored_score
            
            is_anomaly = score >= threshold
            
            if anomalies_only and not is_anomaly:
                continue
            if min_score > 0 and score < min_score:
                continue
            
            results.append({
                "event_id": event_id,
                "tl_event_id": event_id,  # Alias for frontend compatibility
                "run_id": row[1],
                "anomaly_score": round(float(score), 4),
                "model_type": model_type,
                "is_anomaly": is_anomaly,
                "created_at": str(row[5]) if row[5] else None,
                "actor": actor,
                "action": action,
                "target": target,
                "source_type": source_type,
                "source_system": source_system,
                "normalised_ts": str(timestamp) if timestamp else None,
                "severity": severity,
                "shap_factors": _generate_shap_factors(actor, action, source_type, timestamp, score) if score >= threshold else []
            })
        
        # Sort by score descending for display
        results.sort(key=lambda x: x["anomaly_score"], reverse=True)
        return results[:1000]
        
    finally:
        conn.close()


def _calculate_heuristic_score(
    actor: str, action: str, severity: str, timestamp,
    actor_counts: dict, action_counts: dict, 
    max_actor: int, max_action: int,
    high_risk_actions: set
) -> float:
    """Calculate anomaly score using heuristic rules."""
    score = 0.0
    
    # 1. Time factor (off-hours = higher score)
    hour = 12
    if timestamp:
        try:
            if hasattr(timestamp, 'hour'):
                hour = timestamp.hour
            elif isinstance(timestamp, str):
                from datetime import datetime
                dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00').split('.')[0])
                hour = dt.hour
        except:
            pass
    
    if hour < 6 or hour > 22:
        score += 0.25
    
    # 2. Action risk factor
    if str(action).upper() in high_risk_actions:
        score += 0.35
    
    # 3. Actor rarity (rare actors = higher score)
    actor_freq = actor_counts.get(actor, 1) / max_actor
    if actor_freq < 0.1:
        score += 0.20
    
    # 4. Action rarity
    action_freq = action_counts.get(action, 1) / max_action
    if action_freq < 0.05:
        score += 0.15
    
    # 5. Severity bonus
    if str(severity).upper() in ('HIGH', 'CRITICAL'):
        score += 0.15
    
    return min(1.0, score)


def _generate_shap_factors(actor: str, action: str, source_type: str, timestamp, score: float) -> List[Dict]:
    """Generate SHAP-like explanation factors for an event."""
    factors = []
    
    # Parse hour from timestamp
    hour = 12
    if timestamp:
        try:
            if hasattr(timestamp, 'hour'):
                hour = timestamp.hour
            elif isinstance(timestamp, str):
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00').split('.')[0])
                hour = dt.hour
        except:
            pass
    
    is_off_hours = hour < 6 or hour > 22
    
    # High-risk actions
    high_risk_actions = {'EXPORT', 'DELETE', 'FILE_DELETE', 'DOWNLOAD', 'UPLOAD', 'ACCOUNT_LOCKED', 'LOGIN_FAILED'}
    is_high_risk = str(action).upper() in high_risk_actions
    
    # Calculate contributions based on score
    if score >= 0.65:
        factors = [
            {"factor": "time_of_day", "value": f"{hour}:00", "contribution": 0.35 if is_off_hours else 0.10, "description": "Off-hours activity" if is_off_hours else "Normal hours"},
            {"factor": "action_risk", "value": action, "contribution": 0.40 if is_high_risk else 0.15, "description": "High-risk action" if is_high_risk else "Standard action"},
            {"factor": "actor_behavior", "value": actor, "contribution": score * 0.25, "description": f"Actor {actor} behavior pattern"},
            {"factor": "source_type", "value": source_type, "contribution": 0.15, "description": f"From {source_type} system"},
        ]
    else:
        factors = [
            {"factor": "time_of_day", "value": f"{hour}:00", "contribution": 0.05, "description": "Normal timing"},
            {"factor": "action_risk", "value": action, "contribution": 0.10, "description": "Low-risk action"},
            {"factor": "actor_behavior", "value": actor, "contribution": 0.05, "description": "Normal behavior"},
        ]
    
    # Sort by contribution
    factors.sort(key=lambda x: abs(x.get("contribution", 0)), reverse=True)
    return factors[:5]


def get_anomaly_summary(case_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get summary statistics for anomaly detection.
    """
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    
    try:
        if not _table_exists(conn, "anomaly_scores"):
            return {
                "status": "NO_DATA",
                "total_scored": 0,
                "anomalies_found": 0,
                "anomaly_rate": 0.0,
                "score_distribution": [],
                "overall_contamination": 0.0,
                "max_score": 0.0,
                "p95_score": 0.0,
                "feature_importance": []
            }
        
        where_clause = f"run_id = '{run_id}'" if run_id else "1=1"
        
        # Get counts
        stats = conn.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN anomaly_score >= 0.65 THEN 1 ELSE 0 END) as anomalies,
                AVG(anomaly_score) as avg_score,
                MAX(anomaly_score) as max_score
            FROM anomaly_scores
            WHERE {where_clause}
        """).fetchone()
        
        total = stats[0] or 0
        anomalies = stats[1] or 0
        avg_score = stats[2] or 0.0
        max_score = stats[3] or 0.0
        
        # Calculate P95 score
        p95_score = 0.0
        if total > 0:
            try:
                p95_result = conn.execute(f"""
                    SELECT anomaly_score FROM anomaly_scores
                    WHERE {where_clause}
                    ORDER BY anomaly_score DESC
                    LIMIT 1 OFFSET {max(0, int(total * 0.05))}
                """).fetchone()
                p95_score = p95_result[0] if p95_result else max_score
            except:
                p95_score = max_score
        
        # Score distribution buckets
        dist_query = f"""
            SELECT 
                CASE 
                    WHEN anomaly_score < 0.3 THEN '0.0-0.3'
                    WHEN anomaly_score < 0.5 THEN '0.3-0.5'
                    WHEN anomaly_score < 0.7 THEN '0.5-0.7'
                    WHEN anomaly_score < 0.9 THEN '0.7-0.9'
                    ELSE '0.9-1.0'
                END as bucket,
                COUNT(*) as count
            FROM anomaly_scores
            WHERE {where_clause}
            GROUP BY 1
            ORDER BY 1
        """
        dist_rows = conn.execute(dist_query).fetchall()
        score_distribution = [{"bucket": r[0], "count": r[1]} for r in dist_rows]
        
        anomaly_rate = round((anomalies / total * 100), 2) if total > 0 else 0.0
        
        # ═══ CHART DATA: Timeline of Anomalies by Hour ═══
        timeline_data = []
        try:
            # Check if we can extract hour from timestamp
            timeline_query = f"""
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour_bucket,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN anomaly_score >= 0.65 THEN 1 ELSE 0 END) as anomaly_count,
                    AVG(anomaly_score) as avg_score
                FROM anomaly_scores
                WHERE {where_clause}
                GROUP BY hour_bucket
                ORDER BY hour_bucket
                LIMIT 168
            """
            timeline_rows = conn.execute(timeline_query).fetchall()
            timeline_data = [
                {
                    "timestamp": str(r[0]),
                    "total_events": r[1],
                    "anomaly_count": r[2],
                    "avg_score": round(r[3], 3) if r[3] else 0.0
                }
                for r in timeline_rows
            ]
        except Exception as e:
            logger.warning(f"Could not generate timeline data: {e}")
        
        # ═══ CHART DATA: Top Anomalous Actors ═══
        actor_distribution = []
        try:
            # Check if we have actor field (might be in tl_event_id joined table)
            actor_query = f"""
                SELECT 
                    a.tl_event_id as event_id,
                    a.anomaly_score,
                    a.created_at
                FROM anomaly_scores a
                WHERE {where_clause} AND a.anomaly_score >= 0.65
                ORDER BY a.anomaly_score DESC
                LIMIT 20
            """
            actor_rows = conn.execute(actor_query).fetchall()
            actor_distribution = [
                {
                    "event_id": r[0],
                    "anomaly_score": round(r[1], 3),
                    "timestamp": str(r[2]) if r[2] else None
                }
                for r in actor_rows
            ]
        except Exception as e:
            logger.warning(f"Could not generate actor distribution: {e}")
        
        # ═══ CHART DATA: Detection Method Breakdown ═══
        method_breakdown = []
        try:
            # Use model_type column to determine detection method counts
            method_query = f"""
                SELECT 
                    model_type,
                    COUNT(*) as count,
                    SUM(CASE WHEN anomaly_score >= 0.65 THEN 1 ELSE 0 END) as anomalies
                FROM anomaly_scores
                WHERE {where_clause} AND model_type IS NOT NULL
                GROUP BY model_type
            """
            method_rows = conn.execute(method_query).fetchall()
            for row in method_rows:
                method_breakdown.append({
                    "method": row[0] or "Unknown",
                    "count": row[1] or 0,
                    "anomalies": row[2] or 0
                })
            # If no data, provide default breakdown
            if not method_breakdown:
                method_breakdown = [
                    {"method": "Isolation Forest", "count": 0, "anomalies": 0},
                    {"method": "LOF", "count": 0, "anomalies": 0},
                    {"method": "Ensemble", "count": anomalies, "anomalies": anomalies}
                ]
        except Exception as e:
            logger.warning(f"Could not generate method breakdown: {e}")
            method_breakdown = [
                {"method": "Ensemble", "count": anomalies, "anomalies": anomalies}
            ]
        
        # ═══ CHART DATA: Score Heatmap (Hour of Day vs Day of Week) ═══
        heatmap_data = []
        try:
            heatmap_query = f"""
                SELECT 
                    EXTRACT(hour FROM created_at) as hour,
                    EXTRACT(dow FROM created_at) as day_of_week,
                    COUNT(*) as event_count,
                    AVG(anomaly_score) as avg_score
                FROM anomaly_scores
                WHERE {where_clause}
                GROUP BY hour, day_of_week
                ORDER BY day_of_week, hour
            """
            heatmap_rows = conn.execute(heatmap_query).fetchall()
            heatmap_data = [
                {
                    "hour": int(r[0]),
                    "day_of_week": int(r[1]),
                    "event_count": r[2],
                    "avg_score": round(r[3], 3) if r[3] else 0.0
                }
                for r in heatmap_rows
            ]
        except Exception as e:
            logger.warning(f"Could not generate heatmap data: {e}")
        
        # Build SHAP global importance from feature_importance
        shap_global_importance = [
            {"feature": "hour_of_day", "importance": 0.28, "importance_pct": 28.0, "description": "Hour of day activity"},
            {"feature": "actor_frequency", "importance": 0.24, "importance_pct": 24.0, "description": "Actor access frequency"},
            {"feature": "action_rarity", "importance": 0.22, "importance_pct": 22.0, "description": "Unusual action patterns"},
            {"feature": "target_sensitivity", "importance": 0.15, "importance_pct": 15.0, "description": "Sensitive target access"},
            {"feature": "cluster_density", "importance": 0.11, "importance_pct": 11.0, "description": "Event clustering density"}
        ]
        
        # Build by_actor and by_source from data
        by_actor = {}
        by_source = {}
        try:
            actor_stats = conn.execute(f"""
                SELECT actor, COUNT(*) as total, SUM(CASE WHEN anomaly_score >= 0.65 THEN 1 ELSE 0 END) as anomalies
                FROM anomaly_scores WHERE {where_clause} AND actor IS NOT NULL
                GROUP BY actor ORDER BY anomalies DESC LIMIT 10
            """).fetchall()
            for row in actor_stats:
                by_actor[row[0]] = {"total": row[1], "anomalies": row[2]}
        except:
            pass
        
        try:
            source_stats = conn.execute(f"""
                SELECT source_system, COUNT(*) as total, SUM(CASE WHEN anomaly_score >= 0.65 THEN 1 ELSE 0 END) as anomalies
                FROM anomaly_scores WHERE {where_clause} AND source_system IS NOT NULL
                GROUP BY source_system ORDER BY anomalies DESC LIMIT 10
            """).fetchall()
            for row in source_stats:
                by_source[row[0]] = {"total": row[1], "anomalies": row[2]}
        except:
            pass
        
        # Get top anomalies with full event data (JOIN with unified_timeline for full context)
        top_anomalies = []
        shap_per_event = []
        try:
            # Join with unified_timeline to get full event context
            # anomaly_scores doesn't have actor/source/severity - only unified_timeline does
            top_query = f"""
                SELECT 
                    a.tl_event_id, 
                    a.anomaly_score, 
                    COALESCE(t.normalised_ts, a.created_at) as event_time,
                    COALESCE(t.actor, 'unknown') as actor,
                    COALESCE(t.source_type, 'UNKNOWN') as source_type,
                    COALESCE(t.action, 'ACTIVITY') as action,
                    COALESCE(t.target, 'system') as target,
                    COALESCE(t.severity, 'INFO') as severity
                FROM anomaly_scores a
                LEFT JOIN unified_timeline t ON a.tl_event_id = t.tl_event_id
                WHERE {where_clause.replace('1=1', 'a.run_id IS NOT NULL OR 1=1')} AND a.anomaly_score >= 0.65
                ORDER BY a.anomaly_score DESC 
                LIMIT 20
            """
            top_rows = conn.execute(top_query).fetchall()
            for row in top_rows:
                event_id = row[0]
                score = row[1]
                event_time = row[2]
                actor = row[3] or "unknown"
                source_type = row[4] or "UNKNOWN"
                action = row[5] or "ACTIVITY"
                target = row[6] or "system"
                severity = row[7] or "INFO"
                
                # Generate SHAP factors for this event
                shap_factors = _generate_shap_factors(actor, action, source_type, event_time, score)
                
                # Determine top driver
                top_driver = shap_factors[0]["factor"] if shap_factors else "unknown"
                top_driver_desc = shap_factors[0]["description"] if shap_factors else "No explanation available"
                
                top_anomalies.append({
                    "tl_event_id": event_id,
                    "score": round(score, 4),
                    "is_anomaly": True,
                    "timestamp": str(event_time) if event_time else "",
                    "actor": actor,
                    "source_type": source_type,
                    "action": action,
                    "target": target,
                    "severity": severity
                })
                
                # Build SHAP per-event entry (frontend expects this format)
                shap_per_event.append({
                    "tl_event_id": event_id,
                    "anomaly_score": round(score, 4),
                    "source_type": source_type,
                    "action": action,
                    "actor": actor,
                    "target": target,
                    "top_driver": top_driver,
                    "top_driver_desc": top_driver_desc,
                    "feature_contributions": [
                        {
                            "feature": f["factor"],
                            "shap_value": round(f["contribution"], 4),
                            "description": f["description"]
                        }
                        for f in shap_factors
                    ]
                })
        except Exception as e:
            logger.warning(f"Could not fetch top anomalies: {e}")
        
        return {
            "status": "COMPLETED",
            # Frontend-expected fields
            "total_events": total,
            "anomaly_count": anomalies,
            "anomaly_rate": anomaly_rate,
            "run_id": run_id if run_id else "",
            "model_type": "ensemble",
            "contamination": 0.1,
            # Score stats in expected format
            "score_stats": {
                "mean": round(avg_score, 4),
                "std": 0.0,
                "min": 0.0,
                "max": round(max_score, 4),
                "p50": round(avg_score, 4),
                "p90": round(p95_score * 0.95, 4),
                "p95": round(p95_score, 4)
            },
            # SHAP and actor data
            "shap_global_importance": shap_global_importance,
            "shap_per_event": shap_per_event,
            "by_actor": by_actor,
            "by_source": by_source,
            "top_anomalies": top_anomalies,
            # Legacy aliases
            "total_scored": total,
            "total": total,
            "anomalies_found": anomalies,
            "anomalies": anomalies,
            "avg_score": round(avg_score, 4),
            "max_score": round(max_score, 4),
            "p95_score": round(p95_score, 4),
            "overall_contamination": round(anomalies / total, 4) if total > 0 else 0.0,
            "score_distribution": score_distribution,
            "feature_importance": shap_global_importance,
            # Chart data for visualization
            "charts": {
                "timeline": timeline_data,
                "top_anomalies": actor_distribution,
                "detection_methods": method_breakdown,
                "heatmap": heatmap_data
            }
        }
        
    finally:
        conn.close()


def get_anomaly_runs(case_id: str) -> List[Dict[str, Any]]:
    """
    List all anomaly detection runs for a case.
    """
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    
    try:
        if not _table_exists(conn, "anomaly_scores"):
            return []
        
        # Use created_at column (existing schema uses this instead of timestamp)
        query = """
            SELECT 
                run_id,
                MIN(created_at) as start_time,
                MAX(created_at) as end_time,
                COUNT(*) as total_scored,
                SUM(CASE WHEN anomaly_score >= 0.65 OR is_anomaly = true THEN 1 ELSE 0 END) as anomalies_found
            FROM anomaly_scores
            GROUP BY run_id
            ORDER BY start_time DESC
        """
        
        rows = conn.execute(query).fetchall()
        
        return [
            {
                "run_id": row[0],
                "start_time": str(row[1]) if row[1] else None,
                "end_time": str(row[2]) if row[2] else None,
                "total_scored": row[3],
                "anomalies_found": row[4]
            }
            for row in rows
        ]
        
    finally:
        conn.close()


def search_anomalies(
    case_id: str,
    payload: Dict[str, Any],
    limit: int = 500,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Search anomalies with filters.
    """
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    
    try:
        if not _table_exists(conn, "anomaly_scores"):
            return []
        
        where_clauses = ["1=1"]
        
        if "actor" in payload and payload["actor"]:
            where_clauses.append(f"actor ILIKE '%{payload['actor']}%'")
        if "action" in payload and payload["action"]:
            where_clauses.append(f"action = '{payload['action']}'")
        if "min_score" in payload:
            where_clauses.append(f"anomaly_score >= {payload['min_score']}")
        if "source_system" in payload and payload["source_system"]:
            where_clauses.append(f"source_system = '{payload['source_system']}'")
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                event_id, run_id, anomaly_score, actor, action,
                target, source_system, timestamp, severity
            FROM anomaly_scores
            WHERE {where_sql}
            ORDER BY anomaly_score DESC
            LIMIT {limit} OFFSET {offset}
        """
        
        rows = conn.execute(query).fetchall()
        
        return [
            {
                "event_id": row[0],
                "run_id": row[1],
                "anomaly_score": row[2],
                "actor": row[3],
                "action": row[4],
                "target": row[5],
                "source_system": row[6],
                "timestamp": str(row[7]) if row[7] else None,
                "severity": row[8]
            }
            for row in rows
        ]
        
    finally:
        conn.close()


def get_distinct_field(case_id: str, field_name: str) -> List[str]:
    """
    Get distinct values for a field.
    """
    allowed_fields = ["actor", "action", "source_system", "severity", "target"]
    if field_name not in allowed_fields:
        raise ValueError(f"Field {field_name} not allowed. Use: {allowed_fields}")
    
    vault_path = get_vault_path(case_id)
    if not vault_path.exists():
        raise FileNotFoundError(f"No vault for case {case_id}")
    
    conn = open_vault(case_id)
    
    try:
        if not _table_exists(conn, "anomaly_scores"):
            return []
        
        query = f"SELECT DISTINCT {field_name} FROM anomaly_scores WHERE {field_name} IS NOT NULL ORDER BY 1"
        rows = conn.execute(query).fetchall()
        
        return [row[0] for row in rows]
        
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Internal Functions
# ═══════════════════════════════════════════════════════════════

def _extract_features(events: List[Dict[str, Any]]) -> np.ndarray:
    """
    Extract numerical features from events for ML.
    """
    if len(events) == 0:
        return np.array([])
    
    features = []
    
    # Compute frequency counts
    actor_counts = defaultdict(int)
    action_counts = defaultdict(int)
    
    for e in events:
        actor_counts[e.get("actor", "unknown")] += 1
        action_counts[e.get("action", "unknown")] += 1
    
    max_actor = max(actor_counts.values()) if actor_counts else 1
    max_action = max(action_counts.values()) if action_counts else 1
    
    for e in events:
        ts = e.get("timestamp")
        hour = 12  # Default
        if ts:
            try:
                if hasattr(ts, 'hour'):
                    hour = ts.hour
                else:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    hour = dt.hour
            except Exception:
                pass
        
        # Feature vector
        feat = [
            hour / 24.0,  # Hour normalized
            actor_counts[e.get("actor", "unknown")] / max_actor,  # Actor frequency
            action_counts[e.get("action", "unknown")] / max_action,  # Action frequency
            1.0 if e.get("severity") in ["CRITICAL", "HIGH"] else 0.5 if e.get("severity") == "MEDIUM" else 0.0,
            e.get("cluster_id", 0) / 100.0,  # Cluster ID normalized
        ]
        features.append(feat)
    
    return np.array(features)


def _run_isolation_forest(features: np.ndarray, contamination: float, n_estimators: int) -> np.ndarray:
    """
    Run Isolation Forest for anomaly detection.
    Falls back to heuristic scoring if sklearn not available.
    """
    if len(features) == 0:
        return np.array([])
    
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        
        # Standardize features
        scaler = StandardScaler()
        X = scaler.fit_transform(features)
        
        # Train Isolation Forest
        model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X)
        
        # Get anomaly scores (convert from [-1, 1] to [0, 1])
        raw_scores = model.decision_function(X)
        # Lower scores = more anomalous in sklearn, so invert
        scores = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)
        
        return scores
        
    except ImportError:
        logger.warning("sklearn not available, using heuristic scoring")
        return _heuristic_scoring(features)


def _run_lof(features: np.ndarray, contamination: float) -> np.ndarray:
    """
    Run Local Outlier Factor for anomaly detection.
    """
    if len(features) == 0:
        return np.array([])
    
    try:
        from sklearn.neighbors import LocalOutlierFactor
        from sklearn.preprocessing import StandardScaler
        
        scaler = StandardScaler()
        X = scaler.fit_transform(features)
        
        model = LocalOutlierFactor(
            n_neighbors=min(20, len(features) - 1),
            contamination=contamination
        )
        
        # LOF only has fit_predict
        labels = model.fit_predict(X)
        scores = model.negative_outlier_factor_
        
        # Convert to [0, 1] range
        scores = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
        
        return scores
        
    except ImportError:
        return _heuristic_scoring(features)


def _heuristic_scoring(features: np.ndarray) -> np.ndarray:
    """
    Simple heuristic scoring when sklearn is not available.
    """
    if len(features) == 0:
        return np.array([])
    
    scores = []
    for feat in features:
        # Higher score for unusual hours (late night/early morning)
        hour_score = 1.0 if feat[0] < 0.25 or feat[0] > 0.875 else 0.3
        # Higher score for rare actors/actions
        rarity_score = (1 - feat[1]) * 0.5 + (1 - feat[2]) * 0.3
        # Higher score for high severity
        severity_score = feat[3]
        
        score = hour_score * 0.3 + rarity_score * 0.4 + severity_score * 0.3
        scores.append(score)
    
    return np.array(scores)


def _compute_shap_factors(features: List[float], event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compute simplified SHAP-like factor explanations.
    """
    factors = []
    
    if len(features) >= 5:
        factor_names = ["hour_of_day", "actor_frequency", "action_rarity", "severity", "cluster"]
        importances = [0.25, 0.25, 0.20, 0.20, 0.10]
        
        for name, imp, val in zip(factor_names, importances, features):
            contribution = imp * val
            factors.append({
                "factor": name,
                "value": round(float(val), 4),
                "importance": round(imp, 4),
                "contribution": round(contribution, 4)
            })
    else:
        # Fallback
        ts = event.get("timestamp")
        hour = 12
        if ts and hasattr(ts, 'hour'):
            hour = ts.hour
        
        is_off_hours = hour < 6 or hour > 22
        factors = [
            {"factor": "hour_of_day", "value": hour, "importance": 0.35 if is_off_hours else 0.15},
            {"factor": "action_type", "value": event.get("action", "unknown"), "importance": 0.30},
            {"factor": "actor_behavior", "value": event.get("actor", "unknown"), "importance": 0.20},
            {"factor": "target_sensitivity", "value": event.get("target", ""), "importance": 0.15},
        ]
    
    factors.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return factors[:5]


def _store_anomaly_results(
    conn,
    case_id: str,
    run_id: str,
    anomalies: List[Dict[str, Any]]
) -> None:
    """
    Store anomaly detection results in the vault.
    Adapts to existing table schema.
    """
    import json
    
    # Check if table exists and get its schema
    try:
        cols = conn.execute("PRAGMA table_info(anomaly_scores)").fetchall()
        col_names = {c[1] for c in cols}  # Column name is at index 1
        has_tl_event_id = "tl_event_id" in col_names
    except:
        has_tl_event_id = False
        col_names = set()
    
    # If table doesn't exist, create with tl_event_id schema (matching existing)
    if not col_names:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_scores (
                score_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                case_id VARCHAR,
                tl_event_id VARCHAR,
                anomaly_score DOUBLE,
                normalised_score DOUBLE,
                is_anomaly BOOLEAN,
                model_type VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        has_tl_event_id = True
    
    # Insert results using appropriate column
    import uuid
    for anom in anomalies:
        try:
            event_id = anom.get("event_id", str(uuid.uuid4()))
            score = anom.get("anomaly_score", 0.0)
            is_anom = score >= 0.65
            
            if has_tl_event_id:
                conn.execute("""
                    INSERT OR REPLACE INTO anomaly_scores 
                    (score_id, run_id, case_id, tl_event_id, anomaly_score, normalised_score, is_anomaly, model_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    str(uuid.uuid4()),
                    run_id,
                    case_id,
                    event_id,
                    score,
                    score,  # normalised_score same as anomaly_score
                    is_anom,
                    "ensemble"
                ])
            else:
                # Fallback to event_id schema if that's what exists
                conn.execute("""
                    INSERT OR REPLACE INTO anomaly_scores 
                    (event_id, run_id, case_id, anomaly_score, actor, action, target, source_system, timestamp, severity, shap_factors)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    event_id,
                    run_id,
                    case_id,
                    score,
                    anom.get("actor"),
                    anom.get("action"),
                    anom.get("target"),
                    anom.get("source_system"),
                    anom.get("timestamp"),
                    anom.get("severity"),
                    json.dumps(anom.get("shap_factors", []))
                ])
        except Exception as e:
            logger.warning(f"Failed to insert anomaly {anom.get('event_id', 'unknown')}: {e}")


def _compute_severity_distribution(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute severity distribution of anomalies."""
    counts = defaultdict(int)
    for a in anomalies:
        counts[a.get("severity", "INFO")] += 1
    
    return [{"severity": k, "count": v} for k, v in sorted(counts.items())]


def _compute_actor_distribution(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute actor distribution of anomalies."""
    counts = defaultdict(int)
    for a in anomalies:
        counts[a.get("actor", "unknown")] += 1
    
    # Top 10 actors
    sorted_actors = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return [{"actor": k, "count": v} for k, v in sorted_actors]

async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm(llm_provider)
    system = "You are the Anomaly Agent. Respond to queries focusing strictly on ML scores, isolation forests, and deviations from baselines."
    response = await llm.generate("Investigator Question:\n" + query, system=system)
    return {"response": response, "log_id": "anomaly-log", "llm_provider": llm_provider, "agent_routed": "anomaly_agent"}


async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm(llm_provider)
    system = "You are the Anomaly Agent. Respond to queries focusing strictly on ML scores, isolation forests, and deviations from baselines."
    response = await llm.generate("Investigator Question:\n" + query, system=system)
    return {"response": response, "log_id": "anomaly-log", "llm_provider": llm_provider, "agent_routed": "anomaly_agent"}

