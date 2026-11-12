"""
Correlation & Root-Cause Analysis Agent — LangGraph Pipeline.

6-node pipeline:
  1. load_enriched_data   — JOIN timeline + anomaly scores + anchors
  2. extract_entities     — Parse actors, IPs, hosts, sessions, targets
  3. build_graph          — Apply join rules to create entity edges
  4. score_entities       — Aggregate severity per entity
  5. generate_narrative   — LLM root-cause story with MITRE ATT&CK
  6. store_and_audit      — Persist graph + narrative, hash, CoC
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, TypedDict
from collections import defaultdict

import numpy as np

from langgraph.graph import StateGraph, END

from operation_room.database import open_vault
from operation_room.utils.hashing import hash_records
from operation_room.services.audit_service import record_coc_event
from operation_room.services import neo4j_manager as neo4j_service
from operation_room.services import networkx_engine as networkx_service

logger = logging.getLogger(__name__)


def get_neo4j_manager(*args, **kwargs):
    """Wrapper to keep engine lookup patchable in tests and integrations."""
    return neo4j_service.get_neo4j_manager(*args, **kwargs)


def get_networkx_engine():
    """Wrapper to keep engine lookup patchable in tests and integrations."""
    return networkx_service.get_networkx_engine()


# ── Default join rules (seeded on first run) ─────────────────

DEFAULT_RULES = [
    {"rule_id": "rule-actor",  "name": "Same Actor",      "description": "Links events performed by the same user/actor",
     "join_field": "actor",     "window_seconds": 3600,    "enabled": True,  "priority": 10},
    {"rule_id": "rule-srcip",  "name": "Same Source IP",   "description": "Links events originating from the same IP address",
     "join_field": "source_ip", "window_seconds": 1800,    "enabled": True,  "priority": 9},
    {"rule_id": "rule-dstip",  "name": "Same Dest IP",     "description": "Links events targeting the same IP address",
     "join_field": "destination_ip", "window_seconds": 1800, "enabled": True, "priority": 8},
    {"rule_id": "rule-sess",   "name": "Same Session",     "description": "Links events sharing a session ID",
     "join_field": "session_id", "window_seconds": 7200,   "enabled": True,  "priority": 10},
    {"rule_id": "rule-target", "name": "Same Target",      "description": "Links events accessing the same resource/target",
     "join_field": "target",    "window_seconds": 600,     "enabled": True,  "priority": 7},
    {"rule_id": "rule-host",   "name": "Same Host",        "description": "Links events on the same source system/host",
     "join_field": "source_system", "window_seconds": 3600, "enabled": True, "priority": 6},
]


# ── MITRE ATT&CK Mapping ────────────────────────────────────

MITRE_MAP = {
    "LOGIN_SUCCESS": "TA0001:Initial Access",   "LOGIN_FAILED": "TA0006:Credential Access",
    "MFA_CHALLENGE": "TA0006:Credential Access", "PASSWORD_CHANGE": "TA0003:Persistence",
    "ACCOUNT_LOCKED": "TA0006:Credential Access",
    "VPN_CONNECT": "TA0001:Initial Access",      "VPN_FAILED": "TA0001:Initial Access",
    "ALLOW": "TA0011:Command and Control",        "DENY": "TA0011:Command and Control",
    "DROP": "TA0005:Defense Evasion",
    "SELECT": "TA0009:Collection",  "EXPORT": "TA0010:Exfiltration",
    "DELETE": "TA0040:Impact",      "CREATE_TABLE": "TA0003:Persistence",
    "HTTP_POST": "TA0011:Command and Control", "ERROR_500": "TA0040:Impact",
    "MALWARE_DETECTED": "TA0002:Execution",   "QUARANTINE": "TA0005:Defense Evasion",
    "PROCESS_BLOCKED": "TA0002:Execution",
    "FILE_READ": "TA0009:Collection", "FILE_WRITE": "TA0003:Persistence",
    "FILE_DELETE": "TA0040:Impact",   "FILE_COPY": "TA0010:Exfiltration",
}


# ═══════════════════════════════════════════════════════════════
# State Schema
# ═══════════════════════════════════════════════════════════════

class CorrelationState(TypedDict, total=False):
    case_id: str
    run_id: str
    llm_provider: str       # "ollama" or "gemini"
    window_seconds: int
    severity_weights: dict  # {"anomaly": 0.4, "privilege": 0.3, "frequency": 0.3}

    enriched_events: list[dict]
    join_rules: list[dict]
    nodes: list[dict]
    edges: list[dict]
    mitre_tactics: list[str]
    narrative: str
    critical_path: list[str]
    recommendations: list[str]
    hash_value: str
    coc_event_id: str
    status: str
    error: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_detail(detail):
    """Safely parse detail JSON."""
    if not detail:
        return {}
    if isinstance(detail, dict):
        return detail
    try:
        return json.loads(detail)
    except (json.JSONDecodeError, TypeError):
        return {}


# ═══════════════════════════════════════════════════════════════
# Node 1: Load Enriched Data
# ═══════════════════════════════════════════════════════════════

def load_enriched_data(state: CorrelationState) -> dict:
    """Join timeline + anomaly scores + anchors into enriched events."""
    case_id = state.get("case_id", "")
    run_id = state.get("run_id", str(uuid.uuid4()))
    conn = open_vault(case_id)
    try:
        # Join timeline with latest anomaly scores
        rows = conn.execute("""
            SELECT t.tl_event_id, t.normalised_ts, t.source_type, t.source_system,
                   t.actor, t.action, t.target, t.severity, t.detail,
                   t.is_anchor, t.anchor_label,
                   COALESCE(s.anomaly_score, 0) as anomaly_score,
                   COALESCE(s.is_anomaly, FALSE) as is_anomaly
            FROM unified_timeline t
            LEFT JOIN (
                SELECT tl_event_id, anomaly_score, is_anomaly
                FROM anomaly_scores
                WHERE run_id = (SELECT run_id FROM anomaly_runs WHERE case_id = ? AND status = 'COMPLETED' ORDER BY completed_at DESC LIMIT 1)
            ) s ON t.tl_event_id = s.tl_event_id
            WHERE t.case_id = ?
            ORDER BY t.normalised_ts ASC
        """, [case_id, case_id]).fetchall()

        cols = ["tl_event_id", "normalised_ts", "source_type", "source_system",
                "actor", "action", "target", "severity", "detail",
                "is_anchor", "anchor_label", "anomaly_score", "is_anomaly"]
        events = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("normalised_ts") and not isinstance(d["normalised_ts"], str):
                d["normalised_ts"] = str(d["normalised_ts"])
            d["detail_parsed"] = _parse_detail(d.get("detail"))
            events.append(d)

        # Load join rules (seed defaults if empty)
        rules_res = conn.execute("SELECT COUNT(*) FROM correlation_rules").fetchone()
        rules_exist = rules_res[0] if rules_res else 0
        if rules_exist == 0:
            for r in DEFAULT_RULES:
                conn.execute("""
                    INSERT INTO correlation_rules (rule_id, name, description, join_field, window_seconds, enabled, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [r["rule_id"], r["name"], r["description"], r["join_field"], r["window_seconds"], r["enabled"], r["priority"]])

        rules = []
        for row in conn.execute("SELECT rule_id, name, description, join_field, window_seconds, enabled, priority FROM correlation_rules WHERE enabled = TRUE ORDER BY priority DESC").fetchall():
            rules.append(dict(zip(["rule_id", "name", "description", "join_field", "window_seconds", "enabled", "priority"], row)))

        # Record run start
        conn.execute("""
            INSERT INTO correlation_runs (run_id, case_id, params_json, llm_provider, status, started_at)
            VALUES (?, ?, ?, ?, 'RUNNING', ?)
        """, [run_id, case_id, json.dumps({"severity_weights": state.get("severity_weights", {})}),
              state.get("llm_provider", "ollama"), _now_iso()])

        logger.info(f"[CorrelationAgent] Loaded {len(events)} enriched events, {len(rules)} join rules")
        return {"enriched_events": events, "join_rules": rules, "run_id": run_id, "status": "data_loaded"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Node 2: Extract Entities
# ═══════════════════════════════════════════════════════════════

def extract_entities(state: CorrelationState) -> dict:
    """Parse events into entity nodes: USER, IP, HOST, SESSION, DATA_OBJECT."""
    events = state.get("enriched_events", [])
    nodes_map = {}  # key: (entity_type, entity_value) → node dict

    def _add_node(etype, evalue, event):
        key = (etype, evalue)
        ts_str = event.get("normalised_ts", "")
        anom = float(event.get("anomaly_score", 0))
        if key not in nodes_map:
            nodes_map[key] = {
                "node_id": str(uuid.uuid4()),
                "entity_type": etype, "entity_value": evalue,
                "event_count": 0, "anomaly_scores": [],
                "first_seen": ts_str, "last_seen": ts_str,
                "actions": set(), "sources": set(), "severities": [],
            }
        n = nodes_map[key]
        n["event_count"] += 1
        n["anomaly_scores"].append(anom)
        n["last_seen"] = ts_str
        n["actions"].add(event.get("action", ""))
        n["sources"].add(event.get("source_type", ""))
        sev_map = {"HIGH": 3, "MEDIUM": 2, "INFO": 1}
        n["severities"].append(sev_map.get(event.get("severity", "INFO"), 1))

    for ev in events:
        # Actor → USER node
        actor = ev.get("actor")
        if actor:
            _add_node("USER", actor, ev)

        # Source system → HOST node
        system = ev.get("source_system")
        if system:
            _add_node("HOST", system, ev)

        # Target → DATA_OBJECT node
        target = ev.get("target")
        if target:
            _add_node("DATA_OBJECT", target, ev)

        detail = ev.get("detail_parsed", {})

        # Source IP → IP node
        src_ip = detail.get("source_ip")
        if src_ip:
            _add_node("IP", src_ip, ev)

        # Dest IP → IP node
        dst_ip = detail.get("destination_ip")
        if dst_ip:
            _add_node("IP", dst_ip, ev)

        # Session → SESSION node
        sess = detail.get("session_id")
        if sess:
            _add_node("SESSION", sess, ev)

    # Convert sets to lists for JSON compatibility
    nodes = []
    for key, n in nodes_map.items():
        n["actions"] = list(n["actions"])
        n["sources"] = list(n["sources"])
        nodes.append(n)

    logger.info(f"[CorrelationAgent] Extracted {len(nodes)} entities")
    return {"nodes": nodes, "status": "entities_extracted"}


# ═══════════════════════════════════════════════════════════════
# Node 3: Build Graph
# ═══════════════════════════════════════════════════════════════

def build_graph(state: CorrelationState) -> dict:
    """Apply join rules to create edges between entity nodes."""
    events = state.get("enriched_events", [])
    nodes = state.get("nodes", [])
    rules = state.get("join_rules", [])

    # Build lookup: entity_value → node
    node_lookup = {}
    for n in nodes:
        node_lookup[(n["entity_type"], n["entity_value"])] = n

    # Relationship type mapping
    REL_MAP = {
        "actor": ("USER", None, "PERFORMED"),
        "source_ip": ("IP", None, "AUTHENTICATED_FROM"),
        "destination_ip": (None, "IP", "CONNECTED_TO"),
        "session_id": ("SESSION", None, "USED_SESSION"),
        "target": (None, "DATA_OBJECT", "ACCESSED"),
        "source_system": ("HOST", None, "EXECUTED_ON"),
    }

    edges_map = {}  # (src_node_id, tgt_node_id, rel) → edge dict

    for ev in events:
        detail = ev.get("detail_parsed", {})
        actor = ev.get("actor")
        actor_node = node_lookup.get(("USER", actor))
        if not actor_node:
            continue

        # For each join rule, create edges
        for rule in rules:
            field = rule["join_field"]
            rel_info = REL_MAP.get(field)
            if not rel_info:
                continue

            src_type, tgt_type, relationship = rel_info

            # Get field value from event or detail
            if field in ("source_ip", "destination_ip", "session_id"):
                value = detail.get(field)
            elif field == "actor":
                value = ev.get("actor")
            elif field == "target":
                value = ev.get("target")
            elif field == "source_system":
                value = ev.get("source_system")
            else:
                continue

            if not value:
                continue

            # Determine source and target nodes
            if src_type and tgt_type:
                src_node = node_lookup.get((src_type, actor))
                tgt_node = node_lookup.get((tgt_type, value))
            elif src_type:
                src_node = node_lookup.get((src_type, value))
                tgt_node = actor_node
            else:
                src_node = actor_node
                tgt_node = node_lookup.get((tgt_type, value))

            if not src_node or not tgt_node or src_node["node_id"] == tgt_node["node_id"]:
                continue

            edge_key = (src_node["node_id"], tgt_node["node_id"], relationship)
            
            is_heuristic = rule.get("window_seconds", 0) > 0 or "proximity" in rule.get("name", "").lower()
            edge_confidence = 0.4 if is_heuristic else 1.0
            edge_reason = "Heuristic Temporal Proximity" if is_heuristic else "Deterministic Token Match"

            if edge_key not in edges_map:
                edges_map[edge_key] = {
                    "edge_id": str(uuid.uuid4()),
                    "source_node_id": src_node["node_id"],
                    "target_node_id": tgt_node["node_id"],
                    "source_label": src_node["entity_value"],
                    "target_label": tgt_node["entity_value"],
                    "relationship": relationship,
                    "weight": 0, "evidence_count": 0,
                    "evidence_ids": [],
                    "first_seen": ev.get("normalised_ts"),
                    "last_seen": ev.get("normalised_ts"),
                    "confidence_score": edge_confidence,
                    "join_reason": edge_reason,
                }
            e = edges_map[edge_key]
            e["weight"] += 1
            e["evidence_count"] += 1
            e["evidence_ids"].append(ev.get("tl_event_id"))
            e["last_seen"] = ev.get("normalised_ts")

    edges = list(edges_map.values())
    logger.info(f"[CorrelationAgent] Built graph: {len(nodes)} nodes, {len(edges)} edges")
    return {"edges": edges, "status": "graph_built"}


# ═══════════════════════════════════════════════════════════════
# Node 4: Score Entities
# ═══════════════════════════════════════════════════════════════

def score_entities(state: CorrelationState) -> dict:
    """Compute severity scores per entity node."""
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])
    weights = state.get("severity_weights", {"anomaly": 0.4, "privilege": 0.3, "frequency": 0.3})

    # Compute edge count per node
    edge_counts = defaultdict(int)
    for e in edges:
        edge_counts[e["source_node_id"]] += e["evidence_count"]
        edge_counts[e["target_node_id"]] += e["evidence_count"]

    max_edges = max(edge_counts.values()) if edge_counts else 1
    max_events = max((n["event_count"] for n in nodes), default=1)

    # Privilege scoring: certain actions indicate elevated privilege
    PRIV_ACTIONS = {"DELETE", "EXPORT", "CREATE_TABLE", "PASSWORD_CHANGE", "ACCOUNT_LOCKED",
                    "MALWARE_DETECTED", "PROCESS_BLOCKED", "FILE_DELETE", "FILE_COPY"}

    mitre_tactics = set()

    for n in nodes:
        # Anomaly component: mean anomaly score
        anom_scores = n.get("anomaly_scores", [])
        anom_component = np.mean(anom_scores) if anom_scores else 0

        # Privilege component: fraction of privileged actions
        actions = set(n.get("actions", []))
        priv_overlap = actions & PRIV_ACTIONS
        priv_component = len(priv_overlap) / max(len(actions), 1)

        # Frequency/connectivity component
        freq_component = edge_counts.get(n["node_id"], 0) / max_edges

        # Weighted severity
        severity = (
            weights.get("anomaly", 0.4) * anom_component +
            weights.get("privilege", 0.3) * priv_component +
            weights.get("frequency", 0.3) * freq_component
        )
        n["severity_score"] = round(float(severity), 4)
        n["anomaly_score"] = round(float(anom_component), 4)

        # Collect MITRE tactics
        for action in n.get("actions", []):
            tactic = MITRE_MAP.get(action)
            if tactic:
                mitre_tactics.add(tactic)

    # Sort nodes by severity (descending)
    nodes.sort(key=lambda n: n["severity_score"], reverse=True)

    # Critical path: top 5 severity nodes
    critical_path = [n["node_id"] for n in nodes[:5]]

    logger.info(f"[CorrelationAgent] Scored {len(nodes)} entities, {len(mitre_tactics)} MITRE tactics")
    return {
        "nodes": nodes, "mitre_tactics": sorted(mitre_tactics),
        "critical_path": critical_path, "status": "scored",
    }


# ═══════════════════════════════════════════════════════════════
# Node 5: Generate Narrative (LLM)
# ═══════════════════════════════════════════════════════════════

def generate_narrative(state: CorrelationState) -> dict:
    """Call LLM to produce root-cause narrative with MITRE ATT&CK mapping."""
    import asyncio

    shortest_path_json = state.get("shortest_path_json", {})

    nodes_raw = state.get("nodes", [])
    if isinstance(nodes_raw, dict):
        nodes = []
        for node_id, payload in nodes_raw.items():
            if isinstance(payload, dict):
                merged = {"node_id": node_id}
                merged.update(payload)
                nodes.append(merged)
            else:
                nodes.append({"node_id": node_id, "entity_value": str(payload)})
    else:
        nodes = nodes_raw or []

    edges = state.get("edges", [])
    if not edges and isinstance(shortest_path_json, dict):
        edges = shortest_path_json.get("edges", []) or []

    if not nodes and isinstance(shortest_path_json, dict):
        nodes = shortest_path_json.get("nodes", []) or []

    tactics = state.get("mitre_tactics", [])
    events = state.get("enriched_events", [])

    # Build context for LLM
    top_entities = nodes[:10]
    entity_summary = "\n".join([
        (
            f"- [{n.get('entity_type', 'UNKNOWN')}] "
            f"{n.get('entity_value') or n.get('node_id', '?')}: "
            f"severity={float(n.get('severity_score', 0) or 0):.3f}, "
            f"events={int(n.get('event_count', 0) or 0)}, "
            f"actions={', '.join(n.get('actions', [])[:5])}"
        )
        for n in top_entities
    ])

    top_connections = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)[:10]
    edge_summary = "\n".join([
        (
            f"- {e.get('source_label') or e.get('source_id') or e.get('source_node_id') or '?'} "
            f"--[{e.get('relationship', 'RELATED_TO')}]--> "
            f"{e.get('target_label') or e.get('target_id') or e.get('target_node_id') or '?'} "
            f"(weight={e.get('weight', 0)})"
        )
        for e in top_connections
    ])

    anomalous_events = [ev for ev in events if ev.get("is_anomaly")][:10]
    event_lines = "\n".join([
        f"- [{ev.get('severity')}] {ev.get('normalised_ts','?')[:19]} | {ev.get('actor')} | {ev.get('action')} → {ev.get('target')} (anomaly={ev.get('anomaly_score', 0):.3f})"
        for ev in anomalous_events
    ])

    SYSTEM_MSG = """You are a senior digital forensics analyst. Analyse the correlation data and produce a structured root-cause analysis narrative.

Your narrative MUST include:
1. **Executive Summary** (2-3 sentences)
2. **Attack Timeline** — chronological sequence of key events
3. **MITRE ATT&CK Mapping** — map each phase to a tactic/technique
4. **Critical Entities** — who/what is most involved and why
5. **Root Cause** — the likely entry vector and attack chain
6. **Recommendations** — immediate containment and remediation steps

Be specific, reference actual entity names and timestamps. Use markdown formatting."""

    PROMPT = f"""## Correlation Analysis Data

### Top 10 Entities by Severity
{entity_summary}

### Top 10 Connections
{edge_summary}

### Anomalous Events
{event_lines}

### MITRE ATT&CK Tactics Detected
{', '.join(tactics) if tactics else 'None detected'}

### Graph Statistics
- Total entities: {len(nodes)}
- Total connections: {len(edges)}
- Total events analysed: {len(events)}
- Anomalous events: {len(anomalous_events)}

Please produce the root-cause analysis narrative."""

    # Call LLM
    try:
        from operation_room.services.llm_provider import get_llm
        llm = get_llm(state.get("llm_provider", "ollama"))
        invoke_fn = getattr(llm, "invoke", None)

        if callable(invoke_fn):
            invoked = invoke_fn(f"{SYSTEM_MSG}\n\n{PROMPT}")
            if isinstance(invoked, dict):
                narrative = str(invoked.get("content", ""))
            else:
                narrative = str(invoked)
        else:
            narrative = asyncio.get_event_loop().run_until_complete(
                llm.generate(PROMPT, system=SYSTEM_MSG, temperature=0.3, max_tokens=3000)
            )
    except RuntimeError:
        # No running event loop — create one
        try:
            from operation_room.services.llm_provider import get_llm
            llm = get_llm(state.get("llm_provider", "ollama"))
            invoke_fn = getattr(llm, "invoke", None)

            if callable(invoke_fn):
                invoked = invoke_fn(f"{SYSTEM_MSG}\n\n{PROMPT}")
                if isinstance(invoked, dict):
                    narrative = str(invoked.get("content", ""))
                else:
                    narrative = str(invoked)
            else:
                loop = asyncio.new_event_loop()
                narrative = loop.run_until_complete(
                    llm.generate(PROMPT, system=SYSTEM_MSG, temperature=0.3, max_tokens=3000)
                )
                loop.close()
        except Exception as e:
            logger.error(f"[CorrelationAgent] LLM narrative failed: {e}")
            narrative = _fallback_narrative(nodes, edges, tactics, anomalous_events)

    if not narrative or "[LLM Error]" in narrative:
        narrative = _fallback_narrative(nodes, edges, tactics, anomalous_events)

    # Extract recommendations from narrative or generate defaults
    recommendations = _extract_recommendations(nodes, tactics)

    logger.info(f"[CorrelationAgent] Narrative generated ({len(narrative)} chars)")
    return {
        "narrative": narrative, "recommendations": recommendations,
        "status": "narrative_generated",
    }


def _fallback_narrative(nodes, edges, tactics, anomalous_events):
    """Generate a structured narrative without LLM."""
    top_users = [n for n in nodes[:5] if n["entity_type"] == "USER"]
    top_hosts = [n for n in nodes[:10] if n["entity_type"] == "HOST"]

    lines = ["## Root-Cause Analysis Report\n"]
    lines.append("### Executive Summary")
    lines.append(f"Analysis of {len(nodes)} entities and {len(edges)} connections identified "
                 f"{len(anomalous_events)} anomalous events across multiple log sources.\n")

    if top_users:
        lines.append("### Critical Entities (Users)")
        for u in top_users:
            lines.append(f"- **{u['entity_value']}**: severity={u['severity_score']}, "
                         f"events={u['event_count']}, actions={', '.join(u.get('actions', [])[:3])}")

    if tactics:
        lines.append("\n### MITRE ATT&CK Tactics")
        for t in tactics:
            lines.append(f"- {t}")

    if anomalous_events:
        lines.append("\n### Key Anomalous Events")
        for ev in anomalous_events[:5]:
            lines.append(f"- [{ev.get('severity')}] {ev.get('normalised_ts', '?')[:19]} — "
                         f"{ev.get('actor')} → {ev.get('action')} on {ev.get('target')}")

    lines.append("\n### Recommendations")
    lines.append("- Review credentials of flagged users")
    lines.append("- Investigate anomalous data access patterns")
    lines.append("- Check affected hosts for persistence mechanisms")

    return "\n".join(lines)


def _extract_recommendations(nodes, tactics):
    """Generate recommendations based on entities and tactics."""
    recs = []
    users = [n for n in nodes[:5] if n["entity_type"] == "USER"]
    if users:
        recs.append(f"Reset credentials for flagged users: {', '.join(u['entity_value'] for u in users)}")
    if any("TA0010" in t for t in tactics):
        recs.append("Investigate potential data exfiltration — check outbound data transfers")
    if any("TA0003" in t for t in tactics):
        recs.append("Search for persistence mechanisms — review scheduled tasks, registry keys, cron jobs")
    if any("TA0002" in t for t in tactics):
        recs.append("Scan affected hosts for malware and unauthorized processes")
    recs.append("Preserve all logs and forensic artefacts for chain-of-custody")
    recs.append("Brief incident response team and escalate per policy")
    return recs


# ═══════════════════════════════════════════════════════════════
# Node 6: Store & Audit
# ═══════════════════════════════════════════════════════════════

def store_and_audit(state: CorrelationState) -> dict:
    """Persist graph to DuckDB and record chain-of-custody."""
    case_id = state.get("case_id", "")
    run_id = state.get("run_id", "")
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])

    conn = open_vault(case_id)
    try:
        with conn.transaction():
            # Clean previous run data
            conn.execute("DELETE FROM correlation_nodes WHERE run_id = ?", [run_id])
            conn.execute("DELETE FROM correlation_edges WHERE run_id = ?", [run_id])
            conn.execute("DELETE FROM rca_narratives WHERE run_id = ?", [run_id])

            now = _now_iso()

            # Store nodes
            for n in nodes:
                conn.execute("""
                    INSERT INTO correlation_nodes
                        (node_id, run_id, case_id, entity_type, entity_value,
                         severity_score, anomaly_score, event_count, first_seen, last_seen, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    n["node_id"], run_id, case_id, n["entity_type"], n["entity_value"],
                    n["severity_score"], n.get("anomaly_score", 0), n["event_count"],
                    n.get("first_seen"), n.get("last_seen"),
                    json.dumps({"actions": n.get("actions", []), "sources": n.get("sources", [])}),
                ])

            # clean edge schema safely
            try:
                conn.execute("ALTER TABLE correlation_edges ADD COLUMN confidence_score DOUBLE DEFAULT 1.0")
                conn.execute("ALTER TABLE correlation_edges ADD COLUMN join_reason VARCHAR")
            except Exception:
                pass # existing or failed, ignore

            # Store edges
            for e in edges:
                conn.execute("""
                    INSERT INTO correlation_edges
                        (edge_id, run_id, case_id, source_node_id, target_node_id,
                         relationship, weight, evidence_count, evidence_ids, first_seen, last_seen, confidence_score, join_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    e["edge_id"], run_id, case_id, e["source_node_id"], e["target_node_id"],
                    e["relationship"], e["weight"], e["evidence_count"],
                    json.dumps(e.get("evidence_ids", [])[:50]),  # cap at 50 IDs
                    e.get("first_seen"), e.get("last_seen"),
                    e.get("confidence_score", 1.0), e.get("join_reason", "")
                ])

            # Store narrative
            narrative_id = str(uuid.uuid4())
            narrative_hash = hash_records([{"narrative": state.get("narrative", ""), "run_id": run_id}])
            conn.execute("""
                INSERT INTO rca_narratives
                    (narrative_id, run_id, case_id, narrative_text, mitre_tactics,
                     critical_path, recommendations, llm_provider, hash_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                narrative_id, run_id, case_id, state.get("narrative", ""),
                json.dumps(state.get("mitre_tactics", [])),
                json.dumps(state.get("critical_path", [])),
                json.dumps(state.get("recommendations", [])),
                state.get("llm_provider", "ollama"),
                narrative_hash, now,
            ])

            # Hash the full graph for CoC
            graph_records = [{"node_id": n["node_id"], "severity": n["severity_score"]} for n in nodes]
            graph_hash = hash_records(graph_records)

            # Update run
            conn.execute("""
                UPDATE correlation_runs
                SET status = 'COMPLETED', total_nodes = ?, total_edges = ?,
                    hash_value = ?, completed_at = ?
                WHERE run_id = ?
            """, [len(nodes), len(edges), graph_hash, now, run_id])

        # Chain of custody
        coc_id = record_coc_event(
            case_id=case_id, actor="correlation_agent",
            action="CORRELATION_COMPLETED",
            target_artefact=f"correlation_run:{run_id}",
            justification="Built entity graph and root-cause narrative",
            hash_after=graph_hash,
            details={
                "run_id": run_id, "nodes": len(nodes), "edges": len(edges),
                "mitre_tactics": len(state.get("mitre_tactics", [])),
                "llm_provider": state.get("llm_provider", "ollama"),
            },
        )

        logger.info(f"[CorrelationAgent] Stored: {len(nodes)} nodes, {len(edges)} edges, narrative, CoC={coc_id}")
        return {"hash_value": graph_hash, "coc_event_id": coc_id, "status": "completed"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Build LangGraph
# ═══════════════════════════════════════════════════════════════

def build_correlation_graph():
    graph = StateGraph(CorrelationState)
    graph.add_node("load_enriched_data", load_enriched_data)
    graph.add_node("extract_entities", extract_entities)
    graph.add_node("build_graph", build_graph)
    graph.add_node("score_entities", score_entities)
    graph.add_node("generate_narrative", generate_narrative)
    graph.add_node("store_and_audit", store_and_audit)

    graph.set_entry_point("load_enriched_data")
    graph.add_edge("load_enriched_data", "extract_entities")
    graph.add_edge("extract_entities", "build_graph")
    graph.add_edge("build_graph", "score_entities")
    graph.add_edge("score_entities", "generate_narrative")
    graph.add_edge("generate_narrative", "store_and_audit")
    graph.add_edge("store_and_audit", END)

    return graph.compile()


_compiled = None

def get_correlation_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_correlation_graph()
    return _compiled


# ═══════════════════════════════════════════════════════════════
# Backward-Compatible GraphRAG Helpers
# ═══════════════════════════════════════════════════════════════

def _normalize_edges_for_networkx(edges: list[dict]) -> list[dict]:
    """Normalize edge payloads to NetworkXEngine's expected shape."""
    normalized = []
    for edge in edges or []:
        source_id = edge.get("source_id") or edge.get("source_node_id") or edge.get("source")
        target_id = edge.get("target_id") or edge.get("target_node_id") or edge.get("target")
        if not source_id or not target_id:
            continue

        normalized.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "relationship": edge.get("relationship", "RELATED_TO"),
                "weight": float(edge.get("weight", 1.0) or 1.0),
                "confidence_score": float(edge.get("confidence_score", 1.0) or 1.0),
                "evidence_ids": edge.get("evidence_ids", []) or [],
            }
        )
    return normalized


def _build_graph_structure(events: list[dict], nodes: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """
    Build graph dictionaries from enriched events and node list.

    This helper keeps legacy test contracts intact for GraphRAG phases.
    """
    nodes_dict: dict[str, dict] = {
        n["node_id"]: dict(n)
        for n in (nodes or [])
        if isinstance(n, dict) and n.get("node_id")
    }

    entity_index: dict[tuple[str, str], str] = {}
    for node_id, node in nodes_dict.items():
        etype = node.get("entity_type")
        evalue = node.get("entity_value")
        if etype and evalue:
            entity_index[(str(etype), str(evalue))] = node_id

    edge_map: dict[tuple[str, str, str], dict] = {}

    def _add_edge(source_id: str | None, target_id: str | None, relationship: str, evidence_id: str | None) -> None:
        if not source_id or not target_id or source_id == target_id:
            return

        key = (source_id, target_id, relationship)
        if key not in edge_map:
            edge_map[key] = {
                "edge_id": str(uuid.uuid4()),
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship": relationship,
                "weight": 0.0,
                "confidence_score": 1.0,
                "evidence_ids": [],
            }

        edge = edge_map[key]
        edge["weight"] += 1.0
        if evidence_id and evidence_id not in edge["evidence_ids"]:
            edge["evidence_ids"].append(evidence_id)

    for event in events or []:
        detail = event.get("detail_parsed") or _parse_detail(event.get("detail"))
        evidence_id = event.get("tl_event_id")

        actor_id = entity_index.get(("USER", str(event.get("actor")))) if event.get("actor") else None
        host_id = entity_index.get(("HOST", str(event.get("source_system")))) if event.get("source_system") else None
        target_id = entity_index.get(("DATA_OBJECT", str(event.get("target")))) if event.get("target") else None
        source_ip_id = entity_index.get(("IP", str(detail.get("source_ip")))) if detail.get("source_ip") else None
        destination_ip_id = (
            entity_index.get(("IP", str(detail.get("destination_ip")))) if detail.get("destination_ip") else None
        )
        session_id = entity_index.get(("SESSION", str(detail.get("session_id")))) if detail.get("session_id") else None

        _add_edge(actor_id, host_id, "EXECUTED_ON", evidence_id)
        _add_edge(actor_id, target_id, "ACCESSED", evidence_id)
        _add_edge(host_id, target_id, "HOSTED", evidence_id)
        _add_edge(source_ip_id, actor_id, "AUTHENTICATED_FROM", evidence_id)
        _add_edge(actor_id, destination_ip_id, "CONNECTED_TO", evidence_id)
        _add_edge(actor_id, session_id, "USED_SESSION", evidence_id)

    return nodes_dict, list(edge_map.values())


def _ingest_parallel_engines(nodes_dict: dict[str, dict], edges: list[dict], run_id: str) -> dict:
    """Ingest graph data into Neo4j and NetworkX with graceful fallback."""
    normalized_edges = _normalize_edges_for_networkx(edges)

    neo4j_ingested = False
    networkx_ingested = False
    errors: dict[str, str] = {}

    try:
        neo4j = get_neo4j_manager()
        if neo4j and neo4j.is_available():
            neo4j_ingested = bool(neo4j.ingest_events(nodes_dict, normalized_edges, run_id))
    except Exception as exc:
        errors["neo4j"] = str(exc)
        logger.warning(f"[CorrelationAgent] Neo4j ingestion failed: {exc}")

    try:
        networkx = get_networkx_engine()
        networkx_ingested = bool(networkx.build_graph(nodes_dict, normalized_edges))
    except Exception as exc:
        errors["networkx"] = str(exc)
        logger.warning(f"[CorrelationAgent] NetworkX ingestion failed: {exc}")

    engine_used = "neo4j" if neo4j_ingested else "networkx" if networkx_ingested else "none"

    return {
        "run_id": run_id,
        "engine_used": engine_used,
        "neo4j_ingested": neo4j_ingested,
        "networkx_ingested": networkx_ingested,
        "node_count": len(nodes_dict),
        "edge_count": len(normalized_edges),
        "errors": errors,
    }


def _extract_shortest_path_subgraph(
    nodes_dict: dict[str, dict],
    edges: list[dict],
    run_id: str,
    max_hops: int = 6,
) -> dict | None:
    """Extract a shortest-path subgraph using Neo4j first, then NetworkX fallback."""
    if not nodes_dict:
        return None

    sorted_nodes = sorted(
        nodes_dict.values(),
        key=lambda n: float(n.get("severity_score", 0.0) or 0.0),
        reverse=True,
    )
    if len(sorted_nodes) < 2:
        return None

    source_id = str(sorted_nodes[0].get("node_id")) if sorted_nodes[0].get("node_id") else None
    candidate_targets = [str(n["node_id"]) for n in sorted_nodes[1:] if n.get("node_id")]

    if not source_id or not candidate_targets:
        return None

    # Neo4j primary path extraction.
    try:
        neo4j = get_neo4j_manager()
        if neo4j and neo4j.is_available():
            for target_id in reversed(candidate_targets):
                if target_id == source_id:
                    continue
                path = neo4j.calculate_shortest_path(source_id, target_id, run_id, max_hops=max_hops)
                if path:
                    return path
    except Exception as exc:
        logger.warning(f"[CorrelationAgent] Neo4j shortest-path extraction failed: {exc}")

    # NetworkX fallback path extraction.
    try:
        networkx = get_networkx_engine()
        if not networkx.is_available():
            networkx.build_graph(nodes_dict, _normalize_edges_for_networkx(edges))

        for target_id in reversed(candidate_targets):
            if target_id == source_id:
                continue
            path = networkx.calculate_shortest_path(source_id, target_id, max_hops=max_hops)
            if path:
                return path
    except Exception as exc:
        logger.warning(f"[CorrelationAgent] NetworkX shortest-path extraction failed: {exc}")

    return None


def _build_graphrag_context(shortest_path_json: dict | None) -> str:
    """Build strict GraphRAG context for narrative generation with anti-hallucination guardrails."""
    if shortest_path_json is None:
        return ""

    path_payload = shortest_path_json if isinstance(shortest_path_json, dict) else {}
    nodes = path_payload.get("nodes", []) or []
    edges = path_payload.get("edges", []) or []

    path_length = path_payload.get("path_length")
    if path_length is None:
        path_length = max(len(nodes) - 1, 0)

    source = path_payload.get("source")
    target = path_payload.get("target")
    if not source and nodes:
        source = nodes[0].get("node_id", "?")
    if not target and nodes:
        target = nodes[-1].get("node_id", "?")

    lines = ["## CRITICAL PATH ANALYSIS", ""]
    lines.append(f"Path Length: {path_length}")
    lines.append(f"Source: {source or '?'}")
    lines.append(f"Target: {target or '?'}")
    lines.append("")

    lines.append("### Entities on Critical Path")
    for idx, node in enumerate(nodes, 1):
        entity_type = node.get("entity_type", "UNKNOWN")
        entity_value = node.get("entity_value") or node.get("node_id", "?")
        severity = float(node.get("severity_score", node.get("severity", 0.0)) or 0.0)
        anomaly = float(node.get("anomaly_score", 0.0) or 0.0)

        lines.append(f"{idx}. [{entity_type}] {entity_value}")
        lines.append(f"   - Node ID: {node.get('node_id', '?')}")
        lines.append(f"   - Severity: {severity:.2f}/1.0")
        lines.append(f"   - Anomaly Score: {anomaly:.3f}")

    lines.append("")
    lines.append("### Relationships on Critical Path")
    if not edges:
        lines.append("No explicit path relationships were provided.")

    for idx, edge in enumerate(edges, 1):
        edge_source = edge.get("source_id") or edge.get("source_node_id") or edge.get("source_label") or "?"
        edge_target = edge.get("target_id") or edge.get("target_node_id") or edge.get("target_label") or "?"
        relationship = edge.get("relationship", "RELATED_TO")
        weight = edge.get("weight", 1.0)
        confidence = float(edge.get("confidence_score", 1.0) or 1.0)
        evidence_ids = edge.get("evidence_ids", []) or []

        lines.append(f"{idx}. {edge_source} --[{relationship}]--> {edge_target}")
        lines.append(f"   - Weight: {weight}")
        lines.append(f"   - Confidence: {confidence:.2f}")
        if evidence_ids:
            lines.append(f"   - Evidence IDs: {', '.join(str(eid) for eid in evidence_ids[:20])}")

    lines.append("")
    lines.append("### GraphRAG Safety Rules")
    lines.append("- Analyze ONLY the entities and relationships listed above.")
    lines.append("- Do NOT reference any entities outside this critical path.")
    lines.append("- If evidence is incomplete, state uncertainty explicitly.")

    return "\n".join(lines)


def _fallback_graphrag_context(nodes: list[dict], edges: list[dict]) -> str:
    """Fallback context when shortest path is unavailable."""
    context_lines = ["## Entity Correlation Context (Fallback: Top 10 Entities)\n"]

    top_entities = sorted(nodes or [], key=lambda n: n.get("severity_score", 0), reverse=True)[:10]

    context_lines.append(f"Total entities in case: {len(nodes or [])}")
    context_lines.append(f"Total relationships: {len(edges or [])}\n")

    context_lines.append("### Top Severity Entities\n")
    for i, entity in enumerate(top_entities, 1):
        context_lines.append(
            f"{i}. [{entity.get('entity_type', 'UNKNOWN')}] {entity.get('entity_value', '?')} "
            f"(severity={float(entity.get('severity_score', 0.0) or 0.0):.2f})"
        )

    top_edges = sorted(edges or [], key=lambda e: e.get("weight", 0), reverse=True)[:10]
    context_lines.append("\n### Top Relationships\n")
    for i, edge in enumerate(top_edges, 1):
        context_lines.append(
            f"{i}. {edge.get('source_label', '?')} --[{edge.get('relationship', 'RELATED_TO')}]--> "
            f"{edge.get('target_label', '?')} (weight={edge.get('weight', 0)})"
        )

    context_lines.append(
        "\n**NOTE**: Using top-10 fallback context (shortest path unavailable). "
        "analysis may reference broader entity set."
    )

    return "\n".join(context_lines)


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def run_correlation(case_id: str, llm_provider: str = "ollama", severity_weights: dict | None = None) -> dict:
    """Execute the full correlation pipeline."""
    run_id = str(uuid.uuid4())
    initial: CorrelationState = {
        "case_id": case_id, "run_id": run_id,
        "llm_provider": llm_provider,
        "severity_weights": severity_weights or {"anomaly": 0.4, "privilege": 0.3, "frequency": 0.3},
    }
    graph = get_correlation_graph()
    try:
        result = graph.invoke(initial)
        return {
            "run_id": run_id, "status": "completed",
            "total_nodes": len(result.get("nodes", [])),
            "total_edges": len(result.get("edges", [])),
            "mitre_tactics": result.get("mitre_tactics", []),
            "narrative_preview": (result.get("narrative", ""))[:500],
            "recommendations": result.get("recommendations", []),
        }
    except Exception as e:
        logger.error(f"[CorrelationAgent] Pipeline failed: {e}", exc_info=True)
        try:
            conn = open_vault(case_id)
            conn.execute("UPDATE correlation_runs SET status='FAILED', completed_at=? WHERE run_id=?", [_now_iso(), run_id])
            conn.close()
        except Exception:
            pass
        return {"error": str(e), "run_id": run_id, "status": "FAILED"}


def get_correlation_data(case_id: str, run_id: str | None = None) -> dict:
    """Get graph nodes + edges for visualization."""
    conn = open_vault(case_id)
    try:
        if not run_id:
            latest = conn.execute("SELECT run_id FROM correlation_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1", [case_id]).fetchone()
            run_id = latest[0] if latest else None
        if not run_id:
            return {"nodes": [], "edges": [], "error": "No completed runs"}

        # Nodes
        rows = conn.execute("SELECT node_id, entity_type, entity_value, severity_score, anomaly_score, event_count, first_seen, last_seen, metadata_json FROM correlation_nodes WHERE run_id=?", [run_id]).fetchall()
        cols = ["node_id", "entity_type", "entity_value", "severity_score", "anomaly_score", "event_count", "first_seen", "last_seen", "metadata_json"]
        nodes = []
        for row in rows:
            d = dict(zip(cols, row))
            for k in ("first_seen", "last_seen"):
                if d.get(k) and not isinstance(d[k], str):
                    d[k] = str(d[k])
            if d.get("metadata_json"):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except Exception:
                    d["metadata"] = {}
            nodes.append(d)

        # Edges
        rows = conn.execute("SELECT edge_id, source_node_id, target_node_id, relationship, weight, evidence_count, first_seen, last_seen FROM correlation_edges WHERE run_id=?", [run_id]).fetchall()
        cols = ["edge_id", "source_node_id", "target_node_id", "relationship", "weight", "evidence_count", "first_seen", "last_seen"]
        edges = [dict(zip(cols, row)) for row in rows]

        return {"run_id": run_id, "nodes": nodes, "edges": edges}
    finally:
        conn.close()


def get_narrative(case_id: str, run_id: str | None = None) -> dict:
    """Get AI narrative for a run."""
    conn = open_vault(case_id)
    try:
        if not run_id:
            latest = conn.execute("SELECT run_id FROM correlation_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1", [case_id]).fetchone()
            run_id = latest[0] if latest else None
        if not run_id:
            return {"error": "No completed runs"}

        row = conn.execute("SELECT narrative_text, mitre_tactics, critical_path, recommendations, llm_provider, hash_value, created_at FROM rca_narratives WHERE run_id=? ORDER BY created_at DESC LIMIT 1", [run_id]).fetchone()
        if not row:
            return {"error": "No narrative found"}

        return {
            "run_id": run_id,
            "narrative": row[0],
            "mitre_tactics": json.loads(row[1]) if row[1] else [],
            "critical_path": json.loads(row[2]) if row[2] else [],
            "recommendations": json.loads(row[3]) if row[3] else [],
            "llm_provider": row[4], "hash_value": row[5],
            "created_at": str(row[6]) if row[6] else None,
        }
    finally:
        conn.close()


async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    """Interactive chat with the correlation agent."""
    from operation_room.services.llm_provider import get_llm

    # Get graph context
    graph_data = get_correlation_data(case_id, run_id)
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    context = f"""## Case Graph Context
Entities: {len(nodes)}, Connections: {len(edges)}

Top entities:
""" + "\n".join([f"- [{n['entity_type']}] {n['entity_value']}: severity={n.get('severity_score', 0)}, events={n.get('event_count', 0)}" for n in nodes[:8]])

    system = "You are a forensic investigation assistant. Answer questions about the case using the provided correlation graph data. Be specific and reference entity names."

    llm = get_llm(llm_provider)
    response = await llm.generate(f"{context}\n\n## Investigator Question\n{query}", system=system)

    # Audit log
    log_id = str(uuid.uuid4())
    try:
        conn = open_vault(case_id)
        conn.execute("""
            INSERT INTO agent_chat_logs (log_id, case_id, run_id, user_query, agent_response, llm_provider, context_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [log_id, case_id, run_id, query, response, llm_provider,
              json.dumps({"nodes": len(nodes), "edges": len(edges)}), _now_iso()])
        conn.close()
    except Exception:
        pass

    return {"response": response, "log_id": log_id, "llm_provider": llm_provider}


def get_correlation_runs(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT run_id, case_id, llm_provider, total_nodes, total_edges, status, hash_value, started_at, completed_at
            FROM correlation_runs WHERE case_id=? ORDER BY started_at DESC
        """, [case_id]).fetchall()
        cols = ["run_id", "case_id", "llm_provider", "total_nodes", "total_edges", "status", "hash_value", "started_at", "completed_at"]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            for k in ("started_at", "completed_at"):
                if d.get(k) and not isinstance(d[k], str):
                    d[k] = str(d[k])
            results.append(d)
        return results
    finally:
        conn.close()


def get_rules(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("SELECT rule_id, name, description, join_field, window_seconds, enabled, priority FROM correlation_rules ORDER BY priority DESC").fetchall()
        cols = ["rule_id", "name", "description", "join_field", "window_seconds", "enabled", "priority"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def toggle_rule(case_id: str, rule_id: str, enabled: bool) -> dict:
    conn = open_vault(case_id)
    try:
        conn.execute("UPDATE correlation_rules SET enabled=? WHERE rule_id=?", [enabled, rule_id])
        return {"rule_id": rule_id, "enabled": enabled}
    finally:
        conn.close()
