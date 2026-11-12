"""
Network Analysis Tool - Universal Module Tool Wrapper

Wraps network-related analysis capabilities for forensic investigation.
Provides traffic analysis, flow patterns, and exfiltration detection.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from operation_room.tools.base_tool import (
    ModuleTool,
    ToolInput,
    ToolOutput,
    ToolCapability,
    ToolCategory,
    VisualizationType,
    FindingSeverity,
)

logger = logging.getLogger(__name__)


class NetworkTool(ModuleTool):
    """
    Network Analysis Tool.
    
    Provides:
    - Traffic flow analysis
    - Connection pattern detection
    - Exfiltration candidate identification
    - Protocol distribution analysis
    - Geographic traffic mapping
    
    Capabilities:
    - analyze_flows: Analyze network traffic flows
    - detect_exfil: Detect potential data exfiltration
    - get_top_talkers: Identify highest-volume communicators
    - get_protocol_dist: Protocol distribution analysis
    - generate_sankey: Create traffic flow Sankey diagram
    """
    
    @property
    def tool_id(self) -> str:
        return "network"
    
    @property
    def tool_name(self) -> str:
        return "Network Analysis"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "Network traffic analysis and exfiltration detection"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="analyze_flows",
                description="Analyze network traffic flows",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "time_start": {"type": "string"},
                        "time_end": {"type": "string"},
                        "protocols": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total_flows": {"type": "integer"},
                        "total_bytes": {"type": "integer"},
                        "unique_sources": {"type": "integer"},
                        "unique_destinations": {"type": "integer"}
                    }
                },
                visualization_types=[VisualizationType.SANKEY, VisualizationType.TABLE],
                supports_streaming=True
            ),
            ToolCapability(
                name="detect_exfil",
                description="Detect potential data exfiltration patterns",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "threshold_mb": {"type": "number", "default": 100},
                        "unusual_hours": {"type": "boolean", "default": True}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "candidates": {"type": "array"},
                        "risk_score": {"type": "number"}
                    }
                },
                visualization_types=[VisualizationType.TABLE, VisualizationType.TIMELINE],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_top_talkers",
                description="Identify highest-volume communicators",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                        "direction": {"type": "string", "enum": ["inbound", "outbound", "both"], "default": "both"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "top_sources": {"type": "array"},
                        "top_destinations": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.BAR_CHART, VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_protocol_dist",
                description="Protocol distribution analysis",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "protocols": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.PIE_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="generate_sankey",
                description="Generate traffic flow Sankey diagram",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "max_flows": {"type": "integer", "default": 50}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "visualization": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.SANKEY],
                supports_streaming=False
            ),
        ]
    
    async def execute(self, input: ToolInput) -> ToolOutput:
        start_time = datetime.now()
        
        validation = self.validate_input(input)
        if not validation["valid"]:
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=f"Invalid input: {validation['errors']}"
            )
        
        try:
            if input.capability == "analyze_flows":
                result = await self._analyze_flows(input.case_id, input.parameters)
            elif input.capability == "detect_exfil":
                result = await self._detect_exfil(input.case_id, input.parameters)
            elif input.capability == "get_top_talkers":
                result = await self._get_top_talkers(input.case_id, input.parameters)
            elif input.capability == "get_protocol_dist":
                result = await self._get_protocol_dist(input.case_id)
            elif input.capability == "generate_sankey":
                result = await self._generate_sankey(input.case_id, input.parameters)
            else:
                return ToolOutput(
                    tool_id=self.tool_id,
                    capability=input.capability,
                    request_id=input.request_id,
                    success=False,
                    error=f"Unknown capability: {input.capability}"
                )
            
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=True,
                narrative=result.get("narrative", ""),
                findings=result.get("findings", []),
                visualizations=result.get("visualizations", []),
                tables=result.get("tables", []),
                evidence=result.get("evidence", []),
                execution_time_ms=execution_time_ms,
                page_estimate=result.get("page_estimate", 1),
                confidence_score=result.get("confidence_score", 0.0),
            )
            
        except Exception as e:
            logger.error(f"Network tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _analyze_flows(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze network traffic flows."""
        # Mock flow analysis
        stats = {
            "total_flows": 15847,
            "total_bytes": 2_547_832_104,
            "unique_sources": 47,
            "unique_destinations": 234,
        }
        
        findings = [
            self.create_finding(
                title="High Outbound Traffic Detected",
                description=f"Total outbound: {stats['total_bytes'] / 1_000_000:.1f} MB across {stats['total_flows']} flows",
                severity=FindingSeverity.INFO,
                confidence=0.95,
            )
        ]
        
        return {
            "narrative": f"Network analysis processed {stats['total_flows']:,} flows totaling {stats['total_bytes'] / 1_000_000_000:.2f} GB. {stats['unique_sources']} internal sources communicated with {stats['unique_destinations']} external destinations.",
            "findings": findings,
            "page_estimate": 2,
            "confidence_score": 0.9,
        }
    
    async def _detect_exfil(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detect exfiltration candidates."""
        threshold_mb = params.get("threshold_mb", 100)
        
        # Mock exfiltration candidates
        candidates = [
            {"source": "192.168.1.45", "destination": "45.33.32.156", "bytes": 524_288_000, "time": "2024-03-15T02:30:00Z", "risk": 0.92},
            {"source": "192.168.1.45", "destination": "185.199.108.153", "bytes": 157_286_400, "time": "2024-03-15T03:45:00Z", "risk": 0.78},
        ]
        
        findings = []
        for c in candidates:
            findings.append(
                self.create_finding(
                    title=f"Potential Exfiltration: {c['bytes'] / 1_000_000:.1f} MB",
                    description=f"Large data transfer from {c['source']} to {c['destination']} at unusual hour",
                    severity=FindingSeverity.HIGH if c['risk'] > 0.85 else FindingSeverity.MEDIUM,
                    confidence=c['risk'],
                    evidence_refs=[f"flow-{c['source']}-{c['destination']}"],
                )
            )
        
        return {
            "narrative": f"Identified {len(candidates)} potential exfiltration events exceeding {threshold_mb} MB threshold.",
            "findings": findings,
            "tables": [{
                "title": "Exfiltration Candidates",
                "columns": ["Source", "Destination", "Size (MB)", "Time", "Risk Score"],
                "rows": [[c["source"], c["destination"], f"{c['bytes']/1_000_000:.1f}", c["time"], f"{c['risk']:.2f}"] for c in candidates]
            }],
            "page_estimate": 2,
            "confidence_score": 0.88,
        }
    
    async def _get_top_talkers(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = params.get("limit", 10)
        
        top_sources = [
            {"ip": "192.168.1.45", "bytes": 524_288_000},
            {"ip": "192.168.1.101", "bytes": 312_000_000},
            {"ip": "192.168.1.22", "bytes": 156_000_000},
        ]
        
        viz = self.generate_visualization(
            data=[{"name": t["ip"], "value": t["bytes"] / 1_000_000} for t in top_sources],
            viz_type=VisualizationType.BAR_CHART,
            title="Top Talkers by Volume (MB)",
            config={"height": 250}
        )
        
        return {
            "narrative": f"Top {limit} communicators identified. Highest: {top_sources[0]['ip']} ({top_sources[0]['bytes']/1_000_000:.1f} MB)",
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.95,
        }
    
    async def _get_protocol_dist(self, case_id: str) -> Dict[str, Any]:
        protocols = [
            {"name": "HTTPS", "value": 68},
            {"name": "HTTP", "value": 15},
            {"name": "DNS", "value": 10},
            {"name": "SSH", "value": 5},
            {"name": "Other", "value": 2},
        ]
        
        viz = self.generate_visualization(
            data=protocols,
            viz_type=VisualizationType.PIE_CHART,
            title="Protocol Distribution",
            config={"height": 250}
        )
        
        return {
            "narrative": "Protocol analysis shows HTTPS dominates traffic (68%), followed by HTTP (15%) and DNS (10%).",
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.98,
        }
    
    async def _generate_sankey(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        viz = self.generate_visualization(
            data={"nodes": [], "links": []},
            viz_type=VisualizationType.SANKEY,
            title="Traffic Flow Diagram",
            config={"height": 400}
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 2,
        }


# Register the tool
from operation_room.tools import tool_registry
network_tool = NetworkTool()
tool_registry.register(network_tool)
