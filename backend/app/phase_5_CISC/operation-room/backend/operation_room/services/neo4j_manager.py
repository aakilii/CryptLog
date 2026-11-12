"""
Neo4j Manager for GraphRAG Correlation Engine
Handles Neo4j connection, graph ingestion, shortest path calculations, and graceful fallback
"""

import logging
import os
import shlex
import shutil
import subprocess
import time
import json
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from datetime import datetime

try:
    from neo4j import GraphDatabase, Driver, Session, basic_auth
    from neo4j.exceptions import DriverError, ServiceUnavailable
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Manages Neo4j graph operations with graceful fallback support"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        timeout: float = 3.0
    ):
        """
        Initialize Neo4j manager
        
        Args:
            uri: Neo4j bolt URI (default: localhost:7687)
            username: Neo4j username
            password: Neo4j password
            timeout: Connection timeout in seconds
        """
        if not NEO4J_AVAILABLE:
            logger.warning("neo4j package not installed; Neo4j operations will be unavailable")
            self._driver = None
            self._available = False
            return

        self._uri = uri
        self._username = username
        self._password = password
        self._timeout = timeout
        self._driver: Optional[Driver] = None
        self._available = False
        self._last_error: Optional[str] = None
        self._last_start_attempts: List[Dict[str, Any]] = []

        # Attempt connection on initialization
        self._connect()

    def _parse_uri_host_port(self) -> Tuple[str, int]:
        raw = (self._uri or "").strip()
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        if "/" in raw:
            raw = raw.split("/", 1)[0]

        if ":" in raw:
            host, port_text = raw.rsplit(":", 1)
            try:
                return host or "localhost", int(port_text)
            except ValueError:
                return host or "localhost", 7687

        return raw or "localhost", 7687

    def _is_bolt_port_open(self) -> bool:
        host, port = self._parse_uri_host_port()
        try:
            with socket.create_connection((host, port), timeout=self._timeout):
                return True
        except OSError:
            return False

    def _connect(self) -> bool:
        """
        Attempt to connect to Neo4j
        
        Returns:
            True if connection successful, False otherwise
        """
        if not NEO4J_AVAILABLE:
            return False

        try:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=basic_auth(self._username, self._password),
                connection_timeout=self._timeout
            )
            # Test connection with a simple query
            with self._driver.session() as session:
                session.run("RETURN 1")
            self._available = True
            self._last_error = None
            logger.info(f"✓ Connected to Neo4j at {self._uri}")
            return True
        except (DriverError, ServiceUnavailable) as e:
            logger.warning(f"✗ Neo4j unavailable at {self._uri}: {e}")
            self._driver = None
            self._available = False
            self._last_error = str(e)
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error connecting to Neo4j: {e}")
            self._driver = None
            self._available = False
            self._last_error = str(e)
            return False

    def is_available(self) -> bool:
        """
        Check if Neo4j is available
        
        Returns:
            True if Neo4j connection is active, False otherwise
        """
        if not NEO4J_AVAILABLE:
            return False

        if not self._driver:
            return self._connect()

        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            self._available = True
            self._last_error = None
            return True
        except Exception:
            self._available = False
            self._last_error = "Neo4j session health-check failed"
            self._driver = None
            return False

    def get_diagnostics(self) -> Dict[str, Any]:
        host, port = self._parse_uri_host_port()
        docker = shutil.which("docker")
        neo4j_cli = shutil.which("neo4j")
        sc = shutil.which("sc") if os.name == "nt" else None

        commands = [" ".join(c) for c in self._build_start_commands()]
        return {
            "neo4j_python_driver_installed": NEO4J_AVAILABLE,
            "uri": self._uri,
            "host": host,
            "port": port,
            "bolt_port_open": self._is_bolt_port_open(),
            "driver_connected": bool(self._driver),
            "service_available": bool(self._available and self._driver),
            "docker_available": bool(docker),
            "neo4j_cli_available": bool(neo4j_cli),
            "windows_sc_available": bool(sc),
            "start_command_candidates": commands,
            "last_error": self._last_error,
            "last_start_attempts": self._last_start_attempts[-3:],
        }

    def _build_start_commands(self) -> list[list[str]]:
        """Build candidate commands for starting a local Neo4j instance."""
        override = os.getenv("OPROOM_NEO4J_START_COMMAND", "").strip()
        if override:
            return [shlex.split(override, posix=(os.name != "nt"))]

        commands: list[list[str]] = []

        docker = shutil.which("docker")
        if docker:
            container_name = os.getenv("OPROOM_NEO4J_CONTAINER_NAME", "neo4j")
            commands.append([docker, "start", container_name])

        neo4j_cli = shutil.which("neo4j")
        if neo4j_cli:
            commands.append([neo4j_cli, "start"])

        if os.name == "nt":
            neo4j_home = os.getenv("OPROOM_NEO4J_HOME", "").strip()
            if neo4j_home:
                neo4j_bat = Path(neo4j_home) / "bin" / "neo4j.bat"
                if neo4j_bat.exists():
                    commands.append([str(neo4j_bat), "start"])

            program_files = [
                os.getenv("ProgramFiles", ""),
                os.getenv("ProgramFiles(x86)", ""),
            ]
            for root in [p for p in program_files if p]:
                base = Path(root)
                for match in base.glob("Neo4j*"):
                    neo4j_bat = match / "bin" / "neo4j.bat"
                    if neo4j_bat.exists():
                        commands.append([str(neo4j_bat), "start"])

            sc = shutil.which("sc")
            if sc:
                service_name = os.getenv("OPROOM_NEO4J_SERVICE_NAME", "Neo4j")
                commands.append([sc, "start", service_name])

        dedup: list[list[str]] = []
        seen = set()
        for cmd in commands:
            key = tuple(cmd)
            if key not in seen:
                seen.add(key)
                dedup.append(cmd)
        return dedup

    def start_local_service(self, wait_seconds: float = 20.0) -> bool:
        """
        Try to start a local Neo4j instance using common commands.

        The method is intentionally best-effort: if the project is not
        configured with Docker, a Neo4j CLI, or a Windows service name, it
        simply returns False and the correlation pipeline can fall back to
        NetworkX.
        """
        if self.is_available():
            return True

        self._last_start_attempts = []
        for command in self._build_start_commands():
            try:
                logger.info(f"[Neo4jManager] Attempting to start Neo4j with: {' '.join(command)}")
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self._last_start_attempts.append({
                    "command": " ".join(command),
                    "returncode": int(result.returncode),
                    "stderr": (result.stderr or "")[-400:],
                    "stdout": (result.stdout or "")[-400:],
                })
                if result.returncode != 0:
                    output_text = (result.stderr or result.stdout or "").strip()
                    is_windows_service_missing = (
                        len(command) >= 3
                        and os.name == "nt"
                        and command[0].lower().endswith("sc")
                        and command[1].lower() == "start"
                        and result.returncode == 1060
                    )

                    if is_windows_service_missing:
                        logger.info(
                            "[Neo4jManager] Windows service not installed; skipping service start and using fallback engines."
                        )
                        continue

                    logger.warning(
                        f"[Neo4jManager] Start command exited with code {result.returncode}: "
                        f"{output_text}"
                    )
            except FileNotFoundError:
                self._last_start_attempts.append({
                    "command": " ".join(command),
                    "returncode": -1,
                    "stderr": "command not found",
                    "stdout": "",
                })
                continue
            except subprocess.TimeoutExpired:
                logger.warning(f"[Neo4jManager] Start command timed out: {' '.join(command)}")
                self._last_start_attempts.append({
                    "command": " ".join(command),
                    "returncode": -2,
                    "stderr": "timeout",
                    "stdout": "",
                })
            except Exception as e:
                logger.warning(f"[Neo4jManager] Neo4j start attempt failed: {e}")
                self._last_start_attempts.append({
                    "command": " ".join(command),
                    "returncode": -3,
                    "stderr": str(e),
                    "stdout": "",
                })

            if self._connect() or self.is_available():
                logger.info("[Neo4jManager] Neo4j became available after start attempt")
                return True

            deadline = time.time() + max(wait_seconds, 0.0)
            while time.time() < deadline:
                if self._connect() or self.is_available():
                    logger.info("[Neo4jManager] Neo4j became available after start attempt")
                    return True
                time.sleep(1.0)

        return self.is_available()

    def ensure_available(self, auto_start: bool = True, wait_seconds: float = 20.0) -> bool:
        """Ensure the driver is connected, optionally trying to start Neo4j."""
        if self.is_available():
            return True
        if not auto_start:
            return False
        return self.start_local_service(wait_seconds=wait_seconds)

    def clear_graph(self) -> bool:
        """
        Clear all nodes and relationships from Neo4j
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            with self._driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("✓ Neo4j graph cleared")
            return True
        except Exception as e:
            logger.error(f"✗ Error clearing Neo4j graph: {e}")
            return False

    def ingest_events(
        self,
        nodes: Dict[str, Dict[str, Any]],
        edges: List[Dict[str, Any]],
        run_id: str
    ) -> bool:
        """
        Ingest nodes and edges into Neo4j using UNWIND transactions
        
        Args:
            nodes: Dict of {node_id: node_attributes}
            edges: List of edge dicts with source_id, target_id, relationship, evidence_ids, etc.
            run_id: Correlation run ID for tracking
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            with self._driver.session() as session:
                # Ingest nodes using UNWIND
                node_list = [
                    {
                        "node_id": node_id,
                        "entity_type": attrs.get("entity_type"),
                        "entity_value": attrs.get("entity_value"),
                        "severity_score": attrs.get("severity_score", 0.0),
                        "anomaly_score": attrs.get("anomaly_score", 0.0),
                        "event_count": attrs.get("event_count", 1),
                        "metadata": json.dumps(attrs.get("metadata", {})),
                        "run_id": run_id
                    }
                    for node_id, attrs in nodes.items()
                ]

                session.run("""
                    UNWIND $nodes AS node
                    CREATE (n:Entity {
                        node_id: node.node_id,
                        entity_type: node.entity_type,
                        entity_value: node.entity_value,
                        severity_score: node.severity_score,
                        anomaly_score: node.anomaly_score,
                        event_count: node.event_count,
                        metadata: node.metadata,
                        run_id: node.run_id
                    })
                """, nodes=node_list, run_id=run_id)

                # Ingest edges using UNWIND
                edge_list = [
                    {
                        "source_id": edge.get("source_id"),
                        "target_id": edge.get("target_id"),
                        "relationship": edge.get("relationship", "RELATED_TO"),
                        "weight": edge.get("weight", 1.0),
                        "confidence_score": edge.get("confidence_score", 0.5),
                        "evidence_ids": edge.get("evidence_ids", []),
                        "run_id": run_id
                    }
                    for edge in edges
                ]

                session.run("""
                    UNWIND $edges AS edge
                    MATCH (source:Entity {node_id: edge.source_id, run_id: edge.run_id})
                    MATCH (target:Entity {node_id: edge.target_id, run_id: edge.run_id})
                    CREATE (source)-[r:RELATIONSHIP {
                        relationship: edge.relationship,
                        weight: edge.weight,
                        confidence_score: edge.confidence_score,
                        evidence_ids: edge.evidence_ids,
                        run_id: edge.run_id
                    }]->(target)
                """, edges=edge_list, run_id=run_id)

            logger.info(f"✓ Ingested {len(nodes)} nodes and {len(edges)} edges into Neo4j")
            return True
        except Exception as e:
            logger.error(f"✗ Error ingesting events into Neo4j: {e}")
            return False

    def calculate_shortest_path(
        self,
        source_node_id: str,
        target_node_id: str,
        run_id: str,
        max_hops: int = 6
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate shortest path between two nodes using Neo4j Cypher
        
        Args:
            source_node_id: Source entity node ID
            target_node_id: Target entity node ID
            run_id: Correlation run ID
            max_hops: Maximum number of hops to consider (default: 6)
        
        Returns:
            Dict with path info (nodes, edges, length) or None if not found
        """
        if not self.is_available():
            return None

        try:
            with self._driver.session() as session:
                result = session.run("""
                    MATCH (source:Entity {node_id: $source_id, run_id: $run_id})
                    MATCH (target:Entity {node_id: $target_id, run_id: $run_id})
                    MATCH p = shortestPath((source)-[*1..{max_hops}]-(target))
                    RETURN p, length(p) as path_length
                    LIMIT 1
                """.format(max_hops=max_hops),
                    source_id=source_node_id,
                    target_id=target_node_id,
                    run_id=run_id
                )

                records = list(result)
                if not records:
                    logger.info(f"✗ No path found between {source_node_id} and {target_node_id}")
                    return None

                record = records[0]
                path = record["p"]
                path_length = record["path_length"]

                # Extract nodes and relationships from path
                path_nodes = []
                path_edges = []

                for node in path.nodes:
                    path_nodes.append({
                        "node_id": node["node_id"],
                        "entity_type": node["entity_type"],
                        "entity_value": node["entity_value"],
                        "severity_score": node.get("severity_score", 0.0),
                        "anomaly_score": node.get("anomaly_score", 0.0)
                    })

                for relationship in path.relationships:
                    path_edges.append({
                        "source_id": relationship.start_node["node_id"],
                        "target_id": relationship.end_node["node_id"],
                        "relationship": relationship.type,
                        "weight": relationship.get("weight", 1.0),
                        "confidence_score": relationship.get("confidence_score", 0.5),
                        "evidence_ids": relationship.get("evidence_ids", [])
                    })

                result_dict = {
                    "nodes": path_nodes,
                    "edges": path_edges,
                    "path_length": path_length,
                    "source": source_node_id,
                    "target": target_node_id,
                    "engine_used": "neo4j"
                }

                logger.info(f"✓ Found path of length {path_length} between {source_node_id} and {target_node_id}")
                return result_dict

        except Exception as e:
            logger.error(f"✗ Error calculating shortest path in Neo4j: {e}")
            return None

    def get_subgraph_json(
        self,
        node_ids: List[str],
        run_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Export subgraph as JSON for frontend rendering
        
        Args:
            node_ids: List of node IDs to include in subgraph
            run_id: Correlation run ID
        
        Returns:
            Dict with nodes and edges for rendering, or None if error
        """
        if not self.is_available():
            return None

        try:
            with self._driver.session() as session:
                # Query nodes
                nodes_result = session.run("""
                    MATCH (n:Entity {run_id: $run_id})
                    WHERE n.node_id IN $node_ids
                    RETURN {
                        node_id: n.node_id,
                        entity_type: n.entity_type,
                        entity_value: n.entity_value,
                        severity_score: n.severity_score,
                        anomaly_score: n.anomaly_score
                    } as node
                """, node_ids=node_ids, run_id=run_id)

                nodes = [record["node"] for record in nodes_result]

                # Query edges between these nodes
                edges_result = session.run("""
                    MATCH (source:Entity {run_id: $run_id})-[r:RELATIONSHIP]-(target:Entity {run_id: $run_id})
                    WHERE source.node_id IN $node_ids AND target.node_id IN $node_ids
                    RETURN {
                        source_id: source.node_id,
                        target_id: target.node_id,
                        relationship: r.relationship,
                        weight: r.weight,
                        confidence_score: r.confidence_score,
                        evidence_ids: r.evidence_ids
                    } as edge
                """, node_ids=node_ids, run_id=run_id)

                edges = [record["edge"] for record in edges_result]

                return {
                    "nodes": nodes,
                    "edges": edges,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges)
                }

        except Exception as e:
            logger.error(f"✗ Error retrieving subgraph from Neo4j: {e}")
            return None

    def close(self) -> None:
        """Close Neo4j connection"""
        if self._driver:
            self._driver.close()
            logger.info("✓ Neo4j connection closed")
            self._available = False


# Singleton instance for module-level access
_neo4j_manager: Optional[Neo4jManager] = None


def get_neo4j_manager(
    uri: str = "bolt://localhost:7687",
    username: str = "neo4j",
    password: str = "password"
) -> Neo4jManager:
    """
    Get or create Neo4j manager singleton
    
    Args:
        uri: Neo4j connection URI
        username: Neo4j username
        password: Neo4j password
    
    Returns:
        Neo4jManager instance
    """
    global _neo4j_manager
    if _neo4j_manager is None:
        _neo4j_manager = Neo4jManager(uri=uri, username=username, password=password)
    return _neo4j_manager
