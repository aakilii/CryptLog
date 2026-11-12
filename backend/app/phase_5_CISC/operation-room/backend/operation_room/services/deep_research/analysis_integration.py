"""
Analysis Module Integration for Deep Research.

Connects the Deep Research Orchestrator to existing analysis modules:
- Timeline Analysis
- Anomaly Detection
- Correlation Analysis
- CRUD Analysis
- Network Analysis
- Depth Analysis
- Evidence Vault
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json


logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result from an analysis module."""
    module_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    confidence: float = 0.0
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class AnalysisIntegration:
    """
    Integrates deep research with existing analysis modules.
    
    Provides a unified interface to:
    - Execute analysis modules
    - Collect evidence from results
    - Store in evidence vault
    - Track provenance
    """
    
    def __init__(self, case_id: str):
        """Initialize with case context."""
        self.case_id = case_id
        self._results: Dict[str, List[AnalysisResult]] = {}
    
    async def run_timeline_analysis(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        entity_filter: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Run timeline analysis on case logs.
        
        Returns unified timeline of events.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.timeline_service import TimelineService
            
            service = TimelineService(self.case_id)
            
            # Get timeline events
            events = await service.get_timeline(
                start_time=time_range_start,
                end_time=time_range_end,
            )
            
            # Extract evidence references
            evidence_refs = []
            for event in events[:100]:  # Limit for processing
                if event.get("evidence_id"):
                    evidence_refs.append(event["evidence_id"])
            
            result = AnalysisResult(
                module_name="timeline",
                success=True,
                data={
                    "event_count": len(events),
                    "events": events[:50],  # Sample
                    "time_range": {
                        "start": time_range_start,
                        "end": time_range_end,
                    },
                },
                evidence_refs=evidence_refs,
                confidence=0.9,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"Timeline analysis failed: {e}")
            result = AnalysisResult(
                module_name="timeline",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("timeline", result)
        return result
    
    async def run_anomaly_detection(
        self,
        threshold: float = 0.7,
        algorithms: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Run anomaly detection on case data.
        
        Identifies unusual patterns and outliers.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.anomaly_agent import AnomalyAgent
            
            agent = AnomalyAgent(self.case_id)
            
            # Run detection
            anomalies = await agent.detect_anomalies(
                threshold=threshold,
                algorithms=algorithms or ["isolation_forest", "local_outlier"],
            )
            
            evidence_refs = [a.get("evidence_id") for a in anomalies if a.get("evidence_id")]
            
            result = AnalysisResult(
                module_name="anomaly",
                success=True,
                data={
                    "anomaly_count": len(anomalies),
                    "anomalies": anomalies[:20],
                    "threshold": threshold,
                    "algorithms": algorithms or ["isolation_forest", "local_outlier"],
                },
                evidence_refs=evidence_refs,
                confidence=0.85,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            result = AnalysisResult(
                module_name="anomaly",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("anomaly", result)
        return result
    
    async def run_correlation_analysis(
        self,
        entities: Optional[List[str]] = None,
        correlation_type: str = "entity",
    ) -> AnalysisResult:
        """
        Run correlation analysis on case data.
        
        Identifies relationships between entities and events.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.correlation_agent import CorrelationAgent
            
            agent = CorrelationAgent(self.case_id)
            
            # Run correlation
            correlations = await agent.find_correlations(
                entities=entities,
                correlation_type=correlation_type,
            )
            
            evidence_refs = []
            for corr in correlations:
                evidence_refs.extend(corr.get("evidence_ids", []))
            
            result = AnalysisResult(
                module_name="correlation",
                success=True,
                data={
                    "correlation_count": len(correlations),
                    "correlations": correlations[:20],
                    "correlation_type": correlation_type,
                    "entities_analyzed": entities or "all",
                },
                evidence_refs=list(set(evidence_refs)),
                confidence=0.8,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}")
            result = AnalysisResult(
                module_name="correlation",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("correlation", result)
        return result
    
    async def run_crud_analysis(
        self,
        target_files: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Run CRUD (Create/Read/Update/Delete) analysis.
        
        Tracks file operations and data modifications.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.crud_agent import CRUDAgent
            
            agent = CRUDAgent(self.case_id)
            
            # Analyze file operations
            operations = await agent.analyze_operations(
                target_files=target_files,
            )
            
            evidence_refs = [op.get("evidence_id") for op in operations if op.get("evidence_id")]
            
            result = AnalysisResult(
                module_name="crud",
                success=True,
                data={
                    "operation_count": len(operations),
                    "operations": operations[:30],
                    "summary": {
                        "creates": sum(1 for op in operations if op.get("type") == "create"),
                        "reads": sum(1 for op in operations if op.get("type") == "read"),
                        "updates": sum(1 for op in operations if op.get("type") == "update"),
                        "deletes": sum(1 for op in operations if op.get("type") == "delete"),
                    },
                },
                evidence_refs=evidence_refs,
                confidence=0.9,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"CRUD analysis failed: {e}")
            result = AnalysisResult(
                module_name="crud",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("crud", result)
        return result
    
    async def run_network_analysis(
        self,
        ip_filter: Optional[List[str]] = None,
        protocol_filter: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Run network traffic analysis.
        
        Analyzes network connections and data transfers.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.network_agent import NetworkAgent
            
            agent = NetworkAgent(self.case_id)
            
            # Analyze network
            connections = await agent.analyze_connections(
                ip_filter=ip_filter,
                protocol_filter=protocol_filter,
            )
            
            evidence_refs = [c.get("evidence_id") for c in connections if c.get("evidence_id")]
            
            # Extract unique IPs
            unique_ips = set()
            for conn in connections:
                if conn.get("source_ip"):
                    unique_ips.add(conn["source_ip"])
                if conn.get("dest_ip"):
                    unique_ips.add(conn["dest_ip"])
            
            result = AnalysisResult(
                module_name="network",
                success=True,
                data={
                    "connection_count": len(connections),
                    "connections": connections[:30],
                    "unique_ips": list(unique_ips),
                    "ip_count": len(unique_ips),
                },
                evidence_refs=evidence_refs,
                confidence=0.85,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"Network analysis failed: {e}")
            result = AnalysisResult(
                module_name="network",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("network", result)
        return result
    
    async def run_depth_analysis(
        self,
        entity_id: str,
        depth: int = 3,
    ) -> AnalysisResult:
        """
        Run depth-first analysis on a specific entity.
        
        Traces entity relationships and activities.
        """
        start_time = datetime.now()
        
        try:
            from operation_room.services.depth_agent import DepthAgent
            
            agent = DepthAgent(self.case_id)
            
            # Deep trace
            trace = await agent.trace_entity(
                entity_id=entity_id,
                max_depth=depth,
            )
            
            evidence_refs = trace.get("evidence_ids", [])
            
            result = AnalysisResult(
                module_name="depth",
                success=True,
                data={
                    "entity_id": entity_id,
                    "depth_reached": trace.get("depth", 0),
                    "nodes_visited": trace.get("node_count", 0),
                    "trace": trace,
                },
                evidence_refs=evidence_refs,
                confidence=0.75,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
            
        except Exception as e:
            logger.error(f"Depth analysis failed: {e}")
            result = AnalysisResult(
                module_name="depth",
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )
        
        self._store_result("depth", result)
        return result
    
    async def store_evidence(
        self,
        data: Dict[str, Any],
        evidence_type: str,
        source_module: str,
    ) -> str:
        """
        Store analysis result in evidence vault.
        
        Returns evidence ID with SHA-256 hash.
        """
        try:
            from operation_room.services.evidence_service import EvidenceService
            
            service = EvidenceService(self.case_id)
            
            evidence_id = await service.store_evidence(
                data=json.dumps(data),
                evidence_type=evidence_type,
                source=source_module,
                metadata={
                    "module": source_module,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            
            return evidence_id
            
        except Exception as e:
            logger.error(f"Failed to store evidence: {e}")
            raise
    
    async def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence from vault by ID."""
        try:
            from operation_room.services.evidence_service import EvidenceService
            
            service = EvidenceService(self.case_id)
            return await service.get_evidence(evidence_id)
            
        except Exception as e:
            logger.error(f"Failed to get evidence: {e}")
            return None
    
    def _store_result(self, module: str, result: AnalysisResult) -> None:
        """Store result for later retrieval."""
        if module not in self._results:
            self._results[module] = []
        self._results[module].append(result)
    
    def get_results(self, module: Optional[str] = None) -> List[AnalysisResult]:
        """Get stored results."""
        if module:
            return self._results.get(module, [])
        
        all_results = []
        for results in self._results.values():
            all_results.extend(results)
        return all_results
    
    def get_all_evidence_refs(self) -> List[str]:
        """Get all evidence references from all analyses."""
        refs = set()
        for results in self._results.values():
            for result in results:
                refs.update(result.evidence_refs)
        return list(refs)
    
    async def run_all_analyses(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
    ) -> Dict[str, AnalysisResult]:
        """
        Run all available analysis modules.
        
        Returns dict of module_name -> result.
        """
        results = {}
        
        # Timeline
        results["timeline"] = await self.run_timeline_analysis(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )
        
        # Anomaly
        results["anomaly"] = await self.run_anomaly_detection()
        
        # Correlation
        results["correlation"] = await self.run_correlation_analysis()
        
        # CRUD
        results["crud"] = await self.run_crud_analysis()
        
        # Network
        results["network"] = await self.run_network_analysis()
        
        return results
    
    def compute_overall_confidence(self) -> float:
        """Compute overall confidence from all analyses."""
        all_results = self.get_results()
        if not all_results:
            return 0.0
        
        successful = [r for r in all_results if r.success]
        if not successful:
            return 0.0
        
        return sum(r.confidence for r in successful) / len(successful)
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary of all analyses."""
        all_results = self.get_results()
        
        return {
            "case_id": self.case_id,
            "total_analyses": len(all_results),
            "successful": sum(1 for r in all_results if r.success),
            "failed": sum(1 for r in all_results if not r.success),
            "evidence_collected": len(self.get_all_evidence_refs()),
            "overall_confidence": self.compute_overall_confidence(),
            "modules": {
                module: {
                    "runs": len(results),
                    "latest_success": results[-1].success if results else None,
                    "latest_confidence": results[-1].confidence if results else 0,
                }
                for module, results in self._results.items()
            },
        }
