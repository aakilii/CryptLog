"""
Phase 1 Unit Tests: Dual-Engine Ingestion & Shortest Path
Tests for Neo4j Manager, NetworkX Engine, and parallel ingestion functionality
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock

# Import the managers and engines
from operation_room.services.neo4j_manager import Neo4jManager
from operation_room.services.networkx_engine import NetworkXEngine
from operation_room.services.correlation_agent import (
    _build_graph_structure,
    _ingest_parallel_engines,
    _extract_shortest_path_subgraph,
)


# ═══════════════════════════════════════════════════════════════
# Test Suite 1: Neo4j Manager
# ═══════════════════════════════════════════════════════════════

class TestNeo4jManager:
    """Test Neo4j connection, ingestion, and shortest path"""

    def test_neo4j_unavailable_on_bad_uri(self):
        """Test that Neo4j gracefully marks as unavailable on bad URI"""
        mgr = Neo4jManager(uri="bolt://invalid:9999", timeout=1.0)
        assert mgr.is_available() == False
        logger = mgr._driver if mgr._driver else None
        # Should not raise exception

    def test_neo4j_manager_initialization(self):
        """Test Neo4j manager initializes without errors"""
        mgr = Neo4jManager(uri="bolt://localhost:7687", timeout=1.0)
        # Should initialize without error (may not connect if Neo4j not running)
        assert mgr is not None

    @patch.object(Neo4jManager, "is_available")
    @patch("operation_room.services.neo4j_manager.subprocess.run")
    @patch("operation_room.services.neo4j_manager.shutil.which")
    @patch.dict("os.environ", {"OPROOM_NEO4J_START_COMMAND": "neo4j start"}, clear=False)
    def test_neo4j_auto_start_uses_configured_command(self, mock_which, mock_run, mock_available):
        """Test that the auto-start helper invokes the configured startup command."""
        mock_available.side_effect = [False, True]
        mock_which.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout="started", stderr="")

        mgr = Neo4jManager(uri="bolt://localhost:7687", timeout=1.0)
        result = mgr.start_local_service(wait_seconds=1.0)

        assert result is True
        mock_run.assert_called_once()

    def test_neo4j_graph_operations_when_unavailable(self):
        """Test that graph operations return False/None when Neo4j unavailable"""
        mgr = Neo4jManager(uri="bolt://invalid:9999", timeout=0.5)
        
        nodes = {"node1": {"entity_type": "USER", "entity_value": "alice"}}
        edges = [{"source_id": "node1", "target_id": "node2", "relationship": "PERFORMED"}]
        
        result = mgr.ingest_events(nodes, edges, "test-run")
        assert result == False

    @pytest.mark.skipif(True, reason="Requires running Neo4j instance")
    def test_neo4j_ingest_events(self):
        """Test Neo4j event ingestion (requires Neo4j running)"""
        mgr = Neo4jManager()
        nodes = {
            "node1": {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.8},
            "node2": {"entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5}
        }
        edges = [{
            "source_id": "node1",
            "target_id": "node2",
            "relationship": "EXECUTED_ON",
            "weight": 2.0,
            "confidence_score": 0.9,
            "evidence_ids": ["ev1", "ev2"]
        }]
        
        result = mgr.ingest_events(nodes, edges, "test-run-123")
        assert result == True

    @pytest.mark.skipif(True, reason="Requires running Neo4j instance")
    def test_neo4j_shortest_path(self):
        """Test Neo4j shortest path calculation (requires Neo4j running)"""
        mgr = Neo4jManager()
        result = mgr.calculate_shortest_path("node1", "node2", "test-run", max_hops=6)
        # May be None if no path, but shouldn't raise exception
        assert isinstance(result, (dict, type(None)))


# ═══════════════════════════════════════════════════════════════
# Test Suite 2: NetworkX Engine
# ═══════════════════════════════════════════════════════════════

class TestNetworkXEngine:
    """Test NetworkX graph construction and operations"""

    def test_networkx_build_simple_graph(self):
        """Test building a simple 3-node graph"""
        engine = NetworkXEngine()
        
        nodes = {
            "node1": {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.8},
            "node2": {"entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5},
            "node3": {"entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.3}
        }
        
        edges = [
            {"source_id": "node1", "target_id": "node2", "relationship": "EXECUTED_ON", "weight": 2.0},
            {"source_id": "node2", "target_id": "node3", "relationship": "ACCESSED", "weight": 1.5}
        ]
        
        result = engine.build_graph(nodes, edges)
        assert result == True
        assert engine.is_available() == True
        
        stats = engine.get_graph_stats()
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2

    def test_networkx_shortest_path_simple(self):
        """Test shortest path in a simple linear graph: node1 → node2 → node3"""
        engine = NetworkXEngine()
        
        nodes = {
            "node1": {"entity_type": "USER", "entity_value": "alice"},
            "node2": {"entity_type": "HOST", "entity_value": "server1"},
            "node3": {"entity_type": "DATA_OBJECT", "entity_value": "file.txt"}
        }
        
        edges = [
            {"source_id": "node1", "target_id": "node2", "relationship": "EXECUTED_ON", "weight": 1.0},
            {"source_id": "node2", "target_id": "node3", "relationship": "ACCESSED", "weight": 1.0}
        ]
        
        engine.build_graph(nodes, edges)
        
        result = engine.calculate_shortest_path("node1", "node3", max_hops=6)
        
        assert result is not None
        assert result["path_length"] == 2
        assert len(result["nodes"]) == 3  # node1, node2, node3
        assert result["nodes"][0]["node_id"] == "node1"
        assert result["nodes"][-1]["node_id"] == "node3"

    def test_networkx_shortest_path_respects_max_hops(self):
        """Test that shortest path respects max_hops constraint"""
        engine = NetworkXEngine()
        
        # Build a 10-node chain
        nodes = {f"node{i}": {"entity_type": "USER", "entity_value": f"user{i}"} for i in range(10)}
        edges = [{"source_id": f"node{i}", "target_id": f"node{i+1}", "relationship": "RELATED", "weight": 1.0}
                 for i in range(9)]
        
        engine.build_graph(nodes, edges)
        
        # Try to find path with max_hops=6 (should fail: 9 hops)
        result = engine.calculate_shortest_path("node0", "node9", max_hops=6)
        assert result is None  # Path is 9 hops, exceeds limit

        # Try with max_hops=10 (should succeed)
        result = engine.calculate_shortest_path("node0", "node9", max_hops=10)
        assert result is not None
        assert result["path_length"] == 9

    def test_networkx_no_path_exists(self):
        """Test shortest path when no path exists"""
        engine = NetworkXEngine()
        
        nodes = {
            "node1": {"entity_type": "USER", "entity_value": "alice"},
            "node2": {"entity_type": "USER", "entity_value": "bob"}
            # Disconnected nodes
        }
        edges = []
        
        engine.build_graph(nodes, edges)
        
        result = engine.calculate_shortest_path("node1", "node2", max_hops=6)
        assert result is None

    def test_networkx_get_subgraph_json(self):
        """Test subgraph JSON export"""
        engine = NetworkXEngine()
        
        nodes = {
            "node1": {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.8},
            "node2": {"entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5},
            "node3": {"entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.3}
        }
        
        edges = [
            {"source_id": "node1", "target_id": "node2", "relationship": "EXECUTED_ON", "weight": 2.0},
            {"source_id": "node2", "target_id": "node3", "relationship": "ACCESSED", "weight": 1.5}
        ]
        
        engine.build_graph(nodes, edges)
        
        subgraph = engine.get_subgraph_json(["node1", "node2"])
        
        assert subgraph is not None
        assert len(subgraph["nodes"]) == 2
        assert len(subgraph["edges"]) == 1
        assert subgraph["total_nodes"] == 2
        assert subgraph["total_edges"] == 1

    def test_networkx_clear(self):
        """Test graph clearing"""
        engine = NetworkXEngine()
        
        nodes = {"node1": {"entity_type": "USER", "entity_value": "alice"}}
        edges = []
        
        engine.build_graph(nodes, edges)
        assert engine.is_available() == True
        
        engine.clear()
        assert engine.is_available() == False


# ═══════════════════════════════════════════════════════════════
# Test Suite 3: Parallel Ingestion
# ═══════════════════════════════════════════════════════════════

class TestParallelIngestion:
    """Test parallel Neo4j + NetworkX ingestion"""

    def test_build_graph_structure(self):
        """Test extracting graph structure from events"""
        events = [
            {
                "actor": "alice",
                "source_system": "server1",
                "target": "file.txt",
                "normalised_ts": "2024-01-01T10:00:00Z",
                "tl_event_id": "ev1",
                "detail_parsed": {"source_ip": "192.168.1.1", "destination_ip": "10.0.0.1", "session_id": "sess123"}
            },
            {
                "actor": "alice",
                "source_system": "server1",
                "target": "file.txt",
                "normalised_ts": "2024-01-01T10:01:00Z",
                "tl_event_id": "ev2",
                "detail_parsed": {"source_ip": "192.168.1.1", "destination_ip": "10.0.0.1", "session_id": "sess123"}
            }
        ]
        
        nodes = [
            {"node_id": "node1", "entity_type": "USER", "entity_value": "alice", "severity_score": 0.8, "event_count": 2},
            {"node_id": "node2", "entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5, "event_count": 2},
            {"node_id": "node3", "entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.3, "event_count": 2},
        ]
        
        nodes_dict, edges = _build_graph_structure(events, nodes)
        
        assert len(nodes_dict) == 3
        assert len(edges) > 0
        # Should have created edges between nodes

    def test_extract_shortest_path_with_networkx(self):
        """Test extraction with NetworkX engine"""
        # This test uses NetworkX directly since Neo4j may not be available
        nodes_dict = {
            "node1": {"node_id": "node1", "entity_type": "USER", "entity_value": "alice", "severity_score": 0.8},
            "node2": {"node_id": "node2", "entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5},
            "node3": {"node_id": "node3", "entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.3}
        }
        
        edges = [
            {
                "edge_id": str(uuid.uuid4()),
                "source_node_id": "node1", "target_node_id": "node2",
                "relationship": "EXECUTED_ON", "weight": 1.0, "evidence_ids": ["ev1"]
            },
            {
                "edge_id": str(uuid.uuid4()),
                "source_node_id": "node2", "target_node_id": "node3",
                "relationship": "ACCESSED", "weight": 1.0, "evidence_ids": ["ev2"]
            }
        ]
        
        # Build graph in NetworkX first
        engine = NetworkXEngine()
        edges_for_engine = [
            {"source_id": e["source_node_id"], "target_id": e["target_node_id"],
             "relationship": e["relationship"], "weight": e["weight"], "evidence_ids": e["evidence_ids"],
             "confidence_score": 0.9}
            for e in edges
        ]
        engine.build_graph(nodes_dict, edges_for_engine)
        
        # Now test extraction
        with patch("operation_room.services.correlation_agent.get_networkx_engine", return_value=engine):
            result = _extract_shortest_path_subgraph(nodes_dict, edges, "test-run", max_hops=6)
        
        assert result is not None
        assert "nodes" in result
        assert "edges" in result
        assert "path_length" in result


# ═══════════════════════════════════════════════════════════════
# Test Suite 4: Error Handling
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Test error handling in engines"""

    def test_networkx_empty_graph(self):
        """Test NetworkX with empty graph"""
        engine = NetworkXEngine()
        assert engine.is_available() == False
        
        result = engine.calculate_shortest_path("node1", "node2")
        assert result is None

    def test_networkx_single_node(self):
        """Test NetworkX with single node"""
        engine = NetworkXEngine()
        nodes = {"node1": {"entity_type": "USER", "entity_value": "alice"}}
        edges = []
        
        engine.build_graph(nodes, edges)
        
        result = engine.calculate_shortest_path("node1", "node1")
        # Self-loop or no path
        assert result is None

    def test_neo4j_manager_close(self):
        """Test Neo4j manager cleanup"""
        mgr = Neo4jManager(uri="bolt://invalid:9999", timeout=0.5)
        mgr.close()
        # Should not raise exception
        assert mgr.is_available() == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
