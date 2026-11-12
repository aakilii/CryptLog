"""
Depth/Impact Analysis Tool - Universal Module Tool Wrapper

Wraps impact and depth analysis capabilities.
Provides blast radius calculation and impact assessment.
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


class DepthTool(ModuleTool):
    """
    Depth/Impact Analysis Tool.
    
    Provides:
    - Blast radius calculation
    - Impact propagation analysis
    - Asset dependency mapping
    - Risk scoring
    - Remediation priority
    
    Capabilities:
    - calculate_blast_radius: Calculate incident blast radius
    - get_impact_chain: Trace impact propagation
    - get_affected_assets: List affected assets
    - calculate_risk_score: Overall risk assessment
    - generate_impact_tree: Impact propagation tree visualization
    """
    
    @property
    def tool_id(self) -> str:
        return "depth"
    
    @property
    def tool_name(self) -> str:
        return "Depth/Impact Analysis"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "Blast radius calculation and impact assessment"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="calculate_blast_radius",
                description="Calculate incident blast radius",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "origin_entity": {"type": "string"},
                        "max_depth": {"type": "integer", "default": 5}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total_affected": {"type": "integer"},
                        "by_depth": {"type": "object"},
                        "critical_assets": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH, VisualizationType.METRIC_CARD],
                supports_streaming=True
            ),
            ToolCapability(
                name="get_impact_chain",
                description="Trace impact propagation chain",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "start_entity": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "chain": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.TIMELINE, VisualizationType.NETWORK_GRAPH],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_affected_assets",
                description="List all affected assets with priority",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "asset_types": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "assets": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="calculate_risk_score",
                description="Calculate overall risk score",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "include_factors": {"type": "boolean", "default": True}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "risk_score": {"type": "number"},
                        "risk_level": {"type": "string"},
                        "factors": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.METRIC_CARD, VisualizationType.BAR_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="generate_impact_tree",
                description="Generate impact propagation tree",
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
                        "visualization": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH],
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
            if input.capability == "calculate_blast_radius":
                result = await self._calculate_blast_radius(input.case_id, input.parameters)
            elif input.capability == "get_impact_chain":
                result = await self._get_impact_chain(input.case_id, input.parameters)
            elif input.capability == "get_affected_assets":
                result = await self._get_affected_assets(input.case_id, input.parameters)
            elif input.capability == "calculate_risk_score":
                result = await self._calculate_risk_score(input.case_id, input.parameters)
            elif input.capability == "generate_impact_tree":
                result = await self._generate_impact_tree(input.case_id)
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
            logger.error(f"Depth tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _calculate_blast_radius(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate blast radius."""
        origin = params.get("origin_entity", "compromised_host")
        max_depth = params.get("max_depth", 5)
        
        # Mock blast radius
        by_depth = {
            "Depth 1 (Direct)": 5,
            "Depth 2": 12,
            "Depth 3": 28,
            "Depth 4": 15,
            "Depth 5+": 7
        }
        total = sum(by_depth.values())
        
        critical = [
            {"asset": "db-prod-01", "type": "database", "criticality": "HIGH"},
            {"asset": "auth-server", "type": "service", "criticality": "CRITICAL"},
            {"asset": "file-server-pii", "type": "storage", "criticality": "HIGH"},
        ]
        
        metrics = self.generate_visualization(
            data=[
                {"label": "Total Affected", "value": total},
                {"label": "Critical Assets", "value": len(critical)},
                {"label": "Max Depth", "value": max_depth},
            ],
            viz_type=VisualizationType.METRIC_CARD,
            title="Blast Radius Summary"
        )
        
        depth_viz = self.generate_visualization(
            data=[{"name": k, "value": v} for k, v in by_depth.items()],
            viz_type=VisualizationType.BAR_CHART,
            title="Affected Assets by Depth",
            config={"height": 200}
        )
        
        findings = [
            self.create_finding(
                title=f"Blast Radius: {total} Assets Affected",
                description=f"Impact propagates from {origin} through {max_depth} depth levels, affecting {len(critical)} critical assets",
                severity=FindingSeverity.HIGH,
                confidence=0.9,
            ),
            self.create_finding(
                title="Critical Asset Exposed: auth-server",
                description="Authentication server within blast radius - potential credential compromise",
                severity=FindingSeverity.CRITICAL,
                confidence=0.95,
            ),
        ]
        
        return {
            "narrative": f"Blast radius analysis from {origin} shows {total} affected assets across {max_depth} depth levels. {len(critical)} critical assets are within impact zone.",
            "findings": findings,
            "visualizations": [metrics, depth_viz],
            "tables": [{
                "title": "Critical Assets in Blast Radius",
                "columns": ["Asset", "Type", "Criticality"],
                "rows": [[c["asset"], c["type"], c["criticality"]] for c in critical]
            }],
            "page_estimate": 3,
            "confidence_score": 0.88,
        }
    
    async def _get_impact_chain(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        start = params.get("start_entity", "initial_access")
        
        chain = [
            {"step": 1, "entity": "phishing_email", "action": "Initial Access", "time": "T+0m"},
            {"step": 2, "entity": "workstation-jsmith", "action": "Execution", "time": "T+5m"},
            {"step": 3, "entity": "internal-network", "action": "Lateral Movement", "time": "T+30m"},
            {"step": 4, "entity": "db-prod-01", "action": "Data Access", "time": "T+45m"},
            {"step": 5, "entity": "external-ip", "action": "Exfiltration", "time": "T+90m"},
        ]
        
        findings = [
            self.create_finding(
                title=f"Impact Chain: {len(chain)} Steps",
                description=f"Attack progression from {chain[0]['entity']} to {chain[-1]['entity']} over 90 minutes",
                severity=FindingSeverity.HIGH,
                confidence=0.92,
            )
        ]
        
        return {
            "narrative": f"Impact chain traced {len(chain)} steps from initial access to data exfiltration.",
            "findings": findings,
            "tables": [{
                "title": "Impact Propagation Chain",
                "columns": ["Step", "Entity", "Action", "Time"],
                "rows": [[c["step"], c["entity"], c["action"], c["time"]] for c in chain]
            }],
            "page_estimate": 2,
            "confidence_score": 0.9,
        }
    
    async def _get_affected_assets(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        assets = [
            {"name": "db-prod-01", "type": "database", "priority": 1, "status": "compromised"},
            {"name": "auth-server", "type": "service", "priority": 1, "status": "at_risk"},
            {"name": "file-server-pii", "type": "storage", "priority": 2, "status": "compromised"},
            {"name": "workstation-jsmith", "type": "endpoint", "priority": 2, "status": "compromised"},
            {"name": "backup-server", "type": "storage", "priority": 3, "status": "at_risk"},
        ]
        
        return {
            "narrative": f"Identified {len(assets)} affected assets, {sum(1 for a in assets if a['status']=='compromised')} confirmed compromised.",
            "tables": [{
                "title": "Affected Assets",
                "columns": ["Asset Name", "Type", "Priority", "Status"],
                "rows": [[a["name"], a["type"], a["priority"], a["status"]] for a in assets]
            }],
            "page_estimate": 1,
            "confidence_score": 0.87,
        }
    
    async def _calculate_risk_score(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        include_factors = params.get("include_factors", True)
        
        risk_score = 8.7
        risk_level = "CRITICAL"
        
        factors = [
            {"factor": "Data Sensitivity", "score": 9.2, "weight": 0.3},
            {"factor": "Blast Radius", "score": 8.5, "weight": 0.25},
            {"factor": "Persistence", "score": 7.8, "weight": 0.2},
            {"factor": "Detection Time", "score": 9.0, "weight": 0.15},
            {"factor": "Containment", "score": 8.5, "weight": 0.1},
        ]
        
        metrics = self.generate_visualization(
            data=[
                {"label": "Risk Score", "value": risk_score},
                {"label": "Level", "value": risk_level},
            ],
            viz_type=VisualizationType.METRIC_CARD,
            title="Risk Assessment"
        )
        
        factors_viz = self.generate_visualization(
            data=[{"name": f["factor"], "value": f["score"]} for f in factors],
            viz_type=VisualizationType.BAR_CHART,
            title="Risk Factor Breakdown",
            config={"height": 200, "horizontal": True}
        )
        
        findings = [
            self.create_finding(
                title=f"Overall Risk: {risk_level} ({risk_score}/10)",
                description="High data sensitivity and large blast radius contribute to critical risk rating",
                severity=FindingSeverity.CRITICAL,
                confidence=0.93,
            )
        ]
        
        return {
            "narrative": f"Risk assessment: {risk_level} ({risk_score}/10). Primary factors: Data Sensitivity (9.2), Detection Time (9.0), Blast Radius (8.5).",
            "findings": findings,
            "visualizations": [metrics, factors_viz] if include_factors else [metrics],
            "page_estimate": 2,
            "confidence_score": 0.93,
        }
    
    async def _generate_impact_tree(self, case_id: str) -> Dict[str, Any]:
        viz = self.generate_visualization(
            data={"nodes": [], "edges": []},
            viz_type=VisualizationType.NETWORK_GRAPH,
            title="Impact Propagation Tree",
            config={"height": 500, "layout": "hierarchical"}
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 2,
        }


# Register the tool
from operation_room.tools import tool_registry
depth_tool = DepthTool()
tool_registry.register(depth_tool)
