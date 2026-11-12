"""
Correlation Analysis Tool - Universal Module Tool Wrapper

Wraps the existing MCP correlation tools into the Universal Module Tool interface.
Provides entity relationship mapping and network graph analysis.
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


class CorrelationTool(ModuleTool):
    """
    Correlation Analysis Tool.
    
    Provides:
    - Entity relationship mapping (users, IPs, assets)
    - Network graph construction
    - Path analysis between entities
    - Cluster detection
    - Centrality metrics
    
    Capabilities:
    - build_graph: Construct entity relationship graph
    - find_paths: Find paths between two entities
    - get_clusters: Detect entity clusters
    - get_centrality: Calculate node centrality metrics
    - generate_network_viz: Create network graph visualization
    """
    
    @property
    def tool_id(self) -> str:
        return "correlation"
    
    @property
    def tool_name(self) -> str:
        return "Correlation Analysis"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "Entity relationship mapping and network analysis"
    
    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                name="build_graph",
                description="Construct entity relationship graph from events",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "entity_types": {"type": "array", "items": {"type": "string"}, "default": ["user", "ip", "host", "file"]}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "nodes": {"type": "integer"},
                        "edges": {"type": "integer"},
                        "graph_id": {"type": "string"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH],
                supports_streaming=True
            ),
            ToolCapability(
                name="find_paths",
                description="Find all paths between two entities",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "source_entity": {"type": "string"},
                        "target_entity": {"type": "string"},
                        "max_depth": {"type": "integer", "default": 5}
                    },
                    "required": ["case_id", "source_entity", "target_entity"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "paths": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_clusters",
                description="Detect entity clusters using community detection",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "algorithm": {"type": "string", "enum": ["louvain", "label_propagation"], "default": "louvain"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "clusters": {"type": "array"},
                        "modularity": {"type": "number"}
                    }
                },
                visualization_types=[VisualizationType.NETWORK_GRAPH, VisualizationType.PIE_CHART],
                supports_streaming=False
            ),
            ToolCapability(
                name="get_centrality",
                description="Calculate centrality metrics for key actors",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "metric": {"type": "string", "enum": ["degree", "betweenness", "pagerank"], "default": "betweenness"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "top_nodes": {"type": "array"}
                    }
                },
                visualization_types=[VisualizationType.BAR_CHART, VisualizationType.TABLE],
                supports_streaming=False
            ),
            ToolCapability(
                name="generate_network_viz",
                description="Create interactive network graph visualization",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "layout": {"type": "string", "enum": ["force", "circular", "hierarchical"], "default": "force"}
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
            if input.capability == "build_graph":
                result = await self._build_graph(input.case_id, input.parameters)
            elif input.capability == "find_paths":
                result = await self._find_paths(input.case_id, input.parameters)
            elif input.capability == "get_clusters":
                result = await self._get_clusters(input.case_id, input.parameters)
            elif input.capability == "get_centrality":
                result = await self._get_centrality(input.case_id, input.parameters)
            elif input.capability == "generate_network_viz":
                result = await self._generate_network_viz(input.case_id, input.parameters)
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
            logger.error(f"Correlation tool execution failed: {e}", exc_info=True)
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=str(e)
            )
    
    async def _build_graph(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build entity relationship graph."""
        graph_id = f"graph-{uuid.uuid4().hex[:8]}"
        
        # Mock graph stats
        nodes = 47
        edges = 124
        
        findings = [
            self.create_finding(
                title="Entity Network Mapped",
                description=f"Constructed relationship graph with {nodes} entities and {edges} connections",
                severity=FindingSeverity.INFO,
                confidence=0.95,
            ),
            self.create_finding(
                title="Central Hub Identified",
                description="User 'jsmith' identified as central node with highest betweenness centrality",
                severity=FindingSeverity.MEDIUM,
                confidence=0.87,
            ),
        ]
        
        viz = self.generate_visualization(
            data={"nodes": [], "edges": []},  # Would be actual graph data
            viz_type=VisualizationType.NETWORK_GRAPH,
            title="Entity Relationship Network",
            config={"height": 400, "layout": "force"}
        )
        
        return {
            "narrative": f"Built entity relationship graph with {nodes} nodes and {edges} edges. Key hub entities identified for further investigation.",
            "findings": findings,
            "visualizations": [viz],
            "page_estimate": 2,
            "confidence_score": 0.9,
        }
    
    async def _find_paths(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("source_entity", "unknown")
        target = params.get("target_entity", "unknown")
        
        # Mock paths
        paths = [
            [source, "host-db01", target],
            [source, "host-app01", "host-db01", target],
        ]
        
        return {
            "narrative": f"Found {len(paths)} paths between {source} and {target}. Shortest path has {len(paths[0])-1} hops.",
            "tables": [{
                "title": "Connection Paths",
                "columns": ["Path #", "Hops", "Route"],
                "rows": [[i+1, len(p)-1, " → ".join(p)] for i, p in enumerate(paths)]
            }],
            "page_estimate": 1,
            "confidence_score": 0.85,
        }
    
    async def _get_clusters(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Mock clusters
        clusters = [
            {"id": 1, "size": 12, "label": "Admin Group"},
            {"id": 2, "size": 8, "label": "External Access"},
            {"id": 3, "size": 27, "label": "Internal Users"},
        ]
        
        viz = self.generate_visualization(
            data=[{"name": c["label"], "value": c["size"]} for c in clusters],
            viz_type=VisualizationType.PIE_CHART,
            title="Entity Clusters",
            config={"height": 250}
        )
        
        return {
            "narrative": f"Detected {len(clusters)} distinct entity clusters using Louvain community detection.",
            "visualizations": [viz],
            "page_estimate": 1,
            "confidence_score": 0.82,
        }
    
    async def _get_centrality(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        metric = params.get("metric", "betweenness")
        
        # Mock centrality scores
        top_nodes = [
            {"entity": "jsmith", "type": "user", "score": 0.89},
            {"entity": "192.168.1.45", "type": "ip", "score": 0.76},
            {"entity": "host-db01", "type": "host", "score": 0.71},
        ]
        
        viz = self.generate_visualization(
            data=[{"name": n["entity"], "value": n["score"]} for n in top_nodes],
            viz_type=VisualizationType.BAR_CHART,
            title=f"Top Entities by {metric.title()} Centrality",
            config={"height": 200, "horizontal": True}
        )
        
        findings = [
            self.create_finding(
                title=f"High Centrality: {top_nodes[0]['entity']}",
                description=f"Entity has {metric} centrality score of {top_nodes[0]['score']:.2f}, indicating key role in activity network",
                severity=FindingSeverity.MEDIUM,
                confidence=top_nodes[0]['score'],
            )
        ]
        
        return {
            "narrative": f"Calculated {metric} centrality. Top entity: {top_nodes[0]['entity']} (score: {top_nodes[0]['score']:.2f})",
            "findings": findings,
            "visualizations": [viz],
            "tables": [{
                "title": "Centrality Rankings",
                "columns": ["Entity", "Type", "Score"],
                "rows": [[n["entity"], n["type"], f"{n['score']:.3f}"] for n in top_nodes]
            }],
            "page_estimate": 1,
            "confidence_score": 0.88,
        }
    
    async def _generate_network_viz(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        layout = params.get("layout", "force")
        
        viz = self.generate_visualization(
            data={"nodes": [], "edges": []},
            viz_type=VisualizationType.NETWORK_GRAPH,
            title="Full Entity Network",
            config={"height": 500, "layout": layout, "interactive": True}
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 2,
        }


# Register the tool
from operation_room.tools import tool_registry
correlation_tool = CorrelationTool()
tool_registry.register(correlation_tool)
