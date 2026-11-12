"""
Graph Layout Service for Tree-based Positioning
Implements Reingold-Tilford tree layout for minimizing edge crossings.
"""

import json
import math
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


def _edge_endpoints(edge: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Support both source_node_id/target_node_id and source_id/target_id shapes."""
    source = edge.get("source_node_id") or edge.get("source_id")
    target = edge.get("target_node_id") or edge.get("target_id")
    return source, target


@dataclass
class LayoutNode:
    """Node with position information for layout algorithms."""
    node_id: str
    entity_type: str
    entity_value: str
    x: float = 0.0
    y: float = 0.0
    parent: Optional[str] = None
    children: List[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class TreeLayoutEngine:
    """
    Deterministic tree layout using Reingold-Tilford algorithm.
    
    Properties:
    - Minimizes edge crossings
    - Centered parent above children
    - Consistent spacing
    - O(n) computation
    """
    
    def __init__(self, width: float = 1200.0, height: float = 800.0, 
                 h_spacing: float = 150.0, v_spacing: float = 120.0):
        """
        Initialize layout engine.
        
        Args:
            width: Canvas width (pixels)
            height: Canvas height (pixels)
            h_spacing: Horizontal spacing between siblings
            v_spacing: Vertical spacing between levels
        """
        self.width = width
        self.height = height
        self.h_spacing = h_spacing
        self.v_spacing = v_spacing
        self.nodes: Dict[str, LayoutNode] = {}
        self.edges: Dict[str, tuple] = {}
    
    def build_tree_from_path(self, path_nodes: List[str], edges: List[Dict]) -> None:
        """
        Build tree structure from linear path (shortest path).
        
        Args:
            path_nodes: Ordered list of node IDs from source to target
            edges: List of edge dictionaries with source_node_id, target_node_id
        """
        # Link edges in sequence to form a chain
        for i in range(len(path_nodes) - 1):
            parent_id = path_nodes[i]
            child_id = path_nodes[i + 1]
            
            if parent_id not in self.nodes:
                self.nodes[parent_id] = LayoutNode(node_id=parent_id, entity_type="", entity_value="")
            if child_id not in self.nodes:
                self.nodes[child_id] = LayoutNode(node_id=child_id, entity_type="", entity_value="")
            
            # Set parent-child relationship
            self.nodes[child_id].parent = parent_id
            self.nodes[parent_id].children.append(child_id)
            self.edges[f"{parent_id}-{child_id}"] = (parent_id, child_id)
    
    def apply_reingold_tilford(self, root_id: Optional[str] = None) -> Dict[str, Tuple[float, float]]:
        """
        Apply Reingold-Tilford tree layout algorithm.
        
        Returns:
            Dictionary mapping node_id to (x, y) position
        """
        if not self.nodes:
            return {}
        
        # Find root (node with no parent)
        if not root_id:
            root_id = next((nid for nid, n in self.nodes.items() if n.parent is None), None)
        
        if not root_id:
            # Fallback: use first node if no root found
            root_id = list(self.nodes.keys())[0]
        
        # First pass: calculate width of each subtree
        self._calculate_subtree_width(root_id)
        
        # Second pass: position nodes
        self._position_nodes(root_id, self.width / 2, 50.0)
        
        # Return positions
        return {nid: (n.x, n.y) for nid, n in self.nodes.items()}
    
    def _calculate_subtree_width(self, node_id: str) -> float:
        """Calculate width required for subtree rooted at node_id."""
        node = self.nodes[node_id]
        
        if not node.children:
            return self.h_spacing  # Leaf node width
        
        # Sum widths of all children subtrees
        total_width = 0.0
        for child_id in node.children:
            total_width += self._calculate_subtree_width(child_id)
        
        # Ensure parent is wider than children
        return max(total_width, self.h_spacing)
    
    def _position_nodes(self, node_id: str, x: float, y: float) -> None:
        """Recursively position nodes using Reingold-Tilford algorithm."""
        node = self.nodes[node_id]
        node.x = x
        node.y = y
        
        if not node.children:
            return
        
        # Calculate starting x position for first child (centered under parent)
        total_width = sum(self._get_subtree_width(child_id) for child_id in node.children)
        start_x = x - total_width / 2
        
        # Position each child
        current_x = start_x
        for child_id in node.children:
            subtree_width = self._get_subtree_width(child_id)
            child_x = current_x + subtree_width / 2
            child_y = y + self.v_spacing
            
            self._position_nodes(child_id, child_x, child_y)
            current_x += subtree_width
    
    def _get_subtree_width(self, node_id: str) -> float:
        """Get cached subtree width (set during calculate phase)."""
        node = self.nodes[node_id]
        if not node.children:
            return self.h_spacing
        return sum(self._get_subtree_width(child_id) for child_id in node.children)


class ForcedDirectedFallback:
    """
    Fallback layout when tree structure is not available.
    Uses simple force-directed algorithm for arbitrary graphs.
    """
    
    def __init__(self, width: float = 1200.0, height: float = 800.0, 
                 iterations: int = 50, repulsion: float = 500.0, attraction: float = 0.1):
        """
        Initialize force-directed layout engine.
        
        Args:
            width: Canvas width
            height: Canvas height
            iterations: Number of iterations
            repulsion: Repulsive force factor
            attraction: Attractive force factor
        """
        self.width = width
        self.height = height
        self.iterations = iterations
        self.repulsion = repulsion
        self.attraction = attraction
    
    def layout(self, nodes: List[Dict], edges: List[Dict]) -> Dict[str, Tuple[float, float]]:
        """
        Apply force-directed layout algorithm.
        
        Returns:
            Dictionary mapping node_id to (x, y) position
        """
        if not nodes:
            return {}

        node_ids = [node["node_id"] for node in nodes]
        total_nodes = max(1, len(node_ids))

        adjacency = {nid: set() for nid in node_ids}
        for edge in edges:
            source, target = _edge_endpoints(edge)
            if source in adjacency and target in adjacency:
                adjacency[source].add(target)
                adjacency[target].add(source)
        
        # Initialize positions randomly
        positions = {}
        center_x = self.width * 0.5
        center_y = self.height * 0.5
        max_radius = max(80.0, min(self.width, self.height) * 0.35)
        for idx, nid in enumerate(node_ids):
            degree = len(adjacency.get(nid, []))
            angle = (2.0 * math.pi * idx) / total_nodes
            radius_scale = 1.0 - min(0.6, degree / max(total_nodes, 1))
            radius = max_radius * max(0.25, radius_scale)
            jitter_x = (hash(f"{nid}-x") % 21) - 10
            jitter_y = (hash(f"{nid}-y") % 21) - 10
            positions[nid] = (
                center_x + radius * math.cos(angle) + jitter_x,
                center_y + radius * math.sin(angle) + jitter_y,
            )
        
        # Force-directed iterations
        for _ in range(self.iterations):
            forces = {node["node_id"]: (0.0, 0.0) for node in nodes}
            
            # Repulsive forces between all pairs
            for i, n1 in enumerate(node_ids):
                for n2 in node_ids[i+1:]:
                    x1, y1 = positions[n1]
                    x2, y2 = positions[n2]
                    
                    dx = x2 - x1
                    dy = y2 - y1
                    dist = math.sqrt(dx*dx + dy*dy) + 0.001  # Avoid division by zero
                    
                    # Repulsive force (inverse square)
                    force = -self.repulsion / (dist * dist)
                    fx = force * dx / dist
                    fy = force * dy / dist
                    
                    forces[n1] = (forces[n1][0] - fx, forces[n1][1] - fy)
                    forces[n2] = (forces[n2][0] + fx, forces[n2][1] + fy)
            
            # Attractive forces along edges
            for edge in edges:
                n1, n2 = _edge_endpoints(edge)
                
                if n1 not in positions or n2 not in positions:
                    continue
                
                x1, y1 = positions[n1]
                x2, y2 = positions[n2]
                
                dx = x2 - x1
                dy = y2 - y1
                dist = math.sqrt(dx*dx + dy*dy) + 0.001
                
                # Attractive force (linear spring)
                force = self.attraction * dist
                fx = force * dx / dist
                fy = force * dy / dist
                
                forces[n1] = (forces[n1][0] + fx, forces[n1][1] + fy)
                forces[n2] = (forces[n2][0] - fx, forces[n2][1] - fy)
            
            # Update positions with damping
            damping = 0.9
            for node in nodes:
                nid = node["node_id"]
                fx, fy = forces[nid]
                x, y = positions[nid]
                
                # Apply force with velocity damping
                x += fx * damping * 0.01
                y += fy * damping * 0.01
                
                # Keep within bounds
                x = max(50, min(self.width - 50, x))
                y = max(50, min(self.height - 50, y))
                
                positions[nid] = (x, y)
        
        return positions


def apply_tree_layout(nodes: List[Dict], edges: List[Dict], 
                     path_nodes: Optional[List[str]] = None,
                     width: float = 1200.0, height: float = 800.0) -> Dict[str, Tuple[float, float]]:
    """
    Apply tree layout to correlation graph.
    
    Args:
        nodes: List of node dictionaries (from get_correlation_data)
        edges: List of edge dictionaries (from get_correlation_data)
        path_nodes: Optional ordered list of nodes in shortest path
        width: Canvas width
        height: Canvas height
    
    Returns:
        Dictionary mapping node_id to (x, y) position
    """
    try:
        # If we have a path, use tree layout
        if path_nodes and len(path_nodes) > 1:
            logger.info(f"Applying tree layout for {len(path_nodes)}-node path")
            engine = TreeLayoutEngine(width=width, height=height)
            
            # Add nodes to engine
            for node in nodes:
                nid = node["node_id"]
                layout_node = LayoutNode(
                    node_id=nid,
                    entity_type=node.get("entity_type", ""),
                    entity_value=node.get("entity_value", "")
                )
                engine.nodes[nid] = layout_node
            
            # Build tree from path
            engine.build_tree_from_path(path_nodes, edges)
            
            # Apply Reingold-Tilford
            positions = engine.apply_reingold_tilford(root_id=path_nodes[0])
            logger.info(f"Tree layout complete: {len(positions)} nodes positioned")
            return positions
        
        else:
            # Fallback to force-directed layout
            logger.info("No path provided, using force-directed layout")
            fallback = ForcedDirectedFallback(width=width, height=height)
            return fallback.layout(nodes, edges)
    
    except Exception as e:
        logger.error(f"Layout error: {e}")
        # Final fallback: simple grid layout
        return _grid_layout_fallback(nodes, width, height)


def _grid_layout_fallback(nodes: List[Dict], width: float, height: float) -> Dict[str, Tuple[float, float]]:
    """
    Fallback grid layout when all else fails.
    Arranges nodes in a regular grid pattern.
    """
    positions = {}
    cols = max(1, int(math.sqrt(len(nodes))))
    
    for i, node in enumerate(nodes):
        row = i // cols
        col = i % cols
        
        # Distribute evenly across canvas
        x = 50 + (col * (width - 100) / max(1, cols - 1))
        y = 50 + (row * (height - 100) / max(1, (len(nodes) // cols)))
        
        positions[node["node_id"]] = (x, y)
    
    logger.info(f"Grid layout fallback: {len(positions)} nodes in {cols} columns")
    return positions


def extract_path_from_shortest_path_json(shortest_path_json: Optional[Dict]) -> Optional[List[str]]:
    """
    Extract ordered path of node IDs from shortest_path_json.
    
    Expected structure (from Phase 3):
    {
        "nodes": [
            {"node_id": "user1", ...},
            {"node_id": "host1", ...},
            {"node_id": "user2", ...}
        ],
        "edges": [
            {"source_node_id": "user1", "target_node_id": "host1", ...},
            {"source_node_id": "host1", "target_node_id": "user2", ...}
        ]
    }
    
    Returns:
        Ordered list of node IDs in path, or None if extraction fails
    """
    if not shortest_path_json:
        return None
    
    try:
        nodes = shortest_path_json.get("nodes", [])
        if not nodes:
            return None
        
        # Start with first node
        path = [nodes[0]["node_id"]]
        
        # Follow edges to build path
        edges = shortest_path_json.get("edges", [])
        while len(path) < len(nodes):
            current_node = path[-1]
            
            # Find next edge from current node
            next_edge = next(
                (e for e in edges if _edge_endpoints(e)[0] == current_node),
                None
            )
            
            if not next_edge:
                break
            
            _, next_target = _edge_endpoints(next_edge)
            if not next_target:
                break

            path.append(next_target)
        
        return path if len(path) == len(nodes) else None
    
    except Exception as e:
        logger.warning(f"Failed to extract path from shortest_path_json: {e}")
        return None


def filter_to_path_nodes(nodes: List[Dict], edges: List[Dict], 
                        path_node_ids: List[str]) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter nodes and edges to only those in the path.
    
    Args:
        nodes: Full list of nodes
        edges: Full list of edges
        path_node_ids: Node IDs to keep
    
    Returns:
        Tuple of (filtered_nodes, filtered_edges)
    """
    path_set = set(path_node_ids)
    
    # Filter nodes
    filtered_nodes = [n for n in nodes if n["node_id"] in path_set]
    
    # Filter edges (both endpoints must be in path)
    filtered_edges = [
        e for e in edges 
        if _edge_endpoints(e)[0] in path_set and _edge_endpoints(e)[1] in path_set
    ]
    
    logger.info(f"Filtered to {len(filtered_nodes)} nodes and {len(filtered_edges)} edges from path")
    return filtered_nodes, filtered_edges


def apply_layout_to_graph_response(graph_data: Dict, 
                                  shortest_path_json: Optional[Dict] = None,
                                  width: float = 1200.0,
                                  height: float = 800.0) -> Dict:
    """
    Apply layout to correlation graph response and add positioning.
    
    Args:
        graph_data: Response from get_correlation_data()
        shortest_path_json: Optional shortest_path_json from Phase 3 storage
        width: Canvas width
        height: Canvas height
    
    Returns:
        Enhanced graph_data with layout positioning:
        {
            "run_id": "...",
            "nodes": [...],  # with x, y coordinates
            "edges": [...],
            "layout": "tree" | "force-directed" | "grid",
            "path_count": number of nodes in path
        }
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    
    if not nodes:
        return {**graph_data, "layout": "empty", "positions": {}}
    
    try:
        # Extract path from shortest_path_json if available
        path_nodes = extract_path_from_shortest_path_json(shortest_path_json)
        
        if path_nodes and len(path_nodes) > 1:
            # Filter to path + apply tree layout
            logger.info(f"Using 6-hop path layout with {len(path_nodes)} nodes")
            filtered_nodes, filtered_edges = filter_to_path_nodes(nodes, edges, path_nodes)
            positions = apply_tree_layout(filtered_nodes, filtered_edges, path_nodes, width, height)
            layout_type = "tree"
            layout_nodes = filtered_nodes
            layout_edges = filtered_edges
            path_count = len(path_nodes)
        
        else:
            # No path available; use force-directed on all nodes (limited to topN)
            logger.warning("No valid path found; using force-directed layout on top nodes")
            
            # Limit to top 50 nodes by severity
            sorted_nodes = sorted(nodes, key=lambda n: n.get("severity_score", 0), reverse=True)[:50]
            sorted_node_ids = {n["node_id"] for n in sorted_nodes}
            filtered_edges = [
                e for e in edges
                if _edge_endpoints(e)[0] in sorted_node_ids and _edge_endpoints(e)[1] in sorted_node_ids
            ]
            positions = apply_tree_layout(sorted_nodes, filtered_edges, None, width, height)
            layout_type = "force-directed"
            layout_nodes = sorted_nodes
            layout_edges = filtered_edges
            path_count = 0
        
        # Add positions to nodes
        positioned_nodes = []
        for node in layout_nodes:
            nid = node["node_id"]
            x, y = positions.get(nid, (0, 0))
            positioned_nodes.append({
                **node,
                "x": x,
                "y": y
            })
        
        return {
            "run_id": graph_data.get("run_id"),
            "nodes": positioned_nodes,
            "edges": layout_edges,
            "layout": layout_type,
            "path_count": path_count,
            "node_count": len(positioned_nodes),
            "edge_count": len(layout_edges)
        }
    
    except Exception as e:
        logger.error(f"Layout application failed: {e}")
        # Return original data with grid fallback positions
        positions = _grid_layout_fallback(nodes, width, height)
        positioned_nodes = [
            {**node, "x": positions.get(node["node_id"], (0, 0))[0], 
             "y": positions.get(node["node_id"], (0, 0))[1]}
            for node in nodes
        ]
        return {
            "run_id": graph_data.get("run_id"),
            "nodes": positioned_nodes,
            "edges": edges,
            "layout": "grid-fallback",
            "path_count": 0,
            "node_count": len(positioned_nodes),
            "edge_count": len(edges)
        }
