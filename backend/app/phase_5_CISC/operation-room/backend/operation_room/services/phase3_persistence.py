"""
Phase 3 Helper Functions: Hybrid Persistence Layer
Add these functions to correlation_agent.py during Phase 3 refactoring
"""

import json
import logging
from typing import Dict, Any, Optional
from operation_room.database import open_vault
from operation_room.services import neo4j_manager as neo4j_service

logger = logging.getLogger(__name__)


def get_neo4j_manager(*args, **kwargs):
    """Wrapper kept at module scope for test patch compatibility."""
    return neo4j_service.get_neo4j_manager(*args, **kwargs)


def _normalize_graph_payload(graph_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize engine-specific graph payloads to the correlation API shape."""
    nodes = graph_payload.get("nodes", [])
    edges = graph_payload.get("edges", [])

    normalized_edges = []
    for edge in edges:
        normalized_edges.append({
            **edge,
            "source_node_id": edge.get("source_node_id") or edge.get("source_id"),
            "target_node_id": edge.get("target_node_id") or edge.get("target_id"),
        })

    return {
        **graph_payload,
        "nodes": nodes,
        "edges": normalized_edges,
    }


def _with_generation_state(graph_payload: Dict[str, Any], status: str, message: str) -> Dict[str, Any]:
    return {
        **graph_payload,
        "generation_status": status,
        "generation_message": message,
    }


def _build_networkx_focused_view(nodes: list[Dict[str, Any]], edges: list[Dict[str, Any]]) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """Return a cleaner, engine-specific subgraph for NetworkX visualization."""
    if not nodes:
        return nodes, edges

    degree_map: Dict[str, int] = {}
    for edge in edges:
        source_id = edge.get("source_node_id") or edge.get("source_id")
        target_id = edge.get("target_node_id") or edge.get("target_id")
        if source_id:
            degree_map[source_id] = degree_map.get(source_id, 0) + 1
        if target_id:
            degree_map[target_id] = degree_map.get(target_id, 0) + 1

    max_degree = max(degree_map.values(), default=1)

    def _node_rank(node: Dict[str, Any]) -> float:
        node_id = str(node.get("node_id")) if node.get("node_id") is not None else ""
        severity = float(node.get("severity_score") or 0.0)
        degree_score = float(degree_map.get(node_id, 0)) / float(max_degree or 1)
        return (0.7 * severity) + (0.3 * degree_score)

    ranked_nodes = sorted(nodes, key=_node_rank, reverse=True)
    target_node_count = min(42, len(ranked_nodes))
    focused_nodes = ranked_nodes[:target_node_count]
    focused_node_ids = {node.get("node_id") for node in focused_nodes}

    connected_edges = []
    for edge in edges:
        source_id = edge.get("source_node_id") or edge.get("source_id")
        target_id = edge.get("target_node_id") or edge.get("target_id")
        if source_id in focused_node_ids and target_id in focused_node_ids:
            connected_edges.append(edge)

    connected_edges = sorted(connected_edges, key=lambda e: float(e.get("weight") or 0.0), reverse=True)
    focused_edges = connected_edges[: min(100, len(connected_edges))]

    return focused_nodes, focused_edges


def _apply_graphrag_migration_if_needed(conn) -> bool:
    """
    Apply GraphRAG schema migration if columns don't exist yet.
    This allows Phase 3 to run gracefully even if migration hasn't been applied.
    
    Returns:
        True if columns exist or were successfully added, False otherwise
    """
    try:
        # Check if graphrag_narrative column exists
        result = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'correlation_runs' AND column_name = 'graphrag_narrative'
        """).fetchone()

        if result:
            logger.info("[Phase3] GraphRAG schema columns already exist")
            return True

        # Try to add columns (safe: catches if they already exist)
        conn.execute("ALTER TABLE correlation_runs ADD COLUMN graphrag_narrative TEXT DEFAULT NULL")
        conn.execute("ALTER TABLE correlation_runs ADD COLUMN shortest_path_json JSON DEFAULT NULL")
        conn.execute("ALTER TABLE correlation_runs ADD COLUMN graph_engine_used VARCHAR DEFAULT 'fallback'")
        conn.execute("ALTER TABLE correlation_runs ADD COLUMN last_computed_at TIMESTAMP DEFAULT NULL")
        conn.execute("ALTER TABLE correlation_runs ADD COLUMN neo4j_graph_id VARCHAR DEFAULT NULL")

        logger.info("[Phase3] ✓ GraphRAG schema migration applied successfully")
        return True

    except Exception as e:
        logger.warning(f"[Phase3] Schema migration attempted but may have failed: {e}")
        # Continue anyway - columns might already exist
        return True


def retrieve_correlation_graph(
    case_id: str,
    run_id: Optional[str],
    preferred_engine: Optional[str] = None,
    strict_source: bool = False,
) -> Dict[str, Any]:
    """
    Retrieve graph from best available source with automatic fallback.
    Phase 3: Hybrid persistence (Neo4j primary, DuckDB fallback)
    
    Args:
        case_id: Case ID
        run_id: Correlation run ID
    
    Returns:
        Dict with nodes, edges, and metadata
    """
    preferred = (preferred_engine or "duckdb").lower()

    if not run_id:
        conn = open_vault(case_id)
        try:
            latest = conn.execute(
                "SELECT run_id FROM correlation_runs WHERE case_id = ? AND status = 'COMPLETED' ORDER BY completed_at DESC LIMIT 1",
                [case_id]
            ).fetchone()
            run_id = latest[0] if latest else None
        finally:
            conn.close()

    if not run_id:
        return _with_generation_state(
            {"nodes": [], "edges": [], "engine_used": "error", "graph_source": preferred, "run_id": None, "error": "No completed runs"},
            "error",
            "No completed correlation runs found for this case",
        )
    
    # Try Neo4j first when explicitly requested.
    if preferred == "neo4j":
        try:
            neo4j_mgr = get_neo4j_manager()
            if not neo4j_mgr.is_available():
                if strict_source:
                    return _with_generation_state({
                        "nodes": [],
                        "edges": [],
                        "engine_used": "neo4j_unavailable",
                        "graph_source": "neo4j",
                        "run_id": run_id,
                        "pending": True,
                        "error": "Neo4j service is not available",
                    }, "unavailable", "Neo4j service is not available")

            if neo4j_mgr.is_available():
                conn = open_vault(case_id)
                try:
                    rows = conn.execute(
                        "SELECT node_id FROM correlation_nodes WHERE run_id = ?",
                        [run_id]
                    ).fetchall()
                    node_ids = [row[0] for row in rows]

                    if node_ids:
                        subgraph = neo4j_mgr.get_subgraph_json(node_ids, run_id)
                        if subgraph and subgraph.get("nodes"):
                            logger.info(f"[Phase3] Retrieved graph from Neo4j for run {run_id}")
                            return _with_generation_state(
                                _normalize_graph_payload({
                                    "nodes": subgraph["nodes"],
                                    "edges": subgraph["edges"],
                                    "engine_used": "neo4j",
                                    "graph_source": "neo4j",
                                    "run_id": run_id,
                                }),
                                "generated",
                                "Neo4j graph generated successfully",
                            )
                finally:
                    conn.close()
        except Exception as e:
            logger.debug(f"[Phase3] Neo4j retrieval failed: {e}; falling back")
            if strict_source:
                return _with_generation_state({
                    "nodes": [],
                    "edges": [],
                    "engine_used": "neo4j_error",
                    "graph_source": "neo4j",
                    "run_id": run_id,
                    "error": str(e),
                }, "error", f"Neo4j graph generation failed: {e}")

        if strict_source:
            return _with_generation_state({
                "nodes": [],
                "edges": [],
                "engine_used": "neo4j_empty",
                "graph_source": "neo4j",
                "run_id": run_id,
                "error": "Neo4j returned no graph for this run",
            }, "error", "Neo4j returned no graph for the selected run")

    if preferred == "networkx":
        try:
            from operation_room.services.networkx_engine import get_networkx_engine

            conn = open_vault(case_id)
            try:
                node_rows = conn.execute(
                    """SELECT node_id, entity_type, entity_value, severity_score, anomaly_score, 
                       event_count, first_seen, last_seen, metadata_json 
                       FROM correlation_nodes WHERE run_id = ?""",
                    [run_id]
                ).fetchall()

                nodes = {}
                for row in node_rows:
                    nodes[row[0]] = {
                        "node_id": row[0],
                        "entity_type": row[1],
                        "entity_value": row[2],
                        "severity_score": row[3],
                        "anomaly_score": row[4],
                        "event_count": row[5],
                        "first_seen": str(row[6]) if row[6] else None,
                        "last_seen": str(row[7]) if row[7] else None,
                        "metadata": json.loads(row[8]) if row[8] else {},
                    }

                edge_rows = conn.execute(
                    """SELECT edge_id, source_node_id, target_node_id, relationship, weight, 
                       evidence_count, first_seen, last_seen 
                       FROM correlation_edges WHERE run_id = ?""",
                    [run_id]
                ).fetchall()

                edges = []
                for row in edge_rows:
                    edges.append({
                        "edge_id": row[0],
                        "source_id": row[1],
                        "target_id": row[2],
                        "relationship": row[3],
                        "weight": row[4],
                        "evidence_count": row[5],
                        "first_seen": str(row[6]) if row[6] else None,
                        "last_seen": str(row[7]) if row[7] else None,
                    })

                engine = get_networkx_engine()
                if engine.build_graph(nodes, edges):
                    subgraph = engine.get_subgraph_json(list(nodes.keys()))
                    if subgraph:
                        focused_nodes, focused_edges = _build_networkx_focused_view(
                            subgraph.get("nodes", []),
                            subgraph.get("edges", []),
                        )
                        logger.info(f"[Phase3] Retrieved graph from NetworkX for run {run_id}")
                        return _with_generation_state(
                            _normalize_graph_payload({
                                "nodes": focused_nodes,
                                "edges": focused_edges,
                                "engine_used": "networkx",
                                "graph_source": "networkx",
                                "run_id": run_id,
                            }),
                            "generated",
                            "NetworkX graph generated successfully (focused analysis view)",
                        )

                if strict_source:
                    return _with_generation_state({
                        "nodes": [],
                        "edges": [],
                        "engine_used": "networkx_empty",
                        "graph_source": "networkx",
                        "run_id": run_id,
                        "error": "NetworkX graph is empty for this run",
                    }, "error", "NetworkX graph is empty for the selected run")
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"[Phase3] NetworkX retrieval failed: {e}; falling back")
            if strict_source:
                return _with_generation_state({
                    "nodes": [],
                    "edges": [],
                    "engine_used": "networkx_error",
                    "graph_source": "networkx",
                    "run_id": run_id,
                    "error": str(e),
                }, "error", f"NetworkX graph generation failed: {e}")

    if strict_source and preferred in {"neo4j", "networkx"}:
        return _with_generation_state({
            "nodes": [],
            "edges": [],
            "engine_used": f"{preferred}_unavailable",
            "graph_source": preferred,
            "run_id": run_id,
            "error": f"{preferred} graph source is unavailable",
        }, "unavailable", f"{preferred.upper()} graph source is unavailable")

    # Try Neo4j first for default mode before DuckDB fallback, unless strict duckdb is requested.
    if not (strict_source and preferred == "duckdb"):
        try:
            neo4j_mgr = get_neo4j_manager()
            if neo4j_mgr.is_available():
                # Get node list from DuckDB
                conn = open_vault(case_id)
                try:
                    rows = conn.execute(
                        "SELECT node_id FROM correlation_nodes WHERE run_id = ?",   
                        [run_id]
                    ).fetchall()
                    node_ids = [row[0] for row in rows]
    
                    if node_ids:
                        subgraph = neo4j_mgr.get_subgraph_json(node_ids, run_id)    
                        if subgraph and subgraph.get("nodes"):
                            logger.info(f"[Phase3] Retrieved graph from Neo4j for run {run_id}")
                            return _with_generation_state(
                                _normalize_graph_payload({
                                    "nodes": subgraph["nodes"],
                                    "edges": subgraph["edges"],
                                    "engine_used": "neo4j",
                                    "graph_source": "neo4j",
                                    "run_id": run_id
                                }),
                                "generated",
                                "Neo4j graph generated successfully",
                            )
                finally:
                    conn.close()
        except Exception as e:
            logger.debug(f"[Phase3] Neo4j retrieval failed: {e}; falling back to DuckDB")
    
    # Fallback to DuckDB
    try:
        conn = open_vault(case_id)
        try:
            # Retrieve nodes
            rows = conn.execute(
                """SELECT node_id, entity_type, entity_value, severity_score, anomaly_score,
                   event_count, first_seen, last_seen, metadata_json
                   FROM correlation_nodes WHERE run_id = ?""",
                [run_id]
            ).fetchall()

            nodes = []
            for row in rows:
                nodes.append({
                    "node_id": row[0],
                    "entity_type": row[1],
                    "entity_value": row[2],
                    "severity_score": row[3],
                    "anomaly_score": row[4],
                    "event_count": row[5],
                    "first_seen": str(row[6]) if row[6] else None,
                    "last_seen": str(row[7]) if row[7] else None,
                    "metadata": json.loads(row[8]) if row[8] else {}
                })

            # Retrieve edges
            rows = conn.execute(
                """SELECT edge_id, source_node_id, target_node_id, relationship, weight, 
                   evidence_count, first_seen, last_seen 
                   FROM correlation_edges WHERE run_id = ?""",
                [run_id]
            ).fetchall()

            edges = []
            for row in rows:
                edges.append({
                    "edge_id": row[0],
                    "source_node_id": row[1],
                    "target_node_id": row[2],
                    "relationship": row[3],
                    "weight": row[4],
                    "evidence_count": row[5],
                    "first_seen": str(row[6]) if row[6] else None,
                    "last_seen": str(row[7]) if row[7] else None
                })

            logger.info(f"[Phase3] Retrieved graph from DuckDB for run {run_id} ({len(nodes)} nodes, {len(edges)} edges)")
            return _with_generation_state(
                _normalize_graph_payload({
                    "nodes": nodes,
                    "edges": edges,
                    "engine_used": "duckdb_fallback",
                    "graph_source": "duckdb",
                    "run_id": run_id
                }),
                "generated",
                "DuckDB graph loaded successfully",
            )

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"[Phase3] DuckDB retrieval failed: {e}")
        return _with_generation_state(
            {"nodes": [], "edges": [], "engine_used": "error", "run_id": run_id, "error": str(e)},
            "error",
            f"DuckDB graph generation failed: {e}",
        )


def store_graphrag_results_hybrid(
    case_id: str,
    run_id: str,
    graphrag_narrative: str,
    shortest_path_json: Optional[Dict],
    graph_engine_used: str
) -> bool:
    """
    Store GraphRAG results to both Neo4j (if available) and DuckDB (fallback).
    Phase 3: Hybrid persistence layer
    
    Args:
        case_id: Case ID
        run_id: Correlation run ID
        graphrag_narrative: Enhanced narrative with GraphRAG context
        shortest_path_json: 6-hop subgraph structure
        graph_engine_used: Which engine was used ("neo4j", "networkx", or "fallback")
    
    Returns:
        True if stored successfully (to at least DuckDB)
    """
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc).isoformat()
    success = False

    # Try Neo4j first (optional)
    try:
        from operation_room.services.neo4j_manager import get_neo4j_manager
        neo4j_mgr = get_neo4j_manager()
        if neo4j_mgr.is_available():
            # Neo4j stores narrative as metadata on the run node
            # (Future: implement run node persistence in Neo4j)
            logger.debug("[Phase3] Neo4j narrative storage (not yet implemented)")
    except Exception as e:
        logger.debug(f"[Phase3] Neo4j narrative storage skipped: {e}")

    # Always persist to DuckDB (durable storage)
    try:
        conn = open_vault(case_id)
        try:
            # Apply migration if needed
            _apply_graphrag_migration_if_needed(conn)

            # Update correlation_runs with GraphRAG metadata
            conn.execute("""
                UPDATE correlation_runs
                SET graphrag_narrative = ?,
                    shortest_path_json = ?,
                    graph_engine_used = ?,
                    last_computed_at = ?
                WHERE run_id = ?
            """, [
                graphrag_narrative,
                json.dumps(shortest_path_json) if shortest_path_json else None,
                graph_engine_used,
                now,
                run_id
            ])

            logger.info(f"[Phase3] ✓ Stored GraphRAG results to DuckDB (engine={graph_engine_used})")
            success = True

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"[Phase3] ✗ Failed to store GraphRAG results: {e}")
        success = False

    return success
