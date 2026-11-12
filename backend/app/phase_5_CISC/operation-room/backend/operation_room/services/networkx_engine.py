"""
NetworkX Graph Engine for GraphRAG Correlation
Pure-Python graph construction and shortest path calculation with graceful fallback
"""

import logging
from typing import Dict, List, Optional, Any
import heapq

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

logger = logging.getLogger(__name__)


class NetworkXEngine:
    """
    NetworkX-based graph engine for correlation analysis
    Pure Python implementation, no external service dependencies
    """

    def __init__(self):
        """Initialize NetworkX engine"""
        if not NETWORKX_AVAILABLE:
            logger.warning("networkx package not installed; NetworkX operations will be unavailable")
        
        self._graph: Optional[nx.DiGraph] = None
        self._node_metadata: Dict[str, Dict[str, Any]] = {}
        self._edge_metadata: Dict[tuple, Dict[str, Any]] = {}

    def build_graph(
        self,
        nodes: Dict[str, Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> bool:
        """
        Build NetworkX directed graph from nodes and edges
        
        Args:
            nodes: Dict of {node_id: node_attributes}
            edges: List of edge dicts with source_id, target_id, relationship, etc.
        
        Returns:
            True if successful, False otherwise
        """
        if not NETWORKX_AVAILABLE:
            logger.error("NetworkX not available; cannot build graph")
            return False

        try:
            self._graph = nx.DiGraph()
            self._node_metadata = {}
            self._edge_metadata = {}

            # Add nodes
            for node_id, attributes in nodes.items():
                self._graph.add_node(node_id)
                self._node_metadata[node_id] = attributes

            # Add edges with weights (for shortest path calculation)
            for edge in edges:
                source = edge.get("source_id")
                target = edge.get("target_id")
                
                # Use 1/weight as distance (lower weight = shorter distance)
                weight = edge.get("weight", 1.0)
                distance = 1.0 / max(weight, 0.1)  # Avoid division by zero
                
                self._graph.add_edge(
                    source,
                    target,
                    weight=distance,  # Used for shortest path
                    relationship=edge.get("relationship", "RELATED_TO"),
                    confidence_score=edge.get("confidence_score", 0.5),
                    evidence_ids=edge.get("evidence_ids", [])
                )
                
                # Store edge metadata
                self._edge_metadata[(source, target)] = edge

            logger.info(f"✓ Built NetworkX graph with {len(nodes)} nodes and {len(edges)} edges")
            return True

        except Exception as e:
            logger.error(f"✗ Error building NetworkX graph: {e}")
            self._graph = None
            return False

    def is_available(self) -> bool:
        """
        Check if engine is available (graph built)
        
        Returns:
            True if graph exists and has nodes, False otherwise
        """
        return self._graph is not None and len(self._graph.nodes()) > 0

    def calculate_shortest_path(
        self,
        source_node_id: str,
        target_node_id: str,
        max_hops: int = 6
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate shortest path between two nodes using NetworkX Dijkstra
        
        Args:
            source_node_id: Source entity node ID
            target_node_id: Target entity node ID
            max_hops: Maximum number of hops to consider (default: 6)
        
        Returns:
            Dict with path info (nodes, edges, length) or None if not found
        """
        if not self.is_available():
            logger.error("NetworkX graph not available")
            return None

        if source_node_id == target_node_id:
            logger.info(f"Source and target are identical ({source_node_id}); no path returned")
            return None

        try:
            # Check if nodes exist
            if source_node_id not in self._graph.nodes():
                logger.warning(f"Source node {source_node_id} not in graph")
                return None

            if target_node_id not in self._graph.nodes():
                logger.warning(f"Target node {target_node_id} not in graph")
                return None

            # Calculate shortest path using Dijkstra
            try:
                path_node_ids = nx.shortest_path(
                    self._graph,
                    source=source_node_id,
                    target=target_node_id,
                    weight="weight"
                )
            except nx.NetworkXNoPath:
                logger.info(f"✗ No path found between {source_node_id} and {target_node_id}")
                return None

            # Check max hops constraint
            path_length = len(path_node_ids) - 1
            if path_length > max_hops:
                logger.info(f"Path length {path_length} exceeds max_hops {max_hops}")
                return None

            # Build path nodes
            path_nodes = []
            for node_id in path_node_ids:
                node_meta = self._node_metadata.get(node_id, {})
                path_nodes.append({
                    "node_id": node_id,
                    "entity_type": node_meta.get("entity_type"),
                    "entity_value": node_meta.get("entity_value"),
                    "severity_score": node_meta.get("severity_score", 0.0),
                    "anomaly_score": node_meta.get("anomaly_score", 0.0)
                })

            # Build path edges
            path_edges = []
            for i in range(len(path_node_ids) - 1):
                source = path_node_ids[i]
                target = path_node_ids[i + 1]
                
                # Get edge data
                edge_data = self._graph.get_edge_data(source, target)
                edge_meta = self._edge_metadata.get((source, target), {})
                
                path_edges.append({
                    "source_id": source,
                    "target_id": target,
                    "relationship": edge_meta.get("relationship", "RELATED_TO"),
                    "weight": edge_meta.get("weight", 1.0),
                    "confidence_score": edge_meta.get("confidence_score", 0.5),
                    "evidence_ids": edge_meta.get("evidence_ids", [])
                })

            result_dict = {
                "nodes": path_nodes,
                "edges": path_edges,
                "path_length": path_length,
                "source": source_node_id,
                "target": target_node_id,
                "engine_used": "networkx"
            }

            logger.info(f"✓ Found path of length {path_length} between {source_node_id} and {target_node_id}")
            return result_dict

        except Exception as e:
            logger.error(f"✗ Error calculating shortest path in NetworkX: {e}")
            return None

    def get_subgraph_json(
        self,
        node_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Export subgraph as JSON for frontend rendering
        
        Args:
            node_ids: List of node IDs to include in subgraph
        
        Returns:
            Dict with nodes and edges for rendering, or None if error
        """
        if not self.is_available():
            return None

        try:
            # Filter nodes
            subgraph_nodes = []
            for node_id in node_ids:
                if node_id in self._graph.nodes():
                    node_meta = self._node_metadata.get(node_id, {})
                    subgraph_nodes.append({
                        "node_id": node_id,
                        "entity_type": node_meta.get("entity_type"),
                        "entity_value": node_meta.get("entity_value"),
                        "severity_score": node_meta.get("severity_score", 0.0),
                        "anomaly_score": node_meta.get("anomaly_score", 0.0)
                    })

            # Filter edges (only include edges between subgraph nodes)
            subgraph_edges = []
            for source in node_ids:
                for target in node_ids:
                    if self._graph.has_edge(source, target):
                        edge_meta = self._edge_metadata.get((source, target), {})
                        subgraph_edges.append({
                            "source_id": source,
                            "target_id": target,
                            "relationship": edge_meta.get("relationship", "RELATED_TO"),
                            "weight": edge_meta.get("weight", 1.0),
                            "confidence_score": edge_meta.get("confidence_score", 0.5),
                            "evidence_ids": edge_meta.get("evidence_ids", [])
                        })

            return {
                "nodes": subgraph_nodes,
                "edges": subgraph_edges,
                "total_nodes": len(subgraph_nodes),
                "total_edges": len(subgraph_edges)
            }

        except Exception as e:
            logger.error(f"✗ Error retrieving subgraph from NetworkX: {e}")
            return None

    def get_all_nodes(self) -> List[str]:
        """
        Get all node IDs in graph
        
        Returns:
            List of node IDs
        """
        if not self.is_available():
            return []
        return list(self._graph.nodes())

    def get_node_metadata(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific node
        
        Args:
            node_id: Node ID to query
        
        Returns:
            Node metadata dict or None
        """
        if not self.is_available():
            return None
        return self._node_metadata.get(node_id)

    def clear(self) -> None:
        """Clear the graph"""
        self._graph = None
        self._node_metadata = {}
        self._edge_metadata = {}
        logger.info("✓ NetworkX graph cleared")

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get graph statistics
        
        Returns:
            Dict with node count, edge count, etc.
        """
        if not self.is_available():
            return {}

        return {
            "node_count": len(self._graph.nodes()),
            "edge_count": len(self._graph.edges()),
            "density": nx.density(self._graph),
            "is_connected": nx.is_strongly_connected(self._graph),
            "number_of_components": nx.number_strongly_connected_components(self._graph)
        }


# Singleton instance for module-level access
_networkx_engine: Optional[NetworkXEngine] = None


def get_networkx_engine() -> NetworkXEngine:
    """
    Get or create NetworkX engine singleton
    
    Returns:
        NetworkXEngine instance
    """
    global _networkx_engine
    if _networkx_engine is None:
        _networkx_engine = NetworkXEngine()
    return _networkx_engine
