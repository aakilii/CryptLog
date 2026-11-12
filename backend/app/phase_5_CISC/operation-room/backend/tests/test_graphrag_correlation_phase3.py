"""
Phase 3 Integration Tests: Database Schema & Hybrid Persistence
Tests for schema migration, DuckDB storage, and hybrid Neo4j/DuckDB retrieval
"""

import pytest
import json
from unittest.mock import Mock, patch
from operation_room.services.phase3_persistence import (
    _apply_graphrag_migration_if_needed,
    retrieve_correlation_graph,
    store_graphrag_results_hybrid,
)


# ═══════════════════════════════════════════════════════════════
# Test Suite 1: Schema Migration
# ═══════════════════════════════════════════════════════════════

class TestSchemaMigration:
    """Test GraphRAG schema migration functionality"""

    def test_migration_creates_all_columns(self):
        """Test that migration creates all 5 required columns"""
        # Mock DuckDB connection
        mock_conn = Mock()
        
        # Simulate column doesn't exist (first call)
        mock_conn.execute.side_effect = [
            Mock(fetchone=Mock(return_value=None)),  # Column check query
            None,  # ALTER 1
            None,  # ALTER 2
            None,  # ALTER 3
            None,  # ALTER 4
            None,  # ALTER 5
        ]

        result = _apply_graphrag_migration_if_needed(mock_conn)

        # Should attempt to create columns
        assert result == True
        # Verify ALTER TABLE calls were made
        assert mock_conn.execute.call_count >= 5

    def test_migration_idempotent_when_columns_exist(self):
        """Test that migration is idempotent (safe to run multiple times)"""
        # Mock connection with column already existing
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchone.return_value = ("graphrag_narrative",)

        result = _apply_graphrag_migration_if_needed(mock_conn)

        assert result == True
        # Should only check for existence, not try to ALTER
        assert mock_conn.execute.call_count == 1

    def test_migration_graceful_on_error(self):
        """Test that migration doesn't crash on database errors"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Database locked")

        result = _apply_graphrag_migration_if_needed(mock_conn)

        # Should still return True (graceful fallback)
        assert result == True


# ═══════════════════════════════════════════════════════════════
# Test Suite 2: Hybrid Persistence Write
# ═══════════════════════════════════════════════════════════════

class TestHybridPersistenceWrite:
    """Test storing GraphRAG results to hybrid storage"""

    @patch('operation_room.services.phase3_persistence.open_vault')
    def test_store_graphrag_results_to_duckdb(self, mock_open_vault):
        """Test storing GraphRAG results to DuckDB"""
        mock_conn = Mock()
        mock_open_vault.return_value = mock_conn

        graphrag_narrative = "## Root Cause Analysis\nThe attack originated from alice via server1..."
        shortest_path_json = {
            "path_length": 2,
            "source": "node1",
            "target": "node3",
            "engine_used": "networkx"
        }

        result = store_graphrag_results_hybrid(
            case_id="test-case",
            run_id="run-123",
            graphrag_narrative=graphrag_narrative,
            shortest_path_json=shortest_path_json,
            graph_engine_used="networkx"
        )

        assert result == True
        # Verify UPDATE was called
        mock_conn.execute.assert_called()

    @patch('operation_room.services.phase3_persistence.open_vault')
    def test_store_graphrag_handles_none_path(self, mock_open_vault):
        """Test storing GraphRAG results when path is None"""
        mock_conn = Mock()
        mock_open_vault.return_value = mock_conn

        result = store_graphrag_results_hybrid(
            case_id="test-case",
            run_id="run-123",
            graphrag_narrative="Narrative text",
            shortest_path_json=None,
            graph_engine_used="fallback"
        )

        assert result == True

    @patch('operation_room.services.phase3_persistence.open_vault')
    def test_store_graphrag_graceful_failure(self, mock_open_vault):
        """Test graceful handling when storage fails"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Connection failed")
        mock_open_vault.return_value = mock_conn

        result = store_graphrag_results_hybrid(
            case_id="test-case",
            run_id="run-123",
            graphrag_narrative="Text",
            shortest_path_json={},
            graph_engine_used="fallback"
        )

        # Should return False on failure (not raise exception)
        assert result == False


# ═══════════════════════════════════════════════════════════════
# Test Suite 3: Hybrid Persistence Read
# ═══════════════════════════════════════════════════════════════

class TestHybridPersistenceRead:
    """Test retrieving graph from hybrid storage with fallback"""

    @patch('operation_room.services.phase3_persistence.open_vault')
    @patch('operation_room.services.phase3_persistence.get_neo4j_manager')
    def test_retrieve_from_neo4j_primary(self, mock_get_neo4j, mock_open_vault):
        """Test that Neo4j is tried first"""
        # Mock Neo4j manager
        mock_neo4j_mgr = Mock()
        mock_neo4j_mgr.is_available.return_value = True
        mock_neo4j_mgr.get_subgraph_json.return_value = {
            "nodes": [{"node_id": "n1", "entity_type": "USER", "entity_value": "alice"}],
            "edges": [{"source_id": "n1", "target_id": "n2", "relationship": "CONNECTED"}]
        }
        mock_get_neo4j.return_value = mock_neo4j_mgr

        # Mock DuckDB for node lookup
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [("n1",), ("n2",)]
        mock_open_vault.return_value = mock_conn

        result = retrieve_correlation_graph("test-case", "run-123")

        assert result["engine_used"] == "neo4j"
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["entity_value"] == "alice"

    @patch('operation_room.services.phase3_persistence.open_vault')
    @patch('operation_room.services.phase3_persistence.get_neo4j_manager')
    def test_retrieve_fallback_to_duckdb(self, mock_get_neo4j, mock_open_vault):
        """Test fallback to DuckDB when Neo4j unavailable"""
        # Mock Neo4j as unavailable
        mock_neo4j_mgr = Mock()
        mock_neo4j_mgr.is_available.return_value = False
        mock_get_neo4j.return_value = mock_neo4j_mgr

        # Mock DuckDB retrieval
        mock_conn = Mock()
        
        # First query: get node IDs (fails for Neo4j path)
        # Second query: get nodes
        node_rows = [
            (
                "n1",  # node_id
                "USER",  # entity_type
                "alice",  # entity_value
                0.9,  # severity_score
                0.8,  # anomaly_score
                5,  # event_count
                "2024-01-01T10:00:00Z",  # first_seen
                "2024-01-01T10:05:00Z",  # last_seen
                '{"actions": ["LOGIN"]}'  # metadata_json
            )
        ]
        
        # Third query: get edges
        edge_rows = [
            (
                "e1",  # edge_id
                "n1",  # source_node_id
                "n2",  # target_node_id
                "CONNECTED_TO",  # relationship
                2.0,  # weight
                3,  # evidence_count
                "2024-01-01T10:00:00Z",  # first_seen
                "2024-01-01T10:05:00Z",  # last_seen
            )
        ]

        def execute_side_effect(*args, **kwargs):
            mock_result = Mock()
            if "SELECT node_id FROM correlation_nodes" in args[0]:
                mock_result.fetchall.return_value = [("n1",)]
            elif "SELECT node_id, entity_type" in args[0]:
                mock_result.fetchall.return_value = node_rows
            elif "SELECT edge_id" in args[0]:
                mock_result.fetchall.return_value = edge_rows
            return mock_result

        mock_conn.execute.side_effect = execute_side_effect
        mock_open_vault.return_value = mock_conn

        result = retrieve_correlation_graph("test-case", "run-123")

        assert result["engine_used"] == "duckdb_fallback"
        assert len(result["nodes"]) >= 1
        assert result["nodes"][0]["entity_value"] == "alice"

    @patch('operation_room.services.phase3_persistence.open_vault')
    def test_retrieve_returns_empty_on_error(self, mock_open_vault):
        """Test graceful return of empty graph on errors"""
        mock_open_vault.side_effect = Exception("Database connection failed")

        result = retrieve_correlation_graph("test-case", "run-123")

        assert result["engine_used"] == "error"
        assert len(result["nodes"]) == 0
        assert len(result["edges"]) == 0
        assert "error" in result


# ═══════════════════════════════════════════════════════════════
# Test Suite 4: Data Format Validation
# ═══════════════════════════════════════════════════════════════

class TestDataFormatValidation:
    """Validate that stored/retrieved data maintains integrity"""

    @patch('operation_room.services.phase3_persistence.open_vault')
    @patch('operation_room.services.phase3_persistence.get_neo4j_manager')
    def test_node_metadata_preserved(self, mock_get_neo4j, mock_open_vault):
        """Test that node metadata is correctly preserved through storage"""
        mock_neo4j_mgr = Mock()
        mock_neo4j_mgr.is_available.return_value = False
        mock_get_neo4j.return_value = mock_neo4j_mgr

        mock_conn = Mock()
        
        metadata_json = '{"actions": ["LOGIN", "LOGOUT"], "sources": ["AUTH_LOG"]}'
        node_rows = [
            ("n1", "USER", "alice", 0.9, 0.8, 5, "2024-01-01T10:00:00Z", "2024-01-01T10:05:00Z", metadata_json)
        ]

        def execute_side_effect(*args, **kwargs):
            mock_result = Mock()
            if "SELECT node_id FROM correlation_nodes" in args[0]:
                mock_result.fetchall.return_value = [("n1",)]
            elif "SELECT node_id, entity_type" in args[0]:
                mock_result.fetchall.return_value = node_rows
            elif "SELECT edge_id" in args[0]:
                mock_result.fetchall.return_value = []
            return mock_result

        mock_conn.execute.side_effect = execute_side_effect
        mock_open_vault.return_value = mock_conn

        result = retrieve_correlation_graph("test-case", "run-123")

        # Verify metadata is parsed correctly
        assert result["nodes"][0]["metadata"]["actions"] == ["LOGIN", "LOGOUT"]
        assert result["nodes"][0]["metadata"]["sources"] == ["AUTH_LOG"]

    @patch('operation_room.services.phase3_persistence.open_vault')
    @patch('operation_room.services.phase3_persistence.get_neo4j_manager')
    def test_timestamps_converted_to_strings(self, mock_get_neo4j, mock_open_vault):
        """Test that timestamps are properly converted to strings"""
        mock_neo4j_mgr = Mock()
        mock_neo4j_mgr.is_available.return_value = False
        mock_get_neo4j.return_value = mock_neo4j_mgr

        mock_conn = Mock()
        node_rows = [
            ("n1", "USER", "alice", 0.9, 0.8, 5, "2024-01-01T10:00:00Z", "2024-01-01T10:05:00Z", None)
        ]

        def execute_side_effect(*args, **kwargs):
            mock_result = Mock()
            if "SELECT node_id FROM correlation_nodes" in args[0]:
                mock_result.fetchall.return_value = [("n1",)]
            elif "SELECT node_id, entity_type" in args[0]:
                mock_result.fetchall.return_value = node_rows
            elif "SELECT edge_id" in args[0]:
                mock_result.fetchall.return_value = []
            return mock_result

        mock_conn.execute.side_effect = execute_side_effect
        mock_open_vault.return_value = mock_conn

        result = retrieve_correlation_graph("test-case", "run-123")

        # Verify timestamps are strings
        assert isinstance(result["nodes"][0]["first_seen"], str)
        assert isinstance(result["nodes"][0]["last_seen"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
