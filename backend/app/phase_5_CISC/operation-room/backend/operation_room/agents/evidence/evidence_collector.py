"""
Evidence Collection Agent — LangGraph Pipeline for Evidence Gathering.

The Evidence Collection Agent interfaces with the case vault and forensic modules
to gather evidence relevant to the generated hypotheses.

Pipeline Architecture:
─────────────────────────────────────────────────────────────────────────────────
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     EVIDENCE COLLECTION PIPELINE                         │
   │                                                                          │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │  LOAD    │──▶│   SCAN   │──▶│  CROSS   │──▶│  BUILD   │             │
   │  │HYPOTHESES│   │  MODULES │   │REFERENCE │   │INVENTORY │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   │                                                    │                    │
   │                                                    ▼                    │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │  OUTPUT  │◀──│CALCULATE │◀──│  VERIFY  │◀──│ COMPUTE  │             │
   │  │  SCHEMA  │   │RELEVANCE │   │INTEGRITY │   │  HASHES  │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   └──────────────────────────────────────────────────────────────────────────┘
─────────────────────────────────────────────────────────────────────────────────

Research Integration:
- Digital Forensics Research Workshop (DFRWS) methodologies
- ISO/IEC 27037: Guidelines for identification, collection, acquisition
- NIST SP 800-86: Guide to Integrating Forensic Techniques
- RFC 3227: Guidelines for Evidence Collection and Archiving

Author: NFLIP Development Team
Version: 1.0.0
"""

import json
import uuid
import logging
import hashlib
from datetime import datetime, timezone
from typing import TypedDict, Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from langgraph.graph import StateGraph, END

from operation_room.agents.base import BaseAgent, BaseAgentState, AgentStatus, registry
from operation_room.services.audit_service import record_coc_event
from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceType(str, Enum):
    """Types of forensic evidence."""
    LOG_EVENT = "log_event"
    NETWORK_FLOW = "network_flow"
    FILE_ARTIFACT = "file_artifact"
    MEMORY_DUMP = "memory_dump"
    REGISTRY_KEY = "registry_key"
    DATABASE_RECORD = "database_record"
    AUTHENTICATION_EVENT = "authentication_event"
    PROCESS_EXECUTION = "process_execution"
    CONFIGURATION = "configuration"
    TIMELINE_ENTRY = "timeline_entry"
    ANOMALY_SCORE = "anomaly_score"
    CORRELATION_NODE = "correlation_node"


class EvidenceQuality(str, Enum):
    """Quality assessment of evidence."""
    PRISTINE = "pristine"      # Untouched, cryptographically verified
    VERIFIED = "verified"      # Hash verified, chain intact
    DERIVED = "derived"        # Computed from other evidence
    INCOMPLETE = "incomplete"  # Partial or truncated
    SUSPECT = "suspect"        # Integrity concerns


@dataclass
class EvidenceItem:
    """
    A single piece of forensic evidence.
    """
    evidence_id: str = field(default_factory=lambda: f"EV{uuid.uuid4().hex[:8].upper()}")
    evidence_type: EvidenceType = EvidenceType.LOG_EVENT
    source_module: str = ""
    source_table: str = ""
    
    # Content
    summary: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    # Temporal
    event_timestamp: Optional[str] = None
    collected_at: str = field(default_factory=_now_iso)
    
    # Quality & Integrity
    quality: EvidenceQuality = EvidenceQuality.VERIFIED
    hash_value: str = ""
    
    # Relevance
    hypothesis_ids: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    relevance_reason: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "source_module": self.source_module,
            "source_table": self.source_table,
            "summary": self.summary,
            "raw_data": self.raw_data,
            "event_timestamp": self.event_timestamp,
            "collected_at": self.collected_at,
            "quality": self.quality.value,
            "hash_value": self.hash_value,
            "hypothesis_ids": self.hypothesis_ids,
            "relevance_score": self.relevance_score,
            "relevance_reason": self.relevance_reason,
            "tags": self.tags
        }
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of evidence content."""
        content = json.dumps(self.raw_data, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"


@dataclass
class EvidenceInventory:
    """
    Complete inventory of collected evidence for a case.
    """
    case_id: str = ""
    run_id: str = ""
    collected_at: str = field(default_factory=_now_iso)
    
    # Evidence items
    items: List[EvidenceItem] = field(default_factory=list)
    
    # Statistics
    total_items: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_module: Dict[str, int] = field(default_factory=dict)
    by_hypothesis: Dict[str, int] = field(default_factory=dict)
    
    # Time range
    earliest_timestamp: Optional[str] = None
    latest_timestamp: Optional[str] = None
    
    # Integrity
    inventory_hash: str = ""
    
    def add_item(self, item: EvidenceItem):
        """Add an evidence item and update statistics."""
        self.items.append(item)
        self.total_items = len(self.items)
        
        # Update type counts
        type_key = item.evidence_type.value
        self.by_type[type_key] = self.by_type.get(type_key, 0) + 1
        
        # Update module counts
        if item.source_module:
            self.by_module[item.source_module] = self.by_module.get(item.source_module, 0) + 1
        
        # Update hypothesis counts
        for h_id in item.hypothesis_ids:
            self.by_hypothesis[h_id] = self.by_hypothesis.get(h_id, 0) + 1
        
        # Update time range
        if item.event_timestamp:
            if not self.earliest_timestamp or item.event_timestamp < self.earliest_timestamp:
                self.earliest_timestamp = item.event_timestamp
            if not self.latest_timestamp or item.event_timestamp > self.latest_timestamp:
                self.latest_timestamp = item.event_timestamp
    
    def compute_hash(self) -> str:
        """Compute hash of entire inventory."""
        content = json.dumps([i.to_dict() for i in self.items], sort_keys=True)
        self.inventory_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
        return self.inventory_hash
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "run_id": self.run_id,
            "collected_at": self.collected_at,
            "total_items": self.total_items,
            "by_type": self.by_type,
            "by_module": self.by_module,
            "by_hypothesis": self.by_hypothesis,
            "earliest_timestamp": self.earliest_timestamp,
            "latest_timestamp": self.latest_timestamp,
            "inventory_hash": self.inventory_hash,
            "items": [i.to_dict() for i in self.items]
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceState(TypedDict, total=False):
    """State schema for the evidence collection pipeline."""
    # Input
    case_id: str
    run_id: str
    hypotheses: List[Dict[str, Any]]
    evidence_requirements: List[Dict[str, Any]]
    
    # Module availability
    available_modules: List[str]
    module_status: Dict[str, str]
    
    # Collection results
    timeline_evidence: List[Dict[str, Any]]
    anomaly_evidence: List[Dict[str, Any]]
    correlation_evidence: List[Dict[str, Any]]
    crud_evidence: List[Dict[str, Any]]
    network_evidence: List[Dict[str, Any]]
    depth_evidence: List[Dict[str, Any]]
    
    # Inventory
    inventory: Dict[str, Any]
    
    # Cross-reference
    hypothesis_evidence_map: Dict[str, List[str]]
    
    # Output
    output: Dict[str, Any]
    
    # Metadata
    status: str
    hash_value: str
    coc_event_id: str
    error: Optional[str]
    reasoning_steps: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE QUERY DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

MODULE_QUERIES = {
    "timeline": {
        "tables": ["unified_timeline", "anchor_events"],
        "primary_query": """
            SELECT event_id, case_id, normalised_ts, source_type, source_system,
                   actor, action, target, severity, detail
            FROM unified_timeline
            WHERE case_id = ?
            ORDER BY normalised_ts DESC
            LIMIT 1000
        """,
        "evidence_type": EvidenceType.TIMELINE_ENTRY
    },
    "anomaly": {
        "tables": ["anomaly_scores", "anomaly_runs"],
        "primary_query": """
            SELECT a.event_id, a.anomaly_score, a.is_anomaly, a.shap_values,
                   t.actor, t.action, t.normalised_ts, t.source_type
            FROM anomaly_scores a
            JOIN unified_timeline t ON a.event_id = t.event_id
            WHERE a.run_id = (
                SELECT run_id FROM anomaly_runs 
                WHERE case_id = ? AND status = 'COMPLETED'
                ORDER BY completed_at DESC LIMIT 1
            )
            AND a.is_anomaly = TRUE
            ORDER BY a.anomaly_score DESC
            LIMIT 100
        """,
        "evidence_type": EvidenceType.ANOMALY_SCORE
    },
    "correlation": {
        "tables": ["correlation_nodes", "correlation_edges", "rca_narratives"],
        "primary_query": """
            SELECT n.node_id, n.node_type, n.entity_value, n.severity_score,
                   n.event_count, n.mitre_tactics
            FROM correlation_nodes n
            WHERE n.run_id = (
                SELECT run_id FROM correlation_runs
                WHERE case_id = ? AND status = 'COMPLETED'
                ORDER BY completed_at DESC LIMIT 1
            )
            ORDER BY n.severity_score DESC
            LIMIT 50
        """,
        "evidence_type": EvidenceType.CORRELATION_NODE
    },
    "crud": {
        "tables": ["crud_events", "crud_summary"],
        "primary_query": """
            SELECT event_id, actor, operation, target, data_volume,
                   sensitivity_level, normalised_ts
            FROM crud_events
            WHERE case_id = ?
            AND (operation = 'DELETE' OR operation = 'EXPORT' OR data_volume > 1000000)
            ORDER BY normalised_ts DESC
            LIMIT 100
        """,
        "evidence_type": EvidenceType.DATABASE_RECORD
    },
    "network": {
        "tables": ["network_flows", "exfil_candidates"],
        "primary_query": """
            SELECT flow_id, source_ip, dest_ip, dest_port, protocol,
                   bytes_out, packets, flow_start, flow_duration
            FROM network_flows
            WHERE case_id = ?
            ORDER BY bytes_out DESC
            LIMIT 100
        """,
        "evidence_type": EvidenceType.NETWORK_FLOW
    },
    "depth": {
        "tables": ["depth_assessment"],
        "primary_query": """
            SELECT run_id, account_depth, system_depth, data_depth, control_depth,
                   overall_score, impact_narrative
            FROM depth_assessment
            WHERE case_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
        "evidence_type": EvidenceType.CONFIGURATION
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE NODES
# ═══════════════════════════════════════════════════════════════════════════════

def load_hypotheses(state: EvidenceState) -> dict:
    """
    Node 1: Load hypotheses and evidence requirements.
    """
    run_id = state.get("run_id", str(uuid.uuid4()))
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Loading hypotheses for case {case_id}")
    
    hypotheses = state.get("hypotheses", [])
    requirements = state.get("evidence_requirements", [])
    
    return {
        "run_id": run_id,
        "status": "loading",
        "reasoning_steps": [{
            "step": "load_hypotheses",
            "description": f"Loaded {len(hypotheses)} hypotheses with {len(requirements)} evidence requirements",
            "timestamp": _now_iso(),
            "details": {
                "hypothesis_count": len(hypotheses),
                "requirement_count": len(requirements)
            }
        }]
    }


def scan_modules(state: EvidenceState) -> dict:
    """
    Node 2: Scan available modules and their status.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Scanning available modules")
    
    available_modules = []
    module_status = {}
    
    try:
        conn = open_vault(case_id)
        
        # Check each module's tables
        for module_name, module_config in MODULE_QUERIES.items():
            tables = module_config["tables"]
            has_data = False
            
            for table in tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id = ?", [case_id]).fetchone()
                    if count and count[0] > 0:
                        has_data = True
                        break
                except Exception:
                    pass
            
            if has_data:
                available_modules.append(module_name)
                module_status[module_name] = "available"
            else:
                module_status[module_name] = "no_data"
                
    except Exception as e:
        logger.warning(f"[{run_id}] Module scan error: {e}")
    
    return {
        "available_modules": available_modules,
        "module_status": module_status,
        "status": "scanned",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "scan_modules",
            "description": f"Found {len(available_modules)} modules with data",
            "timestamp": _now_iso(),
            "details": {
                "available": available_modules,
                "status": module_status
            }
        }]
    }


def collect_timeline_evidence(state: EvidenceState) -> dict:
    """
    Node 3a: Collect evidence from timeline module.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Collecting timeline evidence")
    
    evidence = []
    
    if "timeline" not in state.get("available_modules", []):
        return {"timeline_evidence": []}
    
    try:
        conn = open_vault(case_id)
        query = MODULE_QUERIES["timeline"]["primary_query"]
        rows = conn.execute(query, [case_id]).fetchall()
        
        for row in rows:
            item = EvidenceItem(
                evidence_type=EvidenceType.TIMELINE_ENTRY,
                source_module="timeline",
                source_table="unified_timeline",
                summary=f"{row[5]} performed {row[6]} on {row[7]}" if len(row) > 7 else "Timeline event",
                raw_data={
                    "event_id": row[0],
                    "normalised_ts": str(row[2]) if row[2] else None,
                    "source_type": row[3],
                    "source_system": row[4],
                    "actor": row[5],
                    "action": row[6],
                    "target": row[7] if len(row) > 7 else None,
                    "severity": row[8] if len(row) > 8 else None
                },
                event_timestamp=str(row[2]) if row[2] else None,
                quality=EvidenceQuality.VERIFIED
            )
            item.hash_value = item.compute_hash()
            evidence.append(item.to_dict())
            
    except Exception as e:
        logger.warning(f"[{run_id}] Timeline collection error: {e}")
    
    return {
        "timeline_evidence": evidence,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "collect_timeline_evidence",
            "description": f"Collected {len(evidence)} timeline events",
            "timestamp": _now_iso()
        }]
    }


def collect_anomaly_evidence(state: EvidenceState) -> dict:
    """
    Node 3b: Collect evidence from anomaly module.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Collecting anomaly evidence")
    
    evidence = []
    
    if "anomaly" not in state.get("available_modules", []):
        return {"anomaly_evidence": []}
    
    try:
        conn = open_vault(case_id)
        query = MODULE_QUERIES["anomaly"]["primary_query"]
        rows = conn.execute(query, [case_id]).fetchall()
        
        for row in rows:
            item = EvidenceItem(
                evidence_type=EvidenceType.ANOMALY_SCORE,
                source_module="anomaly",
                source_table="anomaly_scores",
                summary=f"Anomaly detected: {row[4]} {row[5]} (score: {row[1]:.2f})" if len(row) > 5 else "Anomaly event",
                raw_data={
                    "event_id": row[0],
                    "anomaly_score": float(row[1]) if row[1] else 0,
                    "is_anomaly": bool(row[2]),
                    "shap_values": row[3],
                    "actor": row[4] if len(row) > 4 else None,
                    "action": row[5] if len(row) > 5 else None,
                    "normalised_ts": str(row[6]) if len(row) > 6 and row[6] else None,
                    "source_type": row[7] if len(row) > 7 else None
                },
                event_timestamp=str(row[6]) if len(row) > 6 and row[6] else None,
                quality=EvidenceQuality.DERIVED,
                relevance_score=float(row[1]) if row[1] else 0
            )
            item.hash_value = item.compute_hash()
            evidence.append(item.to_dict())
            
    except Exception as e:
        logger.warning(f"[{run_id}] Anomaly collection error: {e}")
    
    return {
        "anomaly_evidence": evidence,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "collect_anomaly_evidence",
            "description": f"Collected {len(evidence)} anomaly events",
            "timestamp": _now_iso()
        }]
    }


def collect_correlation_evidence(state: EvidenceState) -> dict:
    """
    Node 3c: Collect evidence from correlation module.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Collecting correlation evidence")
    
    evidence = []
    
    if "correlation" not in state.get("available_modules", []):
        return {"correlation_evidence": []}
    
    try:
        conn = open_vault(case_id)
        query = MODULE_QUERIES["correlation"]["primary_query"]
        rows = conn.execute(query, [case_id]).fetchall()
        
        for row in rows:
            item = EvidenceItem(
                evidence_type=EvidenceType.CORRELATION_NODE,
                source_module="correlation",
                source_table="correlation_nodes",
                summary=f"{row[1]} entity: {row[2]} (severity: {row[3]:.2f})" if len(row) > 3 else "Correlation node",
                raw_data={
                    "node_id": row[0],
                    "node_type": row[1],
                    "entity_value": row[2],
                    "severity_score": float(row[3]) if len(row) > 3 and row[3] else 0,
                    "event_count": row[4] if len(row) > 4 else 0,
                    "mitre_tactics": row[5] if len(row) > 5 else None
                },
                quality=EvidenceQuality.DERIVED,
                relevance_score=float(row[3]) if len(row) > 3 and row[3] else 0
            )
            item.hash_value = item.compute_hash()
            evidence.append(item.to_dict())
            
    except Exception as e:
        logger.warning(f"[{run_id}] Correlation collection error: {e}")
    
    return {
        "correlation_evidence": evidence,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "collect_correlation_evidence",
            "description": f"Collected {len(evidence)} correlation nodes",
            "timestamp": _now_iso()
        }]
    }


def collect_crud_evidence(state: EvidenceState) -> dict:
    """
    Node 3d: Collect evidence from CRUD module.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Collecting CRUD evidence")
    
    evidence = []
    
    if "crud" not in state.get("available_modules", []):
        return {"crud_evidence": []}
    
    try:
        conn = open_vault(case_id)
        query = MODULE_QUERIES["crud"]["primary_query"]
        rows = conn.execute(query, [case_id]).fetchall()
        
        for row in rows:
            item = EvidenceItem(
                evidence_type=EvidenceType.DATABASE_RECORD,
                source_module="crud",
                source_table="crud_events",
                summary=f"{row[1]} performed {row[2]} on {row[3]}" if len(row) > 3 else "CRUD event",
                raw_data={
                    "event_id": row[0],
                    "actor": row[1],
                    "operation": row[2],
                    "target": row[3],
                    "data_volume": row[4] if len(row) > 4 else 0,
                    "sensitivity_level": row[5] if len(row) > 5 else None,
                    "normalised_ts": str(row[6]) if len(row) > 6 and row[6] else None
                },
                event_timestamp=str(row[6]) if len(row) > 6 and row[6] else None,
                quality=EvidenceQuality.VERIFIED
            )
            item.hash_value = item.compute_hash()
            evidence.append(item.to_dict())
            
    except Exception as e:
        logger.warning(f"[{run_id}] CRUD collection error: {e}")
    
    return {
        "crud_evidence": evidence,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "collect_crud_evidence",
            "description": f"Collected {len(evidence)} CRUD events",
            "timestamp": _now_iso()
        }]
    }


def collect_network_evidence(state: EvidenceState) -> dict:
    """
    Node 3e: Collect evidence from network module.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Collecting network evidence")
    
    evidence = []
    
    if "network" not in state.get("available_modules", []):
        return {"network_evidence": []}
    
    try:
        conn = open_vault(case_id)
        query = MODULE_QUERIES["network"]["primary_query"]
        rows = conn.execute(query, [case_id]).fetchall()
        
        for row in rows:
            item = EvidenceItem(
                evidence_type=EvidenceType.NETWORK_FLOW,
                source_module="network",
                source_table="network_flows",
                summary=f"Flow {row[1]} -> {row[2]}:{row[3]} ({row[5]} bytes)" if len(row) > 5 else "Network flow",
                raw_data={
                    "flow_id": row[0],
                    "source_ip": row[1],
                    "dest_ip": row[2],
                    "dest_port": row[3],
                    "protocol": row[4] if len(row) > 4 else None,
                    "bytes_out": row[5] if len(row) > 5 else 0,
                    "packets": row[6] if len(row) > 6 else 0,
                    "flow_start": str(row[7]) if len(row) > 7 and row[7] else None,
                    "flow_duration": row[8] if len(row) > 8 else None
                },
                event_timestamp=str(row[7]) if len(row) > 7 and row[7] else None,
                quality=EvidenceQuality.VERIFIED
            )
            item.hash_value = item.compute_hash()
            evidence.append(item.to_dict())
            
    except Exception as e:
        logger.warning(f"[{run_id}] Network collection error: {e}")
    
    return {
        "network_evidence": evidence,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "collect_network_evidence",
            "description": f"Collected {len(evidence)} network flows",
            "timestamp": _now_iso()
        }]
    }


def build_inventory(state: EvidenceState) -> dict:
    """
    Node 4: Build complete evidence inventory.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    
    logger.info(f"[{run_id}] Building evidence inventory")
    
    inventory = EvidenceInventory(case_id=case_id, run_id=run_id)
    
    # Add all evidence
    all_evidence = (
        state.get("timeline_evidence", []) +
        state.get("anomaly_evidence", []) +
        state.get("correlation_evidence", []) +
        state.get("crud_evidence", []) +
        state.get("network_evidence", []) +
        state.get("depth_evidence", [])
    )
    
    for ev_dict in all_evidence:
        item = EvidenceItem(
            evidence_id=ev_dict.get("evidence_id", str(uuid.uuid4())),
            evidence_type=EvidenceType(ev_dict.get("evidence_type", "log_event")),
            source_module=ev_dict.get("source_module", ""),
            source_table=ev_dict.get("source_table", ""),
            summary=ev_dict.get("summary", ""),
            raw_data=ev_dict.get("raw_data", {}),
            event_timestamp=ev_dict.get("event_timestamp"),
            quality=EvidenceQuality(ev_dict.get("quality", "verified")),
            hash_value=ev_dict.get("hash_value", ""),
            hypothesis_ids=ev_dict.get("hypothesis_ids", []),
            relevance_score=ev_dict.get("relevance_score", 0.0),
            relevance_reason=ev_dict.get("relevance_reason", ""),
            tags=ev_dict.get("tags", [])
        )
        inventory.add_item(item)
    
    # Compute inventory hash
    inventory.compute_hash()
    
    return {
        "inventory": inventory.to_dict(),
        "status": "inventory_built",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "build_inventory",
            "description": f"Built inventory with {inventory.total_items} items",
            "timestamp": _now_iso(),
            "details": {
                "total_items": inventory.total_items,
                "by_type": inventory.by_type,
                "by_module": inventory.by_module
            }
        }]
    }


def cross_reference_hypotheses(state: EvidenceState) -> dict:
    """
    Node 5: Cross-reference evidence with hypotheses.
    """
    run_id = state["run_id"]
    hypotheses = state.get("hypotheses", [])
    inventory = state.get("inventory", {})
    
    logger.info(f"[{run_id}] Cross-referencing evidence with hypotheses")
    
    hypothesis_evidence_map = {}
    
    # Map evidence to hypotheses based on requirements
    for h in hypotheses:
        h_id = h.get("hypothesis_id", "")
        h_type = h.get("hypothesis_type", "")
        involved_entities = h.get("involved_entities", [])
        
        matching_evidence = []
        
        # Search inventory for relevant evidence
        for item in inventory.get("items", []):
            raw_data = item.get("raw_data", {})
            
            # Match by actor/entity
            item_actor = raw_data.get("actor", "")
            if item_actor and any(e.lower() in item_actor.lower() for e in involved_entities):
                matching_evidence.append(item.get("evidence_id"))
                continue
            
            # Match by hypothesis type
            if h_type == "data_exfiltration":
                if item.get("source_module") in ["network", "crud"]:
                    if raw_data.get("bytes_out", 0) > 100000 or raw_data.get("operation") in ["EXPORT", "DELETE"]:
                        matching_evidence.append(item.get("evidence_id"))
            
            elif h_type == "lateral_movement":
                if item.get("source_module") == "anomaly":
                    if raw_data.get("is_anomaly"):
                        matching_evidence.append(item.get("evidence_id"))
            
            elif h_type in ["credential_theft", "privilege_escalation"]:
                if raw_data.get("action") in ["LOGIN_SUCCESS", "LOGIN_FAILED", "PASSWORD_CHANGE"]:
                    matching_evidence.append(item.get("evidence_id"))
        
        hypothesis_evidence_map[h_id] = list(set(matching_evidence))
    
    return {
        "hypothesis_evidence_map": hypothesis_evidence_map,
        "status": "cross_referenced",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "cross_reference_hypotheses",
            "description": f"Mapped evidence to {len(hypothesis_evidence_map)} hypotheses",
            "timestamp": _now_iso(),
            "details": {
                "mappings": {k: len(v) for k, v in hypothesis_evidence_map.items()}
            }
        }]
    }


def generate_output(state: EvidenceState) -> dict:
    """
    Node 6: Generate final output.
    """
    run_id = state["run_id"]
    case_id = state["case_id"]
    inventory = state.get("inventory", {})
    
    logger.info(f"[{run_id}] Generating evidence collection output")
    
    output = {
        "case_id": case_id,
        "run_id": run_id,
        "generated_at": _now_iso(),
        "inventory": inventory,
        "hypothesis_evidence_map": state.get("hypothesis_evidence_map", {}),
        "module_status": state.get("module_status", {}),
        "available_modules": state.get("available_modules", []),
        "statistics": {
            "total_evidence": inventory.get("total_items", 0),
            "by_type": inventory.get("by_type", {}),
            "by_module": inventory.get("by_module", {}),
            "time_range": {
                "earliest": inventory.get("earliest_timestamp"),
                "latest": inventory.get("latest_timestamp")
            }
        },
        "reasoning_trace": state.get("reasoning_steps", [])
    }
    
    # Compute hash
    hash_value = f"sha256:{hashlib.sha256(json.dumps(output, sort_keys=True).encode()).hexdigest()}"
    
    # Record CoC
    try:
        conn = open_vault(case_id)
        coc_event_id = record_coc_event(
            conn=conn,
            case_id=case_id,
            event_type="EVIDENCE_COLLECTION_COMPLETED",
            actor="evidence_collection_agent",
            description=f"Collected {inventory.get('total_items', 0)} evidence items",
            data_hash=hash_value
        )
    except Exception as e:
        logger.warning(f"[{run_id}] Failed to record CoC: {e}")
        coc_event_id = None
    
    return {
        "output": output,
        "hash_value": hash_value,
        "coc_event_id": coc_event_id,
        "status": "completed"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD LANGGRAPH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def build_evidence_graph() -> StateGraph:
    """Build the LangGraph state machine for evidence collection."""
    workflow = StateGraph(EvidenceState)
    
    # Add nodes
    workflow.add_node("load_hypotheses", load_hypotheses)
    workflow.add_node("scan_modules", scan_modules)
    workflow.add_node("collect_timeline_evidence", collect_timeline_evidence)
    workflow.add_node("collect_anomaly_evidence", collect_anomaly_evidence)
    workflow.add_node("collect_correlation_evidence", collect_correlation_evidence)
    workflow.add_node("collect_crud_evidence", collect_crud_evidence)
    workflow.add_node("collect_network_evidence", collect_network_evidence)
    workflow.add_node("build_inventory", build_inventory)
    workflow.add_node("cross_reference_hypotheses", cross_reference_hypotheses)
    workflow.add_node("generate_output", generate_output)
    
    # Add edges
    workflow.set_entry_point("load_hypotheses")
    workflow.add_edge("load_hypotheses", "scan_modules")
    workflow.add_edge("scan_modules", "collect_timeline_evidence")
    workflow.add_edge("collect_timeline_evidence", "collect_anomaly_evidence")
    workflow.add_edge("collect_anomaly_evidence", "collect_correlation_evidence")
    workflow.add_edge("collect_correlation_evidence", "collect_crud_evidence")
    workflow.add_edge("collect_crud_evidence", "collect_network_evidence")
    workflow.add_edge("collect_network_evidence", "build_inventory")
    workflow.add_edge("build_inventory", "cross_reference_hypotheses")
    workflow.add_edge("cross_reference_hypotheses", "generate_output")
    workflow.add_edge("generate_output", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE COLLECTION AGENT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceCollectionAgent(BaseAgent):
    """
    Evidence Collection Agent.
    
    Gathers and catalogs forensic evidence from all modules.
    """
    
    def __init__(self, llm_provider: str = "ollama"):
        super().__init__(llm_provider=llm_provider)
        self._graph = build_evidence_graph()
    
    @property
    def agent_id(self) -> str:
        return "evidence_collection_agent"
    
    @property
    def agent_name(self) -> str:
        return "Evidence Collection Agent"
    
    @property
    def agent_description(self) -> str:
        return "Gathers and catalogs forensic evidence from all investigative modules"
    
    @property
    def dependencies(self) -> List[str]:
        return ["hypothesis_analysis_agent"]
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["case_id"],
            "properties": {
                "case_id": {"type": "string"},
                "hypotheses": {"type": "array"},
                "evidence_requirements": {"type": "array"}
            }
        }
    
    async def execute(self, state: BaseAgentState) -> BaseAgentState:
        """Execute the evidence collection pipeline."""
        input_data = state.get("input_data", {})
        
        evidence_state: EvidenceState = {
            "case_id": input_data.get("case_id", state.get("case_id", "")),
            "run_id": state.get("run_id", str(uuid.uuid4())),
            "hypotheses": input_data.get("hypotheses", []),
            "evidence_requirements": input_data.get("evidence_requirements", [])
        }
        
        result = await self._graph.ainvoke(evidence_state)
        
        state["output_data"] = result.get("output", {})
        
        self._add_reasoning_step(
            state,
            "evidence_collection_complete",
            f"Collected {result.get('inventory', {}).get('total_items', 0)} evidence items"
        )
        
        return state
    
    async def collect(
        self,
        case_id: str,
        hypotheses: List[Dict[str, Any]] = None,
        evidence_requirements: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to collect evidence for a case.
        """
        state: BaseAgentState = {
            "run_id": str(uuid.uuid4()),
            "case_id": case_id,
            "input_data": {
                "case_id": case_id,
                "hypotheses": hypotheses or [],
                "evidence_requirements": evidence_requirements or []
            }
        }
        
        result = await self.run(state)
        return result.get("output_data", {})


# Register with global registry
registry.register(EvidenceCollectionAgent())
