"""
Correlation & Root-Cause Analysis API routes.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from operation_room.database import open_vault, get_vault_path

router = APIRouter(prefix="/api/cases/{case_id}/correlation", tags=["correlation"])
logger = logging.getLogger(__name__)


def _graph_engine_label(engine_used: Optional[str]) -> str:
    if not engine_used:
        return "legacy fallback"

    normalized = engine_used.lower()
    if "neo4j" in normalized:
        return "Neo4j primary engine"
    if "networkx" in normalized:
        return "NetworkX fallback"
    if "duckdb" in normalized:
        return "DuckDB stored graph"
    if "fallback" in normalized:
        return "Fallback graph path"
    return engine_used.replace("_", " ").title()


def _layout_label(layout: Optional[str]) -> str:
    if not layout:
        return "browser physics fallback"

    normalized = layout.lower()
    if normalized == "tree":
        return "backend tree layout"
    if normalized == "force-directed":
        return "backend force-directed fallback"
    if normalized == "grid-fallback":
        return "backend grid fallback"
    if normalized == "empty":
        return "empty graph"
    if normalized == "browser-physics-fallback":
        return "browser physics fallback"
    return layout.replace("_", " ")


class RunCorrelationRequest(BaseModel):
    llm_provider: str = "ollama"
    severity_weights: dict = {"anomaly": 0.4, "privilege": 0.3, "frequency": 0.3}


class ChatRequest(BaseModel):
    query: str
    llm_provider: str = "ollama"
    run_id: Optional[str] = None


class ToggleRuleRequest(BaseModel):
    enabled: bool


@router.post("/run")
async def run_correlation(case_id: str, body: RunCorrelationRequest):
    from operation_room.services.correlation_agent import run_correlation as _run
    try:
        return _run(case_id, llm_provider=body.llm_provider, severity_weights=body.severity_weights)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/graph")
async def get_graph(
    case_id: str,
    run_id: Optional[str] = None,
    graph_engine: Optional[str] = None,
    strict_source: bool = True,
):
    try:
        from operation_room.services.phase3_persistence import retrieve_correlation_graph
        preferred_engine = (graph_engine or "duckdb").lower()
        neo4j_progress = None
        neo4j_diagnostics = None

        if preferred_engine == "neo4j":
            from operation_room.services.neo4j_manager import get_neo4j_manager

            neo4j_mgr = get_neo4j_manager()
            neo4j_diagnostics = neo4j_mgr.get_diagnostics()
            if not neo4j_mgr.is_available():
                logger.info("Neo4j unavailable on request; attempting best-effort service start")
                started = neo4j_mgr.start_local_service(wait_seconds=14.0)
                neo4j_diagnostics = neo4j_mgr.get_diagnostics()
                neo4j_progress = {
                    "state": "ready" if started else "unavailable",
                    "message": (
                        "Neo4j is available. Loading graph..."
                        if started
                        else (
                            f"Neo4j service is not available on {neo4j_diagnostics.get('host', 'localhost')}:"
                            f"{neo4j_diagnostics.get('port', 7687)}. Start Neo4j to view this graph source."
                        )
                    ),
                    "retry_after_ms": 2500 if started else 0,
                }

        graph_data = retrieve_correlation_graph(
            case_id,
            run_id or "",
            preferred_engine=preferred_engine,
            strict_source=strict_source,
        )
        if graph_data.get("engine_used") and not graph_data.get("graph_engine_used"):
            graph_data["graph_engine_used"] = graph_data.get("engine_used")
        graph_data["graph_source_requested"] = preferred_engine
        graph_data["graph_source"] = graph_data.get("graph_source", preferred_engine)
        graph_data["graph_source_requested_label"] = {
            "duckdb": "DuckDB correlation graph",
            "neo4j": "Neo4j correlation graph",
            "networkx": "NetworkX correlation graph",
        }.get(preferred_engine, "DuckDB correlation graph")
        graph_data["graph_source_label"] = {
            "duckdb": "DuckDB correlation graph",
            "neo4j": "Neo4j correlation graph",
            "networkx": "NetworkX correlation graph",
        }.get(graph_data.get("graph_source", preferred_engine), "DuckDB correlation graph")
        graph_data["graph_engine_label"] = _graph_engine_label(graph_data.get("graph_engine_used"))
        graph_data["graph_fallback_reason"] = None
        graph_data["layout_source"] = None
        graph_data["layout_label"] = "browser physics fallback"
        graph_data["graph_engine_requested"] = preferred_engine
        if neo4j_diagnostics is not None:
            graph_data["neo4j_diagnostics"] = neo4j_diagnostics
        graph_data["generation_status"] = graph_data.get("generation_status") or ("generated" if graph_data.get("nodes") else "pending")
        graph_data["generation_message"] = graph_data.get("generation_message") or (
            f"{preferred_engine.upper()} graph generated successfully"
            if graph_data.get("nodes")
            else f"Generating {preferred_engine.upper()} graph..."
        )

        if neo4j_progress and graph_data.get("graph_engine_used") != "neo4j":
            graph_data["graph_pending"] = True
            graph_data["progress_state"] = neo4j_progress["state"]
            graph_data["progress_message"] = neo4j_progress["message"]
            graph_data["retry_after_ms"] = neo4j_progress["retry_after_ms"]
            graph_data["generation_status"] = "pending" if neo4j_progress["state"] == "ready" else "unavailable"
            graph_data["generation_message"] = neo4j_progress["message"]

        if graph_data.get("graph_engine_used") and graph_data.get("graph_engine_used") != preferred_engine:
            graph_data["graph_fallback_reason"] = f"Requested {preferred_engine}, used {graph_data['graph_engine_used']}"

        if strict_source and graph_data.get("graph_source") != preferred_engine:
            graph_data["graph_fallback_reason"] = None
            graph_data["nodes"] = []
            graph_data["edges"] = []
            graph_data["graph_pending"] = True
            graph_data["progress_state"] = "waiting"
            graph_data["progress_message"] = f"Waiting for {preferred_engine.upper()} graph data..."
            graph_data["retry_after_ms"] = 3000
            graph_data["generation_status"] = "pending"
            graph_data["generation_message"] = graph_data["progress_message"]
        
        # Apply tree layout from Phase 3 shortest_path
        from operation_room.services.graph_layout import apply_layout_to_graph_response
        from operation_room.database import open_vault
        import json
        
        # Retrieve shortest_path_json from Phase 3
        if graph_data.get("nodes"):
            try:
                run_ref = graph_data.get("run_id") or run_id
                conn = open_vault(case_id)
                result = conn.execute(
                    "SELECT shortest_path_json, graph_engine_used, last_computed_at FROM correlation_runs WHERE run_id=? LIMIT 1",
                    [run_ref]
                ).fetchone()
                
                shortest_path_json = None
                if result:
                    if result[1]:
                        graph_data["run_graph_engine_used"] = result[1]
                    if result[2]:
                        graph_data["last_computed_at"] = str(result[2])

                if result and result[0]:
                    try:
                        shortest_path_json = json.loads(result[0])
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif graph_data.get("graph_engine_used"):
                      pass # Silent fallback to standard force-directed layout if no explicit tree path exists
                conn.close()
                
                # Apply tree layout with shortest_path context.
                # Keep API provenance metadata stable even if layout helper returns
                # a reduced shape containing only graph geometry fields.
                provenance = {
                    "graph_source_requested": graph_data.get("graph_source_requested"),
                    "graph_source_requested_label": graph_data.get("graph_source_requested_label"),
                    "graph_source": graph_data.get("graph_source"),
                    "graph_source_label": graph_data.get("graph_source_label"),
                    "graph_engine_used": graph_data.get("graph_engine_used"),
                    "graph_engine_label": graph_data.get("graph_engine_label"),
                    "neo4j_diagnostics": graph_data.get("neo4j_diagnostics"),
                    "run_graph_engine_used": graph_data.get("run_graph_engine_used"),
                    "graph_engine_requested": graph_data.get("graph_engine_requested"),
                    "graph_fallback_reason": graph_data.get("graph_fallback_reason"),
                    "last_computed_at": graph_data.get("last_computed_at"),
                    "graph_pending": graph_data.get("graph_pending"),
                    "progress_state": graph_data.get("progress_state"),
                    "progress_message": graph_data.get("progress_message"),
                    "retry_after_ms": graph_data.get("retry_after_ms"),
                    "generation_status": graph_data.get("generation_status"),
                    "generation_message": graph_data.get("generation_message"),
                }

                graph_data = apply_layout_to_graph_response(
                    graph_data,
                    shortest_path_json=shortest_path_json,
                    width=1200.0,
                    height=800.0
                )
                graph_data.update({k: v for k, v in provenance.items() if v is not None})
                graph_data["layout_source"] = graph_data.get("layout")
                graph_data["layout_label"] = _layout_label(graph_data.get("layout"))
            except Exception as e:
                logger.warning(f"Tree layout failed: {e}; returning graph without positioning")
                graph_data["layout"] = "browser-physics-fallback"
                graph_data["layout_source"] = "browser-physics-fallback"
                graph_data["layout_label"] = _layout_label("browser-physics-fallback")
                graph_data["graph_fallback_reason"] = f"Backend layout failed: {e}"
        else:
            graph_data["layout"] = "empty"
            graph_data["layout_source"] = "empty"
            graph_data["layout_label"] = _layout_label("empty")
        
        return graph_data
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/narrative")
async def get_narrative(case_id: str, run_id: Optional[str] = None):
    from operation_room.services.correlation_agent import get_narrative as _get
    try:
        # Get base narrative
        narrative_data = _get(case_id, run_id)
        
        if narrative_data.get("error"):
            return narrative_data
        
        # Enhance with Phase 3 GraphRAG data if available
        from operation_room.database import open_vault
        import json
        
        try:
            conn = open_vault(case_id)
            result = conn.execute(
                "SELECT graphrag_narrative, graph_engine_used, last_computed_at FROM correlation_runs WHERE run_id=? LIMIT 1",
                [narrative_data.get("run_id")]
            ).fetchone()
            
            if result:
                graphrag_narrative, engine_used, computed_at = result
                # Add GraphRAG fields if they exist
                if graphrag_narrative:
                    narrative_data["graphrag_narrative"] = graphrag_narrative
                if engine_used:
                    narrative_data["graph_engine_used"] = engine_used
                if computed_at:
                    narrative_data["last_computed_at"] = str(computed_at)
            
            conn.close()
        except Exception as e:
            import logging
            logging.warning(f"Failed to retrieve GraphRAG data: {e}")
            # Continue with base narrative
        
        return narrative_data
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.post("/chat")
async def chat(case_id: str, body: ChatRequest):
    from operation_room.services.intent_router import intent_router
    try:
        # Route intent first
        agent_id, reason = await intent_router.route_prompt(body.query)
        
        # Switch logic based on routed agent
        if agent_id == "timeline_agent":
            from operation_room.services.timeline_service import chat_with_agent as timeline_chat
            return await timeline_chat(case_id, body.query, body.llm_provider, body.run_id)
        elif agent_id == "network_agent":
            from operation_room.services.network_agent import chat_with_agent as network_chat
            return await network_chat(case_id, body.query, body.llm_provider, body.run_id)
        elif agent_id == "anomaly_agent":
            from operation_room.services.anomaly_agent import chat_with_agent as anomaly_chat
            return await anomaly_chat(case_id, body.query, body.llm_provider, body.run_id)
        else:
            # Fallback to the overarching correlation agent graph context
            from operation_room.services.correlation_agent import chat_with_agent
            return await chat_with_agent(case_id, body.query, body.llm_provider, body.run_id)
            
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.get("/runs")
async def list_runs(case_id: str):
    from operation_room.services.correlation_agent import get_correlation_runs
    try:
        return get_correlation_runs(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.get("/rules")
async def list_rules(case_id: str):
    from operation_room.services.correlation_agent import get_rules
    try:
        return get_rules(case_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


@router.put("/rules/{rule_id}")
async def update_rule(case_id: str, rule_id: str, body: ToggleRuleRequest):
    from operation_room.services.correlation_agent import toggle_rule
    try:
        return toggle_rule(case_id, rule_id, body.enabled)
    except FileNotFoundError:
        raise HTTPException(404, f"No vault for case {case_id}")


# LLM providers list (global, not case-specific)
@router.get("/providers")
async def list_providers(case_id: str):
    from operation_room.services.llm_provider import list_providers
    return list_providers()

@router.get("/heuristics/ransomware_ancestry")
async def get_ransomware_ancestry(case_id: str):
    import duckdb
    from operation_room.config import settings
    vault_db = get_vault_path(case_id)
    
    if not vault_db.exists():
        raise HTTPException(404, "Vault not found")

    con = open_vault(case_id)
    try:
        # Proper recursive CTE for ransomware ancestry over crud_events
        query = """
        WITH RECURSIVE ancestry AS (
            -- Base case: Ransomware activity (DELETE or CREATE)
            SELECT 
                event_id,
                timestamp,
                user_name,
                operation_type,
                table_name as target,
                1 as depth,
                event_id as root_id
            FROM crud_events
            WHERE operation_type IN ('DELETE', 'CREATE')

            UNION ALL

            -- Recursive step: Find preceding events by the same user quickly
            SELECT 
                c.event_id,
                c.timestamp,
                c.user_name,
                c.operation_type,
                c.table_name as target,
                a.depth + 1,
                a.root_id
            FROM crud_events c
            JOIN ancestry a ON c.user_name = a.user_name 
            WHERE c.timestamp < a.timestamp
              AND c.timestamp >= a.timestamp - INTERVAL '5 minutes'
              AND a.depth < 5
        )
        SELECT 
            depth,
            operation_type,
            COUNT(*) as frequency
        FROM ancestry
        GROUP BY 1, 2
        ORDER BY depth, frequency DESC
        """
        df = con.execute(query).df()
        results = df.to_dict(orient="records")  # type: ignore

        return {
            "status": "success",
            "ancestry_tree": results
        }
    except Exception as e:
        import logging
        logging.error(f"Error in ancestry CTE: {e}")
        return {
            "status": "error",
            "message": str(e),
            "ancestry_tree": []
        }
    finally:
        con.close()
