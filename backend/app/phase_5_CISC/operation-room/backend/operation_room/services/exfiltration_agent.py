"""
Data Exfiltration Intelligence — modular detection pipeline.

9 engines executed in sequence:
  1. Normalisation       — unified schema from existing tables
  2. Behaviour Graph     — directed interaction graph (User→File→Device→IP)
  3. Data Flow Detection — READ→TRANSFORM→SEND chains
  4. Multi-Channel Correlation — USB / Email / Cloud / Web / Bluetooth clustering
  5. Intent Detection    — behavioural anomaly scoring
  6. Ghost Transfer      — inferred exfil without direct logs
  7. Staging Detection   — compression / encryption prep
  8. Scoring             — composite risk score with configurable weights
  9. Explainable AI      — human-readable reasoning per incident
"""

import json
import uuid
import hashlib
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from operation_room.database import open_vault

_DEFAULT_CONFIG: dict[str, dict[str, float]] = {
    "data_flow":    {"window_secs": 1800, "min_bytes": 50000},
    "channel":      {"window_secs": 600},
    "intent":       {"bulk_access_threshold": 5, "off_hours_start": 18, "off_hours_end": 7,
                     "w_bulk": 0.30, "w_offhours": 0.25, "w_new_device": 0.20, "w_staging": 0.25},
    "ghost":        {"max_gap_secs": 3600},
    "staging":      {"extensions": 0},  # placeholder — extensions checked dynamically
    "scoring":      {"w_flow": 0.30, "w_intent": 0.25, "w_anomaly": 0.20, "w_sensitivity": 0.25},
}

_STAGING_EXTENSIONS = {".zip", ".tar", ".gz", ".7z", ".rar", ".enc", ".locked", ".crypt", ".gpg", ".aes"}
_INTERNAL_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "192.168.", "127.")
_CHANNEL_KEYWORDS = {
    "USB": ["usb", "removable", "/media/usb"],
    "EMAIL": ["smtp", "email", "outlook", "exchange", "mail"],
    "CLOUD": ["s3", "onedrive", "dropbox", "gdrive", "sharepoint", "blob.core"],
    "BLUETOOTH": ["bluetooth", "bt:", "obex"],
    "WEB": ["http", "https", "443", "web", "upload"],
}


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_external(ip: str) -> bool:
    if not ip:
        return False
    return not any(ip.startswith(p) for p in _INTERNAL_PREFIXES)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = defaultdict(int)
    for c in s:
        freq[c] += 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _parse_detail(raw: str | dict | None) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _load_config(conn, case_id: str) -> dict:
    """Load config from DB, falling back to defaults."""
    config: dict[str, dict[str, float]] = {}
    for engine, params in _DEFAULT_CONFIG.items():
        config[engine] = dict(params)

    try:
        conn.execute("SELECT engine, param_name, param_value FROM exfil_intel_config WHERE case_id = ?", [case_id])
        for engine, name, value in conn.fetchall():
            if engine not in config:
                config[engine] = {}
            config[engine][name] = value
    except Exception:
        pass
    return config


# ── Engine 1: Normalisation ──────────────────────────────────────────────

def _normalise(conn, case_id: str) -> list[dict]:
    """Pull events from unified_timeline + raw_events into a flat schema."""
    conn.execute("""
        SELECT tl_event_id, normalised_ts, actor, action, target,
               source_type, source_system, severity, detail
        FROM unified_timeline WHERE case_id = ?
        ORDER BY normalised_ts
    """, [case_id])
    rows = conn.fetchall()

    events: list[dict] = []
    for r in rows:
        detail = _parse_detail(r[8])
        events.append({
            "id": r[0],
            "timestamp": str(r[1]) if r[1] else "",
            "actor": r[2] or "",
            "event_type": r[5] or "",
            "action": r[3] or "",
            "file_name": _extract_file(r[4], detail),
            "file_hash": detail.get("file_hash", ""),
            "src": detail.get("source_ip", ""),
            "dst": detail.get("destination_ip", detail.get("dest_ip", "")),
            "device_type": r[6] or "",
            "target": r[4] or "",
            "severity": r[7] or "INFO",
            "metadata": detail,
            "bytes": detail.get("bytes", detail.get("response_bytes", 0)) or 0,
        })
    return events


def _extract_file(target: str | None, detail: dict) -> str:
    if not target:
        return ""
    if "/" in target and "." in target.split("/")[-1]:
        return target
    return detail.get("path", detail.get("file", target or ""))


# ── Engine 2: Behaviour Graph ────────────────────────────────────────────

def _build_graph(events: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Build directed graph.  Returns (nodes_by_id, edges_list)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def ensure_node(ntype: str, value: str, ts: str) -> str:
        key = f"{ntype}::{value}"
        if key not in nodes:
            nodes[key] = {
                "node_id": _uid(), "node_type": ntype, "node_value": value,
                "event_count": 0, "risk_score": 0.0,
                "first_seen": ts, "last_seen": ts, "metadata_json": "{}",
            }
        nodes[key]["event_count"] += 1
        if ts and ts > nodes[key]["last_seen"]:
            nodes[key]["last_seen"] = ts
        return key

    for ev in events:
        ts = ev["timestamp"]
        actor_key = ensure_node("USER", ev["actor"], ts) if ev["actor"] else None
        file_key = ensure_node("FILE", ev["file_name"], ts) if ev["file_name"] and "/" in ev["file_name"] else None
        device_key = ensure_node("DEVICE", ev["device_type"], ts) if ev["device_type"] else None
        src_key = ensure_node("IP", ev["src"], ts) if ev["src"] else None
        dst_key = ensure_node("IP", ev["dst"], ts) if ev["dst"] and _is_external(ev["dst"]) else None

        action = ev["action"].upper()
        rel = _action_to_rel(action, ev["event_type"])

        if actor_key and file_key:
            edges.append(_edge(actor_key, file_key, rel, ts, ev["id"]))
        if actor_key and dst_key:
            edges.append(_edge(actor_key, dst_key, "CONNECT", ts, ev["id"]))
        if file_key and dst_key and rel in ("SEND", "WRITE"):
            edges.append(_edge(file_key, dst_key, "SEND", ts, ev["id"]))
        if actor_key and device_key:
            edges.append(_edge(actor_key, device_key, "USED", ts, ev["id"]))
        if src_key and actor_key:
            edges.append(_edge(src_key, actor_key, "AUTHENTICATED_FROM", ts, ev["id"]))

    return nodes, edges


def _action_to_rel(action: str, event_type: str) -> str:
    reads = {"SELECT", "FILE_READ", "HTTP_GET", "READ", "EXPORT"}
    writes = {"INSERT", "FILE_WRITE", "HTTP_POST", "HTTP_PUT", "UPDATE", "CREATE", "CREATE_TABLE", "FILE_COPY"}
    sends = {"SEND", "UPLOAD", "HTTP_POST", "VPN_CONNECT"}
    if action in reads:
        return "READ"
    if action in writes:
        return "WRITE"
    if action in sends:
        return "SEND"
    return "INTERACT"


def _edge(src_key: str, tgt_key: str, rel: str, ts: str, evidence_id: str) -> dict:
    return {
        "edge_id": _uid(), "source_key": src_key, "target_key": tgt_key,
        "relationship": rel, "weight": 1.0,
        "evidence_count": 1, "evidence_ids": json.dumps([evidence_id]),
        "first_seen": ts, "last_seen": ts,
    }


# ── Engine 3: Data Flow Detection ────────────────────────────────────────

def _detect_data_flows(events: list[dict], config: dict) -> list[dict]:
    """Detect READ → WRITE/SEND chains within configurable time windows."""
    window = config["data_flow"]["window_secs"]
    min_bytes = config["data_flow"]["min_bytes"]

    actor_events: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        if ev["actor"]:
            actor_events[ev["actor"]].append(ev)

    flows: list[dict] = []
    for actor, evs in actor_events.items():
        reads = [e for e in evs if _action_to_rel(e["action"].upper(), e["event_type"]) == "READ"]
        sends = [e for e in evs if _action_to_rel(e["action"].upper(), e["event_type"]) in ("SEND", "WRITE") and _is_external(e["dst"])]

        for read_ev in reads:
            r_ts = _parse_ts(read_ev["timestamp"])
            if r_ts is None:
                continue
            for send_ev in sends:
                s_ts = _parse_ts(send_ev["timestamp"])
                if s_ts is None:
                    continue
                delta = (s_ts - r_ts).total_seconds()
                if 0 < delta <= window:
                    read_bytes = int(read_ev.get("bytes", 0) or 0)
                    send_bytes = int(send_ev.get("bytes", 0) or 0)
                    if read_bytes >= min_bytes or send_bytes >= min_bytes:
                        flows.append({
                            "actor": actor, "read_event": read_ev, "send_event": send_ev,
                            "time_delta": delta, "bytes_read": read_bytes, "bytes_sent": send_bytes,
                            "channel": _classify_channel(send_ev),
                            "data_target": read_ev["target"],
                            "dst_ip": send_ev["dst"],
                        })
    return flows


def _parse_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        clean = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _classify_channel(ev: dict) -> str:
    """Classify event into an exfiltration channel."""
    haystack = json.dumps(ev).lower()
    for channel, keywords in _CHANNEL_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return channel
    if _is_external(ev.get("dst", "")):
        return "WEB"
    return "UNKNOWN"


# ── Engine 4: Multi-Channel Correlation ──────────────────────────────────

def _correlate_channels(data_flows: list[dict], config: dict) -> list[dict]:
    """Group flows by actor + time window into correlated clusters."""
    window = config["channel"]["window_secs"]
    actor_flows: dict[str, list[dict]] = defaultdict(list)
    for f in data_flows:
        actor_flows[f["actor"]].append(f)

    clusters: list[dict] = []
    for actor, flows in actor_flows.items():
        flows.sort(key=lambda f: f["send_event"]["timestamp"])
        cluster: list[dict] = []
        for f in flows:
            if not cluster:
                cluster = [f]
                continue
            prev_ts = _parse_ts(cluster[-1]["send_event"]["timestamp"])
            curr_ts = _parse_ts(f["send_event"]["timestamp"])
            if prev_ts and curr_ts and (curr_ts - prev_ts).total_seconds() <= window:
                cluster.append(f)
            else:
                if len(cluster) >= 1:
                    clusters.append({"actor": actor, "flows": cluster, "channels": list({c["channel"] for c in cluster})})
                cluster = [f]
        if cluster:
            clusters.append({"actor": actor, "flows": cluster, "channels": list({c["channel"] for c in cluster})})
    return clusters


# ── Engine 5: Intent Detection ───────────────────────────────────────────

def _detect_intent(events: list[dict], data_flows: list[dict], config: dict) -> dict[str, float]:
    """Score each actor's exfiltration intent (0–1)."""
    cfg = config["intent"]
    actor_scores: dict[str, dict] = {}

    actor_events: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        if ev["actor"]:
            actor_events[ev["actor"]].append(ev)

    known_devices: dict[str, set] = defaultdict(set)
    for ev in events:
        if ev["actor"] and ev["device_type"]:
            known_devices[ev["actor"]].add(ev["device_type"])

    flow_actors = {f["actor"] for f in data_flows}

    for actor, evs in actor_events.items():
        reads = [e for e in evs if _action_to_rel(e["action"].upper(), e["event_type"]) == "READ"]
        bulk = min(1.0, len(reads) / max(cfg["bulk_access_threshold"] * 10, 1))

        off_hours_count = 0
        for e in evs:
            ts = _parse_ts(e["timestamp"])
            if ts:
                hour = ts.hour
                if hour >= cfg["off_hours_start"] or hour < cfg["off_hours_end"]:
                    off_hours_count += 1
        off_hours = min(1.0, off_hours_count / max(len(evs), 1) * 2)

        unique_devices = len(known_devices.get(actor, set()))
        new_device = min(1.0, max(0, unique_devices - 2) / 3)

        staging = 1.0 if actor in flow_actors else 0.0
        for e in evs:
            fname = e.get("file_name", "")
            if fname:
                ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if ext in _STAGING_EXTENSIONS:
                    staging = 1.0
                    break

        score = (cfg["w_bulk"] * bulk + cfg["w_offhours"] * off_hours +
                 cfg["w_new_device"] * new_device + cfg["w_staging"] * staging)
        actor_scores[actor] = min(1.0, score)

    return actor_scores


# ── Engine 6: Ghost Transfer Detection ───────────────────────────────────

def _detect_ghost_transfers(events: list[dict], data_flows: list[dict], config: dict) -> list[dict]:
    """Infer exfiltration where file was read but no local write logged, yet outbound traffic exists."""
    max_gap = config["ghost"]["max_gap_secs"]
    flow_read_ids = {f["read_event"]["id"] for f in data_flows}

    actor_events: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        if ev["actor"]:
            actor_events[ev["actor"]].append(ev)

    ghosts: list[dict] = []
    for actor, evs in actor_events.items():
        reads = [e for e in evs if _action_to_rel(e["action"].upper(), e["event_type"]) == "READ" and e["id"] not in flow_read_ids]
        outbounds = [e for e in evs if _is_external(e.get("dst", ""))]

        for read_ev in reads:
            r_ts = _parse_ts(read_ev["timestamp"])
            if r_ts is None:
                continue
            local_writes = [e for e in evs
                            if _action_to_rel(e["action"].upper(), e["event_type"]) == "WRITE"
                            and not _is_external(e.get("dst", ""))
                            and _parse_ts(e["timestamp"]) and
                            0 <= (_parse_ts(e["timestamp"]) - r_ts).total_seconds() <= max_gap]
            if local_writes:
                continue

            nearby_out = [e for e in outbounds
                          if _parse_ts(e["timestamp"]) and
                          0 < (_parse_ts(e["timestamp"]) - r_ts).total_seconds() <= max_gap]
            if nearby_out:
                ghosts.append({
                    "actor": actor, "read_event": read_ev,
                    "outbound_event": nearby_out[0],
                    "reasoning": (f"Actor '{actor}' read '{read_ev['target']}' at {read_ev['timestamp']}, "
                                  f"no local write was logged, but outbound traffic to "
                                  f"{nearby_out[0].get('dst', '?')} occurred {int((_parse_ts(nearby_out[0]['timestamp']) - r_ts).total_seconds())}s later."),
                })
    return ghosts


# ── Engine 7: Staging Detection ──────────────────────────────────────────

def _detect_staging(events: list[dict]) -> list[dict]:
    """Detect compression, encryption, and batch file creation patterns."""
    staged: list[dict] = []
    for ev in events:
        fname = ev.get("file_name", "") or ev.get("target", "")
        action = ev.get("action", "").upper()
        detail = ev.get("metadata", {})

        if not fname:
            continue
        ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        process = detail.get("process", "")

        is_staging = False
        reason = ""
        if ext in _STAGING_EXTENSIONS and action in ("FILE_WRITE", "FILE_COPY", "WRITE", "CREATE"):
            is_staging = True
            reason = f"File '{fname}' written with staging extension '{ext}'"
        elif process.lower() in ("7z.exe", "zip.exe", "tar", "gzip", "rar.exe", "gpg", "openssl"):
            is_staging = True
            reason = f"Staging tool '{process}' executed by {ev['actor']}"
        elif action in ("QUARANTINE", "PROCESS_BLOCKED") and "archiver" in str(detail.get("threat", "")).lower():
            is_staging = True
            reason = f"EPP blocked archiver: {detail.get('threat', '')}"

        if is_staging:
            staged.append({
                "actor": ev["actor"], "event": ev,
                "file": fname, "extension": ext,
                "reason": reason,
            })
    return staged


# ── Engine 8: Scoring ────────────────────────────────────────────────────

def _score_incidents(
    data_flows: list[dict],
    ghost_transfers: list[dict],
    staging: list[dict],
    intent_scores: dict[str, float],
    anomaly_lookup: dict[str, float],
    sensitivity_lookup: dict[str, str],
    config: dict,
) -> list[dict]:
    """Produce scored incident objects."""
    cfg = config["scoring"]
    incidents: list[dict] = []
    staging_actors = {s["actor"] for s in staging}

    for flow in data_flows:
        actor = flow["actor"]
        flow_signal = min(1.0, (flow["bytes_read"] + flow["bytes_sent"]) / 5_000_000)
        intent = intent_scores.get(actor, 0.0)
        anomaly = anomaly_lookup.get(actor, 0.0)
        sens_str = sensitivity_lookup.get(flow["data_target"], "LOW")
        sens_val = {"LOW": 0.1, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 1.0}.get(sens_str, 0.1)

        confidence = (cfg["w_flow"] * flow_signal + cfg["w_intent"] * intent +
                      cfg["w_anomaly"] * anomaly + cfg["w_sensitivity"] * sens_val)
        confidence = min(1.0, confidence)
        risk = _risk_category(confidence)

        incidents.append({
            "incident_id": _uid(), "actor": actor,
            "channel": flow["channel"], "data_target": flow["data_target"],
            "dst_ip": flow["dst_ip"],
            "bytes_accessed": flow["bytes_read"], "bytes_exfil": flow["bytes_sent"],
            "confidence": round(confidence, 4), "risk_category": risk,
            "intent_score": round(intent, 4),
            "is_ghost": False, "is_staged": actor in staging_actors,
            "normalised_ts": flow["send_event"]["timestamp"],
            "flow_signal": flow_signal, "anomaly_signal": anomaly, "sensitivity_signal": sens_val,
        })

    for ghost in ghost_transfers:
        actor = ghost["actor"]
        intent = intent_scores.get(actor, 0.0)
        anomaly = anomaly_lookup.get(actor, 0.0)
        confidence = min(1.0, 0.3 + 0.3 * intent + 0.2 * anomaly + 0.2 * (1 if actor in staging_actors else 0))
        incidents.append({
            "incident_id": _uid(), "actor": actor,
            "channel": "INFERRED", "data_target": ghost["read_event"]["target"],
            "dst_ip": ghost["outbound_event"].get("dst", ""),
            "bytes_accessed": int(ghost["read_event"].get("bytes", 0) or 0), "bytes_exfil": 0,
            "confidence": round(confidence, 4), "risk_category": _risk_category(confidence),
            "intent_score": round(intent, 4),
            "is_ghost": True, "is_staged": actor in staging_actors,
            "normalised_ts": ghost["outbound_event"]["timestamp"],
            "flow_signal": 0.3, "anomaly_signal": anomaly, "sensitivity_signal": 0.3,
        })

    incidents.sort(key=lambda x: x["confidence"], reverse=True)
    return incidents


def _risk_category(confidence: float) -> str:
    if confidence >= 0.75:
        return "CRITICAL"
    if confidence >= 0.50:
        return "HIGH"
    if confidence >= 0.25:
        return "MEDIUM"
    return "LOW"


# ── Engine 9: Explainable AI ────────────────────────────────────────────

def _explain_incidents(incidents: list[dict], staging: list[dict], ghost_transfers: list[dict]) -> list[dict]:
    """Attach human-readable explanations to each incident."""
    staging_reasons = {s["actor"]: s["reason"] for s in staging}
    ghost_reasons = {g["actor"]: g["reasoning"] for g in ghost_transfers}

    for inc in incidents:
        factors = []
        if inc["flow_signal"] > 0.5:
            factors.append(f"Large data movement detected ({inc['bytes_accessed']}B read → {inc['bytes_exfil']}B sent)")
        if inc["intent_score"] > 0.4:
            factors.append(f"High behavioural intent score ({inc['intent_score']:.2f}): bulk access, off-hours, or new devices")
        if inc["anomaly_signal"] > 0.3:
            factors.append(f"ML anomaly model flagged actor's events (score: {inc['anomaly_signal']:.2f})")
        if inc["sensitivity_signal"] > 0.5:
            factors.append(f"Accessed sensitive data target: {inc['data_target']}")
        if inc["is_ghost"]:
            factors.append(f"Ghost transfer: {ghost_reasons.get(inc['actor'], 'No local write logged after read')}")
        if inc["is_staged"]:
            factors.append(f"Staging activity: {staging_reasons.get(inc['actor'], 'Compression/encryption detected')}")
        if inc["channel"] not in ("UNKNOWN", "INFERRED"):
            factors.append(f"Exfiltration channel: {inc['channel']}")

        explanation = "; ".join(factors) if factors else "Low-confidence detection based on available signals"

        inc["explanation"] = explanation
        inc["contributing_factors"] = json.dumps(factors)
        inc["timeline_json"] = json.dumps([
            {"step": "Data Access", "timestamp": inc["normalised_ts"], "detail": f"Read {inc['data_target']}"},
            {"step": "Transfer", "timestamp": inc["normalised_ts"], "detail": f"Sent to {inc['dst_ip']} via {inc['channel']}"},
        ])
    return incidents


# ── Pipeline orchestrator ────────────────────────────────────────────────

def _get_anomaly_lookup(conn, case_id: str) -> dict[str, float]:
    """Max anomaly score per actor from most recent anomaly run."""
    try:
        conn.execute("""
            SELECT ut.actor, MAX(a.normalised_score)
            FROM anomaly_scores a
            JOIN unified_timeline ut ON a.tl_event_id = ut.tl_event_id
            WHERE a.case_id = ? AND a.is_anomaly = TRUE
            GROUP BY ut.actor
        """, [case_id])
        return {r[0]: r[1] for r in conn.fetchall() if r[0]}
    except Exception:
        return {}


def _get_sensitivity_lookup(conn, case_id: str) -> dict[str, str]:
    """Target → max sensitivity from CRUD events."""
    try:
        conn.execute("""
            SELECT target_object, MAX(sensitivity) FROM crud_events
            WHERE case_id = ? GROUP BY target_object
        """, [case_id])
        priority = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        result: dict[str, str] = {}
        for target, sens in conn.fetchall():
            if target:
                result[target] = sens or "LOW"
        return result
    except Exception:
        return {}


def run_exfiltration_analysis(case_id: str, **kwargs) -> dict:
    """Execute the full 9-engine pipeline."""
    conn = open_vault(case_id)
    run_id = _uid()
    config = _load_config(conn, case_id)

    conn.execute("""
        INSERT INTO exfil_intel_runs (run_id, case_id, params_json, status)
        VALUES (?, ?, ?, 'RUNNING')
    """, [run_id, case_id, json.dumps(kwargs)])

    try:
        events = _normalise(conn, case_id)
        nodes, edges = _build_graph(events)
        data_flows = _detect_data_flows(events, config)
        clusters = _correlate_channels(data_flows, config)
        intent_scores = _detect_intent(events, data_flows, config)
        ghost_transfers = _detect_ghost_transfers(events, data_flows, config)
        staging = _detect_staging(events)
        anomaly_lookup = _get_anomaly_lookup(conn, case_id)
        sensitivity_lookup = _get_sensitivity_lookup(conn, case_id)

        incidents = _score_incidents(data_flows, ghost_transfers, staging,
                                     intent_scores, anomaly_lookup, sensitivity_lookup, config)
        incidents = _explain_incidents(incidents, staging, ghost_transfers)

        _persist(conn, case_id, run_id, nodes, edges, incidents, clusters)

        high_risk = [i for i in incidents if i["risk_category"] in ("HIGH", "CRITICAL")]
        affected_actors = list({i["actor"] for i in incidents})
        affected_devices = list({i["dst_ip"] for i in incidents if i["dst_ip"]})
        total_bytes = sum(i["bytes_exfil"] for i in incidents)
        overall_risk = "CRITICAL" if any(i["risk_category"] == "CRITICAL" for i in incidents) \
            else "HIGH" if high_risk else "MEDIUM" if incidents else "LOW"

        canonical = json.dumps(incidents, sort_keys=True, separators=(",", ":"))
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()

        conn.execute("""
            UPDATE exfil_intel_runs SET
                total_incidents = ?, high_risk_count = ?, affected_actors = ?,
                affected_devices = ?, total_bytes_out = ?, overall_risk = ?,
                status = 'COMPLETED', hash_value = ?, completed_at = current_timestamp
            WHERE run_id = ?
        """, [len(incidents), len(high_risk), len(affected_actors),
              len(affected_devices), total_bytes, overall_risk, hash_val, run_id])

        conn.execute("""
            INSERT INTO chain_of_custody (event_id, case_id, actor, action, target_artefact, justification, hash_after)
            VALUES (?, ?, 'exfiltration_agent', 'EXFIL_INTEL_RUN', 'exfil_intel_incidents',
                    'Data Exfiltration Intelligence analysis completed', ?)
        """, [_uid(), case_id, hash_val])

        return {
            "run_id": run_id, "status": "COMPLETED",
            "total_incidents": len(incidents), "high_risk_count": len(high_risk),
            "affected_actors": len(affected_actors), "affected_devices": len(affected_devices),
            "total_bytes_out": total_bytes, "overall_risk": overall_risk,
            "graph_nodes": len(nodes), "graph_edges": len(edges),
            "data_flows": len(data_flows), "ghost_transfers": len(ghost_transfers),
            "staging_events": len(staging), "channel_clusters": len(clusters),
        }

    except Exception as exc:
        conn.execute("UPDATE exfil_intel_runs SET status = 'FAILED' WHERE run_id = ?", [run_id])
        raise exc


def _persist(conn, case_id: str, run_id: str,
             nodes: dict, edges: list, incidents: list, clusters: list):
    """Write all results to DuckDB tables."""
    conn.execute("DELETE FROM exfil_graph_nodes WHERE case_id = ?", [case_id])
    conn.execute("DELETE FROM exfil_graph_edges WHERE case_id = ?", [case_id])
    conn.execute("DELETE FROM exfil_intel_incidents WHERE case_id = ?", [case_id])
    conn.execute("DELETE FROM exfil_channel_stats WHERE case_id = ?", [case_id])

    for key, n in nodes.items():
        conn.execute("""
            INSERT INTO exfil_graph_nodes
                (node_id, run_id, case_id, node_type, node_value,
                 event_count, risk_score, first_seen, last_seen, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [n["node_id"], run_id, case_id, n["node_type"], n["node_value"],
              n["event_count"], n["risk_score"], n["first_seen"], n["last_seen"],
              n["metadata_json"]])

    for e in edges:
        src_node_id = nodes[e["source_key"]]["node_id"] if e["source_key"] in nodes else ""
        tgt_node_id = nodes[e["target_key"]]["node_id"] if e["target_key"] in nodes else ""
        conn.execute("""
            INSERT INTO exfil_graph_edges
                (edge_id, run_id, case_id, source_node_id, target_node_id,
                 relationship, weight, evidence_count, evidence_ids, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [e["edge_id"], run_id, case_id, src_node_id, tgt_node_id,
              e["relationship"], e["weight"], e["evidence_count"], e["evidence_ids"],
              e["first_seen"], e["last_seen"]])

    for inc in incidents:
        conn.execute("""
            INSERT INTO exfil_intel_incidents
                (incident_id, run_id, case_id, actor, channel, data_target,
                 dst_ip, bytes_accessed, bytes_exfil, confidence, risk_category,
                 intent_score, is_ghost, is_staged, explanation,
                 contributing_factors, timeline_json, normalised_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [inc["incident_id"], run_id, case_id, inc["actor"], inc["channel"],
              inc["data_target"], inc["dst_ip"], inc["bytes_accessed"], inc["bytes_exfil"],
              inc["confidence"], inc["risk_category"], inc["intent_score"],
              inc["is_ghost"], inc["is_staged"], inc["explanation"],
              inc["contributing_factors"], inc["timeline_json"], inc["normalised_ts"]])

    channel_agg: dict[str, dict] = {}
    for inc in incidents:
        ch = inc["channel"]
        if ch not in channel_agg:
            channel_agg[ch] = {"count": 0, "bytes": 0, "conf_sum": 0.0, "actors": set()}
        channel_agg[ch]["count"] += 1
        channel_agg[ch]["bytes"] += inc["bytes_exfil"]
        channel_agg[ch]["conf_sum"] += inc["confidence"]
        channel_agg[ch]["actors"].add(inc["actor"])

    for ch, agg in channel_agg.items():
        conn.execute("""
            INSERT INTO exfil_channel_stats
                (stat_id, run_id, case_id, channel, incident_count,
                 total_bytes, avg_confidence, actors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [_uid(), run_id, case_id, ch, agg["count"], agg["bytes"],
              round(agg["conf_sum"] / max(agg["count"], 1), 4),
              json.dumps(list(agg["actors"]))])


# ── Public query functions ───────────────────────────────────────────────

def run_exfiltration_analysis_streamed(case_id: str, **kwargs):
    """Generator that yields SSE-friendly dicts for each pipeline stage."""
    import time as _time
    conn = open_vault(case_id)
    run_id = _uid()
    config = _load_config(conn, case_id)
    engines = [
        "Normalisation", "Behaviour Graph", "Data Flow Detection",
        "Channel Correlation", "Intent Detection", "Ghost Transfer",
        "Staging Detection", "Scoring", "Explainable AI",
    ]

    conn.execute("""
        INSERT INTO exfil_intel_runs (run_id, case_id, params_json, status)
        VALUES (?, ?, ?, 'RUNNING')
    """, [run_id, case_id, json.dumps(kwargs)])

    yield {"type": "start", "run_id": run_id, "engines": engines, "total": len(engines)}

    try:
        yield {"type": "engine", "index": 0, "name": "Normalisation", "status": "running"}
        events = _normalise(conn, case_id)
        yield {"type": "engine", "index": 0, "name": "Normalisation", "status": "done",
               "detail": f"{len(events)} events normalised"}

        yield {"type": "engine", "index": 1, "name": "Behaviour Graph", "status": "running"}
        nodes, edges = _build_graph(events)
        yield {"type": "engine", "index": 1, "name": "Behaviour Graph", "status": "done",
               "detail": f"{len(nodes)} nodes, {len(edges)} edges"}

        yield {"type": "engine", "index": 2, "name": "Data Flow Detection", "status": "running"}
        data_flows = _detect_data_flows(events, config)
        yield {"type": "engine", "index": 2, "name": "Data Flow Detection", "status": "done",
               "detail": f"{len(data_flows)} flows detected"}

        yield {"type": "engine", "index": 3, "name": "Channel Correlation", "status": "running"}
        clusters = _correlate_channels(data_flows, config)
        yield {"type": "engine", "index": 3, "name": "Channel Correlation", "status": "done",
               "detail": f"{len(clusters)} clusters"}

        yield {"type": "engine", "index": 4, "name": "Intent Detection", "status": "running"}
        intent_scores = _detect_intent(events, data_flows, config)
        yield {"type": "engine", "index": 4, "name": "Intent Detection", "status": "done",
               "detail": f"{len(intent_scores)} actors scored"}

        yield {"type": "engine", "index": 5, "name": "Ghost Transfer", "status": "running"}
        ghost_transfers = _detect_ghost_transfers(events, data_flows, config)
        yield {"type": "engine", "index": 5, "name": "Ghost Transfer", "status": "done",
               "detail": f"{len(ghost_transfers)} ghost transfers"}

        yield {"type": "engine", "index": 6, "name": "Staging Detection", "status": "running"}
        staging = _detect_staging(events)
        yield {"type": "engine", "index": 6, "name": "Staging Detection", "status": "done",
               "detail": f"{len(staging)} staging events"}

        yield {"type": "engine", "index": 7, "name": "Scoring", "status": "running"}
        anomaly_lookup = _get_anomaly_lookup(conn, case_id)
        sensitivity_lookup = _get_sensitivity_lookup(conn, case_id)
        incidents = _score_incidents(data_flows, ghost_transfers, staging,
                                     intent_scores, anomaly_lookup, sensitivity_lookup, config)
        yield {"type": "engine", "index": 7, "name": "Scoring", "status": "done",
               "detail": f"{len(incidents)} incidents scored"}

        yield {"type": "engine", "index": 8, "name": "Explainable AI", "status": "running"}
        incidents = _explain_incidents(incidents, staging, ghost_transfers)
        yield {"type": "engine", "index": 8, "name": "Explainable AI", "status": "done",
               "detail": f"{len(incidents)} explanations generated"}

        yield {"type": "persist", "status": "running"}
        _persist(conn, case_id, run_id, nodes, edges, incidents, clusters)

        high_risk = [i for i in incidents if i["risk_category"] in ("HIGH", "CRITICAL")]
        affected_actors = list({i["actor"] for i in incidents})
        affected_devices = list({i["dst_ip"] for i in incidents if i["dst_ip"]})
        total_bytes = sum(i["bytes_exfil"] for i in incidents)
        overall_risk = "CRITICAL" if any(i["risk_category"] == "CRITICAL" for i in incidents) \
            else "HIGH" if high_risk else "MEDIUM" if incidents else "LOW"

        canonical = json.dumps(incidents, sort_keys=True, separators=(",", ":"))
        hash_val = hashlib.sha256(canonical.encode()).hexdigest()

        conn.execute("""
            UPDATE exfil_intel_runs SET
                total_incidents = ?, high_risk_count = ?, affected_actors = ?,
                affected_devices = ?, total_bytes_out = ?, overall_risk = ?,
                status = 'COMPLETED', hash_value = ?, completed_at = current_timestamp
            WHERE run_id = ?
        """, [len(incidents), len(high_risk), len(affected_actors),
              len(affected_devices), total_bytes, overall_risk, hash_val, run_id])

        conn.execute("""
            INSERT INTO chain_of_custody (event_id, case_id, actor, action, target_artefact, justification, hash_after)
            VALUES (?, ?, 'exfiltration_agent', 'EXFIL_INTEL_RUN', 'exfil_intel_incidents',
                    'Data Exfiltration Intelligence analysis completed', ?)
        """, [_uid(), case_id, hash_val])

        yield {"type": "complete", "run_id": run_id, "status": "COMPLETED",
               "total_incidents": len(incidents), "high_risk_count": len(high_risk),
               "affected_actors": len(affected_actors), "affected_devices": len(affected_devices),
               "total_bytes_out": total_bytes, "overall_risk": overall_risk,
               "graph_nodes": len(nodes), "graph_edges": len(edges),
               "data_flows": len(data_flows), "ghost_transfers": len(ghost_transfers),
               "staging_events": len(staging), "channel_clusters": len(clusters)}

    except Exception as exc:
        conn.execute("UPDATE exfil_intel_runs SET status = 'FAILED' WHERE run_id = ?", [run_id])
        yield {"type": "error", "message": str(exc)}


def get_exfil_summary(case_id: str, run_id: str | None = None) -> dict:
    conn = open_vault(case_id)
    if run_id:
        conn.execute("SELECT * FROM exfil_intel_runs WHERE run_id = ? AND case_id = ?", [run_id, case_id])
    else:
        conn.execute("SELECT * FROM exfil_intel_runs WHERE case_id = ? ORDER BY started_at DESC LIMIT 1", [case_id])
    row = conn.fetchone()
    if not row:
        return {}
    cols = ["run_id", "case_id", "params_json", "total_incidents", "high_risk_count",
            "affected_actors", "affected_devices", "total_bytes_out", "overall_risk",
            "status", "hash_value", "started_at", "completed_at"]
    return {c: (str(row[i]) if row[i] is not None else None) for i, c in enumerate(cols)}


def get_exfil_incidents(case_id: str, run_id: str | None = None) -> list[dict]:
    conn = open_vault(case_id)
    where = "case_id = ?"
    params: list = [case_id]
    if run_id:
        where += " AND run_id = ?"
        params.append(run_id)
    conn.execute(f"""
        SELECT incident_id, run_id, actor, channel, data_target, dst_ip,
               bytes_accessed, bytes_exfil, confidence, risk_category,
               intent_score, is_ghost, is_staged, explanation,
               contributing_factors, timeline_json, normalised_ts
        FROM exfil_intel_incidents WHERE {where}
        ORDER BY confidence DESC
    """, params)
    cols = ["incident_id", "run_id", "actor", "channel", "data_target", "dst_ip",
            "bytes_accessed", "bytes_exfil", "confidence", "risk_category",
            "intent_score", "is_ghost", "is_staged", "explanation",
            "contributing_factors", "timeline_json", "normalised_ts"]
    rows = conn.fetchall()
    result = []
    for r in rows:
        d = {}
        for i, c in enumerate(cols):
            val = r[i]
            if c in ("contributing_factors", "timeline_json"):
                try:
                    val = json.loads(val) if val else []
                except (json.JSONDecodeError, TypeError):
                    val = []
            elif isinstance(val, datetime):
                val = val.isoformat()
            d[c] = val
        result.append(d)
    return result


def get_exfil_graph(case_id: str, run_id: str | None = None) -> dict:
    conn = open_vault(case_id)
    where = "case_id = ?"
    params: list = [case_id]
    if run_id:
        where += " AND run_id = ?"
        params.append(run_id)

    conn.execute(f"""
        SELECT node_id, node_type, node_value, event_count, risk_score,
               first_seen, last_seen, metadata_json
        FROM exfil_graph_nodes WHERE {where}
    """, params)
    nodes = [{"id": r[0], "type": r[1], "value": r[2], "event_count": r[3],
              "risk_score": r[4], "first_seen": str(r[5]) if r[5] else None,
              "last_seen": str(r[6]) if r[6] else None}
             for r in conn.fetchall()]

    conn.execute(f"""
        SELECT edge_id, source_node_id, target_node_id, relationship,
               weight, evidence_count, first_seen, last_seen
        FROM exfil_graph_edges WHERE {where}
    """, params)
    e_edges = [{"id": r[0], "source": r[1], "target": r[2], "relationship": r[3],
                "weight": r[4], "evidence_count": r[5],
                "first_seen": str(r[6]) if r[6] else None,
                "last_seen": str(r[7]) if r[7] else None}
               for r in conn.fetchall()]
    return {"nodes": nodes, "edges": e_edges}


def get_exfil_channels(case_id: str, run_id: str | None = None) -> list[dict]:
    conn = open_vault(case_id)
    where = "case_id = ?"
    params: list = [case_id]
    if run_id:
        where += " AND run_id = ?"
        params.append(run_id)
    conn.execute(f"""
        SELECT channel, incident_count, total_bytes, avg_confidence, actors
        FROM exfil_channel_stats WHERE {where}
    """, params)
    return [{"channel": r[0], "count": r[1], "bytes": r[2], "avg_confidence": r[3],
             "actors": json.loads(r[4]) if r[4] else []}
            for r in conn.fetchall()]


def get_exfil_runs(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    conn.execute("""
        SELECT run_id, total_incidents, high_risk_count, affected_actors,
               affected_devices, total_bytes_out, overall_risk, status,
               started_at, completed_at
        FROM exfil_intel_runs WHERE case_id = ?
        ORDER BY started_at DESC
    """, [case_id])
    cols = ["run_id", "total_incidents", "high_risk_count", "affected_actors",
            "affected_devices", "total_bytes_out", "overall_risk", "status",
            "started_at", "completed_at"]
    return [{c: (str(r[i]) if r[i] is not None else None) for i, c in enumerate(cols)}
            for r in conn.fetchall()]
