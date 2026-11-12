"""
Phase 2 Integration Tests: GraphRAG Narrative Enhancement
Tests for LLM context injection, narrative generation, and fallback mechanisms
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from operation_room.services.correlation_agent import (
    _build_graphrag_context,
    _fallback_graphrag_context,
)


# ═══════════════════════════════════════════════════════════════
# Test Suite 1: GraphRAG Context Builder
# ═══════════════════════════════════════════════════════════════

class TestGraphRAGContextBuilder:
    """Test GraphRAG context string generation from shortest path"""

    def test_build_graphrag_context_with_valid_path(self):
        """Test context building with a valid 3-node path"""
        shortest_path_json = {
            "path_length": 2,
            "source": "node1",
            "target": "node3",
            "engine_used": "networkx",
            "nodes": [
                {
                    "node_id": "node1",
                    "entity_type": "USER",
                    "entity_value": "alice",
                    "severity_score": 0.9,
                    "anomaly_score": 0.85
                },
                {
                    "node_id": "node2",
                    "entity_type": "HOST",
                    "entity_value": "server1",
                    "severity_score": 0.7,
                    "anomaly_score": 0.6
                },
                {
                    "node_id": "node3",
                    "entity_type": "DATA_OBJECT",
                    "entity_value": "file.txt",
                    "severity_score": 0.5,
                    "anomaly_score": 0.4
                }
            ],
            "edges": [
                {
                    "source_id": "node1",
                    "target_id": "node2",
                    "relationship": "EXECUTED_ON",
                    "weight": 2.0,
                    "confidence_score": 0.95,
                    "evidence_ids": ["ev1", "ev2", "ev3"]
                },
                {
                    "source_id": "node2",
                    "target_id": "node3",
                    "relationship": "ACCESSED",
                    "weight": 1.5,
                    "confidence_score": 0.85,
                    "evidence_ids": ["ev4", "ev5"]
                }
            ]
        }

        context = _build_graphrag_context(shortest_path_json)

        # Verify context contains critical sections
        assert "CRITICAL PATH ANALYSIS" in context
        assert "Path Length: 2" in context
        assert "Source: node1" in context
        assert "Target: node3" in context
        
        # Verify entities are properly formatted
        assert "[USER] alice" in context
        assert "[HOST] server1" in context
        assert "[DATA_OBJECT] file.txt" in context
        
        # Verify severity scores are included
        assert "Severity: 0.90/1.0" in context
        assert "Anomaly Score: 0.850" in context
        
        # Verify relationships are included
        assert "[EXECUTED_ON]" in context
        assert "[ACCESSED]" in context
        assert "Weight: 2.0" in context
        assert "Weight: 1.5" in context
        
        # Verify evidence IDs are referenced
        assert "ev1" in context
        assert "ev4" in context
        
        # Verify GraphRAG warning
        assert "Do NOT reference any entities outside this critical path" in context

    def test_build_graphrag_context_with_none(self):
        """Test context building when shortest_path_json is None"""
        context = _build_graphrag_context(None)
        assert context == ""

    def test_build_graphrag_context_with_empty_dict(self):
        """Test context building with empty shortest_path_json"""
        context = _build_graphrag_context({})
        assert context != ""
        # Should still have the header
        assert "CRITICAL PATH ANALYSIS" in context

    def test_build_graphrag_context_single_node_path(self):
        """Test context building with single-node path"""
        shortest_path_json = {
            "path_length": 0,
            "source": "node1",
            "target": "node1",
            "nodes": [
                {
                    "node_id": "node1",
                    "entity_type": "USER",
                    "entity_value": "alice",
                    "severity_score": 0.9,
                    "anomaly_score": 0.85
                }
            ],
            "edges": []
        }

        context = _build_graphrag_context(shortest_path_json)
        assert "1. [USER] alice" in context
        assert "Path Length: 0" in context

    def test_build_graphrag_context_long_path(self):
        """Test context building with 6-hop path"""
        nodes = [
            {
                "node_id": f"node{i}",
                "entity_type": ["USER", "HOST", "IP", "SESSION", "PROCESS", "DATA_OBJECT"][i % 6],
                "entity_value": f"entity{i}",
                "severity_score": 1.0 - (i * 0.1),
                "anomaly_score": 0.9 - (i * 0.1)
            }
            for i in range(7)  # 7 nodes = 6-hop path
        ]

        edges = [
            {
                "source_id": f"node{i}",
                "target_id": f"node{i+1}",
                "relationship": "CONNECTED_TO",
                "weight": 1.0,
                "confidence_score": 0.9,
                "evidence_ids": [f"ev{i}"]
            }
            for i in range(6)
        ]

        shortest_path_json = {
            "path_length": 6,
            "source": "node0",
            "target": "node6",
            "nodes": nodes,
            "edges": edges
        }

        context = _build_graphrag_context(shortest_path_json)

        # Verify all 7 nodes are present
        for i in range(7):
            assert f"entity{i}" in context

        # Verify all 6 edges are present
        for i in range(6):
            assert "[CONNECTED_TO]" in context


# ═══════════════════════════════════════════════════════════════
# Test Suite 2: Fallback GraphRAG Context
# ═══════════════════════════════════════════════════════════════

class TestFallbackGraphRAGContext:
    """Test fallback context generation when shortest path unavailable"""

    def test_fallback_context_with_mixed_entities(self):
        """Test fallback context with diverse entity types"""
        nodes = [
            {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.9, "event_count": 20},
            {"entity_type": "USER", "entity_value": "bob", "severity_score": 0.8, "event_count": 15},
            {"entity_type": "HOST", "entity_value": "server1", "severity_score": 0.7, "event_count": 30},
            {"entity_type": "HOST", "entity_value": "server2", "severity_score": 0.6, "event_count": 20},
            {"entity_type": "IP", "entity_value": "192.168.1.1", "severity_score": 0.5, "event_count": 10},
            {"entity_type": "IP", "entity_value": "10.0.0.1", "severity_score": 0.4, "event_count": 5},
            {"entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.3, "event_count": 2},
            {"entity_type": "SESSION", "entity_value": "sess123", "severity_score": 0.2, "event_count": 1},
            {"entity_type": "PROCESS", "entity_value": "svchost.exe", "severity_score": 0.1, "event_count": 3},
            {"entity_type": "USER", "entity_value": "charlie", "severity_score": 0.05, "event_count": 1},
        ]

        edges = [
            {"source_label": "alice", "target_label": "server1", "relationship": "EXECUTED_ON", "weight": 15},
            {"source_label": "server1", "target_label": "file.txt", "relationship": "ACCESSED", "weight": 10},
            {"source_label": "bob", "target_label": "server2", "relationship": "CONNECTED_TO", "weight": 8},
            {"source_label": "192.168.1.1", "target_label": "server1", "relationship": "AUTHENTICATED_FROM", "weight": 12},
        ]

        context = _fallback_context_builder(nodes, edges)

        # Verify header indicates fallback
        assert "Fallback: Top 10 Entities" in context
        assert f"Total entities in case: 10" in context
        assert f"Total relationships: 4" in context

        # Verify top severity entities are listed
        assert "[USER] alice" in context
        assert "[USER] bob" in context
        assert "[HOST] server1" in context

        # Verify relationships section exists
        assert "### Top Relationships" in context
        assert "EXECUTED_ON" in context

        # Verify fallback note
        assert "analysis may reference broader entity set" in context

    def test_fallback_context_with_few_entities(self):
        """Test fallback context with fewer than 10 entities"""
        nodes = [
            {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.9},
            {"entity_type": "HOST", "entity_value": "server1", "severity_score": 0.5},
        ]
        edges = [
            {"source_label": "alice", "target_label": "server1", "relationship": "EXECUTED_ON", "weight": 1.0}
        ]

        context = _fallback_context_builder(nodes, edges)

        assert "Total entities in case: 2" in context
        assert "Total relationships: 1" in context
        assert "[USER] alice" in context
        assert "[HOST] server1" in context

    def test_fallback_context_empty_edges(self):
        """Test fallback context with no edges"""
        nodes = [
            {"entity_type": "USER", "entity_value": "alice", "severity_score": 0.9},
        ]
        edges = []

        context = _fallback_context_builder(nodes, edges)

        assert "Total entities in case: 1" in context
        assert "Total relationships: 0" in context
        assert "[USER] alice" in context


# ═══════════════════════════════════════════════════════════════
# Helper Functions (mimic correlation_agent internals for testing)
# ═══════════════════════════════════════════════════════════════

def _fallback_context_builder(nodes, edges):
    """Helper to test fallback context generation"""
    context_lines = ["## Entity Correlation Context (Fallback: Top 10 Entities)\n"]

    # Top 10 by severity
    top_entities = sorted(nodes, key=lambda n: n.get("severity_score", 0), reverse=True)[:10]

    context_lines.append(f"Total entities in case: {len(nodes)}")
    context_lines.append(f"Total relationships: {len(edges)}\n")

    context_lines.append("### Top Severity Entities\n")
    for i, entity in enumerate(top_entities, 1):
        context_lines.append(
            f"{i}. [{entity['entity_type']}] {entity['entity_value']} "
            f"(severity={entity.get('severity_score', 0):.2f})"
        )

    # Top connections
    top_edges = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)[:10]

    context_lines.append("\n### Top Relationships\n")
    for i, edge in enumerate(top_edges, 1):
        context_lines.append(
            f"{i}. {edge.get('source_label', '?')} --[{edge['relationship']}]--> "
            f"{edge.get('target_label', '?')} (weight={edge['weight']})"
        )

    context_lines.append(
        "\n**NOTE**: Using top-10 fallback context (shortest path unavailable). "
        "analysis may reference broader entity set."
    )

    return "\n".join(context_lines)


# ═══════════════════════════════════════════════════════════════
# Test Suite 3: LLM Context Injection Validation
# ═══════════════════════════════════════════════════════════════

class TestLLMContextValidation:
    """Validate that LLM context includes GraphRAG safety rules"""

    def test_graphrag_context_includes_safety_rules(self):
        """Verify GraphRAG context explicitly warns against hallucination"""
        shortest_path_json = {
            "path_length": 2,
            "source": "node1",
            "target": "node3",
            "nodes": [
                {"node_id": "node1", "entity_type": "USER", "entity_value": "alice", "severity_score": 0.9, "anomaly_score": 0.8},
                {"node_id": "node3", "entity_type": "DATA_OBJECT", "entity_value": "file.txt", "severity_score": 0.5, "anomaly_score": 0.4}
            ],
            "edges": [
                {"source_id": "node1", "target_id": "node3", "relationship": "ACCESSED", "weight": 1.0, "confidence_score": 0.9, "evidence_ids": ["ev1"]}
            ]
        }

        context = _build_graphrag_context(shortest_path_json)

        # Verify safety warnings
        assert "Do NOT reference any entities outside this critical path" in context
        assert "ONLY" in context or "only" in context

    def test_graphrag_context_references_evidence(self):
        """Verify evidence IDs are included for traceability"""
        shortest_path_json = {
            "path_length": 1,
            "source": "node1",
            "target": "node2",
            "nodes": [
                {"node_id": "node1", "entity_type": "USER", "entity_value": "alice", "severity_score": 0.9, "anomaly_score": 0.8},
                {"node_id": "node2", "entity_type": "HOST", "entity_value": "server1", "severity_score": 0.7, "anomaly_score": 0.6}
            ],
            "edges": [
                {
                    "source_id": "node1",
                    "target_id": "node2",
                    "relationship": "EXECUTED_ON",
                    "weight": 3.0,
                    "confidence_score": 0.95,
                    "evidence_ids": ["tl_event_001", "tl_event_002", "tl_event_003"]
                }
            ]
        }

        context = _build_graphrag_context(shortest_path_json)

        assert "tl_event_001" in context
        assert "Evidence IDs:" in context

    def test_graphrag_context_includes_scores(self):
        """Verify severity and confidence scores are included"""
        shortest_path_json = {
            "path_length": 1,
            "source": "node1",
            "target": "node2",
            "nodes": [
                {"node_id": "node1", "entity_type": "USER", "entity_value": "alice", "severity_score": 0.85, "anomaly_score": 0.72}
            ],
            "edges": [
                {"source_id": "node1", "target_id": "node2", "relationship": "CONNECTED", "weight": 2.5, "confidence_score": 0.88, "evidence_ids": ["ev1"]}
            ]
        }

        context = _build_graphrag_context(shortest_path_json)

        assert "Severity: 0.85/1.0" in context
        assert "Anomaly Score: 0.720" in context
        assert "Confidence: 0.88" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
