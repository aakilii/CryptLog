"""
Evidence Binding Service — Phase 2.

Provides predefined DuckDB queries for all 7 investigative modules.
Returns data + SHA-256 row hashes for evidence-bound report blocks.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _hash_rows(rows: list[dict]) -> str:
    """Hash a list of row dicts for tamper detection."""
    canonical = json.dumps(rows, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, default=str).encode('utf-8')
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ═══════════════════════════════════════════════════════════════
# Predefined Query Registry
# ═══════════════════════════════════════════════════════════════

PREDEFINED_QUERIES = {
    # ── Timeline Module ─────────────────────────────────────
    "timeline": {
        "events_by_hour": {
            "title": "Events by Hour",
            "description": "Count of events per hour from unified timeline",
            "sql": """
                SELECT strftime(timestamp, '%Y-%m-%d %H:00') as hour,
                       COUNT(*) as event_count,
                       COUNT(DISTINCT source_type) as sources
                FROM unified_timeline
                GROUP BY 1 ORDER BY 1
            """,
            "chart_type": "area",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "area", "interpolate": "monotone", "opacity": 0.7,
                         "color": "#2563eb"},
                "encoding": {
                    "x": {"field": "hour", "type": "temporal", "title": "Time"},
                    "y": {"field": "event_count", "type": "quantitative", "title": "Events"}
                }
            }
        },
        "severity_distribution": {
            "title": "Severity Distribution",
            "description": "Event count by severity level",
            "sql": """
                SELECT COALESCE(severity, 'UNKNOWN') as severity,
                       COUNT(*) as count
                FROM unified_timeline
                GROUP BY 1 ORDER BY count DESC
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4},
                "encoding": {
                    "x": {"field": "severity", "type": "nominal", "title": "Severity"},
                    "y": {"field": "count", "type": "quantitative", "title": "Count"},
                    "color": {"field": "severity", "type": "nominal",
                              "scale": {"domain": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN"],
                                        "range": ["#dc2626", "#ea580c", "#d97706", "#2563eb", "#64748b", "#94a3b8"]}}
                }
            }
        },
        "source_breakdown": {
            "title": "Events by Source Type",
            "description": "Event count by log source type",
            "sql": """
                SELECT source_type, COUNT(*) as count
                FROM unified_timeline
                GROUP BY 1 ORDER BY count DESC LIMIT 10
            """,
            "chart_type": "donut",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "arc", "innerRadius": 50},
                "encoding": {
                    "theta": {"field": "count", "type": "quantitative"},
                    "color": {"field": "source_type", "type": "nominal", "title": "Source"},
                }
            }
        },
    },

    # ── Anomaly Module ──────────────────────────────────────
    "anomaly": {
        "score_histogram": {
            "title": "Anomaly Score Distribution",
            "description": "Histogram of anomaly scores across events",
            "sql": """
                SELECT anomaly_score, event_index,
                       CASE WHEN is_anomaly THEN 'Anomalous' ELSE 'Normal' END as status
                FROM anomaly_scores
                ORDER BY anomaly_score DESC LIMIT 200
            """,
            "chart_type": "scatter",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "point", "filled": True, "size": 60},
                "encoding": {
                    "x": {"field": "event_index", "type": "quantitative", "title": "Event Index"},
                    "y": {"field": "anomaly_score", "type": "quantitative", "title": "Anomaly Score"},
                    "color": {"field": "status", "type": "nominal",
                              "scale": {"domain": ["Anomalous", "Normal"],
                                        "range": ["#dc2626", "#2563eb"]}}
                }
            }
        },
        "top_anomalies": {
            "title": "Top 20 Anomalies",
            "description": "Highest-scoring anomalous events",
            "sql": """
                SELECT event_index, anomaly_score,
                       COALESCE(top_feature_1, '') as feature_1,
                       COALESCE(top_shap_1, 0) as shap_1,
                       COALESCE(top_feature_2, '') as feature_2,
                       COALESCE(top_shap_2, 0) as shap_2
                FROM anomaly_scores
                WHERE is_anomaly = true
                ORDER BY anomaly_score DESC LIMIT 20
            """,
            "chart_type": "table",
            "vega_spec": None,
        },
    },

    # ── Correlation Module ──────────────────────────────────
    "correlation": {
        "entity_types": {
            "title": "Entity Type Distribution",
            "description": "Count of entities by type in correlation graph",
            "sql": """
                SELECT entity_type, COUNT(*) as count
                FROM correlation_nodes
                GROUP BY 1 ORDER BY count DESC
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#2563eb"},
                "encoding": {
                    "x": {"field": "entity_type", "type": "nominal", "title": "Entity Type"},
                    "y": {"field": "count", "type": "quantitative", "title": "Count"}
                }
            }
        },
        "edge_relationships": {
            "title": "Relationship Types",
            "description": "Edge count by relationship type",
            "sql": """
                SELECT relationship, COUNT(*) as count
                FROM correlation_edges
                GROUP BY 1 ORDER BY count DESC LIMIT 10
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#059669"},
                "encoding": {
                    "y": {"field": "relationship", "type": "nominal", "title": "Relationship", "sort": "-x"},
                    "x": {"field": "count", "type": "quantitative", "title": "Count"}
                }
            }
        },
        "graph_data": {
            "title": "Full Entity Graph",
            "description": "Nodes and edges for network graph rendering",
            "sql": "SELECT * FROM correlation_nodes LIMIT 100",
            "chart_type": "graph",
            "vega_spec": None,
        },
    },

    # ── CRUD Module ─────────────────────────────────────────
    "crud": {
        "operations_by_type": {
            "title": "CRUD Operation Distribution",
            "description": "Count of events by operation type (Create/Read/Update/Delete)",
            "sql": """
                SELECT operation_type, COUNT(*) as count
                FROM crud_events
                GROUP BY 1 ORDER BY count DESC
            """,
            "chart_type": "donut",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "arc", "innerRadius": 50},
                "encoding": {
                    "theta": {"field": "count", "type": "quantitative"},
                    "color": {"field": "operation_type", "type": "nominal",
                              "scale": {"domain": ["CREATE", "READ", "UPDATE", "DELETE"],
                                        "range": ["#059669", "#2563eb", "#d97706", "#dc2626"]}}
                }
            }
        },
        "sensitivity_breakdown": {
            "title": "Data Sensitivity Levels",
            "description": "Events by data sensitivity classification",
            "sql": """
                SELECT COALESCE(sensitivity_tag, 'UNCLASSIFIED') as sensitivity,
                       COUNT(*) as count
                FROM crud_events
                GROUP BY 1 ORDER BY count DESC
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4},
                "encoding": {
                    "x": {"field": "sensitivity", "type": "nominal", "title": "Sensitivity"},
                    "y": {"field": "count", "type": "quantitative", "title": "Count"},
                    "color": {"field": "sensitivity", "type": "nominal",
                              "scale": {"domain": ["TOP_SECRET", "SECRET", "CONFIDENTIAL", "INTERNAL", "UNCLASSIFIED"],
                                        "range": ["#dc2626", "#ea580c", "#d97706", "#2563eb", "#64748b"]}}
                }
            }
        },
        "ransomware_burst": {
            "title": "Ransomware File Encryption Burst",
            "description": "Rapid succession of DELETE and CREATE operations indicative of ransomware",
            "sql": """
                WITH file_activity AS (
                    SELECT 
                        time_bucket(INTERVAL '1 minute', CAST(timestamp AS TIMESTAMP)) AS minute,
                        operation_type,
                        COUNT(*) as op_count
                    FROM crud_events
                    WHERE operation_type IN ('DELETE', 'CREATE')
                    GROUP BY 1, 2
                )
                SELECT minute, operation_type, op_count
                FROM file_activity
                ORDER BY minute
            """,
            "chart_type": "area",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "title": "File Activity (Create vs Delete) per Minute",
                "width": "container",
                "height": "container",
                "mark": "area",
                "encoding": {
                    "x": {
                        "field": "minute",
                        "type": "temporal",
                        "title": "Time",
                        "axis": {"format": "%H:%M"}
                    },
                    "y": {
                        "field": "op_count",
                        "type": "quantitative",
                        "title": "Operations Count"
                    },
                    "color": {
                        "field": "operation_type",
                        "type": "nominal",
                        "scale": {"domain": ["CREATE", "DELETE"], "range": ["#10b981", "#ef4444"]}
                    }
                }
            }
        },
    },

    # ── Network Module ──────────────────────────────────────
    "network": {
        "bytes_by_protocol": {
            "title": "Traffic by Protocol",
            "description": "Total bytes transferred by protocol",
            "sql": """
                SELECT protocol, SUM(bytes_sent + bytes_received) as total_bytes,
                       COUNT(*) as flow_count
                FROM network_flows
                GROUP BY 1 ORDER BY total_bytes DESC LIMIT 10
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#2563eb"},
                "encoding": {
                    "y": {"field": "protocol", "type": "nominal", "title": "Protocol", "sort": "-x"},
                    "x": {"field": "total_bytes", "type": "quantitative", "title": "Total Bytes"}
                }
            }
        },
        "exfil_candidates": {
            "title": "Exfiltration Candidates",
            "description": "Top suspicious data transfer events",
            "sql": """
                SELECT destination_ip, total_bytes, session_count,
                       COALESCE(threat_label, 'Unknown') as threat,
                       risk_score
                FROM exfil_candidates
                ORDER BY risk_score DESC LIMIT 15
            """,
            "chart_type": "table",
            "vega_spec": None,
        },
        "destination_map": {
            "title": "Top Destinations by Bytes",
            "description": "Top 10 destination IPs by data volume",
            "sql": """
                SELECT destination_ip, SUM(bytes_sent) as bytes_out,
                       COUNT(*) as connections
                FROM network_flows
                GROUP BY 1 ORDER BY bytes_out DESC LIMIT 10
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#ea580c"},
                "encoding": {
                    "y": {"field": "destination_ip", "type": "nominal", "sort": "-x"},
                    "x": {"field": "bytes_out", "type": "quantitative", "title": "Bytes Sent"}
                }
            }
        },
    },

    # ── Depth Module ────────────────────────────────────────
    "depth": {
        "dimension_scores": {
            "title": "Penetration Dimension Scores",
            "description": "4D severity: account, system, data, and control",
            "sql": """
                SELECT COALESCE(target_entity, 'Overall') as entity,
                       account_score, system_score, data_score, control_score,
                       composite_score
                FROM depth_details
                ORDER BY composite_score DESC LIMIT 10
            """,
            "chart_type": "table",
            "vega_spec": None,
        },
        "composite_bar": {
            "title": "Composite Scores by Entity",
            "description": "Bar chart of composite penetration scores",
            "sql": """
                SELECT COALESCE(target_entity, 'Entity ' || ROWID) as entity,
                       composite_score
                FROM depth_details
                ORDER BY composite_score DESC LIMIT 10
            """,
            "chart_type": "bar",
            "vega_spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "mark": {"type": "bar", "cornerRadiusEnd": 4},
                "encoding": {
                    "y": {"field": "entity", "type": "nominal", "sort": "-x"},
                    "x": {"field": "composite_score", "type": "quantitative", "title": "Composite Score"},
                    "color": {"value": "#dc2626"}
                }
            }
        },
    },

    # ── Case/Evidence Module ────────────────────────────────
    "evidence": {
        "coc_timeline": {
            "title": "Chain of Custody Timeline",
            "description": "All CoC events in chronological order",
            "sql": """
                SELECT timestamp, actor, action, target_artefact,
                       COALESCE(hash_after, '') as hash
                FROM chain_of_custody
                ORDER BY timestamp DESC LIMIT 30
            """,
            "chart_type": "table",
            "vega_spec": None,
        },
        "evidence_hashes": {
            "title": "Evidence Integrity Status",
            "description": "All evidence file hashes",
            "sql": """
                SELECT file_path, hash_algorithm, hash_value,
                       computed_at
                FROM evidence_hashes
                ORDER BY computed_at DESC
            """,
            "chart_type": "table",
            "vega_spec": None,
        },
    },
}


def list_available_queries(module: str = None) -> list[dict]:
    """List available predefined queries, optionally filtered by module."""
    result = []
    modules = [module] if module else PREDEFINED_QUERIES.keys()
    for mod in modules:
        if mod not in PREDEFINED_QUERIES:
            continue
        for qid, q in PREDEFINED_QUERIES[mod].items():
            result.append({
                "module": mod,
                "query_id": qid,
                "title": q["title"],
                "description": q["description"],
                "chart_type": q["chart_type"],
                "has_vega_spec": q["vega_spec"] is not None,
            })
    return result


def execute_binding_query(case_id: str, module: str, query_id: str) -> dict:
    """Execute a predefined query and return data + integrity hash."""
    if module not in PREDEFINED_QUERIES:
        return {"error": f"Unknown module: {module}"}
    if query_id not in PREDEFINED_QUERIES[module]:
        return {"error": f"Unknown query: {query_id}"}

    q = PREDEFINED_QUERIES[module][query_id]
    conn = open_vault(case_id)

    try:
        result = conn.execute(q["sql"]).fetchall()
        columns = [desc[0] for desc in conn.description]
        rows = [dict(zip(columns, row)) for row in result]

        data_hash = _hash_rows(rows)

        return {
            "module": module,
            "query_id": query_id,
            "title": q["title"],
            "chart_type": q["chart_type"],
            "columns": columns,
            "data": rows,
            "row_count": len(rows),
            "data_hash": data_hash,
            "vega_spec": q["vega_spec"],
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"[Binding] Query failed: {module}/{query_id}: {e}")
        return {
            "module": module,
            "query_id": query_id,
            "title": q["title"],
            "data": [],
            "row_count": 0,
            "data_hash": "sha256:empty",
            "error": str(e),
        }
    finally:
        conn.close()


def verify_binding_hash(case_id: str, module: str, query_id: str,
                        expected_hash: str) -> dict:
    """Re-execute query and compare hash to detect tampering."""
    result = execute_binding_query(case_id, module, query_id)
    current_hash = result.get("data_hash", "")
    tampered = current_hash != expected_hash

    return {
        "module": module,
        "query_id": query_id,
        "expected_hash": expected_hash,
        "current_hash": current_hash,
        "tampered": tampered,
        "status": "TAMPERED" if tampered else "VERIFIED",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
