"""
Timeline Reconstruction service.

Reads raw_events from the Case Vault, normalises timestamps to UTC,
merges them into a unified_timeline table, applies DBSCAN clustering,
running Time-Skew heuristics, hashes the result and records chain-of-custody.
"""

import json
import uuid
from datetime import datetime, timezone
import numpy as np
from collections import defaultdict
from sklearn.cluster import DBSCAN

from operation_room.database import open_vault
from operation_room.config import settings
from operation_room.utils.hashing import hash_records
from operation_room.services.audit_service import record_coc_event
from operation_room.utils.query_builder import build_where_clause


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Severity classification ──────────────────────────────────────────────

_HIGH_SEVERITY_ACTIONS = {
    "LOGIN_FAILED", "ACCOUNT_LOCKED", "MALWARE_DETECTED", "QUARANTINE",
    "PROCESS_BLOCKED", "DENY", "DROP", "ERROR_500", "DELETE",
    "FILE_DELETE", "EXPORT", "RATE_LIMIT",
}
_MEDIUM_SEVERITY_ACTIONS = {
    "MFA_CHALLENGE", "PASSWORD_CHANGE", "VPN_FAILED", "UPDATE",
    "CREATE_TABLE", "FILE_WRITE", "FILE_RENAME", "FILE_COPY",
    "HTTP_DELETE", "HTTP_PUT",
}


def _classify_severity(action: str) -> str:
    if action in _HIGH_SEVERITY_ACTIONS:
        return "HIGH"
    if action in _MEDIUM_SEVERITY_ACTIONS:
        return "MEDIUM"
    return "INFO"


# ── Build timeline ───────────────────────────────────────────────────────

def build_timeline(case_id: str, data: dict) -> dict:
    """
    Full pipeline:
      1. Read raw_events from vault
      2. Normalise timestamps & fields
      3. Insert into unified_timeline
      4. Auto-detect anchors
      5. Hash + CoC
    """
    conn = open_vault(case_id)
    now = _now_iso()

    try:
        # Optionally wipe previous timeline
        if data.get("force_rebuild", False):
            conn.execute("DELETE FROM unified_timeline WHERE case_id = ?", [case_id])
            conn.execute("DELETE FROM anchor_events WHERE case_id = ?", [case_id])

        # Check if timeline already exists
        existing = conn.execute(
            "SELECT COUNT(*) FROM unified_timeline WHERE case_id = ?", [case_id]
        ).fetchone()[0]
        if existing > 0 and not data.get("force_rebuild", False):
            return {
                "total_events": existing,
                "clusters_detected": conn.execute(
                    "SELECT COUNT(*) FROM temporal_clusters WHERE case_id = ?", [case_id]
                ).fetchone()[0],
                "hash_value": "",
                "coc_event_id": "",
                "message": f"Timeline already exists with {existing} events. Use force_rebuild=true to rebuild.",
            }

        # ① Read raw_events
        source_filter = ""
        params = [case_id]
        if data.get("source_types"):
            placeholders = ",".join(["?" for _ in data["source_types"]])
            source_filter = f" AND source_type IN ({placeholders})"
            params.extend(data["source_types"])

        time_filter = ""
        if data.get("time_start"):
            time_filter += " AND timestamp >= ?"
            params.append(data["time_start"])
        if data.get("time_end"):
            time_filter += " AND timestamp <= ?"
            params.append(data["time_end"])

        rows = conn.execute(
            f"""
            SELECT event_id, case_id, source_type, timestamp,
                   source_system, actor, action, target, detail
            FROM raw_events
            WHERE case_id = ?{source_filter}{time_filter}
            ORDER BY event_id ASC
            """,
            params,
        ).fetchall()

        cols = ["event_id", "case_id", "source_type", "timestamp",
                "source_system", "actor", "action", "target", "detail"]

        # -- Zero-event diagnostics ------------------------------------------
        if not rows:
            diag_source_types = []
            try:
                st = conn.execute(
                    "SELECT DISTINCT source_type FROM raw_events WHERE case_id = ?",
                    [case_id],
                ).fetchall()
                diag_source_types = [r[0] for r in st if r[0]]
            except Exception:
                pass

            diag_total_raw = 0
            try:
                diag_total_raw = conn.execute(
                    "SELECT COUNT(*) FROM raw_events WHERE case_id = ?",
                    [case_id],
                ).fetchone()[0]
            except Exception:
                pass

            diag_time_range = None
            try:
                tr = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM raw_events WHERE case_id = ?",
                    [case_id],
                ).fetchone()
                if tr and tr[0]:
                    diag_time_range = {"min": str(tr[0]), "max": str(tr[1])}
            except Exception:
                pass

            return {
                "total_events": 0,
                "clusters_detected": 0,
                "hash_value": "",
                "coc_event_id": "",
                "message": "Zero events matched. See diagnostics for details.",
                "diagnostics": {
                    "raw_event_count": diag_total_raw,
                    "available_source_types": diag_source_types,
                    "requested_source_types": data.get("source_types"),
                    "requested_time_start": data.get("time_start"),
                    "requested_time_end": data.get("time_end"),
                    "raw_time_range": diag_time_range,
                    "suggestion": (
                        "No raw events matched the filters. "
                        "Check source_types and time range constraints, "
                        "or ensure logs have been ingested for this case."
                    ),
                },
            }

        # ② Normalise & Execute Time-Skew Heuristics
        normalised = []
        last_ts_epoch = None
        
        for row in rows:
            rec = dict(zip(cols, row))
            ts_raw = rec["timestamp"]
            if ts_raw and not isinstance(ts_raw, str):
                ts_str = str(ts_raw)
            else:
                ts_str = ts_raw or now
                
            try:
                curr_ts_epoch = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except Exception:
                curr_ts_epoch = 0.0

            is_time_stomped = False
            uncertainty_sec = 0.0
            severity = _classify_severity(rec.get("action", ""))

            # Time-Skew Check: if timestamps decrement while sequence increments -> tampering
            if last_ts_epoch is not None:
                if curr_ts_epoch < last_ts_epoch:
                    is_time_stomped = True
                    severity = "CRITICAL"
                    uncertainty_sec = abs(last_ts_epoch - curr_ts_epoch)
            last_ts_epoch = curr_ts_epoch

            tl_id = str(uuid.uuid4())
            event = {
                "tl_event_id": tl_id,
                "case_id": case_id,
                "original_event_id": rec["event_id"],
                "normalised_ts": ts_str,
                "utc_offset": "+00:00",
                "source_type": rec.get("source_type", "UNKNOWN"),
                "source_system": rec.get("source_system"),
                "actor": rec.get("actor"),
                "action": rec.get("action"),
                "target": rec.get("target"),
                "severity": severity,
                "detail": rec.get("detail"),
                "is_time_stomped": is_time_stomped,
                "uncertainty_sec": uncertainty_sec,
                "cluster_id": None,
            }
            normalised.append(event)

        # ③ Dynamic DBSCAN Clustering
        # Sort chronologically for ML ingestion and DB storage
        normalised.sort(key=lambda x: datetime.fromisoformat(x["normalised_ts"].replace("Z", "+00:00")).timestamp())
        epoch_times = [datetime.fromisoformat(x["normalised_ts"].replace("Z", "+00:00")).timestamp() for x in normalised]
        
        cluster_window_seconds = float(data.get("cluster_window_seconds", 300))
        min_cluster_samples = int(data.get("min_cluster_samples", 3))
        cluster_count = 0

        if epoch_times:
            cluster_map = defaultdict(list)
            X = np.array(epoch_times).reshape(-1, 1)
            db = DBSCAN(eps=cluster_window_seconds, min_samples=min_cluster_samples).fit(X)
            
            for event, lbl in zip(normalised, db.labels_):
                lbl = int(lbl)
                if lbl != -1:
                    event["cluster_id"] = lbl
                    cluster_map[lbl].append(event)
                
                conn.execute(
                    """
                    INSERT INTO unified_timeline
                        (tl_event_id, case_id, original_event_id, normalised_ts,
                         utc_offset, source_type, source_system, actor, action,
                         target, severity, detail, is_time_stomped, cluster_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        event["tl_event_id"], case_id, event["original_event_id"],
                        event["normalised_ts"], event["utc_offset"],
                        event["source_type"], event["source_system"],
                        event["actor"], event["action"], event["target"],
                        event["severity"], event["detail"],
                        event["is_time_stomped"], event["cluster_id"], now,
                    ],
                )
                
            cluster_count = len(cluster_map.keys())
            for c_id, evs in cluster_map.items():
                evs_sorted = sorted(evs, key=lambda x: x["normalised_ts"])
                actions = [e["action"] for e in evs if e["action"]]
                dominant = max(set(actions), key=actions.count) if actions else "UNKNOWN"
                
                conn.execute(
                    """
                    INSERT INTO temporal_clusters
                        (cluster_id, case_id, cluster_number, start_ts, end_ts, event_count, dominant_action, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [str(uuid.uuid4()), case_id, c_id, evs_sorted[0]["normalised_ts"], evs_sorted[-1]["normalised_ts"], len(evs), dominant, now]
                )

        # ④ Hash the timeline
        hash_value = hash_records(normalised, settings.HASH_ALGORITHM)

        # ⑤ CoC (keep vault connection open until after CoC is recorded)
        coc_id = record_coc_event(
            case_id=case_id,
            actor="analyst",
            action="TIMELINE_BUILT",
            target_artefact="unified_timeline",
            justification="Timeline reconstruction from raw events",
            hash_after=hash_value,
            details={
                "total_events": len(normalised),
                "clusters_detected": cluster_count,
                "source_types": list(set(e["source_type"] for e in normalised)),
            },
        )

        return {
            "total_events": len(normalised),
            "clusters_detected": cluster_count,
            "hash_value": hash_value,
            "coc_event_id": coc_id,
            "message": f"Timeline built with {len(normalised)} events spread across {cluster_count} clusters.",
        }
    finally:
        try:
            conn.close()
        except Exception:
            # Connection may already be closed by nested operations; ignore to stay resilient.
            pass


# ── Query timeline ───────────────────────────────────────────────────────

def get_timeline(case_id: str, filters: dict) -> dict:
    """Fetch timeline events grouped by DBSCAN Temporal Clusters."""
    conn = open_vault(case_id)
    try:
        where = ["case_id = ?"]
        params = [case_id]

        if filters.get("actor"):
            where.append("actor = ?")
            params.append(filters["actor"])
        if filters.get("source_type"):
            where.append("source_type = ?")
            params.append(filters["source_type"])
        if filters.get("source_system"):
            where.append("source_system = ?")
            params.append(filters["source_system"])
        if filters.get("action"):
            where.append("action = ?")
            params.append(filters["action"])
        if filters.get("severity"):
            where.append("severity = ?")
            params.append(filters["severity"])
        if filters.get("time_stomped_only"):
            where.append("is_time_stomped = TRUE")
        if filters.get("anchors_only"):
            where.append("is_anchor = TRUE")
        if filters.get("time_start"):
            where.append("normalised_ts >= ?")
            params.append(filters["time_start"])
        if filters.get("time_end"):
            where.append("normalised_ts <= ?")
            params.append(filters["time_end"])
        if filters.get("keyword"):
            where.append("(action LIKE ? OR target LIKE ? OR detail LIKE ?)")   
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw, kw])

        limit = min(filters.get("limit", 5000), 5000)
        offset = filters.get("offset", 0)

        query = f"""
            SELECT tl_event_id, case_id, original_event_id, normalised_ts,      
                   utc_offset, source_type, source_system, actor, action,       
                   target, severity, detail, is_time_stomped, cluster_id, is_anchor, anchor_label
            FROM unified_timeline
            WHERE {' AND '.join(where)}
            ORDER BY normalised_ts ASC
            LIMIT {limit} OFFSET {offset}
        """

        rows = conn.execute(query, params).fetchall()
        cols = ["tl_event_id", "case_id", "original_event_id", "normalised_ts",
                "utc_offset", "source_type", "source_system", "actor", "action",
                "target", "severity", "detail", "is_time_stomped", "cluster_id", "is_anchor", "anchor_label"]

        cluster_map = defaultdict(lambda: {"events": [], "start": None, "end": None})
        unclustered = []
        
        for row in rows:
            rec = dict(zip(cols, row))
            c_id = rec["cluster_id"]
            
            if c_id is not None:
                cmap = cluster_map[c_id]
                cmap["events"].append(rec)
                
                # Update boundaries
                ts = rec["normalised_ts"]
                if cmap["start"] is None or ts < cmap["start"]: cmap["start"] = ts
                if cmap["end"] is None or ts > cmap["end"]: cmap["end"] = ts
            else:
                unclustered.append(rec)
                
        clusters_out = []
        for c_id, cmap in cluster_map.items():
            evs = cmap["events"]
            clusters_out.append({
                "cluster_id": c_id,
                "start": cmap["start"],
                "end": cmap["end"],
                "event_count": len(evs),
                "events": evs
            })

        # Append unclustered points as pseudo-cluster for rendering, or simply append them
        if unclustered:
            clusters_out.append({
                "cluster_id": "outliers",
                "start": unclustered[0]["normalised_ts"] if unclustered else None,
                "end": unclustered[-1]["normalised_ts"] if unclustered else None,
                "event_count": len(unclustered),
                "events": unclustered
            })

        return {"clusters": clusters_out}
    finally:
        conn.close()




# ── Advanced Search & Stats ──────────────────────────────────────────────

def get_timeline_stats(case_id: str) -> dict:
    """Get summary statistics for the entire timeline (no filters)."""
    conn = open_vault(case_id)
    try:
        # Total events and anchors
        total = conn.execute("SELECT COUNT(*) FROM unified_timeline WHERE case_id = ?", [case_id]).fetchone()[0]
        total_anchors = conn.execute("SELECT COUNT(*) FROM unified_timeline WHERE case_id = ? AND is_anchor = TRUE", [case_id]).fetchone()[0]
        
        # Events by source
        source_rows = conn.execute("""
            SELECT source_type, COUNT(*) 
            FROM unified_timeline 
            WHERE case_id = ? 
            GROUP BY source_type 
            ORDER BY COUNT(*) DESC
        """, [case_id]).fetchall()
        sources = {r[0]: r[1] for r in source_rows}
        
        # Events by actor
        actor_rows = conn.execute("""
            SELECT actor, COUNT(*) 
            FROM unified_timeline 
            WHERE case_id = ? AND actor IS NOT NULL
            GROUP BY actor 
            ORDER BY COUNT(*) DESC
        """, [case_id]).fetchall()
        actors = {r[0]: r[1] for r in actor_rows}
        
        # Time span
        span = conn.execute("""
            SELECT MIN(normalised_ts), MAX(normalised_ts) 
            FROM unified_timeline 
            WHERE case_id = ?
        """, [case_id]).fetchone()
        time_span_start = str(span[0]) if span[0] else None
        time_span_end = str(span[1]) if span[1] else None
        
        # Events by hour
        hour_rows = conn.execute("""
            SELECT strftime('%Y-%m-%d %H:00', normalised_ts) as hour, COUNT(*) 
            FROM unified_timeline 
            WHERE case_id = ? AND normalised_ts IS NOT NULL
            GROUP BY hour 
            ORDER BY hour
        """, [case_id]).fetchall()
        events_by_hour = {r[0]: r[1] for r in hour_rows}
        
        return {
            "total_events": total,
            "total_anchors": total_anchors,
            "sources": sources,
            "actors": actors,
            "time_span_start": time_span_start,
            "time_span_end": time_span_end,
            "events_by_hour": events_by_hour
        }
    finally:
        conn.close()


def get_timeline_search(case_id: str, search_query: dict, limit: int = 500, offset: int = 0, anchors_only: bool = False) -> list[dict]:
    conn = open_vault(case_id)
    try:
        where_clause, params = build_where_clause(search_query)
        base_where = "case_id = ?"
        all_params = [case_id]

        if where_clause:
            full_where = f"{base_where} AND {where_clause}"
            all_params.extend(params)
        else:
            full_where = base_where
        
        if anchors_only:
            full_where += " AND is_anchor = TRUE"

        query = f'''
            SELECT tl_event_id, case_id, original_event_id, normalised_ts,
                   utc_offset, source_type, source_system, actor, action,
                   target, severity, detail, cluster_id, is_time_stomped, is_anchor, anchor_label
            FROM unified_timeline
            WHERE {full_where}
            ORDER BY normalised_ts ASC
            LIMIT {limit} OFFSET {offset}
        '''

        rows = conn.execute(query, all_params).fetchall()
        cols = [
            "tl_event_id", "case_id", "original_event_id", "normalised_ts",
            "utc_offset", "source_type", "source_system", "actor", "action",
            "target", "severity", "detail", "cluster_id", "is_time_stomped", "is_anchor", "anchor_label"
        ]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("normalised_ts") and not isinstance(d["normalised_ts"], str):
                d["normalised_ts"] = str(d["normalised_ts"])
            results.append(d)
        return results
    finally:
        conn.close()

def get_timeline_stats_search(case_id: str, search_query: dict, anchors_only: bool = False) -> dict:
    conn = open_vault(case_id)
    try:
        where_clause, params = build_where_clause(search_query)
        base_where = "case_id = ?"
        all_params = [case_id]

        if where_clause:
            full_where = f"{base_where} AND {where_clause}"
            all_params.extend(params)
        else:
            full_where = base_where

        if anchors_only:
            full_where += " AND is_anchor = TRUE"

        total = conn.execute(f"SELECT COUNT(*) FROM unified_timeline WHERE {full_where}", all_params).fetchone()[0]
        clusters = conn.execute(f"SELECT COUNT(DISTINCT cluster_id) FROM unified_timeline WHERE cluster_id IS NOT NULL AND {full_where}", all_params).fetchone()[0]

        source_rows = conn.execute(f"SELECT source_type, COUNT(*) FROM unified_timeline WHERE {full_where} GROUP BY source_type ORDER BY COUNT(*) DESC", all_params).fetchall()
        sources = {r[0]: r[1] for r in source_rows}

        action_rows = conn.execute(f"SELECT action, COUNT(*) FROM unified_timeline WHERE {full_where} GROUP BY action ORDER BY COUNT(*) DESC", all_params).fetchall()
        actions = {r[0]: r[1] for r in action_rows}

        return {
            "total_events": total,
            "clusters": clusters,
            "sources": sources,
            "actions": actions
        }
    finally:
        conn.close()

def toggle_anchor(case_id: str, data: dict) -> dict:
    conn = open_vault(case_id)
    try:
        tl_id = data['tl_event_id']
        label = data.get('label', '')
        is_anchor = data.get('is_anchor', True)
        
        if is_anchor:
            conn.execute('UPDATE unified_timeline SET is_anchor = TRUE, anchor_label = ? WHERE tl_event_id = ?', [label, tl_id])
        else:
            conn.execute('UPDATE unified_timeline SET is_anchor = FALSE, anchor_label = NULL WHERE tl_event_id = ?', [tl_id])
            
        from operation_room.services.audit_service import record_coc_event
        record_coc_event(case_id=case_id, actor='analyst', action='ANCHOR_TOGGLED', target_artefact=f'timeline_event:{tl_id}', justification=f'Anchor toggled to {is_anchor}')
        return {"status": "ok"}
    finally:
        conn.close()

def get_anchors(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("SELECT tl_event_id, normalised_ts, action, actor, target, source_type, severity, detail, anchor_label FROM unified_timeline WHERE case_id = ? AND is_anchor = TRUE ORDER BY normalised_ts ASC", [case_id]).fetchall()
        cols = ["tl_event_id", "normalised_ts", "action", "actor", "target", "source_type", "severity", "detail", "anchor_label"]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("normalised_ts") and not isinstance(d["normalised_ts"], str):
                d["normalised_ts"] = str(d["normalised_ts"])
            results.append(d)
        return results
    finally:
        conn.close()

async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm(llm_provider)
    system = "You are the Timeline Agent. Respond to queries focusing strictly on sequences of events and timestamps."
    response = await llm.generate("Investigator Question:\n" + query, system=system)
    return {"response": response, "log_id": "timeline-log", "llm_provider": llm_provider, "agent_routed": "timeline_agent"}

