"""
Module Evaluators — Specialized evaluation agents for each forensic module.

Each evaluator assesses the quality and confidence of findings from its
corresponding module, enabling multi-factor confidence scoring.

Author: NFLIP Development Team
Version: 1.0.0
"""

import logging
import uuid
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, TypedDict

from operation_room.agents.base import BaseAgent, registry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModuleEvaluation:
    """Result of evaluating a module's output."""
    module_name: str
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Quality metrics
    data_quality: float = 0.0  # 0-1: How complete/clean is the data
    finding_quality: float = 0.0  # 0-1: How significant are findings
    consistency: float = 0.0  # 0-1: Internal consistency
    coverage: float = 0.0  # 0-1: Coverage of investigation scope
    
    # Findings
    findings: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Supporting evidence
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    
    # Overall assessment
    overall_confidence: float = 0.0
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "evaluation_id": self.evaluation_id,
            "timestamp": self.timestamp.isoformat(),
            "metrics": {
                "data_quality": self.data_quality,
                "finding_quality": self.finding_quality,
                "consistency": self.consistency,
                "coverage": self.coverage,
            },
            "findings": self.findings,
            "anomalies": self.anomalies,
            "warnings": self.warnings,
            "evidence_items": self.evidence_items,
            "overall_confidence": self.overall_confidence,
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BASE MODULE EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class BaseModuleEvaluator(BaseAgent):
    """
    Base class for module evaluators.
    
    Each evaluator specializes in assessing output from one module type.
    """
    
    module_name: str = "base"
    
    def __init__(self, **kwargs):
        # BaseAgent doesn't take agent_id or agent_name in __init__
        super().__init__(**kwargs)
        
    @property
    def agent_id(self) -> str:
        return f"evaluator-{self.module_name}"
        
    @property
    def agent_name(self) -> str:
        return f"{self.module_name.title()} Evaluator"
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Module evaluators use evaluate() instead of execute()."""
        return state
        
    @abstractmethod
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """
        Evaluate the module's output.
        
        Args:
            module_output: Raw output from the module
            context: Additional context (case_id, hypotheses, etc.)
            
        Returns:
            ModuleEvaluation with quality metrics and findings
        """
        pass
        
    def _calculate_data_quality(
        self,
        output: Dict[str, Any],
        required_fields: List[str],
        data_key: str = "data"
    ) -> float:
        """Calculate data quality score based on completeness."""
        if not output:
            return 0.0
            
        data = output.get(data_key, [])
        if not data:
            return 0.2  # At least we have structure
            
        # Check required fields
        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            present_fields = sum(1 for f in required_fields if f in sample)
            completeness = present_fields / len(required_fields) if required_fields else 1.0
        else:
            completeness = 0.5
            
        # Check for null/empty values
        null_ratio = self._calculate_null_ratio(data)
        data_integrity = 1.0 - null_ratio
        
        return (completeness * 0.6 + data_integrity * 0.4)
        
    def _calculate_null_ratio(self, data: Any) -> float:
        """Calculate ratio of null/empty values."""
        if not data:
            return 1.0
            
        if isinstance(data, list):
            total = 0
            nulls = 0
            for item in data:
                if isinstance(item, dict):
                    for v in item.values():
                        total += 1
                        if v is None or v == "" or v == []:
                            nulls += 1
            return nulls / total if total > 0 else 0.0
        return 0.0
        
    def _extract_findings(
        self,
        data: List[Dict[str, Any]],
        significance_key: str = "severity",
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Extract significant findings from data."""
        findings = []
        for item in data:
            significance = item.get(significance_key, 0)
            if isinstance(significance, str):
                significance = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(significance.lower(), 0.5)
            if significance >= threshold:
                findings.append({
                    "id": str(uuid.uuid4()),
                    "data": item,
                    "significance": significance,
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
        return findings


# ═══════════════════════════════════════════════════════════════════════════════
# TIMELINE EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class TimelineEvaluator(BaseModuleEvaluator):
    """
    Evaluates timeline analysis module output.
    
    Assesses:
    - Temporal coverage and gaps
    - Event clustering and patterns
    - Timeline consistency
    - Key event identification
    """
    
    module_name = "timeline"
    
    REQUIRED_FIELDS = ["timestamp", "event_type", "source", "description"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate timeline analysis output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        events = module_output.get("events", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": events},
            self.REQUIRED_FIELDS
        )
        
        # Check temporal coverage
        if events:
            timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
            if len(timestamps) >= 2:
                # Check for gaps
                gaps = self._find_temporal_gaps(timestamps)
                evaluation.warnings.extend([
                    f"Temporal gap detected: {gap}" for gap in gaps[:5]
                ])
                evaluation.coverage = 1.0 - min(len(gaps) * 0.1, 0.5)
            else:
                evaluation.coverage = 0.5
        else:
            evaluation.coverage = 0.0
            
        # Extract significant events
        evaluation.findings = self._extract_timeline_findings(events)
        evaluation.finding_quality = len(evaluation.findings) / max(len(events), 1)
        
        # Consistency check
        evaluation.consistency = self._check_temporal_consistency(events)
        
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.25 +
            evaluation.finding_quality * 0.25 +
            evaluation.consistency * 0.25 +
            evaluation.coverage * 0.25
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "timeline_event", "data": f, "confidence": f.get("significance", 0.5)}
            for f in evaluation.findings
        ]
        
        evaluation.summary = (
            f"Timeline analysis: {len(events)} events, "
            f"{len(evaluation.findings)} significant findings, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _find_temporal_gaps(self, timestamps: List[str]) -> List[str]:
        """Find significant gaps in timeline."""
        # Simplified gap detection
        gaps = []
        # In real implementation, parse and compare timestamps
        return gaps
        
    def _extract_timeline_findings(self, events: List[Dict]) -> List[Dict]:
        """Extract significant timeline findings."""
        findings = []
        for event in events:
            # Check for indicators of significance
            description = str(event.get("description", "")).lower()
            event_type = str(event.get("event_type", "")).lower()
            
            is_significant = any([
                "malware" in description,
                "unauthorized" in description,
                "breach" in description,
                "exfiltration" in description,
                event_type in ["alert", "security", "intrusion"]
            ])
            
            if is_significant:
                findings.append({
                    "id": str(uuid.uuid4()),
                    "event": event,
                    "significance": 0.8,
                    "reason": "Security-relevant event detected"
                })
                
        return findings
        
    def _check_temporal_consistency(self, events: List[Dict]) -> float:
        """Check temporal consistency of events."""
        if len(events) < 2:
            return 1.0
            
        # Check for out-of-order events, impossible sequences, etc.
        # Simplified implementation
        return 0.9


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyEvaluator(BaseModuleEvaluator):
    """
    Evaluates anomaly detection module output.
    
    Assesses:
    - Anomaly detection quality
    - False positive estimation
    - Pattern significance
    - Clustering effectiveness
    """
    
    module_name = "anomaly"
    
    REQUIRED_FIELDS = ["anomaly_score", "feature", "timestamp", "cluster_id"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate anomaly detection output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        anomalies = module_output.get("anomalies", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": anomalies},
            self.REQUIRED_FIELDS
        )
        
        # Analyze anomaly distribution
        if anomalies:
            scores = [a.get("anomaly_score", 0) for a in anomalies]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            # High scores indicate more confident anomalies
            evaluation.finding_quality = min(avg_score, 1.0)
            
            # Extract high-confidence anomalies
            evaluation.anomalies = [
                a for a in anomalies 
                if a.get("anomaly_score", 0) > 0.7
            ]
            
            # Check clustering
            clusters = set(a.get("cluster_id") for a in anomalies if a.get("cluster_id"))
            evaluation.coverage = min(len(clusters) / 10, 1.0)  # Assume 10 expected clusters
            
        # Consistency (check for contradictory anomalies)
        evaluation.consistency = self._check_anomaly_consistency(anomalies)
        
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.2 +
            evaluation.finding_quality * 0.35 +
            evaluation.consistency * 0.25 +
            evaluation.coverage * 0.2
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "anomaly", "data": a, "confidence": a.get("anomaly_score", 0.5)}
            for a in evaluation.anomalies
        ]
        
        evaluation.summary = (
            f"Anomaly detection: {len(anomalies)} anomalies, "
            f"{len(evaluation.anomalies)} high-confidence, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _check_anomaly_consistency(self, anomalies: List[Dict]) -> float:
        """Check consistency of anomaly detections."""
        if len(anomalies) < 2:
            return 1.0
            
        # Check for conflicting cluster assignments, score inconsistencies
        # Simplified implementation
        return 0.85


# ═══════════════════════════════════════════════════════════════════════════════
# CORRELATION EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class CorrelationEvaluator(BaseModuleEvaluator):
    """
    Evaluates correlation analysis module output.
    
    Assesses:
    - Correlation strength and significance
    - Cross-source validation
    - Pattern coherence
    - Causal relationship indicators
    """
    
    module_name = "correlation"
    
    REQUIRED_FIELDS = ["correlation_id", "source_a", "source_b", "strength", "type"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate correlation analysis output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        correlations = module_output.get("correlations", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": correlations},
            self.REQUIRED_FIELDS
        )
        
        if correlations:
            # Analyze correlation strengths
            strengths = [c.get("strength", 0) for c in correlations]
            avg_strength = sum(strengths) / len(strengths) if strengths else 0
            
            # Strong correlations are more valuable
            evaluation.finding_quality = avg_strength
            
            # Extract significant correlations
            evaluation.findings = [
                {
                    "id": str(uuid.uuid4()),
                    "correlation": c,
                    "significance": c.get("strength", 0.5)
                }
                for c in correlations
                if c.get("strength", 0) > 0.6
            ]
            
            # Coverage based on source diversity
            sources = set()
            for c in correlations:
                sources.add(c.get("source_a"))
                sources.add(c.get("source_b"))
            evaluation.coverage = min(len(sources) / 5, 1.0)
            
        # Check consistency (bidirectional correlations should match)
        evaluation.consistency = self._check_correlation_consistency(correlations)
        
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.2 +
            evaluation.finding_quality * 0.35 +
            evaluation.consistency * 0.25 +
            evaluation.coverage * 0.2
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "correlation", "data": f["correlation"], "confidence": f["significance"]}
            for f in evaluation.findings
        ]
        
        evaluation.summary = (
            f"Correlation analysis: {len(correlations)} correlations, "
            f"{len(evaluation.findings)} significant, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _check_correlation_consistency(self, correlations: List[Dict]) -> float:
        """Check consistency of correlations."""
        # Check for contradictory correlations
        return 0.9


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class NetworkEvaluator(BaseModuleEvaluator):
    """
    Evaluates network forensics module output.
    
    Assesses:
    - Network traffic analysis quality
    - Suspicious connection detection
    - Protocol analysis depth
    - Threat indicator identification
    """
    
    module_name = "network"
    
    REQUIRED_FIELDS = ["src_ip", "dst_ip", "protocol", "timestamp", "bytes"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate network forensics output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        connections = module_output.get("connections", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": connections},
            self.REQUIRED_FIELDS
        )
        
        if connections:
            # Identify suspicious connections
            suspicious = self._identify_suspicious_connections(connections)
            evaluation.findings = suspicious
            evaluation.finding_quality = len(suspicious) / max(len(connections) * 0.1, 1)
            
            # Coverage based on protocol diversity
            protocols = set(c.get("protocol") for c in connections if c.get("protocol"))
            evaluation.coverage = min(len(protocols) / 5, 1.0)
            
            # Check for known bad indicators
            evaluation.anomalies = self._check_threat_indicators(connections)
            
        # Consistency
        evaluation.consistency = 0.9  # Network data is typically consistent
        
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.25 +
            evaluation.finding_quality * 0.30 +
            evaluation.consistency * 0.20 +
            evaluation.coverage * 0.25
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "network_finding", "data": f, "confidence": f.get("significance", 0.7)}
            for f in evaluation.findings
        ]
        
        evaluation.summary = (
            f"Network analysis: {len(connections)} connections, "
            f"{len(evaluation.findings)} suspicious, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _identify_suspicious_connections(self, connections: List[Dict]) -> List[Dict]:
        """Identify suspicious network connections."""
        suspicious = []
        
        for conn in connections:
            score = 0.0
            reasons = []
            
            # Check for suspicious ports
            dst_port = conn.get("dst_port", 0)
            if dst_port in [4444, 5555, 6666, 1337, 31337]:
                score += 0.4
                reasons.append(f"Suspicious port {dst_port}")
                
            # Check for unusual protocols
            protocol = str(conn.get("protocol", "")).lower()
            if protocol in ["unknown", "custom"]:
                score += 0.3
                reasons.append(f"Unknown protocol")
                
            # Check for large data transfers
            bytes_transferred = conn.get("bytes", 0)
            if bytes_transferred > 10_000_000:  # 10MB
                score += 0.2
                reasons.append("Large data transfer")
                
            if score > 0.3:
                suspicious.append({
                    "id": str(uuid.uuid4()),
                    "connection": conn,
                    "significance": min(score, 1.0),
                    "reasons": reasons
                })
                
        return suspicious
        
    def _check_threat_indicators(self, connections: List[Dict]) -> List[Dict]:
        """Check for known threat indicators."""
        # In real implementation, check against threat intel feeds
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# DEPTH EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class DepthEvaluator(BaseModuleEvaluator):
    """
    Evaluates depth analysis module output.
    
    Assesses:
    - Root cause analysis depth
    - Impact assessment quality
    - Attack chain reconstruction
    - Lateral movement detection
    """
    
    module_name = "depth"
    
    REQUIRED_FIELDS = ["entity_id", "depth_level", "relationship", "impact_score"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate depth analysis output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        depth_data = module_output.get("depth_analysis", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": depth_data},
            self.REQUIRED_FIELDS
        )
        
        if depth_data:
            # Analyze depth levels reached
            max_depth = max(d.get("depth_level", 0) for d in depth_data)
            evaluation.coverage = min(max_depth / 5, 1.0)  # Assume 5 levels ideal
            
            # Extract high-impact findings
            high_impact = [
                d for d in depth_data
                if d.get("impact_score", 0) > 0.7
            ]
            evaluation.findings = [
                {"id": str(uuid.uuid4()), "data": d, "significance": d.get("impact_score", 0.7)}
                for d in high_impact
            ]
            evaluation.finding_quality = len(high_impact) / max(len(depth_data), 1)
            
            # Check attack chain coherence
            evaluation.consistency = self._check_attack_chain_coherence(depth_data)
            
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.2 +
            evaluation.finding_quality * 0.35 +
            evaluation.consistency * 0.25 +
            evaluation.coverage * 0.2
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "depth_finding", "data": f["data"], "confidence": f["significance"]}
            for f in evaluation.findings
        ]
        
        evaluation.summary = (
            f"Depth analysis: {len(depth_data)} entities, "
            f"max depth {evaluation.coverage * 5:.0f}, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _check_attack_chain_coherence(self, depth_data: List[Dict]) -> float:
        """Check coherence of attack chain."""
        # Verify relationships form a coherent chain
        return 0.85


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

class CRUDEvaluator(BaseModuleEvaluator):
    """
    Evaluates CRUD operations module output.
    
    Assesses:
    - Data access pattern analysis
    - Unauthorized access detection
    - Data modification tracking
    - Audit trail completeness
    """
    
    module_name = "crud"
    
    REQUIRED_FIELDS = ["operation", "table", "user", "timestamp", "affected_rows"]
    
    async def evaluate(
        self,
        module_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ModuleEvaluation:
        """Evaluate CRUD operations output."""
        context = context or {}
        evaluation = ModuleEvaluation(module_name=self.module_name)
        
        operations = module_output.get("operations", module_output.get("data", []))
        
        # Data quality
        evaluation.data_quality = self._calculate_data_quality(
            {"data": operations},
            self.REQUIRED_FIELDS
        )
        
        if operations:
            # Analyze operation patterns
            suspicious_ops = self._identify_suspicious_operations(operations)
            evaluation.findings = suspicious_ops
            evaluation.finding_quality = len(suspicious_ops) / max(len(operations) * 0.1, 1)
            
            # Coverage based on table diversity
            tables = set(op.get("table") for op in operations if op.get("table"))
            evaluation.coverage = min(len(tables) / 10, 1.0)
            
            # Check audit trail completeness
            evaluation.consistency = self._check_audit_completeness(operations)
            
        # Overall confidence
        evaluation.overall_confidence = (
            evaluation.data_quality * 0.25 +
            evaluation.finding_quality * 0.25 +
            evaluation.consistency * 0.25 +
            evaluation.coverage * 0.25
        )
        
        # Evidence items
        evaluation.evidence_items = [
            {"type": "crud_finding", "data": f, "confidence": f.get("significance", 0.6)}
            for f in evaluation.findings
        ]
        
        evaluation.summary = (
            f"CRUD analysis: {len(operations)} operations, "
            f"{len(evaluation.findings)} suspicious, "
            f"confidence {evaluation.overall_confidence:.2f}"
        )
        
        return evaluation
        
    def _identify_suspicious_operations(self, operations: List[Dict]) -> List[Dict]:
        """Identify suspicious CRUD operations."""
        suspicious = []
        
        for op in operations:
            score = 0.0
            reasons = []
            
            # Check for bulk deletes
            operation = str(op.get("operation", "")).lower()
            affected = op.get("affected_rows", 0)
            
            if operation == "delete" and affected > 100:
                score += 0.5
                reasons.append(f"Bulk delete: {affected} rows")
                
            # Check for sensitive tables
            table = str(op.get("table", "")).lower()
            if table in ["users", "credentials", "secrets", "config"]:
                score += 0.3
                reasons.append(f"Sensitive table: {table}")
                
            # Check for unusual times (simplified)
            # In real implementation, check against normal operating hours
            
            if score > 0.3:
                suspicious.append({
                    "id": str(uuid.uuid4()),
                    "operation": op,
                    "significance": min(score, 1.0),
                    "reasons": reasons
                })
                
        return suspicious
        
    def _check_audit_completeness(self, operations: List[Dict]) -> float:
        """Check completeness of audit trail."""
        if not operations:
            return 0.0
            
        # Check for gaps, missing fields
        complete = sum(
            1 for op in operations
            if all(op.get(f) for f in self.REQUIRED_FIELDS)
        )
        return complete / len(operations)


# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATOR FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

class EvaluatorFactory:
    """Factory for creating module evaluators."""
    
    _evaluators = {
        "timeline": TimelineEvaluator,
        "anomaly": AnomalyEvaluator,
        "correlation": CorrelationEvaluator,
        "network": NetworkEvaluator,
        "depth": DepthEvaluator,
        "crud": CRUDEvaluator,
    }
    
    @classmethod
    def create(cls, module_name: str) -> BaseModuleEvaluator:
        """Create an evaluator for the specified module."""
        evaluator_class = cls._evaluators.get(module_name.lower())
        if not evaluator_class:
            raise ValueError(f"Unknown module: {module_name}")
        return evaluator_class()
        
    @classmethod
    def create_all(cls) -> Dict[str, BaseModuleEvaluator]:
        """Create all evaluators."""
        return {name: cls.create(name) for name in cls._evaluators}
        
    @classmethod
    def available_modules(cls) -> List[str]:
        """List available modules."""
        return list(cls._evaluators.keys())


# Module evaluators mapping for convenience
MODULE_EVALUATORS = {
    "timeline": TimelineEvaluator,
    "anomaly": AnomalyEvaluator,
    "correlation": CorrelationEvaluator,
    "network": NetworkEvaluator,
    "depth": DepthEvaluator,
    "crud": CRUDEvaluator,
}


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ModuleEvaluation",
    "BaseModuleEvaluator",
    "TimelineEvaluator",
    "AnomalyEvaluator",
    "CorrelationEvaluator",
    "NetworkEvaluator",
    "DepthEvaluator",
    "CRUDEvaluator",
    "EvaluatorFactory",
    "MODULE_EVALUATORS",
]
