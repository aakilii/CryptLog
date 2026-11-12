"""
Phase 4: Backend API Tree-Layout Tests
Tests tree layout algorithm, position calculation, API integration, and fallback handling.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import math
from typing import Dict, List, Tuple

# Import layout service
from operation_room.services.graph_layout import (
    TreeLayoutEngine,
    ForcedDirectedFallback,
    apply_tree_layout,
    extract_path_from_shortest_path_json,
    filter_to_path_nodes,
    apply_layout_to_graph_response,
    _grid_layout_fallback,
    LayoutNode
)


class TestTreeLayoutEngine(unittest.TestCase):
    """Test Reingold-Tilford tree layout algorithm."""
    
    def setUp(self):
        """Initialize layout engine."""
        self.engine = TreeLayoutEngine(width=1200.0, height=800.0, h_spacing=150.0, v_spacing=120.0)
    
    def test_tree_layout_simple_chain(self):
        """Test tree layout on simple linear path."""
        # Create 3-node chain
        path_nodes = ["node1", "node2", "node3"]
        edges = [
            {"source_node_id": "node1", "target_node_id": "node2"},
            {"source_node_id": "node2", "target_node_id": "node3"}
        ]
        
        self.engine.build_tree_from_path(path_nodes, edges)
        positions = self.engine.apply_reingold_tilford(root_id="node1")
        
        # Verify all nodes positioned
        self.assertEqual(len(positions), 3)
        
        # Verify hierarchy: node1 at top, node2 below, node3 below node2
        x1, y1 = positions["node1"]
        x2, y2 = positions["node2"]
        x3, y3 = positions["node3"]
        
        # Y-coordinates should increase
        self.assertLess(y1, y2)
        self.assertLess(y2, y3)
        
        # All positions should be within bounds
        for node_id, (x, y) in positions.items():
            self.assertGreater(x, 0)
            self.assertGreater(y, 0)
            self.assertLess(x, 1200)
            self.assertLess(y, 800)
    
    def test_tree_layout_branching(self):
        """Test tree layout with branching structure."""
        # Create tree: node1 -> [node2, node3], node2 -> node4
        nodes_dict = {
            "node1": LayoutNode("node1", "", ""),
            "node2": LayoutNode("node2", "", ""),
            "node3": LayoutNode("node3", "", ""),
            "node4": LayoutNode("node4", "", "")
        }
        
        # Set parent-child relationships
        nodes_dict["node2"].parent = "node1"
        nodes_dict["node3"].parent = "node1"
        nodes_dict["node4"].parent = "node2"
        
        nodes_dict["node1"].children = ["node2", "node3"]
        nodes_dict["node2"].children = ["node4"]
        
        self.engine.nodes = nodes_dict
        positions = self.engine.apply_reingold_tilford(root_id="node1")
        
        # Verify all nodes positioned
        self.assertEqual(len(positions), 4)
        
        # Verify hierarchy
        y1 = positions["node1"][1]
        y2 = positions["node2"][1]
        y3 = positions["node3"][1]
        y4 = positions["node4"][1]
        
        # node1 at top
        self.assertLess(y1, y2)
        self.assertLess(y1, y3)
        # node2 and node3 at same level
        self.assertAlmostEqual(y2, y3, delta=1.0)
        # node4 below node2
        self.assertLess(y2, y4)
    
    def test_tree_layout_single_node(self):
        """Test layout with single node."""
        self.engine.nodes["node1"] = LayoutNode("node1", "", "")
        positions = self.engine.apply_reingold_tilford(root_id="node1")
        
        self.assertEqual(len(positions), 1)
        x, y = positions["node1"]
        # Should be centered
        self.assertAlmostEqual(x, 600, delta=50)
    
    def test_tree_layout_centering(self):
        """Test that parent is centered above children."""
        # Create binary tree: node1 -> [node2, node3]
        nodes_dict = {
            "node1": LayoutNode("node1", "", ""),
            "node2": LayoutNode("node2", "", ""),
            "node3": LayoutNode("node3", "", "")
        }
        
        nodes_dict["node2"].parent = "node1"
        nodes_dict["node3"].parent = "node1"
        nodes_dict["node1"].children = ["node2", "node3"]
        
        self.engine.nodes = nodes_dict
        positions = self.engine.apply_reingold_tilford(root_id="node1")
        
        # Parent should be centered between children
        x1 = positions["node1"][0]
        x2 = positions["node2"][0]
        x3 = positions["node3"][0]
        
        # x1 should be approximately (x2 + x3) / 2
        expected_x1 = (x2 + x3) / 2
        self.assertAlmostEqual(x1, expected_x1, delta=10)


class TestForcedDirectedLayout(unittest.TestCase):
    """Test force-directed layout fallback."""
    
    def setUp(self):
        """Initialize force-directed engine."""
        self.engine = ForcedDirectedFallback(width=1200.0, height=800.0, iterations=10)
    
    def test_force_directed_layout(self):
        """Test force-directed layout on arbitrary graph."""
        nodes = [
            {"node_id": "n1", "entity_type": "user", "entity_value": "alice"},
            {"node_id": "n2", "entity_type": "host", "entity_value": "host1"},
            {"node_id": "n3", "entity_type": "file", "entity_value": "file1"}
        ]
        
        edges = [
            {"source_node_id": "n1", "target_node_id": "n2"},
            {"source_node_id": "n2", "target_node_id": "n3"}
        ]
        
        positions = self.engine.layout(nodes, edges)
        
        # Verify all nodes positioned
        self.assertEqual(len(positions), 3)
        
        # All positions should be within bounds
        for nid, (x, y) in positions.items():
            self.assertGreater(x, 0)
            self.assertGreater(y, 0)
            self.assertLess(x, 1200)
            self.assertLess(y, 800)
    
    def test_force_directed_empty_graph(self):
        """Test force-directed with empty graph."""
        positions = self.engine.layout([], [])
        self.assertEqual(len(positions), 0)
    
    def test_force_directed_single_node(self):
        """Test force-directed with single node."""
        nodes = [{"node_id": "n1", "entity_type": "user", "entity_value": "alice"}]
        positions = self.engine.layout(nodes, [])
        
        self.assertEqual(len(positions), 1)
        x, y = positions["n1"]
        self.assertGreater(x, 0)
        self.assertGreater(y, 0)


class TestPathExtraction(unittest.TestCase):
    """Test path extraction from shortest_path_json."""
    
    def test_extract_path_valid(self):
        """Test path extraction from valid shortest_path_json."""
        shortest_path_json = {
            "nodes": [
                {"node_id": "user1", "severity": 0.9},
                {"node_id": "host1", "severity": 0.8},
                {"node_id": "user2", "severity": 0.7}
            ],
            "edges": [
                {"source_node_id": "user1", "target_node_id": "host1"},
                {"source_node_id": "host1", "target_node_id": "user2"}
            ]
        }
        
        path = extract_path_from_shortest_path_json(shortest_path_json)
        
        self.assertIsNotNone(path)
        self.assertEqual(path, ["user1", "host1", "user2"])
    
    def test_extract_path_single_node(self):
        """Test path extraction with single node."""
        shortest_path_json = {
            "nodes": [{"node_id": "user1", "severity": 0.9}],
            "edges": []
        }
        
        path = extract_path_from_shortest_path_json(shortest_path_json)
        
        self.assertIsNotNone(path)
        self.assertEqual(path, ["user1"])
    
    def test_extract_path_empty(self):
        """Test path extraction from empty json."""
        path = extract_path_from_shortest_path_json({})
        self.assertIsNone(path)
    
    def test_extract_path_none(self):
        """Test path extraction from None."""
        path = extract_path_from_shortest_path_json(None)
        self.assertIsNone(path)
    
    def test_extract_path_disconnected(self):
        """Test path extraction with disconnected edges."""
        shortest_path_json = {
            "nodes": [
                {"node_id": "user1"},
                {"node_id": "host1"},
                {"node_id": "user2"}
            ],
            "edges": [
                # Missing edge from host1 to user2
                {"source_node_id": "user1", "target_node_id": "host1"}
            ]
        }
        
        path = extract_path_from_shortest_path_json(shortest_path_json)
        
        # Should return partial path or None
        if path:
            self.assertLess(len(path), 3)


class TestPathFiltering(unittest.TestCase):
    """Test filtering nodes and edges to path."""
    
    def test_filter_to_path_valid(self):
        """Test filtering to specified path nodes."""
        nodes = [
            {"node_id": "n1", "severity": 0.9},
            {"node_id": "n2", "severity": 0.8},
            {"node_id": "n3", "severity": 0.7},
            {"node_id": "n4", "severity": 0.6}
        ]
        
        edges = [
            {"source_node_id": "n1", "target_node_id": "n2"},
            {"source_node_id": "n2", "target_node_id": "n3"},
            {"source_node_id": "n3", "target_node_id": "n4"}
        ]
        
        path_nodes = ["n1", "n2", "n3"]
        
        filtered_nodes, filtered_edges = filter_to_path_nodes(nodes, edges, path_nodes)
        
        # Should keep only path nodes
        self.assertEqual(len(filtered_nodes), 3)
        self.assertFalse(any(n["node_id"] == "n4" for n in filtered_nodes))
        
        # Should keep only edges between path nodes
        self.assertEqual(len(filtered_edges), 2)
        self.assertFalse(any(e["target_node_id"] == "n4" for e in filtered_edges))
    
    def test_filter_to_path_single_node(self):
        """Test filtering to single node."""
        nodes = [
            {"node_id": "n1", "severity": 0.9},
            {"node_id": "n2", "severity": 0.8}
        ]
        
        edges = [{"source_node_id": "n1", "target_node_id": "n2"}]
        
        filtered_nodes, filtered_edges = filter_to_path_nodes(nodes, edges, ["n1"])
        
        self.assertEqual(len(filtered_nodes), 1)
        self.assertEqual(filtered_nodes[0]["node_id"], "n1")
        self.assertEqual(len(filtered_edges), 0)
    
    def test_filter_to_path_empty_path(self):
        """Test filtering with empty path."""
        nodes = [{"node_id": "n1", "severity": 0.9}]
        edges = []
        
        filtered_nodes, filtered_edges = filter_to_path_nodes(nodes, edges, [])
        
        self.assertEqual(len(filtered_nodes), 0)
        self.assertEqual(len(filtered_edges), 0)

    def test_filter_to_path_accepts_source_id_aliases(self):
        """Edges with source_id/target_id should still be filtered correctly."""
        nodes = [
            {"node_id": "n1", "severity": 0.9},
            {"node_id": "n2", "severity": 0.8},
            {"node_id": "n3", "severity": 0.7},
        ]
        edges = [
            {"source_id": "n1", "target_id": "n2"},
            {"source_id": "n2", "target_id": "n3"},
        ]

        filtered_nodes, filtered_edges = filter_to_path_nodes(nodes, edges, ["n1", "n2"])

        self.assertEqual(len(filtered_nodes), 2)
        self.assertEqual(len(filtered_edges), 1)


class TestApplyTreeLayout(unittest.TestCase):
    """Test apply_tree_layout integration function."""
    
    def test_apply_tree_layout_with_path(self):
        """Test tree layout application with path."""
        nodes = [
            {"node_id": "n1", "entity_type": "user", "severity_score": 0.9},
            {"node_id": "n2", "entity_type": "host", "severity_score": 0.8},
            {"node_id": "n3", "entity_type": "file", "severity_score": 0.7}
        ]
        
        edges = [
            {"source_node_id": "n1", "target_node_id": "n2"},
            {"source_node_id": "n2", "target_node_id": "n3"}
        ]
        
        path_nodes = ["n1", "n2", "n3"]
        
        positions = apply_tree_layout(nodes, edges, path_nodes, width=1200, height=800)
        
        self.assertEqual(len(positions), 3)

    def test_apply_layout_response_accepts_edge_aliases(self):
        """Backend layout should handle NetworkX-style source_id/target_id edges."""
        graph_data = {
            "run_id": "r1",
            "nodes": [
                {"node_id": "n1", "severity_score": 0.9},
                {"node_id": "n2", "severity_score": 0.7},
            ],
            "edges": [
                {"source_id": "n1", "target_id": "n2", "relationship": "RELATED_TO", "weight": 1.0}
            ],
        }

        out = apply_layout_to_graph_response(graph_data, shortest_path_json=None)

        self.assertEqual(out["layout"], "force-directed")
        self.assertEqual(len(out["nodes"]), 2)
        self.assertEqual(len(out["edges"]), 1)
        self.assertIn("x", out["nodes"][0])
        self.assertIn("y", out["nodes"][0])
    
    def test_apply_tree_layout_no_path(self):
        """Test tree layout without path (force-directed fallback)."""
        nodes = [
            {"node_id": "n1", "entity_type": "user", "severity_score": 0.9},
            {"node_id": "n2", "entity_type": "host", "severity_score": 0.8}
        ]
        
        edges = [{"source_node_id": "n1", "target_node_id": "n2"}]
        
        positions = apply_tree_layout(nodes, edges, path_nodes=None)
        
        self.assertEqual(len(positions), 2)
    
    def test_apply_tree_layout_empty(self):
        """Test tree layout with empty graph."""
        positions = apply_tree_layout([], [], path_nodes=None)
        self.assertEqual(len(positions), 0)


class TestApplyLayoutToGraphResponse(unittest.TestCase):
    """Test apply_layout_to_graph_response integration."""
    
    def test_apply_layout_complete_response(self):
        """Test applying layout to complete graph response."""
        graph_data = {
            "run_id": "run123",
            "nodes": [
                {"node_id": "n1", "entity_type": "user", "entity_value": "alice", "severity_score": 0.9},
                {"node_id": "n2", "entity_type": "host", "entity_value": "host1", "severity_score": 0.8},
                {"node_id": "n3", "entity_type": "file", "entity_value": "file1", "severity_score": 0.7}
            ],
            "edges": [
                {"source_node_id": "n1", "target_node_id": "n2"},
                {"source_node_id": "n2", "target_node_id": "n3"}
            ]
        }
        
        shortest_path_json = {
            "nodes": [{"node_id": "n1"}, {"node_id": "n2"}, {"node_id": "n3"}],
            "edges": [
                {"source_node_id": "n1", "target_node_id": "n2"},
                {"source_node_id": "n2", "target_node_id": "n3"}
            ]
        }
        
        result = apply_layout_to_graph_response(graph_data, shortest_path_json)
        
        # Should have layout metadata
        self.assertIn("layout", result)
        self.assertIn("path_count", result)
        self.assertIn("node_count", result)
        self.assertIn("edge_count", result)
        
        # Nodes should have x, y coordinates
        for node in result["nodes"]:
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertIsInstance(node["x"], (int, float))
            self.assertIsInstance(node["y"], (int, float))
    
    def test_apply_layout_no_shortest_path(self):
        """Test layout application without shortest_path_json."""
        graph_data = {
            "run_id": "run123",
            "nodes": [
                {"node_id": "n1", "entity_type": "user", "severity_score": 0.9},
                {"node_id": "n2", "entity_type": "host", "severity_score": 0.8}
            ],
            "edges": [{"source_node_id": "n1", "target_node_id": "n2"}]
        }
        
        result = apply_layout_to_graph_response(graph_data, shortest_path_json=None)
        
        # Should still have layout (force-directed fallback)
        self.assertIn("layout", result)
        self.assertIn("nodes", result)
    
    def test_apply_layout_empty_graph(self):
        """Test layout application on empty graph."""
        graph_data = {
            "run_id": "run123",
            "nodes": [],
            "edges": []
        }
        
        result = apply_layout_to_graph_response(graph_data)
        
        self.assertEqual(result["layout"], "empty")
        self.assertEqual(len(result["nodes"]), 0)


class TestGridLayoutFallback(unittest.TestCase):
    """Test grid layout fallback."""
    
    def test_grid_layout_multiple_nodes(self):
        """Test grid layout with multiple nodes."""
        nodes = [
            {"node_id": f"n{i}", "entity_type": "user"} for i in range(9)
        ]
        
        positions = _grid_layout_fallback(nodes, width=1200, height=800)
        
        self.assertEqual(len(positions), 9)
        
        # All positions should be within bounds
        for nid, (x, y) in positions.items():
            self.assertGreater(x, 0)
            self.assertGreater(y, 0)
            self.assertLess(x, 1200)
            self.assertLess(y, 800)
    
    def test_grid_layout_single_node(self):
        """Test grid layout with single node."""
        nodes = [{"node_id": "n1"}]
        positions = _grid_layout_fallback(nodes, width=1200, height=800)
        
        self.assertEqual(len(positions), 1)
    
    def test_grid_layout_empty(self):
        """Test grid layout with empty nodes."""
        positions = _grid_layout_fallback([], width=1200, height=800)
        self.assertEqual(len(positions), 0)


class TestPhase4Integration(unittest.TestCase):
    """Integration tests for Phase 4 tree-layout API."""
    
    def test_end_to_end_tree_layout(self):
        """Test end-to-end tree layout pipeline."""
        # Simulate correl ation engine output
        graph_data = {
            "run_id": "run456",
            "nodes": [
                {"node_id": "user1", "entity_type": "user", "entity_value": "admin", "severity_score": 0.95},
                {"node_id": "host1", "entity_type": "host", "entity_value": "server1", "severity_score": 0.85},
                {"node_id": "file1", "entity_type": "file", "entity_value": "config.ini", "severity_score": 0.75},
                {"node_id": "user2", "entity_type": "user", "entity_value": "guest", "severity_score": 0.60}
            ],
            "edges": [
                {"source_node_id": "user1", "target_node_id": "host1", "weight": 2.0},
                {"source_node_id": "host1", "target_node_id": "file1", "weight": 1.8},
                {"source_node_id": "file1", "target_node_id": "user2", "weight": 1.5}
            ]
        }
        
        # 6-hop path from Phase 3
        shortest_path_json = {
            "nodes": [
                {"node_id": "user1", "severity": 0.95},
                {"node_id": "host1", "severity": 0.85},
                {"node_id": "file1", "severity": 0.75}
            ],
            "edges": [
                {"source_node_id": "user1", "target_node_id": "host1"},
                {"source_node_id": "host1", "target_node_id": "file1"}
            ]
        }
        
        # Apply layout
        result = apply_layout_to_graph_response(graph_data, shortest_path_json)
        
        # Validate response structure
        self.assertEqual(result["run_id"], "run456")
        self.assertGreater(len(result["nodes"]), 0)
        self.assertIn("layout", result)
        self.assertIn("path_count", result)
        
        # Validate all nodes have positions
        for node in result["nodes"]:
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertGreaterEqual(node["x"], 0)
            self.assertGreaterEqual(node["y"], 0)
        
        # Should use tree layout (path-based)
        if result["path_count"] > 0:
            self.assertEqual(result["layout"], "tree")


if __name__ == "__main__":
    unittest.main()
