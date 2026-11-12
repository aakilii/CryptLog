"""
Report Studio — Unified Module Insight Aggregator.

Provides a single service that extracts actionable insights from all 7 investigative
modules for the AI Writer Agent. Includes summary statistics, key findings, and
narrative-ready data points.

Each module insight includes:
- summary: High-level metrics for quick reference
- key_findings: Top discoveries for AI narrative generation
- chart_data: Pre-aggregated data for visualization
- evidence_refs: Hash-backed references for citations
"""

import json
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, Any, List
from collections import defaultdict

from operation_room.database import open_vault
from operation_room.services.studio_service import (
    get_timeline_chart_data, get_anomaly_chart_data, get_correlation_chart_data,
    get_crud_chart_data, get_network_chart_data, get_depth_chart_data,
)

# Oracle 26AI Open-Source Alternatives - Validation & Evidence Services
try:
    from operation_room.services.validation_memory import get_validation_memory
    from operation_room.services.evidence_vault import get_evidence_vault
    MEMORY_SERVICES_AVAILABLE = True
except ImportError:
    MEMORY_SERVICES_AVAILABLE = False

logger = logging.getLogger(__name__)

# Memory service caches (per-case)
_validation_memory_cache: Dict[str, Any] = {}
_evidence_vault_cache: Dict[str, Any] = {}

def _get_validation_memory(case_id: str):
    """Get or create ValidationMemory for case."""
    if not MEMORY_SERVICES_AVAILABLE:
        return None
    if case_id not in _validation_memory_cache:
        try:
            _validation_memory_cache[case_id] = get_validation_memory(case_id)
        except Exception as e:
            logger.debug(f"ValidationMemory unavailable for {case_id}: {e}")
            return None
    return _validation_memory_cache[case_id]

def _get_evidence_vault_service(case_id: str):
    """Get or create EvidenceVault for case."""
    if not MEMORY_SERVICES_AVAILABLE:
        return None
    if case_id not in _evidence_vault_cache:
        try:
            _evidence_vault_cache[case_id] = get_evidence_vault(case_id)
        except Exception as e:
            logger.debug(f"EvidenceVault unavailable for {case_id}: {e}")
            return None
    return _evidence_vault_cache[case_id]

# TTL Cache for aggregated insights (Phase 5 Performance)
_INSIGHTS_CACHE: Dict[str, Tuple[float, dict]] = {}
INSIGHTS_TTL_SECONDS = 120.0  # 2 minutes bounded TTL

def clear_insights_cache(case_id: str):
    """Invalidate insights TTL cache for a case."""
    if case_id in _INSIGHTS_CACHE:
        del _INSIGHTS_CACHE[case_id]

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_data(data: dict) -> str:
    """SHA-256 hash of data for integrity verification."""
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str).encode('utf-8')
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE INSIGHT EXTRACTORS
# ═══════════════════════════════════════════════════════════════════════════════

def get_case_insight(case_id: str) -> dict:
    """Extract case metadata and evidence integrity info."""
    conn = open_vault(case_id)
    try:
        # Case metadata - using canonical case_metadata table
        case_row = conn.execute("""
            SELECT case_id, title, description, status, created_at, lead_investigator
            FROM case_metadata WHERE case_id = ? LIMIT 1
        """, [case_id]).fetchone()
        
        # Evidence hashes - using canonical column names: artefact_name, created_at
        evidence_rows = conn.execute("""
            SELECT artefact_name, hash_algorithm, hash_value, created_at
            FROM evidence_hashes ORDER BY created_at DESC
        """).fetchall()
        
        # Chain of custody summary
        coc_count = conn.execute("SELECT COUNT(*) FROM chain_of_custody").fetchone()[0]
        coc_recent = conn.execute("""
            SELECT timestamp, actor, action, target_artefact
            FROM chain_of_custody ORDER BY timestamp DESC LIMIT 5
        """).fetchall()
        
        summary = {
            "case_name": case_row[1] if case_row else "Unknown Case",
            "status": case_row[3] if case_row else "UNKNOWN",
            "investigator": case_row[5] if case_row else "Unknown",
            "evidence_files": len(evidence_rows),
            "coc_events": coc_count,
        }
        
        key_findings = []
        if evidence_rows:
            key_findings.append(f"{len(evidence_rows)} evidence files with verified SHA-256 hashes")
        if coc_count > 0:
            key_findings.append(f"{coc_count} chain-of-custody events recorded")
        
        return {
            "module": "case",
            "summary": summary,
            "key_findings": key_findings,
            "evidence_refs": [
                {"type": "evidence_hash", "path": r[0], "hash": f"{r[1]}:{r[2]}", "computed_at": str(r[3])}
                for r in evidence_rows[:10]
            ],
            "recent_coc": [
                {"timestamp": str(r[0]), "actor": r[1], "action": r[2], "target": r[3]}
                for r in coc_recent
            ],
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Case insight extraction failed: {e}")
        return {"module": "case", "summary": {}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_timeline_insight(case_id: str) -> dict:
    """Extract timeline insights with key events and patterns."""
    conn = open_vault(case_id)
    try:
        # Basic stats
        stats = conn.execute("""
            SELECT COUNT(*) as total,
                   MIN(normalised_ts) as first_event,
                   MAX(normalised_ts) as last_event,
                   COUNT(DISTINCT source_type) as sources,
                   COUNT(DISTINCT actor) as actors
            FROM unified_timeline WHERE case_id = ?
        """, [case_id]).fetchone()
        
        # Severity breakdown
        severity_rows = conn.execute("""
            SELECT severity, COUNT(*) as count
            FROM unified_timeline WHERE case_id = ?
            GROUP BY severity ORDER BY count DESC
        """, [case_id]).fetchall()
        
        # Peak activity (find hour with most events)
        peak = conn.execute("""
            SELECT strftime('%Y-%m-%d %H:00', normalised_ts) as hour, COUNT(*) as count
            FROM unified_timeline WHERE case_id = ?
            GROUP BY hour ORDER BY count DESC LIMIT 1
        """, [case_id]).fetchone()
        
        # Anchor events (significant markers)
        anchors = conn.execute("""
            SELECT normalised_ts, source_type, action, actor, severity, detail
            FROM unified_timeline
            WHERE case_id = ? AND (severity = 'CRITICAL' OR severity = 'HIGH')
            ORDER BY normalised_ts LIMIT 10
        """, [case_id]).fetchall()
        
        summary = {
            "total_events": stats[0] if stats else 0,
            "time_range": {
                "start": str(stats[1]) if stats and stats[1] else None,
                "end": str(stats[2]) if stats and stats[2] else None,
            },
            "unique_sources": stats[3] if stats else 0,
            "unique_actors": stats[4] if stats else 0,
            "peak_activity": {"hour": peak[0], "count": peak[1]} if peak else None,
            "severity_breakdown": {r[0]: r[1] for r in severity_rows},
        }
        
        key_findings = []
        if summary["total_events"] > 0:
            key_findings.append(f"{summary['total_events']:,} events across {summary['unique_sources']} log sources")
        if peak:
            key_findings.append(f"Peak activity: {peak[1]} events at {peak[0]}")
        
        crit_count = summary["severity_breakdown"].get("CRITICAL", 0)
        high_count = summary["severity_breakdown"].get("HIGH", 0)
        if crit_count > 0:
            key_findings.append(f"{crit_count} CRITICAL severity events detected")
        if high_count > 0:
            key_findings.append(f"{high_count} HIGH severity events detected")
        
        return {
            "module": "timeline",
            "summary": summary,
            "key_findings": key_findings,
            "anchor_events": [
                {"timestamp": str(a[0]), "source": a[1], "action": a[2], 
                 "actor": a[3], "severity": a[4]}
                for a in anchors
            ],
            "chart_data": get_timeline_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Timeline insight extraction failed: {e}")
        return {"module": "timeline", "summary": {}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_anomaly_insight(case_id: str) -> dict:
    """Extract anomaly detection insights with SHAP explanations."""
    conn = open_vault(case_id)
    try:
        # Get latest completed run
        run = conn.execute("""
            SELECT run_id, model_type, anomaly_count, contamination, completed_at
            FROM anomaly_runs WHERE case_id = ? AND status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()
        
        if not run:
            return {
                "module": "anomaly",
                "summary": {"has_data": False},
                "key_findings": ["No anomaly detection run completed"],
                "data_hash": _hash_data({}),
                "extracted_at": _now_iso(),
            }
        
        run_id, model_type, anom_count, contamination, comp_at = run
        
        # Anomaly statistics
        stats = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) as anomalies,
                   AVG(anomaly_score) as avg_score,
                   MAX(anomaly_score) as max_score
            FROM anomaly_scores WHERE run_id = ?
        """, [run_id]).fetchone()
        
        # Top anomalies with SHAP
        top_anomalies = conn.execute("""
            SELECT s.event_index, s.anomaly_score, s.top_feature_1, s.top_shap_1,
                   s.top_feature_2, s.top_shap_2, t.actor, t.action, t.source_type
            FROM anomaly_scores s
            LEFT JOIN unified_timeline t ON s.tl_event_id = t.tl_event_id
            WHERE s.run_id = ? AND s.is_anomaly = true
            ORDER BY s.anomaly_score DESC LIMIT 15
        """, [run_id]).fetchall()
        
        # Actor anomaly distribution
        actor_anomalies = conn.execute("""
            SELECT t.actor, COUNT(*) as count, AVG(s.anomaly_score) as avg_score
            FROM anomaly_scores s
            JOIN unified_timeline t ON s.tl_event_id = t.tl_event_id
            WHERE s.run_id = ? AND s.is_anomaly = true AND t.actor IS NOT NULL
            GROUP BY t.actor ORDER BY count DESC LIMIT 10
        """, [run_id]).fetchall()
        
        summary = {
            "has_data": True,
            "model_type": model_type,
            "total_scored": stats[0],
            "anomaly_count": anom_count or stats[1],
            "contamination": contamination,
            "avg_score": round(float(stats[2] or 0), 4),
            "max_score": round(float(stats[3] or 0), 4),
            "completed_at": str(comp_at),
        }
        
        key_findings = []
        anomaly_rate = (summary["anomaly_count"] / summary["total_scored"] * 100) if summary["total_scored"] > 0 else 0
        key_findings.append(f"{summary['anomaly_count']} anomalies detected ({anomaly_rate:.1f}% of events)")
        
        if top_anomalies:
            top = top_anomalies[0]
            key_findings.append(f"Highest anomaly score: {top[1]:.3f} (event {top[0]})")
            if top[2]:  # SHAP feature
                key_findings.append(f"Top contributing feature: {top[2]} (SHAP: {top[3]:.3f})")
        
        if actor_anomalies:
            top_actor = actor_anomalies[0]
            key_findings.append(f"Most anomalous actor: {top_actor[0]} ({top_actor[1]} anomalies)")
        
        return {
            "module": "anomaly",
            "summary": summary,
            "key_findings": key_findings,
            "top_anomalies": [
                {
                    "event_index": a[0], "score": round(float(a[1]), 4),
                    "shap_features": [
                        {"feature": a[2], "contribution": round(float(a[3] or 0), 4)} if a[2] else None,
                        {"feature": a[4], "contribution": round(float(a[5] or 0), 4)} if a[4] else None,
                    ],
                    "actor": a[6], "action": a[7], "source": a[8],
                }
                for a in top_anomalies
            ],
            "actor_distribution": [
                {"actor": a[0], "count": a[1], "avg_score": round(float(a[2]), 4)}
                for a in actor_anomalies
            ],
            "chart_data": get_anomaly_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Anomaly insight extraction failed: {e}")
        return {"module": "anomaly", "summary": {"has_data": False}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_correlation_insight(case_id: str) -> dict:
    """Extract correlation & RCA insights with MITRE ATT&CK mapping."""
    conn = open_vault(case_id)
    try:
        # Latest run - using canonical column names: total_nodes, total_edges
        run = conn.execute("""
            SELECT run_id, total_nodes, total_edges, params_json,
                   (SELECT narrative_text FROM impact_narratives WHERE run_id = correlation_runs.run_id LIMIT 1) as narrative,
                   completed_at
            FROM correlation_runs WHERE case_id = ? AND status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()
        
        if not run:
            return {
                "module": "correlation",
                "summary": {"has_data": False},
                "key_findings": ["No correlation analysis completed"],
                "data_hash": _hash_data({}),
                "extracted_at": _now_iso(),
            }
        
        run_id = run[0]
        
        # Entity breakdown
        entity_types = conn.execute("""
            SELECT entity_type, COUNT(*) as count, AVG(severity_score) as avg_sev
            FROM correlation_nodes WHERE run_id = ?
            GROUP BY entity_type ORDER BY count DESC
        """, [run_id]).fetchall()
        
        # High-severity entities
        high_sev_entities = conn.execute("""
            SELECT entity_type, entity_value, severity_score, event_count
            FROM correlation_nodes WHERE run_id = ? AND severity_score >= 0.7
            ORDER BY severity_score DESC LIMIT 10
        """, [run_id]).fetchall()
        
        # Relationship types
        relationships = conn.execute("""
            SELECT relationship, COUNT(*) as count
            FROM correlation_edges WHERE run_id = ?
            GROUP BY relationship ORDER BY count DESC LIMIT 10
        """, [run_id]).fetchall()
        
        # Parse MITRE tactics
        mitre_tactics = []
        if run[3]:
            try:
                if isinstance(run[3], str):
                    params = json.loads(run[3]) if run[3].strip().startswith("{") else {}
                elif isinstance(run[3], dict):
                    params = run[3]
                else:
                    params = {}
                raw_tactics = params.get("mitre_tactics", [])
                if isinstance(raw_tactics, str):
                    mitre_tactics = [t.strip() for t in raw_tactics.split(",") if t.strip()]
                elif isinstance(raw_tactics, list):
                    mitre_tactics = [str(t) for t in raw_tactics if t]
            except Exception:
                pass
        
        summary = {
            "has_data": True,
            "node_count": run[1],  # total_nodes from canonical schema
            "edge_count": run[2],  # total_edges from canonical schema
            "mitre_tactics": mitre_tactics,
            "has_narrative": bool(run[4]),
            "completed_at": str(run[5]),
            "entity_type_counts": {r[0]: r[1] for r in entity_types},
        }
        
        key_findings = []
        key_findings.append(f"Entity graph: {summary['node_count']} nodes, {summary['edge_count']} edges")
        
        if mitre_tactics:
            key_findings.append(f"MITRE ATT&CK tactics detected: {', '.join(mitre_tactics[:5])}")
        
        if high_sev_entities:
            top = high_sev_entities[0]
            key_findings.append(f"Highest risk entity: {top[0]}:{top[1]} (severity: {top[2]:.2f})")
        
        for et, count, avg_sev in entity_types[:3]:
            key_findings.append(f"{count} {et} entities identified (avg severity: {avg_sev:.2f})")
        
        return {
            "module": "correlation",
            "summary": summary,
            "key_findings": key_findings,
            "ai_narrative": run[4] if run[4] else None,
            "high_severity_entities": [
                {"type": e[0], "value": e[1], "severity": round(float(e[2]), 3), "events": e[3]}
                for e in high_sev_entities
            ],
            "relationships": [{"type": r[0], "count": r[1]} for r in relationships],
            "chart_data": get_correlation_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Correlation insight extraction failed: {e}")
        return {"module": "correlation", "summary": {"has_data": False}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_crud_insight(case_id: str) -> dict:
    """Extract CRUD & data access insights with sensitivity analysis."""
    conn = open_vault(case_id)
    try:
        # Latest run - using canonical column name: total_events (not event_count)
        run = conn.execute("""
            SELECT run_id, total_events, high_risk_count, completed_at
            FROM crud_runs WHERE case_id = ? AND status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()
        
        if not run:
            return {
                "module": "crud",
                "summary": {"has_data": False},
                "key_findings": ["No CRUD analysis completed"],
                "data_hash": _hash_data({}),
                "extracted_at": _now_iso(),
            }
        
        run_id = run[0]
        
        # CRUD type breakdown
        crud_types = conn.execute("""
            SELECT crud_type, COUNT(*) as count, SUM(volume_bytes) as total_bytes
            FROM crud_events WHERE run_id = ?
            GROUP BY crud_type ORDER BY count DESC
        """, [run_id]).fetchall()
        
        # Sensitivity breakdown
        sensitivity = conn.execute("""
            SELECT sensitivity, COUNT(*) as count
            FROM crud_events WHERE run_id = ?
            GROUP BY sensitivity ORDER BY count DESC
        """, [run_id]).fetchall()
        
        # High-risk events
        high_risk = conn.execute("""
            SELECT actor, target_object, crud_type, sensitivity, volume_bytes, normalised_ts
            FROM crud_events WHERE run_id = ? AND is_high_risk = true
            ORDER BY normalised_ts DESC LIMIT 15
        """, [run_id]).fetchall()
        
        # Top actors by activity
        actors = conn.execute("""
            SELECT actor, COUNT(*) as ops, SUM(volume_bytes) as total_bytes,
                   SUM(CASE WHEN is_high_risk THEN 1 ELSE 0 END) as high_risk
            FROM crud_events WHERE run_id = ? AND actor IS NOT NULL
            GROUP BY actor ORDER BY high_risk DESC, ops DESC LIMIT 10
        """, [run_id]).fetchall()
        
        summary = {
            "has_data": True,
            "total_events": run[1],
            "high_risk_count": run[2],
            "completed_at": str(run[3]),
            "crud_breakdown": {r[0]: {"count": r[1], "bytes": r[2] or 0} for r in crud_types},
            "sensitivity_breakdown": {r[0]: r[1] for r in sensitivity},
        }
        
        key_findings = []
        key_findings.append(f"{summary['total_events']} data access events analyzed")
        
        if summary["high_risk_count"] > 0:
            key_findings.append(f"⚠️ {summary['high_risk_count']} HIGH RISK data access events detected")
        
        sens_critical = summary["sensitivity_breakdown"].get("CRITICAL", 0) + summary["sensitivity_breakdown"].get("TOP_SECRET", 0)
        if sens_critical > 0:
            key_findings.append(f"{sens_critical} operations on CRITICAL/TOP SECRET data")
        
        delete_count = summary["crud_breakdown"].get("DELETE", {}).get("count", 0)
        if delete_count > 0:
            key_findings.append(f"{delete_count} DELETE operations detected")
        
        if actors:
            top_actor = actors[0]
            key_findings.append(f"Most active actor: {top_actor[0]} ({top_actor[1]} operations, {top_actor[3]} high-risk)")
        
        return {
            "module": "crud",
            "summary": summary,
            "key_findings": key_findings,
            "high_risk_events": [
                {
                    "actor": h[0], "target": h[1], "operation": h[2],
                    "sensitivity": h[3], "bytes": h[4], "timestamp": str(h[5])
                }
                for h in high_risk
            ],
            "actor_activity": [
                {"actor": a[0], "operations": a[1], "bytes": a[2] or 0, "high_risk": a[3]}
                for a in actors
            ],
            "chart_data": get_crud_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] CRUD insight extraction failed: {e}")
        return {"module": "crud", "summary": {"has_data": False}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_network_insight(case_id: str) -> dict:
    """Extract network & exfiltration insights."""
    conn = open_vault(case_id)
    try:
        # Latest run - using canonical column names: total_flows, exfil_candidates
        run = conn.execute("""
            SELECT run_id, total_flows, suspicious_count, exfil_candidates, completed_at
            FROM network_runs WHERE case_id = ? AND status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()
        
        if not run:
            return {
                "module": "network",
                "summary": {"has_data": False},
                "key_findings": ["No network analysis completed"],
                "data_hash": _hash_data({}),
                "extracted_at": _now_iso(),
            }
        
        run_id = run[0]
        
        # Traffic statistics
        traffic = conn.execute("""
            SELECT SUM(bytes_sent) as total_out, SUM(bytes_received) as total_in,
                   COUNT(DISTINCT dst_ip) as unique_destinations,
                   COUNT(DISTINCT actor) as unique_actors
            FROM network_flows WHERE run_id = ?
        """, [run_id]).fetchone()
        
        # Protocol breakdown
        protocols = conn.execute("""
            SELECT protocol, COUNT(*) as count, SUM(bytes_sent + bytes_received) as total_bytes
            FROM network_flows WHERE run_id = ?
            GROUP BY protocol ORDER BY total_bytes DESC LIMIT 10
        """, [run_id]).fetchall()
        
        # Exfiltration candidates
        exfil = conn.execute("""
            SELECT e.actor, e.dst_ip, e.bytes_network, e.confidence, ds.threat_intel
            FROM exfil_candidates e
            LEFT JOIN destination_summary ds
              ON ds.run_id = e.run_id AND ds.dst_ip = e.dst_ip
            WHERE e.run_id = ?
            ORDER BY e.confidence DESC LIMIT 10
        """, [run_id]).fetchall()
        
        # Suspicious destinations
        suspicious_dests = conn.execute("""
            SELECT dst_ip, COUNT(*) as connections, SUM(bytes_sent) as bytes_out
            FROM network_flows WHERE run_id = ? AND is_suspicious = true
            GROUP BY dst_ip ORDER BY bytes_out DESC LIMIT 10
        """, [run_id]).fetchall()
        
        summary = {
            "has_data": True,
            "flow_count": run[1],  # total_flows from canonical schema
            "suspicious_count": run[2],
            "exfil_candidate_count": run[3],  # exfil_candidates from canonical schema
            "completed_at": str(run[4]),
            "bytes_outbound": traffic[0] or 0,
            "bytes_inbound": traffic[1] or 0,
            "unique_destinations": traffic[2] or 0,
            "unique_actors": traffic[3] or 0,
            "protocol_breakdown": {p[0]: {"count": p[1], "bytes": p[2] or 0} for p in protocols},
        }
        
        key_findings = []
        key_findings.append(f"{summary['flow_count']} network flows analyzed")
        
        if summary["suspicious_count"] > 0:
            key_findings.append(f"⚠️ {summary['suspicious_count']} suspicious network flows detected")
        
        if summary["exfil_candidate_count"] > 0:
            key_findings.append(f"🚨 {summary['exfil_candidate_count']} potential data exfiltration events")
        
        # Format bytes
        bytes_out_mb = summary["bytes_outbound"] / (1024 * 1024) if summary["bytes_outbound"] else 0
        if bytes_out_mb > 100:
            key_findings.append(f"Total outbound traffic: {bytes_out_mb:.1f} MB")
        
        if exfil:
            top_exfil = exfil[0]
            key_findings.append(f"Top exfil candidate: {top_exfil[0]} → {top_exfil[1]} ({top_exfil[2] or 0} bytes, {top_exfil[3]:.0%} confidence)")
        
        return {
            "module": "network",
            "summary": summary,
            "key_findings": key_findings,
            "exfil_candidates": [
                {
                    "actor": e[0], "destination": e[1], "bytes": e[2] or 0,
                    "confidence": round(float(e[3]), 3) if e[3] else 0,
                    "threat_intel": e[4], "geo": None,
                }
                for e in exfil
            ],
            "suspicious_destinations": [
                {"ip": s[0], "connections": s[1], "bytes_out": s[2] or 0}
                for s in suspicious_dests
            ],
            "chart_data": get_network_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Network insight extraction failed: {e}")
        return {"module": "network", "summary": {"has_data": False}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


def get_depth_insight(case_id: str) -> dict:
    """Extract depth & impact assessment insights."""
    conn = open_vault(case_id)
    try:
        # Latest run - canonical schema doesn't have business_impact column
        # Get business impact from impact_narratives table instead
        run = conn.execute("""
            SELECT run_id, account_depth, system_depth, data_depth, control_depth,
                   overall_severity, severity_label, completed_at
            FROM depth_runs WHERE case_id = ? AND status = 'COMPLETED'
            ORDER BY completed_at DESC LIMIT 1
        """, [case_id]).fetchone()
        
        if not run:
            return {
                "module": "depth",
                "summary": {"has_data": False},
                "key_findings": ["No depth assessment completed"],
                "data_hash": _hash_data({}),
                "extracted_at": _now_iso(),
            }
        
        run_id = run[0]
        
        # Dimension details
        details = conn.execute("""
            SELECT dimension, metric_name, metric_value, max_value, evidence
            FROM depth_details WHERE run_id = ?
            ORDER BY dimension, metric_value DESC
        """, [run_id]).fetchall()
        
        dim_metrics = defaultdict(list)
        for dim, name, val, max_val, evidence in details:
            dim_metrics[dim].append({
                "metric": name,
                "value": round(float(val or 0), 3),
                "max": float(max_val or 10),
                "evidence": evidence,
            })
        
        # Get business impact from impact_narratives table (canonical location)
        business_impact = None
        narrative_row = conn.execute("""
            SELECT narrative_text, executive_summary
            FROM impact_narratives WHERE run_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, [run_id]).fetchone()
        
        if narrative_row:
            business_impact = {
                "narrative": narrative_row[0],
                "executive_summary": narrative_row[1]
            }
        
        summary = {
            "has_data": True,
            "scores": {
                "account": round(float(run[1] or 0), 3),
                "system": round(float(run[2] or 0), 3),
                "data": round(float(run[3] or 0), 3),
                "control": round(float(run[4] or 0), 3),
            },
            "overall_severity": round(float(run[5] or 0), 3),
            "severity_label": run[6],
            "completed_at": str(run[7]),
        }
        
        key_findings = []
        key_findings.append(f"Overall severity: {summary['severity_label']} ({summary['overall_severity']:.1%})")
        
        # Find highest dimension
        max_dim = max(summary["scores"].items(), key=lambda x: x[1])
        key_findings.append(f"Deepest penetration: {max_dim[0].upper()} dimension ({max_dim[1]:.1%})")
        
        # Critical thresholds
        for dim, score in summary["scores"].items():
            if score >= 0.8:
                key_findings.append(f"🚨 CRITICAL {dim.upper()} compromise ({score:.1%})")
            elif score >= 0.6:
                key_findings.append(f"⚠️ SIGNIFICANT {dim.upper()} compromise ({score:.1%})")
        
        if business_impact:
            if isinstance(business_impact, dict):
                for impact_type, value in list(business_impact.items())[:2]:
                    key_findings.append(f"Business impact ({impact_type}): {value}")
        
        return {
            "module": "depth",
            "summary": summary,
            "key_findings": key_findings,
            "dimension_details": dict(dim_metrics),
            "business_impact": business_impact,
            "chart_data": get_depth_chart_data(case_id),
            "data_hash": _hash_data(summary),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"[ReportStudio] Depth insight extraction failed: {e}")
        return {"module": "depth", "summary": {"has_data": False}, "key_findings": [], "error": str(e)}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_insights(case_id: str, validate_claims: bool = False) -> dict:
    """
    Aggregate insights from all 7 modules into a single response.
    This is the main entry point for the Report Studio and Writer Agent.
    
    Args:
        case_id: Case identifier
        validate_claims: If True, validate key findings using Oracle 26AI memory
    """
    # Phase 5: Fast Path - TTL Caching
    now = time.time()
    cache_key = f"{case_id}_{validate_claims}"
    if cache_key in _INSIGHTS_CACHE:
        timestamp, cached_data = _INSIGHTS_CACHE[cache_key]
        if now - timestamp < INSIGHTS_TTL_SECONDS:
            logger.info(f"[Cache Hit] get_all_insights for {case_id}")
            return cached_data
    
    logger.info(f"[Cache Miss] Generating full insights payload for {case_id}")

    insights = {
        "case_id": case_id,
        "extracted_at": _now_iso(),
        "modules": {
            "case": get_case_insight(case_id),
            "timeline": get_timeline_insight(case_id),
            "anomaly": get_anomaly_insight(case_id),
            "correlation": get_correlation_insight(case_id),
            "crud": get_crud_insight(case_id),
            "network": get_network_insight(case_id),
            "depth": get_depth_insight(case_id),
        }
    }
    
    # Compute combined key findings (top 5 from each module)
    all_findings = []
    priority_order = ["depth", "anomaly", "network", "correlation", "crud", "timeline", "case"]
    
    for module in priority_order:
        module_findings = insights["modules"].get(module, {}).get("key_findings", [])
        for finding in module_findings[:3]:
            all_findings.append({"module": module, "finding": finding})
    
    insights["combined_findings"] = all_findings[:15]

    # Compute overall integrity hash
    insights["integrity_hash"] = _hash_data({
        m: insights["modules"][m].get("data_hash", "")
        for m in insights["modules"]
    })
    
    # Oracle 26AI: Validate claims across all modules (advisory only)
    if validate_claims:
        validation_mem = _get_validation_memory(case_id)
        if validation_mem:
            try:
                validation_warnings = []
                for module_name, module_data in insights["modules"].items():
                    key_findings = module_data.get("key_findings", [])
                    for finding in key_findings:
                        if isinstance(finding, str) and len(finding) > 20:
                            # Track claim for validation
                            result = validation_mem.extract_and_validate_section(
                                section_text=finding,
                                section_name=module_name
                            )
                            if result.get("unsupported_claims"):
                                validation_warnings.extend([
                                    {"module": module_name, "claim": c.get("text", c), "status": "unsupported"}
                                    for c in result["unsupported_claims"][:2]
                                ])
                
                insights["validation"] = {
                    "checked": True,
                    "warnings_count": len(validation_warnings),
                    "warnings": validation_warnings[:10],  # Top 10
                    "advisory": True  # Flag but don't block
                }
            except Exception as e:
                logger.debug(f"Claim validation failed: {e}")
                insights["validation"] = {"checked": False, "error": str(e)}

    _INSIGHTS_CACHE[cache_key] = (time.time(), insights)
    return insights


def get_module_insight(case_id: str, module: str) -> dict:
    """Get insight for a specific module."""
    extractors = {
        "case": get_case_insight,
        "timeline": get_timeline_insight,
        "anomaly": get_anomaly_insight,
        "correlation": get_correlation_insight,
        "crud": get_crud_insight,
        "network": get_network_insight,
        "depth": get_depth_insight,
    }
    
    if module not in extractors:
        return {"error": f"Unknown module: {module}", "available": list(extractors.keys())}
    
    return extractors[module](case_id)


def get_writer_context(case_id: str, section_type: str, 
                       selected_modules: list[str] = None) -> dict:
    """
    Get context specifically formatted for the Writer Agent.
    Includes only relevant insights based on section type.
    """
    section_module_map = {
        "executive_summary": ["depth", "anomaly", "correlation", "network"],
        "case_overview": ["case", "timeline"],
        "timeline_narrative": ["timeline", "anomaly"],
        "anomaly_findings": ["anomaly"],
        "attack_chain": ["correlation", "anomaly"],
        "data_access": ["crud"],
        "network_activity": ["network"],
        "depth_assessment": ["depth"],
        "remediation": ["depth", "anomaly", "correlation", "network", "crud"],
        "chain_of_custody": ["case"],
    }
    
    # Use provided modules or section defaults (fallback to all available modules, not section keys)
    if selected_modules:
        modules = selected_modules
    elif section_type in section_module_map:
        modules = section_module_map[section_type]
    else:
        # Fallback: all available module names
        modules = ["case", "timeline", "anomaly", "crud", "network", "correlation", "depth"]
    
    context = {
        "case_id": case_id,
        "section_type": section_type,
        "extracted_at": _now_iso(),
        "modules": {},
    }
    
    for module in modules:
        insight = get_module_insight(case_id, module)
        if not insight.get("error"):
            context["modules"][module] = {
                "summary": insight.get("summary", {}),
                "key_findings": insight.get("key_findings", []),
            }
            # Include additional relevant data based on section
            if section_type == "anomaly_findings" and module == "anomaly":
                context["modules"][module]["top_anomalies"] = insight.get("top_anomalies", [])
            elif section_type == "attack_chain" and module == "correlation":
                context["modules"][module]["ai_narrative"] = insight.get("ai_narrative")
                context["modules"][module]["high_severity_entities"] = insight.get("high_severity_entities", [])
            elif section_type == "network_activity" and module == "network":
                context["modules"][module]["exfil_candidates"] = insight.get("exfil_candidates", [])
            elif section_type == "data_access" and module == "crud":
                context["modules"][module]["high_risk_events"] = insight.get("high_risk_events", [])
    
    return context


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-MODULE CORRELATION QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_anomaly_timeline_correlation(case_id: str, time_window_minutes: int = 15) -> dict:
    """
    Correlate anomalies with timeline events that occurred within a time window.
    This helps investigators see what normal events happened around anomaly detection.
    
    Returns events before/during/after each anomaly for context.
    """
    conn = open_vault(case_id)
    try:
        # Get all detected anomalies
        anomalies = conn.execute("""
            SELECT row_id, timestamp, entity, anomaly_type, score, explanation
            FROM anomaly_scores 
            WHERE score > 0.5
            ORDER BY score DESC
            LIMIT 50
        """).fetchall()
        
        if not anomalies:
            return {"correlations": [], "message": "No significant anomalies found"}
        
        correlations = []
        for anomaly in anomalies:
            anomaly_time = anomaly[1]
            
            # Find timeline events within the time window
            related_events = conn.execute("""
                SELECT timestamp, source, event_type, actor, action, target, raw_log
                FROM unified_timeline
                WHERE timestamp BETWEEN datetime(?, '-? minutes') AND datetime(?, '+? minutes')
                ORDER BY timestamp
                LIMIT 20
            """, [anomaly_time, time_window_minutes, anomaly_time, time_window_minutes]).fetchall()
            
            correlations.append({
                "anomaly": {
                    "id": anomaly[0],
                    "timestamp": anomaly_time,
                    "entity": anomaly[2],
                    "type": anomaly[3],
                    "score": anomaly[4],
                    "explanation": anomaly[5],
                },
                "timeline_context": [
                    {
                        "timestamp": e[0],
                        "source": e[1],
                        "event_type": e[2],
                        "actor": e[3],
                        "action": e[4],
                        "target": e[5],
                        "timing": "before" if e[0] < anomaly_time else ("during" if e[0] == anomaly_time else "after"),
                    }
                    for e in related_events
                ],
                "event_count": len(related_events),
            })
        
        return {
            "correlations": correlations,
            "total_anomalies": len(anomalies),
            "time_window_minutes": time_window_minutes,
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"Anomaly-timeline correlation failed: {e}")
        return {"correlations": [], "error": str(e)}
    finally:
        conn.close()


def get_network_crud_correlation(case_id: str) -> dict:
    """
    Correlate network exfiltration candidates with CRUD data access events.
    This reveals if data accessed was subsequently exfiltrated.
    
    Critical for data breach investigations.
    """
    conn = open_vault(case_id)
    try:
        # Get exfiltration candidates
        exfil = conn.execute("""
            SELECT src_ip, dst_ip, dst_port, bytes_out, packets, start_time, protocol
            FROM exfil_candidates
            ORDER BY bytes_out DESC
            LIMIT 30
        """).fetchall()
        
        # Get high-risk CRUD events (reads and exports)
        crud_events = conn.execute("""
            SELECT timestamp, actor, operation, object_type, object_id, risk_score, details
            FROM crud_events
            WHERE operation IN ('READ', 'EXPORT', 'DOWNLOAD', 'COPY') 
            AND risk_score >= 0.5
            ORDER BY timestamp DESC
            LIMIT 100
        """).fetchall()
        
        # Build correlation: match by time proximity and actor/IP overlap
        correlations = []
        for ex in exfil:
            src_ip = ex[0]
            exfil_time = ex[5]
            
            # Find CRUD events from similar time or by matching actor
            related_crud = [
                {
                    "timestamp": c[0],
                    "actor": c[1],
                    "operation": c[2],
                    "object_type": c[3],
                    "object_id": c[4],
                    "risk_score": c[5],
                }
                for c in crud_events
                if c[0] <= exfil_time  # CRUD event happened before exfil
            ][:10]  # Top 10 most recent
            
            if related_crud:
                correlations.append({
                    "exfiltration": {
                        "src_ip": src_ip,
                        "dst_ip": ex[1],
                        "dst_port": ex[2],
                        "bytes_out": ex[3],
                        "packets": ex[4],
                        "timestamp": exfil_time,
                        "protocol": ex[6],
                    },
                    "related_data_access": related_crud,
                    "potential_data_breach": len(related_crud) > 0,
                    "data_types_accessed": list(set(c["object_type"] for c in related_crud)),
                })
        
        return {
            "correlations": correlations,
            "total_exfil_candidates": len(exfil),
            "total_high_risk_crud": len(crud_events),
            "potential_breaches": sum(1 for c in correlations if c["potential_data_breach"]),
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"Network-CRUD correlation failed: {e}")
        return {"correlations": [], "error": str(e)}
    finally:
        conn.close()


def get_correlation_entity_timeline(case_id: str, entity_id: str = None) -> dict:
    """
    Get the complete activity timeline for an entity from the correlation graph.
    Shows all events involving a specific actor/asset across all modules.
    
    If no entity_id provided, returns top suspicious entities.
    """
    conn = open_vault(case_id)
    try:
        if entity_id:
            # Get all events for specific entity
            timeline_events = conn.execute("""
                SELECT timestamp, source, event_type, action, target, raw_log
                FROM unified_timeline
                WHERE actor = ? OR target = ?
                ORDER BY timestamp
            """, [entity_id, entity_id]).fetchall()
            
            anomalies = conn.execute("""
                SELECT timestamp, anomaly_type, score, explanation
                FROM anomaly_scores
                WHERE entity = ?
                ORDER BY timestamp
            """, [entity_id]).fetchall()
            
            crud_events = conn.execute("""
                SELECT timestamp, operation, object_type, object_id, risk_score
                FROM crud_events
                WHERE actor = ?
                ORDER BY timestamp
            """, [entity_id]).fetchall()
            
            return {
                "entity_id": entity_id,
                "timeline_events": [
                    {"timestamp": e[0], "source": e[1], "type": e[2], "action": e[3], "target": e[4]}
                    for e in timeline_events
                ],
                "anomalies": [
                    {"timestamp": a[0], "type": a[1], "score": a[2], "explanation": a[3]}
                    for a in anomalies
                ],
                "data_access": [
                    {"timestamp": c[0], "operation": c[1], "object": f"{c[2]}:{c[3]}", "risk": c[4]}
                    for c in crud_events
                ],
                "total_events": len(timeline_events) + len(anomalies) + len(crud_events),
            }
        else:
            # Get top suspicious entities from correlation
            entities = conn.execute("""
                SELECT entity_id, entity_type, label, severity, 
                       mitre_tactics, mitre_techniques
                FROM correlation_nodes
                WHERE severity >= 0.5
                ORDER BY severity DESC
                LIMIT 20
            """).fetchall()
            
            return {
                "top_entities": [
                    {
                        "id": e[0],
                        "type": e[1],
                        "label": e[2],
                        "severity": e[3],
                        "mitre_tactics": json.loads(e[4]) if e[4] else [],
                        "mitre_techniques": json.loads(e[5]) if e[5] else [],
                    }
                    for e in entities
                ],
                "total_suspicious": len(entities),
            }
    except Exception as e:
        logger.warning(f"Entity timeline correlation failed: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


def get_attack_chain_summary(case_id: str) -> dict:
    """
    Build a comprehensive attack chain narrative by correlating data across all modules.
    This is the CRITICAL view for investigators - shows the full attack story.
    
    Returns:
    - Initial access indicators
    - Lateral movement patterns
    - Data exfiltration evidence
    - Impact assessment
    """
    conn = open_vault(case_id)
    try:
        # Phase 1: Initial Access - First anomalies and unusual authentications
        initial_access = conn.execute("""
            SELECT timestamp, source, actor, action, target
            FROM unified_timeline
            WHERE event_type IN ('AUTH', 'LOGIN', 'AUTHENTICATION')
            ORDER BY timestamp
            LIMIT 10
        """).fetchall()
        
        first_anomaly = conn.execute("""
            SELECT timestamp, entity, anomaly_type, score, explanation
            FROM anomaly_scores
            ORDER BY timestamp
            LIMIT 1
        """).fetchone()
        
        # Phase 2: Lateral Movement - Entity relationships showing spread
        lateral_edges = conn.execute("""
            SELECT src_entity, relationship, dst_entity, weight, evidence_count
            FROM correlation_edges
            WHERE relationship IN ('accessed', 'connected_to', 'executed_on', 'moved_to')
            ORDER BY weight DESC
            LIMIT 20
        """).fetchall()
        
        # Phase 3: Data Access - What was touched
        sensitive_access = conn.execute("""
            SELECT timestamp, actor, operation, object_type, object_id, risk_score
            FROM crud_events
            WHERE risk_score >= 0.7
            ORDER BY risk_score DESC
            LIMIT 15
        """).fetchall()
        
        # Phase 4: Exfiltration - What left the network
        exfil = conn.execute("""
            SELECT src_ip, dst_ip, bytes_out, start_time, protocol
            FROM exfil_candidates
            ORDER BY bytes_out DESC
            LIMIT 10
        """).fetchall()
        
        # Phase 5: Impact - Depth assessment
        depth = conn.execute("""
            SELECT dimension, score, severity_label, details
            FROM depth_details
            ORDER BY score DESC
        """).fetchall()
        
        # Build attack narrative
        attack_phases = []
        
        if first_anomaly:
            attack_phases.append({
                "phase": "Initial Detection",
                "timestamp": first_anomaly[0],
                "description": f"First anomaly detected: {first_anomaly[2]} on {first_anomaly[1]}",
                "severity": first_anomaly[3],
                "details": first_anomaly[4],
            })
        
        if initial_access:
            attack_phases.append({
                "phase": "Initial Access",
                "timestamp": initial_access[0][0] if initial_access else None,
                "description": f"Authentication events from {len(set(e[2] for e in initial_access))} unique actors",
                "events": [
                    {"time": e[0], "actor": e[2], "action": e[3], "target": e[4]}
                    for e in initial_access[:5]
                ],
            })
        
        if lateral_edges:
            attack_phases.append({
                "phase": "Lateral Movement",
                "description": f"Detected {len(lateral_edges)} lateral movement indicators",
                "movements": [
                    {"from": e[0], "relation": e[1], "to": e[2], "strength": e[3]}
                    for e in lateral_edges[:10]
                ],
            })
        
        if sensitive_access:
            attack_phases.append({
                "phase": "Data Access",
                "description": f"High-risk access to {len(sensitive_access)} sensitive objects",
                "accesses": [
                    {"time": a[0], "actor": a[1], "op": a[2], "object": f"{a[3]}:{a[4]}", "risk": a[5]}
                    for a in sensitive_access[:10]
                ],
            })
        
        if exfil:
            total_bytes = sum(e[2] or 0 for e in exfil)
            attack_phases.append({
                "phase": "Data Exfiltration",
                "description": f"Potential exfiltration of {total_bytes:,} bytes to {len(set(e[1] for e in exfil))} destinations",
                "exfil_events": [
                    {"src": e[0], "dst": e[1], "bytes": e[2], "time": e[3], "protocol": e[4]}
                    for e in exfil[:5]
                ],
            })
        
        if depth:
            attack_phases.append({
                "phase": "Impact Assessment",
                "description": f"Impact across {len(depth)} dimensions",
                "dimensions": [
                    {"dimension": d[0], "score": d[1], "severity": d[2]}
                    for d in depth
                ],
            })
        
        return {
            "attack_chain": attack_phases,
            "total_phases": len(attack_phases),
            "first_indicator": first_anomaly[0] if first_anomaly else None,
            "latest_activity": max(
                (e[0] for e in exfil if e[3]) if exfil else [],
                default=None
            ),
            "summary": {
                "initial_access_events": len(initial_access),
                "lateral_movements": len(lateral_edges),
                "sensitive_accesses": len(sensitive_access),
                "exfil_candidates": len(exfil),
            },
            "extracted_at": _now_iso(),
        }
    except Exception as e:
        logger.warning(f"Attack chain summary failed: {e}")
        return {"attack_chain": [], "error": str(e)}
    finally:
        conn.close()


def get_all_cross_module_insights(case_id: str) -> dict:
    """
    Get all cross-module correlations in one call for the Writer Agent.
    This is the complete picture for report generation.
    """
    return {
        "case_id": case_id,
        "attack_chain": get_attack_chain_summary(case_id),
        "anomaly_timeline": get_anomaly_timeline_correlation(case_id),
        "network_data_correlation": get_network_crud_correlation(case_id),
        "top_entities": get_correlation_entity_timeline(case_id),
        "extracted_at": _now_iso(),
    }
