"""
Evidence Vault System — Immutable evidence storage with hash verification.

This module provides the Evidence Vault infrastructure:
- evidence.anchor: Mark events/findings as vault evidence
- evidence.query: Search and retrieve vault evidence
- evidence.snapshot: Create point-in-time evidence snapshots
- evidence.verify: Verify evidence integrity via SHA-256
- evidence.cite: Generate citations for reports

The Evidence Vault ensures:
1. All evidence is SHA-256 hashed for integrity
2. Cross-referencing between modules
3. Anchor marking for timeline events
4. Citation generation for reports
5. Complete audit trail

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from ..schemas import (
    EvidenceType,
    ModuleName,
    ConfidenceLevel,
)
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    with_evidence_hash,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE VAULT DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceCategory(str, Enum):
    """Categories of evidence in the vault."""
    TIMELINE_ANCHOR = "timeline_anchor"      # Anchored timeline events
    ANOMALY_FINDING = "anomaly_finding"      # Anomaly detections
    CORRELATION_NODE = "correlation_node"    # Entity graph nodes
    CORRELATION_EDGE = "correlation_edge"    # Entity relationships
    CRUD_OPERATION = "crud_operation"        # Data access events
    NETWORK_FLOW = "network_flow"            # Network connections
    EXFIL_CANDIDATE = "exfil_candidate"      # Exfiltration evidence
    DEPTH_METRIC = "depth_metric"            # Impact metrics
    CUSTOM = "custom"                        # User-defined evidence


class AnchorType(str, Enum):
    """Types of anchors for timeline events."""
    INVESTIGATION_START = "investigation_start"
    INVESTIGATION_END = "investigation_end"
    FIRST_MALICIOUS = "first_malicious"
    LAST_MALICIOUS = "last_malicious"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_ACCESS = "data_access"
    DATA_EXFILTRATION = "data_exfiltration"
    CREDENTIAL_ACCESS = "credential_access"
    PERSISTENCE = "persistence"
    CUSTOM = "custom"


class EvidenceItem(BaseModel):
    """A single piece of evidence in the vault."""
    evidence_id: str = Field(
        default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}",
        description="Unique evidence identifier"
    )
    case_id: str = Field(..., description="Associated case ID")
    investigation_id: Optional[str] = Field(None, description="Associated investigation ID")
    
    # Classification
    category: EvidenceCategory = Field(..., description="Evidence category")
    anchor_type: Optional[AnchorType] = Field(None, description="Anchor type if timeline anchor")
    
    # Source information
    source_module: ModuleName = Field(..., description="Module that produced this evidence")
    source_id: str = Field(..., description="Original ID from source module")
    source_run_id: Optional[str] = Field(None, description="Run ID if from analysis")
    
    # Evidence data (immutable)
    data: Dict[str, Any] = Field(..., description="Evidence data payload")
    data_hash: str = Field(..., description="SHA-256 hash of evidence data")
    
    # Key fields extracted for indexing
    entity_type: Optional[str] = Field(None, description="Entity type (USER, IP, HOST, etc.)")
    entity_value: Optional[str] = Field(None, description="Entity value")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp if applicable")
    
    # Confidence and severity
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_level: Optional[ConfidenceLevel] = Field(None)
    severity: Optional[str] = Field(None, description="HIGH/MEDIUM/LOW/INFO")
    
    # Metadata
    label: str = Field(..., description="Human-readable label")
    description: Optional[str] = Field(None, description="Detailed description")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    
    # Relationships
    related_evidence: List[str] = Field(default_factory=list, description="Related evidence IDs")
    hypothesis_ids: List[str] = Field(default_factory=list, description="Linked hypothesis IDs")
    
    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system", description="Creator (system/user)")
    
    # Citation info
    citation_count: int = Field(default=0, description="Times cited in reports")
    last_cited: Optional[datetime] = Field(None, description="Last citation timestamp")


class EvidenceSnapshot(BaseModel):
    """Point-in-time snapshot of evidence state."""
    snapshot_id: str = Field(
        default_factory=lambda: f"snap-{uuid.uuid4().hex[:12]}"
    )
    case_id: str
    investigation_id: Optional[str] = None
    
    # Snapshot content
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    snapshot_hash: str = Field(..., description="Combined hash of all evidence")
    
    # Metadata
    label: str = Field(..., description="Snapshot label")
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"


class EvidenceCitation(BaseModel):
    """Citation reference for reports."""
    citation_id: str = Field(
        default_factory=lambda: f"cite-{uuid.uuid4().hex[:8]}"
    )
    evidence_id: str
    
    # Citation format
    short_ref: str = Field(..., description="Short reference like [EV-001]")
    full_citation: str = Field(..., description="Full citation text")
    
    # Location in report
    report_section: Optional[str] = None
    page_number: Optional[int] = None
    
    # Verification
    hash_at_citation: str = Field(..., description="Hash when cited (for verification)")
    cited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE VAULT STORE
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceVault:
    """
    Central evidence storage with hash verification.
    
    In production, this would be backed by a database with full-text search.
    For now, we use in-memory storage with indexing.
    """
    
    _evidence: Dict[str, EvidenceItem] = {}
    _snapshots: Dict[str, EvidenceSnapshot] = {}
    _citations: Dict[str, EvidenceCitation] = {}
    
    # Indexes for fast lookup
    _by_case: Dict[str, Set[str]] = {}
    _by_category: Dict[str, Set[str]] = {}
    _by_source_module: Dict[str, Set[str]] = {}
    _by_entity: Dict[str, Set[str]] = {}
    _by_tag: Dict[str, Set[str]] = {}
    _by_hypothesis: Dict[str, Set[str]] = {}
    
    @classmethod
    def _compute_hash(cls, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of evidence data using canonical JSON."""
        # Sort keys for deterministic output (RFC 8785 canonical JSON)
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @classmethod
    def add(cls, evidence: EvidenceItem) -> str:
        """Add evidence to the vault."""
        # Verify hash
        computed_hash = cls._compute_hash(evidence.data)
        if evidence.data_hash != computed_hash:
            evidence.data_hash = computed_hash  # Auto-fix if not set
        
        # Store
        cls._evidence[evidence.evidence_id] = evidence
        
        # Update indexes
        if evidence.case_id not in cls._by_case:
            cls._by_case[evidence.case_id] = set()
        cls._by_case[evidence.case_id].add(evidence.evidence_id)
        
        category_key = evidence.category.value
        if category_key not in cls._by_category:
            cls._by_category[category_key] = set()
        cls._by_category[category_key].add(evidence.evidence_id)
        
        module_key = enum_value(evidence.source_module)
        if module_key not in cls._by_source_module:
            cls._by_source_module[module_key] = set()
        cls._by_source_module[module_key].add(evidence.evidence_id)
        
        if evidence.entity_value:
            entity_key = f"{evidence.entity_type}:{evidence.entity_value}"
            if entity_key not in cls._by_entity:
                cls._by_entity[entity_key] = set()
            cls._by_entity[entity_key].add(evidence.evidence_id)
        
        for tag in evidence.tags:
            if tag not in cls._by_tag:
                cls._by_tag[tag] = set()
            cls._by_tag[tag].add(evidence.evidence_id)
        
        for hyp_id in evidence.hypothesis_ids:
            if hyp_id not in cls._by_hypothesis:
                cls._by_hypothesis[hyp_id] = set()
            cls._by_hypothesis[hyp_id].add(evidence.evidence_id)
        
        logger.info(f"Evidence {evidence.evidence_id} added to vault ({evidence.category.value})")
        return evidence.evidence_id
    
    @classmethod
    def get(cls, evidence_id: str) -> Optional[EvidenceItem]:
        """Retrieve evidence by ID."""
        return cls._evidence.get(evidence_id)
    
    @classmethod
    def verify(cls, evidence_id: str) -> Tuple[bool, str]:
        """Verify evidence integrity."""
        evidence = cls._evidence.get(evidence_id)
        if not evidence:
            return False, "Evidence not found"
        
        computed_hash = cls._compute_hash(evidence.data)
        if computed_hash == evidence.data_hash:
            return True, "Hash verified"
        else:
            return False, f"Hash mismatch: expected {evidence.data_hash}, got {computed_hash}"
    
    @classmethod
    def query(
        cls,
        case_id: Optional[str] = None,
        category: Optional[EvidenceCategory] = None,
        source_module: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_value: Optional[str] = None,
        tags: Optional[List[str]] = None,
        hypothesis_id: Optional[str] = None,
        min_confidence: Optional[float] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[EvidenceItem]:
        """Query evidence with filters."""
        # Start with all evidence or filter by case
        if case_id:
            candidate_ids = cls._by_case.get(case_id, set())
        else:
            candidate_ids = set(cls._evidence.keys())
        
        # Apply filters by intersection
        if category:
            category_ids = cls._by_category.get(category.value, set())
            candidate_ids = candidate_ids & category_ids
        
        if source_module:
            module_ids = cls._by_source_module.get(source_module, set())
            candidate_ids = candidate_ids & module_ids
        
        if entity_value:
            entity_key = f"{entity_type}:{entity_value}" if entity_type else f"None:{entity_value}"
            entity_ids = cls._by_entity.get(entity_key, set())
            candidate_ids = candidate_ids & entity_ids
        
        if tags:
            for tag in tags:
                tag_ids = cls._by_tag.get(tag, set())
                candidate_ids = candidate_ids & tag_ids
        
        if hypothesis_id:
            hyp_ids = cls._by_hypothesis.get(hypothesis_id, set())
            candidate_ids = candidate_ids & hyp_ids
        
        # Get evidence items and apply remaining filters
        results = []
        for eid in candidate_ids:
            ev = cls._evidence.get(eid)
            if not ev:
                continue
            
            if min_confidence is not None and ev.confidence_score is not None:
                if ev.confidence_score < min_confidence:
                    continue
            
            if severity and ev.severity != severity:
                continue
            
            results.append(ev)
            
            if len(results) >= limit:
                break
        
        # Sort by timestamp (most recent first)
        results.sort(key=lambda e: e.timestamp or e.created_at, reverse=True)
        return results
    
    @classmethod
    def create_snapshot(
        cls,
        case_id: str,
        label: str,
        investigation_id: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> EvidenceSnapshot:
        """Create a point-in-time snapshot of evidence."""
        # Get evidence IDs
        if evidence_ids:
            ids = evidence_ids
        else:
            ids = list(cls._by_case.get(case_id, []))
        
        # Compute combined hash
        all_hashes = []
        for eid in sorted(ids):
            ev = cls._evidence.get(eid)
            if ev:
                all_hashes.append(ev.data_hash)
        
        combined = ":".join(all_hashes)
        snapshot_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        snapshot = EvidenceSnapshot(
            case_id=case_id,
            investigation_id=investigation_id,
            evidence_ids=ids,
            evidence_count=len(ids),
            snapshot_hash=snapshot_hash,
            label=label,
            description=description
        )
        
        cls._snapshots[snapshot.snapshot_id] = snapshot
        logger.info(f"Snapshot {snapshot.snapshot_id} created with {len(ids)} evidence items")
        return snapshot
    
    @classmethod
    def get_snapshot(cls, snapshot_id: str) -> Optional[EvidenceSnapshot]:
        """Get a snapshot by ID."""
        return cls._snapshots.get(snapshot_id)
    
    @classmethod
    def cite(
        cls,
        evidence_id: str,
        report_section: Optional[str] = None,
        page_number: Optional[int] = None
    ) -> Optional[EvidenceCitation]:
        """Create a citation for an evidence item."""
        evidence = cls._evidence.get(evidence_id)
        if not evidence:
            return None
        
        # Generate citation references
        # Short ref: [EV-XXX] where XXX is last 3 chars of ID
        short_ref = f"[EV-{evidence.evidence_id[-6:].upper()}]"
        
        # Full citation with details
        timestamp_str = evidence.timestamp.isoformat() if evidence.timestamp else "N/A"
        full_citation = (
            f"{short_ref} {evidence.label} "
            f"(Source: {enum_value(evidence.source_module)}, "
            f"ID: {evidence.source_id}, "
            f"Time: {timestamp_str}, "
            f"Hash: {evidence.data_hash[:16]}...)"
        )
        
        citation = EvidenceCitation(
            evidence_id=evidence_id,
            short_ref=short_ref,
            full_citation=full_citation,
            report_section=report_section,
            page_number=page_number,
            hash_at_citation=evidence.data_hash
        )
        
        cls._citations[citation.citation_id] = citation
        
        # Update evidence citation count
        evidence.citation_count += 1
        evidence.last_cited = datetime.now(timezone.utc)
        
        return citation
    
    @classmethod
    def get_citations(cls, evidence_id: str) -> List[EvidenceCitation]:
        """Get all citations for an evidence item."""
        return [c for c in cls._citations.values() if c.evidence_id == evidence_id]
    
    @classmethod
    def link_evidence(cls, evidence_id: str, related_id: str) -> bool:
        """Create bidirectional link between evidence items."""
        ev1 = cls._evidence.get(evidence_id)
        ev2 = cls._evidence.get(related_id)
        
        if not ev1 or not ev2:
            return False
        
        if related_id not in ev1.related_evidence:
            ev1.related_evidence.append(related_id)
        if evidence_id not in ev2.related_evidence:
            ev2.related_evidence.append(evidence_id)
        
        return True
    
    @classmethod
    def link_hypothesis(cls, evidence_id: str, hypothesis_id: str) -> bool:
        """Link evidence to a hypothesis."""
        evidence = cls._evidence.get(evidence_id)
        if not evidence:
            return False
        
        if hypothesis_id not in evidence.hypothesis_ids:
            evidence.hypothesis_ids.append(hypothesis_id)
            
            if hypothesis_id not in cls._by_hypothesis:
                cls._by_hypothesis[hypothesis_id] = set()
            cls._by_hypothesis[hypothesis_id].add(evidence_id)
        
        return True
    
    @classmethod
    def get_stats(cls, case_id: Optional[str] = None) -> Dict[str, Any]:
        """Get vault statistics."""
        if case_id:
            evidence_ids = cls._by_case.get(case_id, set())
        else:
            evidence_ids = set(cls._evidence.keys())
        
        # Count by category
        category_counts = {}
        module_counts = {}
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        total_citations = 0
        
        for eid in evidence_ids:
            ev = cls._evidence.get(eid)
            if not ev:
                continue
            
            cat = ev.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            mod = enum_value(ev.source_module)
            module_counts[mod] = module_counts.get(mod, 0) + 1
            
            if ev.severity:
                severity_counts[ev.severity] = severity_counts.get(ev.severity, 0) + 1
            
            total_citations += ev.citation_count
        
        return {
            "total_evidence": len(evidence_ids),
            "by_category": category_counts,
            "by_module": module_counts,
            "by_severity": severity_counts,
            "total_snapshots": len([s for s in cls._snapshots.values() 
                                   if not case_id or s.case_id == case_id]),
            "total_citations": total_citations
        }
    
    @classmethod
    def clear_case(cls, case_id: str) -> int:
        """Remove all evidence for a case (for testing/cleanup)."""
        evidence_ids = list(cls._by_case.get(case_id, []))
        
        for eid in evidence_ids:
            if eid in cls._evidence:
                del cls._evidence[eid]
        
        if case_id in cls._by_case:
            del cls._by_case[case_id]
        
        return len(evidence_ids)


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE FACTORY — Creates evidence from module outputs
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceFactory:
    """
    Factory for creating evidence items from various module outputs.
    
    Each method handles a specific type of module output and extracts
    the relevant fields for indexing.
    """
    
    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash."""
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @classmethod
    def from_timeline_event(
        cls,
        case_id: str,
        event: Dict[str, Any],
        anchor_type: AnchorType = AnchorType.CUSTOM,
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a timeline event."""
        event_id = event.get("tl_event_id") or event.get("event_id", str(uuid.uuid4()))
        timestamp_str = event.get("normalised_ts") or event.get("timestamp")
        
        # Parse timestamp
        timestamp = None
        if timestamp_str:
            if isinstance(timestamp_str, datetime):
                timestamp = timestamp_str
            else:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except:
                    pass
        
        # Build label
        if not label:
            action = event.get("action", "Event")
            actor = event.get("actor", "Unknown")
            label = f"{action} by {actor}"
        
        # Extract severity
        severity = event.get("severity", "INFO")
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.TIMELINE_ANCHOR,
            anchor_type=anchor_type,
            source_module=ModuleName.TIMELINE,
            source_id=event_id,
            data=event,
            data_hash=cls._compute_hash(event),
            entity_type="ACTOR",
            entity_value=event.get("actor"),
            timestamp=timestamp,
            severity=severity,
            label=label,
            description=event.get("detail"),
            tags=tags or []
        )
    
    @classmethod
    def from_anomaly(
        cls,
        case_id: str,
        anomaly: Dict[str, Any],
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from an anomaly detection result."""
        event_id = anomaly.get("tl_event_id") or anomaly.get("score_id", str(uuid.uuid4()))
        
        # Parse timestamp
        timestamp = None
        timestamp_str = anomaly.get("normalised_ts")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
            except:
                pass
        
        # Build label
        if not label:
            score = anomaly.get("anomaly_score", 0)
            actor = anomaly.get("actor", "Unknown")
            label = f"Anomaly (score: {score:.2f}) by {actor}"
        
        # Map score to confidence
        score = anomaly.get("anomaly_score", 0.5)
        confidence_level = (
            ConfidenceLevel.VERY_HIGH if score >= 0.9 else
            ConfidenceLevel.HIGH if score >= 0.75 else
            ConfidenceLevel.MODERATE if score >= 0.5 else
            ConfidenceLevel.LOW if score >= 0.25 else
            ConfidenceLevel.VERY_LOW
        )
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.ANOMALY_FINDING,
            source_module=ModuleName.ANOMALY,
            source_id=event_id,
            source_run_id=anomaly.get("run_id"),
            data=anomaly,
            data_hash=cls._compute_hash(anomaly),
            entity_type="ACTOR",
            entity_value=anomaly.get("actor"),
            timestamp=timestamp,
            confidence_score=score,
            confidence_level=confidence_level,
            severity="HIGH" if score >= 0.7 else "MEDIUM" if score >= 0.4 else "LOW",
            label=label,
            description=f"Anomaly detected with score {score:.2f}",
            tags=tags or ["anomaly"]
        )
    
    @classmethod
    def from_correlation_node(
        cls,
        case_id: str,
        node: Dict[str, Any],
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a correlation graph node."""
        node_id = node.get("node_id", str(uuid.uuid4()))
        
        entity_type = node.get("entity_type", "UNKNOWN")
        entity_value = node.get("entity_value", "")
        
        if not label:
            label = f"{entity_type}: {entity_value}"
        
        severity_score = node.get("severity_score", 0)
        severity = (
            "HIGH" if severity_score >= 7 else
            "MEDIUM" if severity_score >= 4 else
            "LOW"
        )
        
        # Parse timestamps
        first_seen = None
        if node.get("first_seen"):
            try:
                first_seen = datetime.fromisoformat(str(node["first_seen"]).replace("Z", "+00:00"))
            except:
                pass
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.CORRELATION_NODE,
            source_module=ModuleName.CORRELATION,
            source_id=node_id,
            source_run_id=node.get("run_id"),
            data=node,
            data_hash=cls._compute_hash(node),
            entity_type=entity_type,
            entity_value=entity_value,
            timestamp=first_seen,
            confidence_score=node.get("anomaly_score"),
            severity=severity,
            label=label,
            description=f"{entity_type} with {node.get('event_count', 0)} events",
            tags=tags or [entity_type.lower()]
        )
    
    @classmethod
    def from_correlation_edge(
        cls,
        case_id: str,
        edge: Dict[str, Any],
        source_node: Optional[Dict[str, Any]] = None,
        target_node: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a correlation graph edge."""
        edge_id = edge.get("edge_id", str(uuid.uuid4()))
        
        relationship = edge.get("relationship", "related_to")
        
        if not label:
            src = source_node.get("entity_value", "?") if source_node else "?"
            tgt = target_node.get("entity_value", "?") if target_node else "?"
            label = f"{src} → {relationship} → {tgt}"
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.CORRELATION_EDGE,
            source_module=ModuleName.CORRELATION,
            source_id=edge_id,
            source_run_id=edge.get("run_id"),
            data=edge,
            data_hash=cls._compute_hash(edge),
            entity_type="RELATIONSHIP",
            entity_value=relationship,
            confidence_score=edge.get("confidence_score"),
            severity="MEDIUM",
            label=label,
            description=f"Relationship with {edge.get('weight', 0)} evidence connections",
            tags=tags or ["relationship", relationship.lower().replace(" ", "_")]
        )
    
    @classmethod
    def from_crud_event(
        cls,
        case_id: str,
        crud_event: Dict[str, Any],
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a CRUD event."""
        event_id = crud_event.get("crud_event_id", str(uuid.uuid4()))
        
        crud_type = crud_event.get("crud_type", "UNKNOWN")
        target = crud_event.get("target_object", "")
        actor = crud_event.get("actor", "Unknown")
        
        if not label:
            label = f"{crud_type} on {target} by {actor}"
        
        # Parse timestamp
        timestamp = None
        if crud_event.get("normalised_ts"):
            try:
                timestamp = datetime.fromisoformat(str(crud_event["normalised_ts"]).replace("Z", "+00:00"))
            except:
                pass
        
        sensitivity = crud_event.get("sensitivity", "LOW")
        is_high_risk = crud_event.get("is_high_risk", False)
        
        severity = "HIGH" if is_high_risk or sensitivity in ["CRITICAL", "HIGH"] else "MEDIUM" if sensitivity == "MEDIUM" else "LOW"
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.CRUD_OPERATION,
            source_module=ModuleName.CRUD,
            source_id=event_id,
            source_run_id=crud_event.get("run_id"),
            data=crud_event,
            data_hash=cls._compute_hash(crud_event),
            entity_type="DATA_OBJECT",
            entity_value=target,
            timestamp=timestamp,
            confidence_score=crud_event.get("anomaly_score"),
            severity=severity,
            label=label,
            description=crud_event.get("risk_reason") if is_high_risk else f"{crud_type} operation on {sensitivity} data",
            tags=tags or [crud_type.lower(), sensitivity.lower()]
        )
    
    @classmethod
    def from_network_flow(
        cls,
        case_id: str,
        flow: Dict[str, Any],
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a network flow."""
        flow_id = flow.get("flow_id", str(uuid.uuid4()))
        
        src_ip = flow.get("src_ip", "?")
        dst_ip = flow.get("dst_ip", "?")
        protocol = flow.get("protocol", "TCP")
        
        if not label:
            label = f"{protocol} {src_ip} → {dst_ip}"
        
        # Parse timestamp
        timestamp = None
        if flow.get("normalised_ts"):
            try:
                timestamp = datetime.fromisoformat(str(flow["normalised_ts"]).replace("Z", "+00:00"))
            except:
                pass
        
        is_suspicious = flow.get("is_suspicious", False)
        severity = "HIGH" if is_suspicious else "INFO"
        
        # Determine entity - use destination IP as primary
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.NETWORK_FLOW,
            source_module=ModuleName.NETWORK,
            source_id=flow_id,
            source_run_id=flow.get("run_id"),
            data=flow,
            data_hash=cls._compute_hash(flow),
            entity_type="IP",
            entity_value=dst_ip,
            timestamp=timestamp,
            confidence_score=flow.get("threat_score"),
            severity=severity,
            label=label,
            description=flow.get("suspicion_reason") if is_suspicious else f"{flow.get('bytes_sent', 0)} bytes sent",
            tags=tags or [protocol.lower(), flow.get("direction", "unknown").lower()]
        )
    
    @classmethod
    def from_exfil_candidate(
        cls,
        case_id: str,
        exfil: Dict[str, Any],
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from an exfiltration candidate."""
        exfil_id = exfil.get("exfil_id", str(uuid.uuid4()))
        
        actor = exfil.get("actor", "Unknown")
        dst_ip = exfil.get("dst_ip", "?")
        data_target = exfil.get("data_target", "?")
        confidence = exfil.get("confidence", 0)
        
        if not label:
            label = f"Potential exfil: {data_target} → {dst_ip} by {actor}"
        
        # Parse timestamp
        timestamp = None
        if exfil.get("normalised_ts"):
            try:
                timestamp = datetime.fromisoformat(str(exfil["normalised_ts"]).replace("Z", "+00:00"))
            except:
                pass
        
        confidence_level = (
            ConfidenceLevel.VERY_HIGH if confidence >= 0.9 else
            ConfidenceLevel.HIGH if confidence >= 0.75 else
            ConfidenceLevel.MODERATE if confidence >= 0.5 else
            ConfidenceLevel.LOW if confidence >= 0.25 else
            ConfidenceLevel.VERY_LOW
        )
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.EXFIL_CANDIDATE,
            source_module=ModuleName.NETWORK,
            source_id=exfil_id,
            source_run_id=exfil.get("run_id"),
            data=exfil,
            data_hash=cls._compute_hash(exfil),
            entity_type="IP",
            entity_value=dst_ip,
            timestamp=timestamp,
            confidence_score=confidence,
            confidence_level=confidence_level,
            severity="HIGH" if confidence >= 0.5 else "MEDIUM",
            label=label,
            description=exfil.get("evidence_summary", f"Exfiltration confidence: {confidence:.2f}"),
            tags=tags or ["exfiltration", "data_theft"]
        )
    
    @classmethod
    def from_depth_metric(
        cls,
        case_id: str,
        metric: Dict[str, Any],
        dimension: str,
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        investigation_id: Optional[str] = None
    ) -> EvidenceItem:
        """Create evidence from a depth/impact metric."""
        detail_id = metric.get("detail_id", str(uuid.uuid4()))
        
        metric_name = metric.get("metric_name", "unknown")
        metric_value = metric.get("metric_value", 0)
        
        if not label:
            label = f"{dimension} depth: {metric_name} = {metric_value}"
        
        # Severity based on value vs max
        max_value = metric.get("max_value", 10)
        ratio = metric_value / max_value if max_value > 0 else 0
        severity = "HIGH" if ratio >= 0.7 else "MEDIUM" if ratio >= 0.4 else "LOW"
        
        return EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.DEPTH_METRIC,
            source_module=ModuleName.DEPTH,
            source_id=detail_id,
            source_run_id=metric.get("run_id"),
            data=metric,
            data_hash=cls._compute_hash(metric),
            entity_type="METRIC",
            entity_value=metric_name,
            confidence_score=ratio,
            severity=severity,
            label=label,
            description=f"{dimension} impact: {metric_name} at {ratio:.0%} of maximum",
            tags=tags or [dimension.lower(), "impact"]
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="evidence.anchor",
    category=ToolCategory.EVIDENCE,
    description="Mark an event or finding as anchored evidence in the vault. Anchors are key evidence points used in reports.",
    requires_case_id=True,
    tags={"evidence", "anchor", "vault"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="EVIDENCE_ANCHOR")
async def anchor_evidence(
    case_id: str,
    source_module: str,
    source_id: str,
    anchor_type: str = "custom",
    label: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    event_data: Optional[Dict[str, Any]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Anchor an event or finding as vault evidence.
    
    This marks important events as "anchor points" that will be:
    1. Preserved with SHA-256 hash verification
    2. Used for timeline reconstruction
    3. Cited in generated reports
    4. Cross-referenced with other evidence
    
    Args:
        case_id: Target case ID
        source_module: Module that produced this evidence (timeline, anomaly, etc.)
        source_id: Original ID from the source module
        anchor_type: Type of anchor (investigation_start, first_malicious, etc.)
        label: Human-readable label
        description: Detailed description
        tags: User-defined tags
        event_data: Full event data (if not retrievable from module)
        investigation_id: Associated investigation ID
    
    Returns:
        Evidence item details with vault ID and hash
    """
    logger.info(f"Anchoring evidence from {source_module}: {source_id}")
    
    # Parse module name
    try:
        module = ModuleName(source_module.lower())
    except ValueError:
        module = ModuleName.TIMELINE  # Default
    
    # Parse anchor type
    try:
        anchor = AnchorType(anchor_type.lower())
    except ValueError:
        anchor = AnchorType.CUSTOM
    
    # Get or construct event data
    if not event_data:
        # In production, would fetch from actual module
        event_data = {
            "source_module": source_module,
            "source_id": source_id,
            "case_id": case_id,
            "anchored_at": datetime.now(timezone.utc).isoformat()
        }
    
    # Create evidence based on module type
    if module == ModuleName.TIMELINE:
        evidence = EvidenceFactory.from_timeline_event(
            case_id=case_id,
            event=event_data,
            anchor_type=anchor,
            label=label,
            tags=tags,
            investigation_id=investigation_id
        )
    elif module == ModuleName.ANOMALY:
        evidence = EvidenceFactory.from_anomaly(
            case_id=case_id,
            anomaly=event_data,
            label=label,
            tags=tags,
            investigation_id=investigation_id
        )
    elif module == ModuleName.CORRELATION:
        evidence = EvidenceFactory.from_correlation_node(
            case_id=case_id,
            node=event_data,
            label=label,
            tags=tags,
            investigation_id=investigation_id
        )
    elif module == ModuleName.CRUD:
        evidence = EvidenceFactory.from_crud_event(
            case_id=case_id,
            crud_event=event_data,
            label=label,
            tags=tags,
            investigation_id=investigation_id
        )
    elif module == ModuleName.NETWORK:
        evidence = EvidenceFactory.from_network_flow(
            case_id=case_id,
            flow=event_data,
            label=label,
            tags=tags,
            investigation_id=investigation_id
        )
    else:
        # Generic evidence
        evidence = EvidenceItem(
            case_id=case_id,
            investigation_id=investigation_id,
            category=EvidenceCategory.CUSTOM,
            anchor_type=anchor,
            source_module=module,
            source_id=source_id,
            data=event_data,
            data_hash=EvidenceFactory._compute_hash(event_data),
            label=label or f"Evidence from {source_module}",
            description=description,
            tags=tags or []
        )
    
    # Override description if provided
    if description:
        evidence.description = description
    
    # Add to vault
    EvidenceVault.add(evidence)
    
    return {
        "success": True,
        "evidence_id": evidence.evidence_id,
        "category": evidence.category.value,
        "anchor_type": evidence.anchor_type.value if evidence.anchor_type else None,
        "source_module": enum_value(evidence.source_module),
        "source_id": evidence.source_id,
        "label": evidence.label,
        "data_hash": evidence.data_hash,
        "entity": {
            "type": evidence.entity_type,
            "value": evidence.entity_value
        } if evidence.entity_value else None,
        "severity": evidence.severity,
        "citation_ref": f"[EV-{evidence.evidence_id[-6:].upper()}]",
        "created_at": evidence.created_at.isoformat()
    }


@mcp_tool(
    name="evidence.query",
    category=ToolCategory.EVIDENCE,
    description="Search and retrieve evidence from the vault with filters.",
    requires_case_id=True,
    tags={"evidence", "search", "vault"}
)
@audit_trail(operation="EVIDENCE_QUERY")
async def query_evidence(
    case_id: str,
    category: Optional[str] = None,
    source_module: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_value: Optional[str] = None,
    tags: Optional[List[str]] = None,
    hypothesis_id: Optional[str] = None,
    min_confidence: Optional[float] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Query evidence from the vault with filters.
    
    Args:
        case_id: Target case ID
        category: Evidence category filter
        source_module: Source module filter
        entity_type: Entity type filter (USER, IP, HOST, etc.)
        entity_value: Entity value filter
        tags: Tag filters (all must match)
        hypothesis_id: Filter by linked hypothesis
        min_confidence: Minimum confidence score
        severity: Severity filter (HIGH/MEDIUM/LOW)
        limit: Maximum results
    
    Returns:
        List of matching evidence items
    """
    # Parse category
    cat = None
    if category:
        try:
            cat = EvidenceCategory(category.lower())
        except ValueError:
            pass
    
    # Query vault
    results = EvidenceVault.query(
        case_id=case_id,
        category=cat,
        source_module=source_module,
        entity_type=entity_type,
        entity_value=entity_value,
        tags=tags,
        hypothesis_id=hypothesis_id,
        min_confidence=min_confidence,
        severity=severity,
        limit=limit
    )
    
    return {
        "success": True,
        "count": len(results),
        "evidence": [
            {
                "evidence_id": ev.evidence_id,
                "category": ev.category.value,
                "anchor_type": ev.anchor_type.value if ev.anchor_type else None,
                "source_module": enum_value(ev.source_module),
                "source_id": ev.source_id,
                "label": ev.label,
                "description": ev.description,
                "entity": {
                    "type": ev.entity_type,
                    "value": ev.entity_value
                } if ev.entity_value else None,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
                "confidence_score": ev.confidence_score,
                "confidence_level": enum_value(ev.confidence_level) if ev.confidence_level else None,
                "severity": ev.severity,
                "tags": ev.tags,
                "data_hash": ev.data_hash[:16] + "...",
                "citation_ref": f"[EV-{ev.evidence_id[-6:].upper()}]",
                "citation_count": ev.citation_count,
                "related_count": len(ev.related_evidence),
                "created_at": ev.created_at.isoformat()
            }
            for ev in results
        ]
    }


@mcp_tool(
    name="evidence.snapshot",
    category=ToolCategory.EVIDENCE,
    description="Create a point-in-time snapshot of evidence for the case.",
    requires_case_id=True,
    tags={"evidence", "snapshot", "vault"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="EVIDENCE_SNAPSHOT")
async def create_evidence_snapshot(
    case_id: str,
    label: str,
    description: Optional[str] = None,
    evidence_ids: Optional[List[str]] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Create a point-in-time snapshot of evidence.
    
    Snapshots capture the state of evidence at a specific moment,
    allowing verification that evidence hasn't changed since collection.
    
    Args:
        case_id: Target case ID
        label: Snapshot label (e.g., "Pre-Analysis", "Final Report")
        description: Detailed description
        evidence_ids: Specific evidence to include (all if not specified)
        investigation_id: Associated investigation ID
    
    Returns:
        Snapshot details with combined hash
    """
    snapshot = EvidenceVault.create_snapshot(
        case_id=case_id,
        label=label,
        investigation_id=investigation_id,
        evidence_ids=evidence_ids,
        description=description
    )
    
    return {
        "success": True,
        "snapshot_id": snapshot.snapshot_id,
        "label": snapshot.label,
        "description": snapshot.description,
        "evidence_count": snapshot.evidence_count,
        "snapshot_hash": snapshot.snapshot_hash,
        "created_at": snapshot.created_at.isoformat(),
        "verification_note": "Use evidence.verify with this hash to verify integrity"
    }


@mcp_tool(
    name="evidence.verify",
    category=ToolCategory.EVIDENCE,
    description="Verify evidence integrity using SHA-256 hash.",
    requires_case_id=False,
    tags={"evidence", "verify", "integrity"}
)
@audit_trail(operation="EVIDENCE_VERIFY")
async def verify_evidence(
    evidence_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Verify evidence integrity.
    
    Checks that the evidence data hasn't been modified since collection
    by comparing computed hash with stored hash.
    
    Args:
        evidence_id: Single evidence item to verify
        snapshot_id: Snapshot to verify (all contained evidence)
    
    Returns:
        Verification result with pass/fail status
    """
    if evidence_id:
        valid, message = EvidenceVault.verify(evidence_id)
        return {
            "success": True,
            "verified": valid,
            "evidence_id": evidence_id,
            "message": message
        }
    
    elif snapshot_id:
        snapshot = EvidenceVault.get_snapshot(snapshot_id)
        if not snapshot:
            return {
                "success": False,
                "error": f"Snapshot {snapshot_id} not found"
            }
        
        # Verify all evidence in snapshot
        results = []
        all_valid = True
        
        for eid in snapshot.evidence_ids:
            valid, message = EvidenceVault.verify(eid)
            results.append({
                "evidence_id": eid,
                "valid": valid,
                "message": message
            })
            if not valid:
                all_valid = False
        
        # Recompute snapshot hash
        all_hashes = []
        for eid in sorted(snapshot.evidence_ids):
            ev = EvidenceVault.get(eid)
            if ev:
                all_hashes.append(ev.data_hash)
        
        combined = ":".join(all_hashes)
        computed_hash = hashlib.sha256(combined.encode()).hexdigest()
        hash_match = computed_hash == snapshot.snapshot_hash
        
        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "snapshot_valid": all_valid and hash_match,
            "hash_match": hash_match,
            "expected_hash": snapshot.snapshot_hash,
            "computed_hash": computed_hash,
            "evidence_count": len(snapshot.evidence_ids),
            "evidence_results": results
        }
    
    else:
        return {
            "success": False,
            "error": "Provide either evidence_id or snapshot_id"
        }


@mcp_tool(
    name="evidence.cite",
    category=ToolCategory.EVIDENCE,
    description="Generate a citation for evidence to use in reports.",
    requires_case_id=False,
    tags={"evidence", "cite", "report"}
)
@audit_trail(operation="EVIDENCE_CITE")
async def cite_evidence(
    evidence_id: str,
    report_section: Optional[str] = None,
    page_number: Optional[int] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Generate a citation for evidence.
    
    Creates a formatted citation reference for use in reports,
    including verification hash for integrity.
    
    Args:
        evidence_id: Evidence to cite
        report_section: Section where cited
        page_number: Page number where cited
    
    Returns:
        Citation with short and full reference formats
    """
    citation = EvidenceVault.cite(
        evidence_id=evidence_id,
        report_section=report_section,
        page_number=page_number
    )
    
    if not citation:
        return {
            "success": False,
            "error": f"Evidence {evidence_id} not found"
        }
    
    evidence = EvidenceVault.get(evidence_id)
    
    return {
        "success": True,
        "citation_id": citation.citation_id,
        "evidence_id": evidence_id,
        "short_ref": citation.short_ref,
        "full_citation": citation.full_citation,
        "report_section": citation.report_section,
        "hash_at_citation": citation.hash_at_citation,
        "cited_at": citation.cited_at.isoformat(),
        "evidence_summary": {
            "label": evidence.label if evidence else None,
            "category": evidence.category.value if evidence else None,
            "severity": evidence.severity if evidence else None
        }
    }


@mcp_tool(
    name="evidence.link",
    category=ToolCategory.EVIDENCE,
    description="Link evidence items together or to hypotheses.",
    requires_case_id=False,
    tags={"evidence", "link", "relationship"}
)
@audit_trail(operation="EVIDENCE_LINK")
async def link_evidence(
    evidence_id: str,
    related_evidence_id: Optional[str] = None,
    hypothesis_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Link evidence items together or to hypotheses.
    
    Creates relationships between evidence for cross-referencing
    and hypothesis support tracking.
    
    Args:
        evidence_id: Primary evidence item
        related_evidence_id: Evidence to link (bidirectional)
        hypothesis_id: Hypothesis to link
    
    Returns:
        Link confirmation
    """
    results = []
    
    if related_evidence_id:
        success = EvidenceVault.link_evidence(evidence_id, related_evidence_id)
        results.append({
            "type": "evidence_link",
            "target": related_evidence_id,
            "success": success
        })
    
    if hypothesis_id:
        success = EvidenceVault.link_hypothesis(evidence_id, hypothesis_id)
        results.append({
            "type": "hypothesis_link",
            "target": hypothesis_id,
            "success": success
        })
    
    if not results:
        return {
            "success": False,
            "error": "Provide related_evidence_id or hypothesis_id"
        }
    
    return {
        "success": all(r["success"] for r in results),
        "evidence_id": evidence_id,
        "links": results
    }


@mcp_tool(
    name="evidence.stats",
    category=ToolCategory.EVIDENCE,
    description="Get evidence vault statistics for a case.",
    requires_case_id=True,
    tags={"evidence", "stats", "summary"}
)
@audit_trail(operation="EVIDENCE_STATS")
async def get_evidence_stats(
    case_id: str,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get evidence vault statistics.
    
    Returns counts and breakdowns of evidence by category,
    module, severity, etc.
    
    Args:
        case_id: Target case ID
    
    Returns:
        Statistics summary
    """
    stats = EvidenceVault.get_stats(case_id)
    
    return {
        "success": True,
        "case_id": case_id,
        "statistics": stats
    }


@mcp_tool(
    name="evidence.get",
    category=ToolCategory.EVIDENCE,
    description="Get full evidence details including raw data.",
    requires_case_id=False,
    tags={"evidence", "get", "detail"}
)
@audit_trail(operation="EVIDENCE_GET")
async def get_evidence(
    evidence_id: str,
    include_data: bool = True,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get full evidence details.
    
    Args:
        evidence_id: Evidence to retrieve
        include_data: Include raw data payload
    
    Returns:
        Full evidence details
    """
    evidence = EvidenceVault.get(evidence_id)
    
    if not evidence:
        return {
            "success": False,
            "error": f"Evidence {evidence_id} not found"
        }
    
    result = {
        "success": True,
        "evidence": {
            "evidence_id": evidence.evidence_id,
            "case_id": evidence.case_id,
            "investigation_id": evidence.investigation_id,
            "category": evidence.category.value,
            "anchor_type": evidence.anchor_type.value if evidence.anchor_type else None,
            "source_module": enum_value(evidence.source_module),
            "source_id": evidence.source_id,
            "source_run_id": evidence.source_run_id,
            "data_hash": evidence.data_hash,
            "entity": {
                "type": evidence.entity_type,
                "value": evidence.entity_value
            } if evidence.entity_value else None,
            "timestamp": evidence.timestamp.isoformat() if evidence.timestamp else None,
            "confidence_score": evidence.confidence_score,
            "confidence_level": enum_value(evidence.confidence_level) if evidence.confidence_level else None,
            "severity": evidence.severity,
            "label": evidence.label,
            "description": evidence.description,
            "tags": evidence.tags,
            "related_evidence": evidence.related_evidence,
            "hypothesis_ids": evidence.hypothesis_ids,
            "citation_count": evidence.citation_count,
            "last_cited": evidence.last_cited.isoformat() if evidence.last_cited else None,
            "created_at": evidence.created_at.isoformat(),
            "created_by": evidence.created_by
        }
    }
    
    if include_data:
        result["evidence"]["data"] = evidence.data
    
    return result
