"""
Augment Studio Service — Chart data aggregation from all modules.

Provides pre-computed chart datasets that the frontend studio can consume
for building interactive visualisations.  Handles saving/loading chart
specs with hash integrity.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from collections import defaultdict

from operation_room.database import open_vault
from operation_room.utils.hashing import hash_records
from operation_room.services.audit_service import record_coc_event

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_detail(detail):
    if not detail:
        return {}
    if isinstance(detail, dict):
        return detail
    try:
        return json.loads(detail)
    except (json.JSONDecodeError, TypeError):
        return {}


# ═══════════════════════════════════════════════════════════════
# Dataset: Timeline
# ═══════════════════════════════════════════════════════════════

def get_timeline_chart_data(case_id: str) -> dict:
    """Aggregate timeline events for histograms & source breakdowns."""
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT normalised_ts, source_type, severity, action, actor
            FROM unified_timeline WHERE case_id = ?
            ORDER BY normalised_ts ASC
        """, [case_id]).fetchall()

        hourly = defaultdict(lambda: defaultdict(int))
        source_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        action_counts = defaultdict(int)
        actor_counts = defaultdict(int)

        for ts, src, sev, action, actor in rows:
            ts_str = str(ts) if ts else ""
            hour = ts_str[:13] if len(ts_str) >= 13 else ts_str
            hourly[hour][src or "UNKNOWN"] += 1
            source_counts[src or "UNKNOWN"] += 1
            severity_counts[sev or "INFO"] += 1
            action_counts[action or "UNKNOWN"] += 1
            if actor:
                actor_counts[actor] += 1

        histogram = [{"time": h, **{s: c for s, c in sources.items()}}
                     for h, sources in sorted(hourly.items())]

        return {
            "dataset": "timeline",
            "total_events": len(rows),
            "histogram": histogram,
            "source_distribution": dict(source_counts),
            "severity_distribution": dict(severity_counts),
            "top_actions": dict(sorted(action_counts.items(), key=lambda x: -x[1])[:20]),
            "top_actors": dict(sorted(actor_counts.items(), key=lambda x: -x[1])[:20]),
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Dataset: Anomaly
# ═══════════════════════════════════════════════════════════════

def get_anomaly_chart_data(case_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT s.anomaly_score, s.is_anomaly, t.source_type, t.actor, t.action, t.normalised_ts
            FROM anomaly_scores s
            JOIN unified_timeline t ON s.tl_event_id = t.tl_event_id
            WHERE s.run_id = (SELECT run_id FROM anomaly_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        score_dist = defaultdict(int)
        source_anomalies = defaultdict(int)
        actor_anomalies = defaultdict(lambda: {"total": 0, "anomalous": 0})
        timeline = []

        for score, is_anom, src, actor, action, ts in rows:
            bucket = round(float(score), 1)
            score_dist[bucket] += 1
            if is_anom and src:
                source_anomalies[src] += 1
            if actor:
                actor_anomalies[actor]["total"] += 1
                if is_anom:
                    actor_anomalies[actor]["anomalous"] += 1
            timeline.append({"ts": str(ts)[:13] if ts else "", "score": float(score), "anomaly": bool(is_anom)})

        return {
            "dataset": "anomaly",
            "total_scored": len(rows),
            "total_anomalies": sum(1 for _, a, *_ in rows if a),
            "score_distribution": [{"score": k, "count": v} for k, v in sorted(score_dist.items())],
            "source_anomalies": dict(source_anomalies),
            "actor_anomalies": {k: v for k, v in sorted(actor_anomalies.items(), key=lambda x: -x[1]["anomalous"])[:15]},
        }
    except Exception:
        return {"dataset": "anomaly", "total_scored": 0, "total_anomalies": 0}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Dataset: Correlation
# ═══════════════════════════════════════════════════════════════

def get_correlation_chart_data(case_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        nodes = conn.execute("""
            SELECT entity_type, entity_value, severity_score, event_count, metadata_json
            FROM correlation_nodes
            WHERE run_id = (SELECT run_id FROM correlation_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
            ORDER BY severity_score DESC
        """, [case_id]).fetchall()

        edges = conn.execute("""
            SELECT relationship, weight, source_node_id, target_node_id
            FROM correlation_edges
            WHERE run_id = (SELECT run_id FROM correlation_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        type_counts = defaultdict(int)
        type_severity = defaultdict(list)
        for etype, evalue, sev, count, meta in nodes:
            type_counts[etype] += 1
            type_severity[etype].append(float(sev or 0))

        rel_counts = defaultdict(int)
        for rel, weight, *_ in edges:
            rel_counts[rel] += 1

        return {
            "dataset": "correlation",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_type_counts": dict(type_counts),
            "entity_severity_avg": {k: round(sum(v) / len(v), 3) for k, v in type_severity.items()},
            "relationship_counts": dict(rel_counts),
            "top_entities": [{"type": t, "value": v, "severity": float(s or 0), "events": c}
                             for t, v, s, c, _ in nodes[:15]],
        }
    except Exception:
        return {"dataset": "correlation", "total_nodes": 0, "total_edges": 0}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Dataset: CRUD
# ═══════════════════════════════════════════════════════════════

def get_crud_chart_data(case_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT crud_type, target_object, sensitivity, volume_bytes, is_high_risk, actor, normalised_ts
            FROM crud_events
            WHERE run_id = (SELECT run_id FROM crud_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        type_counts = defaultdict(int)
        type_bytes = defaultdict(int)
        sens_counts = defaultdict(int)
        actor_ops = defaultdict(lambda: defaultdict(int))
        target_ops = defaultdict(lambda: defaultdict(int))

        for ctype, target, sens, vol, risk, actor, ts in rows:
            type_counts[ctype or "UNKNOWN"] += 1
            type_bytes[ctype or "UNKNOWN"] += (vol or 0)
            sens_counts[sens or "LOW"] += 1
            if actor:
                actor_ops[actor][ctype or "UNKNOWN"] += 1
            if target:
                target_ops[target][ctype or "UNKNOWN"] += 1

        return {
            "dataset": "crud",
            "total_events": len(rows),
            "high_risk_count": sum(1 for *_, r, _, _ in rows if r),
            "type_counts": dict(type_counts),
            "type_bytes": dict(type_bytes),
            "sensitivity_counts": dict(sens_counts),
            "top_actors": {k: dict(v) for k, v in sorted(actor_ops.items(), key=lambda x: -sum(x[1].values()))[:10]},
            "top_targets": {k: dict(v) for k, v in sorted(target_ops.items(), key=lambda x: -sum(x[1].values()))[:10]},
        }
    except Exception:
        return {"dataset": "crud", "total_events": 0}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Dataset: Network
# ═══════════════════════════════════════════════════════════════

def get_network_chart_data(case_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        flows = conn.execute("""
            SELECT direction, protocol, bytes_sent, bytes_received, is_suspicious, dst_ip, actor, normalised_ts
            FROM network_flows
            WHERE run_id = (SELECT run_id FROM network_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        dir_counts = defaultdict(int)
        proto_counts = defaultdict(int)
        hourly_volume = defaultdict(lambda: {"outbound": 0, "inbound": 0})
        top_dst = defaultdict(lambda: {"flows": 0, "bytes": 0})

        for direction, proto, sent, recv, susp, dst, actor, ts in flows:
            dir_counts[direction or "UNKNOWN"] += 1
            proto_counts[proto or "UNKNOWN"] += 1
            hour = str(ts)[:13] if ts else ""
            if direction == "OUTBOUND":
                hourly_volume[hour]["outbound"] += (sent or 0)
            else:
                hourly_volume[hour]["inbound"] += (recv or 0)
            if dst:
                top_dst[dst]["flows"] += 1
                top_dst[dst]["bytes"] += (sent or 0)

        exfil = conn.execute("""
            SELECT actor, dst_ip, confidence, bytes_network FROM exfil_candidates
            WHERE run_id = (SELECT run_id FROM network_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        return {
            "dataset": "network",
            "total_flows": len(flows),
            "suspicious_count": sum(1 for *_, s, _, _, _ in flows if s),
            "direction_counts": dict(dir_counts),
            "protocol_counts": dict(proto_counts),
            "hourly_volume": [{"time": h, **v} for h, v in sorted(hourly_volume.items())],
            "top_destinations": dict(sorted(top_dst.items(), key=lambda x: -x[1]["bytes"])[:15]),
            "exfil_candidates": [{"actor": a, "dst_ip": d, "confidence": float(c), "bytes": b} for a, d, c, b in exfil],
        }
    except Exception:
        return {"dataset": "network", "total_flows": 0}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Dataset: Depth
# ═══════════════════════════════════════════════════════════════

def get_depth_chart_data(case_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        row = conn.execute("""
            SELECT account_depth, system_depth, data_depth, control_depth, overall_severity, severity_label
            FROM depth_runs WHERE case_id=? AND status='COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()

        if not row:
            return {"dataset": "depth", "has_data": False}

        details = conn.execute("""
            SELECT dimension, metric_name, metric_value, max_value, evidence
            FROM depth_details
            WHERE run_id = (SELECT run_id FROM depth_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
        """, [case_id]).fetchall()

        dim_metrics = defaultdict(list)
        for dim, name, val, mx, ev in details:
            dim_metrics[dim].append({"name": name, "value": float(val or 0), "max": float(mx or 10)})

        return {
            "dataset": "depth",
            "has_data": True,
            "scores": {"account": float(row[0] or 0), "system": float(row[1] or 0),
                       "data": float(row[2] or 0), "control": float(row[3] or 0)},
            "overall_severity": float(row[4] or 0),
            "severity_label": row[5],
            "dimension_metrics": dict(dim_metrics),
        }
    except Exception:
        return {"dataset": "depth", "has_data": False}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Master: All datasets
# ═══════════════════════════════════════════════════════════════

def get_all_chart_data(case_id: str) -> dict:
    """Fetch all datasets in one call for the studio."""
    return {
        "timeline": get_timeline_chart_data(case_id),
        "anomaly": get_anomaly_chart_data(case_id),
        "correlation": get_correlation_chart_data(case_id),
        "crud": get_crud_chart_data(case_id),
        "network": get_network_chart_data(case_id),
        "depth": get_depth_chart_data(case_id),
    }


# ═══════════════════════════════════════════════════════════════
# Chart CRUD (save/load/list/delete)
# ═══════════════════════════════════════════════════════════════

def save_chart(case_id: str, chart_type: str, title: str,
               dataset: str, config: dict, data_snapshot: dict = None) -> dict:
    conn = open_vault(case_id)
    chart_id = str(uuid.uuid4())
    now = _now_iso()
    config_json = json.dumps(config)
    data_json = json.dumps(data_snapshot) if data_snapshot else "{}"
    hash_val = hash_records([{"chart_id": chart_id, "config": config_json[:500]}])
    try:
        conn.execute("""
            INSERT INTO studio_charts (chart_id, case_id, chart_type, title, dataset, config_json, data_snapshot, hash_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [chart_id, case_id, chart_type, title, dataset, config_json, data_json, hash_val, now, now])

        record_coc_event(case_id=case_id, actor="studio", action="CHART_CREATED",
                         target_artefact=f"chart:{chart_id}", justification=f"Created {chart_type} chart: {title}",
                         hash_after=hash_val, details={"chart_id": chart_id, "type": chart_type, "dataset": dataset})

        return {"chart_id": chart_id, "hash_value": hash_val}
    finally:
        conn.close()


def list_charts(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT chart_id, chart_type, title, dataset, hash_value, created_at
            FROM studio_charts WHERE case_id=? ORDER BY created_at DESC
        """, [case_id]).fetchall()
        return [{"chart_id": r[0], "chart_type": r[1], "title": r[2], "dataset": r[3],
                 "hash_value": r[4], "created_at": str(r[5]) if r[5] else None} for r in rows]
    finally:
        conn.close()


def get_chart(case_id: str, chart_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        row = conn.execute("""
            SELECT chart_id, chart_type, title, dataset, config_json, data_snapshot, hash_value, created_at
            FROM studio_charts WHERE chart_id=? AND case_id=?
        """, [chart_id, case_id]).fetchone()
        if not row:
            return {"error": "Chart not found"}
        result = {"chart_id": row[0], "chart_type": row[1], "title": row[2], "dataset": row[3],
                  "hash_value": row[6], "created_at": str(row[7]) if row[7] else None}
        try:
            result["config"] = json.loads(row[4]) if row[4] else {}
        except Exception:
            result["config"] = {}
        try:
            result["data_snapshot"] = json.loads(row[5]) if row[5] else {}
        except Exception:
            result["data_snapshot"] = {}
        return result
    finally:
        conn.close()


def delete_chart(case_id: str, chart_id: str) -> dict:
    conn = open_vault(case_id)
    try:
        conn.execute("DELETE FROM studio_charts WHERE chart_id=? AND case_id=?", [chart_id, case_id])
        record_coc_event(case_id=case_id, actor="studio", action="CHART_DELETED",
                         target_artefact=f"chart:{chart_id}", justification="Chart deleted by investigator")
        return {"deleted": chart_id}
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════
# Dynamic Widget Refresh
# ═══════════════════════════════════════════════════════════════

def get_refreshed_widget_data(case_id: str, widget_type: str, filters: dict) -> dict:
    """
    Regenerates payload slices dynamically for canvas widgets 
    (Phase 2 Server-Side Render Strategy).
    """
    topN = filters.get("topN", 10)
    # Based on the widget type, we call the appropriate dataset and apply bounds.
    # In a full rollout, this queries duckdb directly with LIMIT topN
    
    if widget_type == 'anomaly' or widget_type == 'shap-explanation':
        full_data = get_anomaly_chart_data(case_id)
        # Apply truncation equivalent logic that was previously in Next.js
        return full_data

    elif widget_type == 'chart' or widget_type.startswith('timeline'):
        full_data = get_timeline_chart_data(case_id)
        # For simplicity during bridging, return full object, and let RightInspector 
        # seamlessly transition. Ideally, pass LIMIT filters directly to DB here.
        return full_data

    # Pass through other types for now
    return get_all_chart_data(case_id)
