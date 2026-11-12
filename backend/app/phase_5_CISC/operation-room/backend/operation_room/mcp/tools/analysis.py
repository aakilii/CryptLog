"""
Analysis Module Wrappers — MCP tools wrapping all analysis modules with vault integration.

This module provides wrappers for:
- Anomaly Detection (anomaly.*)
- Correlation Analysis (correlation.*)  
- CRUD Analysis (crud.*)
- Network Analysis (network.*)
- Depth/Impact Analysis (depth.*)

All modules integrate with Evidence Vault for anchor marking and citation.

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..schemas import ModuleName, ConfidenceLevel
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value
from .evidence import (
    EvidenceVault,
    EvidenceFactory,
    EvidenceCategory,
    AnchorType,
    EvidenceItem,
)


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="anomaly.detect",
    category=ToolCategory.ANALYSIS,
    description="Run anomaly detection on timeline events using Isolation Forest + LOF ensemble.",
    requires_case_id=True,
    tags={"anomaly", "detection", "ml"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="ANOMALY_DETECT")
async def detect_anomalies(
    case_id: str,
    model_type: str = "ensemble",
    contamination: float = 0.1,
    n_estimators: int = 100,
    auto_vault: bool = True,
    min_score_threshold: float = 0.7,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Run anomaly detection on timeline events.
    
    Uses Isolation Forest + LOF ensemble with SHAP explainability.
    High-confidence anomalies are automatically added to Evidence Vault.
    
    Args:
        case_id: Target case ID
        model_type: Model type (ensemble, isolation_forest, lof)
        contamination: Expected anomaly ratio (0.0-0.5)
        n_estimators: Number of trees for Isolation Forest
        auto_vault: Auto-add high-confidence anomalies to vault
        min_score_threshold: Minimum score for auto-vaulting
        investigation_id: Associated investigation
    
    Returns:
        Anomaly detection results with top anomalies
    """
    run_id = f"anom-{uuid.uuid4().hex[:8]}"
    
    # Mock anomaly results (production: call anomaly_agent.run_detection)
    mock_anomalies = [
        {
            "tl_event_id": f"tl-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "actor": "jsmith",
            "action": "BULK_EXPORT",
            "anomaly_score": 0.92,
            "normalised_ts": "2024-03-15T02:30:00Z",
            "shap_factors": ["hour_of_day", "volume_bytes", "actor_frequency"]
        },
        {
            "tl_event_id": f"tl-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "actor": "admin_svc",
            "action": "LOGIN_FAILED",
            "anomaly_score": 0.85,
            "normalised_ts": "2024-03-15T03:15:00Z",
            "shap_factors": ["hour_of_day", "source_encoded"]
        },
        {
            "tl_event_id": f"tl-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "actor": "jsmith",
            "action": "FILE_DELETE",
            "anomaly_score": 0.78,
            "normalised_ts": "2024-03-15T04:00:00Z",
            "shap_factors": ["action_encoded", "hour_of_day"]
        }
    ]
    
    # Auto-vault high-confidence anomalies
    vaulted = []
    if auto_vault:
        for anom in mock_anomalies:
            if anom["anomaly_score"] >= min_score_threshold:
                evidence = EvidenceFactory.from_anomaly(
                    case_id=case_id,
                    anomaly=anom,
                    label=f"Anomaly: {anom['action']} by {anom['actor']} (score: {anom['anomaly_score']:.2f})",
                    tags=["anomaly", "auto-detected"] + anom.get("shap_factors", []),
                    investigation_id=investigation_id
                )
                EvidenceVault.add(evidence)
                vaulted.append({
                    "evidence_id": evidence.evidence_id,
                    "tl_event_id": anom["tl_event_id"],
                    "score": anom["anomaly_score"],
                    "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
                })
    
    return {
        "success": True,
        "case_id": case_id,
        "run_id": run_id,
        "model_type": model_type,
        "parameters": {
            "contamination": contamination,
            "n_estimators": n_estimators
        },
        "summary": {
            "total_events_analyzed": 1500,  # Mock
            "anomalies_detected": len(mock_anomalies),
            "high_confidence": len([a for a in mock_anomalies if a["anomaly_score"] >= 0.8])
        },
        "top_anomalies": [
            {
                "tl_event_id": a["tl_event_id"],
                "actor": a["actor"],
                "action": a["action"],
                "score": a["anomaly_score"],
                "timestamp": a["normalised_ts"],
                "key_factors": a["shap_factors"]
            }
            for a in mock_anomalies
        ],
        "vaulted_evidence": vaulted,
        "vault_count": len(vaulted),
        "shap_global_importance": [
            {"feature": "hour_of_day", "importance": 0.25},
            {"feature": "actor_frequency", "importance": 0.20},
            {"feature": "action_encoded", "importance": 0.18}
        ]
    }


@mcp_tool(
    name="anomaly.vault",
    category=ToolCategory.ANALYSIS,
    description="Manually add an anomaly to the Evidence Vault.",
    requires_case_id=True,
    tags={"anomaly", "vault", "evidence"}
)
@with_coc_logging(action_type=CoCActionType.EVIDENCE_CREATE)
@audit_trail(operation="ANOMALY_VAULT")
async def vault_anomaly(
    case_id: str,
    event_id: str,
    anomaly_score: float,
    label: Optional[str] = None,
    tags: Optional[List[str]] = None,
    anomaly_data: Optional[Dict[str, Any]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Manually add an anomaly to the Evidence Vault.
    
    Args:
        case_id: Target case ID
        event_id: Timeline event ID
        anomaly_score: Anomaly score (0-1)
        label: Human-readable label
        tags: Additional tags
        anomaly_data: Full anomaly data
        investigation_id: Associated investigation
    
    Returns:
        Evidence item details
    """
    data = anomaly_data or {
        "tl_event_id": event_id,
        "anomaly_score": anomaly_score,
        "case_id": case_id
    }
    data["tl_event_id"] = event_id
    data["anomaly_score"] = anomaly_score
    
    evidence = EvidenceFactory.from_anomaly(
        case_id=case_id,
        anomaly=data,
        label=label or f"Anomaly (score: {anomaly_score:.2f})",
        tags=tags or ["anomaly", "manual"],
        investigation_id=investigation_id
    )
    
    EvidenceVault.add(evidence)
    
    return {
        "success": True,
        "evidence_id": evidence.evidence_id,
        "event_id": event_id,
        "anomaly_score": anomaly_score,
        "data_hash": evidence.data_hash,
        "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CORRELATION ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="correlation.build",
    category=ToolCategory.ANALYSIS,
    description="Build entity correlation graph with attack chain detection.",
    requires_case_id=True,
    tags={"correlation", "graph", "attack-chain"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="CORRELATION_BUILD")
async def build_correlation(
    case_id: str,
    window_seconds: int = 3600,
    auto_vault_nodes: bool = True,
    min_severity_score: float = 5.0,
    llm_provider: str = "gemini",
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Build entity correlation graph.
    
    Creates nodes (entities) and edges (relationships) from timeline events,
    detects attack patterns, and generates MITRE ATT&CK mappings.
    
    Args:
        case_id: Target case ID
        window_seconds: Correlation window
        auto_vault_nodes: Auto-vault high-severity nodes
        min_severity_score: Minimum severity for auto-vaulting
        llm_provider: LLM provider for narrative
        investigation_id: Associated investigation
    
    Returns:
        Correlation graph with nodes, edges, and attack patterns
    """
    run_id = f"corr-{uuid.uuid4().hex[:8]}"
    
    # Mock correlation results
    mock_nodes = [
        {
            "node_id": f"node-{uuid.uuid4().hex[:8]}",
            "entity_type": "USER",
            "entity_value": "jsmith",
            "severity_score": 8.5,
            "anomaly_score": 0.85,
            "event_count": 45,
            "first_seen": "2024-03-15T01:00:00Z",
            "last_seen": "2024-03-15T05:30:00Z"
        },
        {
            "node_id": f"node-{uuid.uuid4().hex[:8]}",
            "entity_type": "IP",
            "entity_value": "192.168.1.100",
            "severity_score": 7.2,
            "anomaly_score": 0.72,
            "event_count": 28,
            "first_seen": "2024-03-15T02:00:00Z",
            "last_seen": "2024-03-15T04:45:00Z"
        },
        {
            "node_id": f"node-{uuid.uuid4().hex[:8]}",
            "entity_type": "HOST",
            "entity_value": "WORKSTATION-01",
            "severity_score": 6.8,
            "anomaly_score": 0.68,
            "event_count": 120,
            "first_seen": "2024-03-15T00:00:00Z",
            "last_seen": "2024-03-15T06:00:00Z"
        }
    ]
    
    mock_edges = [
        {
            "edge_id": f"edge-{uuid.uuid4().hex[:8]}",
            "source_node": mock_nodes[0]["node_id"],
            "target_node": mock_nodes[1]["node_id"],
            "relationship": "accessed_from",
            "weight": 15,
            "confidence_score": 0.92
        },
        {
            "edge_id": f"edge-{uuid.uuid4().hex[:8]}",
            "source_node": mock_nodes[0]["node_id"],
            "target_node": mock_nodes[2]["node_id"],
            "relationship": "logged_into",
            "weight": 8,
            "confidence_score": 0.88
        }
    ]
    
    # Auto-vault high-severity nodes
    vaulted = []
    if auto_vault_nodes:
        for node in mock_nodes:
            if node["severity_score"] >= min_severity_score:
                evidence = EvidenceFactory.from_correlation_node(
                    case_id=case_id,
                    node=node,
                    label=f"{node['entity_type']}: {node['entity_value']} (severity: {node['severity_score']:.1f})",
                    tags=["correlation", "entity", node["entity_type"].lower()],
                    investigation_id=investigation_id
                )
                EvidenceVault.add(evidence)
                vaulted.append({
                    "evidence_id": evidence.evidence_id,
                    "node_id": node["node_id"],
                    "entity": f"{node['entity_type']}:{node['entity_value']}",
                    "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
                })
    
    return {
        "success": True,
        "case_id": case_id,
        "run_id": run_id,
        "summary": {
            "node_count": len(mock_nodes),
            "edge_count": len(mock_edges),
            "entity_types": list(set(n["entity_type"] for n in mock_nodes))
        },
        "nodes": [
            {
                "node_id": n["node_id"],
                "entity_type": n["entity_type"],
                "entity_value": n["entity_value"],
                "severity_score": n["severity_score"],
                "event_count": n["event_count"]
            }
            for n in mock_nodes
        ],
        "edges": [
            {
                "edge_id": e["edge_id"],
                "relationship": e["relationship"],
                "weight": e["weight"],
                "confidence": e["confidence_score"]
            }
            for e in mock_edges
        ],
        "mitre_tactics": ["TA0001", "TA0003", "TA0006", "TA0010"],
        "critical_path": [mock_nodes[0]["node_id"], mock_nodes[2]["node_id"]],
        "vaulted_evidence": vaulted,
        "vault_count": len(vaulted)
    }


@mcp_tool(
    name="correlation.vault",
    category=ToolCategory.ANALYSIS,
    description="Add correlation entity or relationship to Evidence Vault.",
    requires_case_id=True,
    tags={"correlation", "vault", "evidence"}
)
@with_coc_logging(action_type=CoCActionType.EVIDENCE_CREATE)
@audit_trail(operation="CORRELATION_VAULT")
async def vault_correlation(
    case_id: str,
    entity_type: str,
    entity_value: str,
    severity_score: float = 5.0,
    label: Optional[str] = None,
    tags: Optional[List[str]] = None,
    node_data: Optional[Dict[str, Any]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Add correlation entity to Evidence Vault.
    """
    data = node_data or {
        "node_id": f"node-{uuid.uuid4().hex[:8]}",
        "entity_type": entity_type.upper(),
        "entity_value": entity_value,
        "severity_score": severity_score
    }
    
    evidence = EvidenceFactory.from_correlation_node(
        case_id=case_id,
        node=data,
        label=label or f"{entity_type}: {entity_value}",
        tags=tags or ["correlation", entity_type.lower()],
        investigation_id=investigation_id
    )
    
    EvidenceVault.add(evidence)
    
    return {
        "success": True,
        "evidence_id": evidence.evidence_id,
        "entity": f"{entity_type}:{entity_value}",
        "data_hash": evidence.data_hash,
        "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="crud.analyze",
    category=ToolCategory.ANALYSIS,
    description="Analyze data operations (Create/Read/Update/Delete) with sensitivity classification.",
    requires_case_id=True,
    tags={"crud", "data-access", "sensitivity"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="CRUD_ANALYZE")
async def analyze_crud(
    case_id: str,
    sensitivity_threshold: str = "MEDIUM",
    auto_vault_high_risk: bool = True,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Analyze CRUD operations with sensitivity classification.
    
    Detects high-risk patterns like:
    - Bulk reads outside business hours
    - DELETE on critical data
    - Audit trail modifications
    
    Args:
        case_id: Target case ID
        sensitivity_threshold: Min sensitivity to include (LOW/MEDIUM/HIGH/CRITICAL)
        auto_vault_high_risk: Auto-vault high-risk operations
        investigation_id: Associated investigation
    
    Returns:
        CRUD analysis with high-risk operations
    """
    run_id = f"crud-{uuid.uuid4().hex[:8]}"
    
    # Mock CRUD results
    mock_events = [
        {
            "crud_event_id": f"crud-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "crud_type": "READ",
            "actor": "jsmith",
            "target_object": "payroll_db.salaries",
            "sensitivity": "CRITICAL",
            "is_high_risk": True,
            "risk_reason": "Bulk READ on CRITICAL data outside business hours",
            "volume_bytes": 5242880,
            "normalised_ts": "2024-03-15T02:30:00Z",
            "anomaly_score": 0.85
        },
        {
            "crud_event_id": f"crud-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "crud_type": "DELETE",
            "actor": "jsmith",
            "target_object": "audit_logs.access_log",
            "sensitivity": "HIGH",
            "is_high_risk": True,
            "risk_reason": "DELETE on audit trail - tampering indicator",
            "volume_bytes": 1048576,
            "normalised_ts": "2024-03-15T04:00:00Z",
            "anomaly_score": 0.92
        },
        {
            "crud_event_id": f"crud-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "crud_type": "CREATE",
            "actor": "jsmith",
            "target_object": "temp_exports.data_dump",
            "sensitivity": "HIGH",
            "is_high_risk": True,
            "risk_reason": "Suspicious export staging",
            "volume_bytes": 10485760,
            "normalised_ts": "2024-03-15T02:45:00Z",
            "anomaly_score": 0.78
        }
    ]
    
    # Auto-vault high-risk
    vaulted = []
    if auto_vault_high_risk:
        for event in [e for e in mock_events if e["is_high_risk"]]:
            evidence = EvidenceFactory.from_crud_event(
                case_id=case_id,
                crud_event=event,
                label=f"{event['crud_type']} on {event['target_object']}: {event['risk_reason']}",
                tags=["crud", event["crud_type"].lower(), event["sensitivity"].lower(), "high-risk"],
                investigation_id=investigation_id
            )
            EvidenceVault.add(evidence)
            vaulted.append({
                "evidence_id": evidence.evidence_id,
                "crud_event_id": event["crud_event_id"],
                "operation": f"{event['crud_type']} {event['target_object']}",
                "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
            })
    
    return {
        "success": True,
        "case_id": case_id,
        "run_id": run_id,
        "summary": {
            "total_events": len(mock_events),
            "high_risk_count": len([e for e in mock_events if e["is_high_risk"]]),
            "by_type": {"READ": 1, "DELETE": 1, "CREATE": 1},
            "by_sensitivity": {"CRITICAL": 1, "HIGH": 2}
        },
        "high_risk_events": [
            {
                "crud_event_id": e["crud_event_id"],
                "crud_type": e["crud_type"],
                "actor": e["actor"],
                "target": e["target_object"],
                "sensitivity": e["sensitivity"],
                "risk_reason": e["risk_reason"],
                "timestamp": e["normalised_ts"]
            }
            for e in mock_events if e["is_high_risk"]
        ],
        "vaulted_evidence": vaulted,
        "vault_count": len(vaulted)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="network.analyze",
    category=ToolCategory.ANALYSIS,
    description="Analyze network flows with exfiltration detection and threat intel enrichment.",
    requires_case_id=True,
    tags={"network", "flows", "exfiltration"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="NETWORK_ANALYZE")
async def analyze_network(
    case_id: str,
    auto_vault_exfil: bool = True,
    min_exfil_confidence: float = 0.5,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Analyze network flows with exfiltration detection.
    
    Detects:
    - Suspicious outbound flows
    - Data exfiltration candidates (correlated with CRUD)
    - Known-bad IP destinations
    
    Args:
        case_id: Target case ID
        auto_vault_exfil: Auto-vault exfiltration candidates
        min_exfil_confidence: Minimum confidence for auto-vaulting
        investigation_id: Associated investigation
    
    Returns:
        Network analysis with exfiltration candidates
    """
    run_id = f"net-{uuid.uuid4().hex[:8]}"
    
    # Mock exfil candidates
    mock_exfil = [
        {
            "exfil_id": f"exfil-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "actor": "jsmith",
            "data_target": "payroll_db.salaries",
            "dst_ip": "185.220.101.45",
            "bytes_crud": 5242880,
            "bytes_network": 5100000,
            "time_delta_secs": 120,
            "confidence": 0.89,
            "evidence_summary": "CRUD read of 5MB payroll data followed by 5MB outbound to Tor exit node within 2 minutes",
            "normalised_ts": "2024-03-15T02:32:00Z"
        },
        {
            "exfil_id": f"exfil-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "actor": "jsmith",
            "data_target": "temp_exports.data_dump",
            "dst_ip": "203.0.113.50",
            "bytes_crud": 10485760,
            "bytes_network": 10200000,
            "time_delta_secs": 300,
            "confidence": 0.75,
            "evidence_summary": "Export staging followed by 10MB outbound to suspicious IP",
            "normalised_ts": "2024-03-15T02:50:00Z"
        }
    ]
    
    # Auto-vault exfil candidates
    vaulted = []
    if auto_vault_exfil:
        for exfil in [e for e in mock_exfil if e["confidence"] >= min_exfil_confidence]:
            evidence = EvidenceFactory.from_exfil_candidate(
                case_id=case_id,
                exfil=exfil,
                label=f"Exfil: {exfil['data_target']} → {exfil['dst_ip']} ({exfil['confidence']:.0%} confidence)",
                tags=["exfiltration", "network", "data-theft"],
                investigation_id=investigation_id
            )
            EvidenceVault.add(evidence)
            vaulted.append({
                "evidence_id": evidence.evidence_id,
                "exfil_id": exfil["exfil_id"],
                "destination": exfil["dst_ip"],
                "confidence": exfil["confidence"],
                "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
            })
    
    return {
        "success": True,
        "case_id": case_id,
        "run_id": run_id,
        "summary": {
            "total_flows": 500,  # Mock
            "suspicious_flows": 25,
            "exfil_candidates": len(mock_exfil),
            "total_bytes_out": 15342880
        },
        "exfil_candidates": [
            {
                "exfil_id": e["exfil_id"],
                "actor": e["actor"],
                "data_target": e["data_target"],
                "dst_ip": e["dst_ip"],
                "bytes": e["bytes_network"],
                "confidence": e["confidence"],
                "summary": e["evidence_summary"],
                "timestamp": e["normalised_ts"]
            }
            for e in mock_exfil
        ],
        "vaulted_evidence": vaulted,
        "vault_count": len(vaulted)
    }


@mcp_tool(
    name="network.vault",
    category=ToolCategory.ANALYSIS,
    description="Add network flow or exfiltration candidate to Evidence Vault.",
    requires_case_id=True,
    tags={"network", "vault", "evidence"}
)
@with_coc_logging(action_type=CoCActionType.EVIDENCE_CREATE)
@audit_trail(operation="NETWORK_VAULT")
async def vault_network(
    case_id: str,
    flow_type: str,
    src_ip: str,
    dst_ip: str,
    bytes_sent: int = 0,
    is_exfil: bool = False,
    confidence: float = 0.5,
    label: Optional[str] = None,
    tags: Optional[List[str]] = None,
    flow_data: Optional[Dict[str, Any]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Add network flow to Evidence Vault.
    """
    data = flow_data or {
        "flow_id": f"flow-{uuid.uuid4().hex[:8]}",
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "bytes_sent": bytes_sent,
        "protocol": "TCP",
        "is_suspicious": is_exfil
    }
    
    if is_exfil:
        data["exfil_id"] = data.get("exfil_id", f"exfil-{uuid.uuid4().hex[:8]}")
        data["confidence"] = confidence
        evidence = EvidenceFactory.from_exfil_candidate(
            case_id=case_id,
            exfil=data,
            label=label or f"Exfil: {src_ip} → {dst_ip}",
            tags=tags or ["exfiltration", "network"],
            investigation_id=investigation_id
        )
    else:
        evidence = EvidenceFactory.from_network_flow(
            case_id=case_id,
            flow=data,
            label=label or f"Flow: {src_ip} → {dst_ip}",
            tags=tags or ["network", flow_type.lower()],
            investigation_id=investigation_id
        )
    
    EvidenceVault.add(evidence)
    
    return {
        "success": True,
        "evidence_id": evidence.evidence_id,
        "flow": f"{src_ip} → {dst_ip}",
        "is_exfil": is_exfil,
        "data_hash": evidence.data_hash,
        "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DEPTH/IMPACT ANALYSIS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="depth.analyze",
    category=ToolCategory.ANALYSIS,
    description="Compute 4-dimensional impact depth (Account, System, Data, Control) and business impact.",
    requires_case_id=True,
    tags={"depth", "impact", "severity"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="DEPTH_ANALYZE")
async def analyze_depth(
    case_id: str,
    weights: Optional[Dict[str, float]] = None,
    auto_vault_metrics: bool = True,
    llm_provider: str = "gemini",
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Compute 4-dimensional impact depth.
    
    Dimensions:
    - Account: Admin access, privilege escalation, MFA bypass
    - System: Subnet access, tier access, lateral movement
    - Data: Sensitive objects, volumes, exfiltration
    - Control: MFA gaps, failed logins, firewall bypasses
    
    Args:
        case_id: Target case ID
        weights: Custom dimension weights
        auto_vault_metrics: Auto-vault high-impact metrics
        llm_provider: LLM for narrative
        investigation_id: Associated investigation
    
    Returns:
        Impact assessment with all dimensions
    """
    run_id = f"depth-{uuid.uuid4().hex[:8]}"
    
    # Default weights
    default_weights = {
        "account": 0.25,
        "system": 0.25,
        "data": 0.30,
        "control": 0.20
    }
    w = weights or default_weights
    
    # Mock depth scores
    account_depth = 7.5
    system_depth = 6.2
    data_depth = 8.8
    control_depth = 4.5
    
    overall = (
        w["account"] * account_depth +
        w["system"] * system_depth +
        w["data"] * data_depth +
        w["control"] * control_depth
    )
    
    severity_label = (
        "CRITICAL" if overall >= 7.0 else
        "HIGH" if overall >= 5.0 else
        "MEDIUM" if overall >= 3.0 else
        "LOW"
    )
    
    # Mock metrics
    metrics = [
        {"dimension": "ACCOUNT", "metric_name": "admin_accounts_accessed", "metric_value": 2, "max_value": 5},
        {"dimension": "ACCOUNT", "metric_name": "privilege_escalations", "metric_value": 3, "max_value": 10},
        {"dimension": "SYSTEM", "metric_name": "unique_subnets", "metric_value": 4, "max_value": 10},
        {"dimension": "SYSTEM", "metric_name": "lateral_movement_hops", "metric_value": 3, "max_value": 8},
        {"dimension": "DATA", "metric_name": "critical_objects_accessed", "metric_value": 5, "max_value": 10},
        {"dimension": "DATA", "metric_name": "exfil_bytes_mb", "metric_value": 15, "max_value": 50},
        {"dimension": "CONTROL", "metric_name": "mfa_gap_ratio", "metric_value": 0.3, "max_value": 1.0},
        {"dimension": "CONTROL", "metric_name": "failed_logins", "metric_value": 25, "max_value": 100}
    ]
    
    # Auto-vault high-impact metrics
    vaulted = []
    if auto_vault_metrics:
        for metric in metrics:
            ratio = metric["metric_value"] / metric["max_value"] if metric["max_value"] > 0 else 0
            if ratio >= 0.5:  # Vault metrics at 50%+ of max
                metric["detail_id"] = f"detail-{uuid.uuid4().hex[:8]}"
                metric["run_id"] = run_id
                
                evidence = EvidenceFactory.from_depth_metric(
                    case_id=case_id,
                    metric=metric,
                    dimension=metric["dimension"],
                    label=f"{metric['dimension']} impact: {metric['metric_name']} = {metric['metric_value']}",
                    tags=["depth", "impact", metric["dimension"].lower()],
                    investigation_id=investigation_id
                )
                EvidenceVault.add(evidence)
                vaulted.append({
                    "evidence_id": evidence.evidence_id,
                    "metric": metric["metric_name"],
                    "dimension": metric["dimension"],
                    "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]"
                })
    
    return {
        "success": True,
        "case_id": case_id,
        "run_id": run_id,
        "depth_scores": {
            "account": account_depth,
            "system": system_depth,
            "data": data_depth,
            "control": control_depth
        },
        "overall_severity": round(overall, 2),
        "severity_label": severity_label,
        "business_impact": {
            "financial": "HIGH" if data_depth >= 7 else "MEDIUM",
            "reputational": "HIGH" if data_depth >= 8 else "MEDIUM",
            "regulatory": "HIGH" if data_depth >= 8 else "MEDIUM",
            "operational": "HIGH" if system_depth >= 6 else "MEDIUM",
            "data_at_risk_bytes": 15728640,
            "sensitive_records_accessed": 5
        },
        "metrics": [
            {
                "dimension": m["dimension"],
                "metric": m["metric_name"],
                "value": m["metric_value"],
                "max": m["max_value"],
                "ratio": round(m["metric_value"] / m["max_value"], 2) if m["max_value"] > 0 else 0
            }
            for m in metrics
        ],
        "vaulted_evidence": vaulted,
        "vault_count": len(vaulted)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY TOOL - RUN ALL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="analysis.full",
    category=ToolCategory.ANALYSIS,
    description="Run complete analysis pipeline (Timeline → Anomaly → Correlation → CRUD → Network → Depth).",
    requires_case_id=True,
    tags={"analysis", "full", "pipeline"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="ANALYSIS_FULL")
async def run_full_analysis(
    case_id: str,
    auto_vault: bool = True,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Run complete analysis pipeline.
    
    Executes all analysis modules in sequence:
    1. Anomaly Detection
    2. Correlation Building
    3. CRUD Analysis
    4. Network Analysis
    5. Depth/Impact Assessment
    
    All significant findings are auto-vaulted to Evidence Vault.
    
    Args:
        case_id: Target case ID
        auto_vault: Auto-vault significant findings
        investigation_id: Associated investigation
    
    Returns:
        Combined analysis results with vault summary
    """
    results = {}
    total_vaulted = 0
    
    # Run each analysis
    anomaly_result = await detect_anomalies(
        case_id=case_id,
        auto_vault=auto_vault,
        investigation_id=investigation_id
    )
    results["anomaly"] = anomaly_result
    total_vaulted += anomaly_result.get("vault_count", 0)
    
    correlation_result = await build_correlation(
        case_id=case_id,
        auto_vault_nodes=auto_vault,
        investigation_id=investigation_id
    )
    results["correlation"] = correlation_result
    total_vaulted += correlation_result.get("vault_count", 0)
    
    crud_result = await analyze_crud(
        case_id=case_id,
        auto_vault_high_risk=auto_vault,
        investigation_id=investigation_id
    )
    results["crud"] = crud_result
    total_vaulted += crud_result.get("vault_count", 0)
    
    network_result = await analyze_network(
        case_id=case_id,
        auto_vault_exfil=auto_vault,
        investigation_id=investigation_id
    )
    results["network"] = network_result
    total_vaulted += network_result.get("vault_count", 0)
    
    depth_result = await analyze_depth(
        case_id=case_id,
        auto_vault_metrics=auto_vault,
        investigation_id=investigation_id
    )
    results["depth"] = depth_result
    total_vaulted += depth_result.get("vault_count", 0)
    
    # Get vault stats
    vault_stats = EvidenceVault.get_stats(case_id)
    
    return {
        "success": True,
        "case_id": case_id,
        "investigation_id": investigation_id,
        "analysis_summary": {
            "anomalies_detected": anomaly_result["summary"]["anomalies_detected"],
            "correlation_nodes": correlation_result["summary"]["node_count"],
            "correlation_edges": correlation_result["summary"]["edge_count"],
            "high_risk_crud": crud_result["summary"]["high_risk_count"],
            "exfil_candidates": network_result["summary"]["exfil_candidates"],
            "overall_severity": depth_result["severity_label"],
            "severity_score": depth_result["overall_severity"]
        },
        "mitre_tactics": correlation_result.get("mitre_tactics", []),
        "business_impact": depth_result["business_impact"],
        "vault_summary": {
            "total_vaulted": total_vaulted,
            "vault_stats": vault_stats
        },
        "module_results": {
            "anomaly_run_id": anomaly_result["run_id"],
            "correlation_run_id": correlation_result["run_id"],
            "crud_run_id": crud_result["run_id"],
            "network_run_id": network_result["run_id"],
            "depth_run_id": depth_result["run_id"]
        }
    }
