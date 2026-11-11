from fastapi import APIRouter, Query
import duckdb
import math
import pandas as pd
import numpy as np

from app.detection.service import run_detection

router = APIRouter()

HOT_DB = "data/hot/analytics.duckdb"


@router.post("/run-detection")
def detect():
    return run_detection()


@router.get("/detection/summary")
def detection_summary(audit_id: str | None = None):
    conn = duckdb.connect(HOT_DB)
    try:
        try:
            conn.execute("SELECT 1 FROM detection_results LIMIT 1")
        except Exception:
            return {"status": "no_results", "message": "Run detection first"}

        w = ""
        p = []
        if audit_id:
            w = "WHERE audit_id = ?"
            p = [audit_id]

        total = conn.execute(f"SELECT COUNT(*) FROM detection_results {w}", p).fetchone()[0]

        if w:
            anomalies = conn.execute(
                "SELECT COUNT(*) FROM detection_results WHERE audit_id = ? AND is_anomaly=1",
                [audit_id],
            ).fetchone()[0]
        else:
            anomalies = conn.execute(
                "SELECT COUNT(*) FROM detection_results WHERE is_anomaly=1"
            ).fetchone()[0]

        buckets = conn.execute(f"""
            SELECT
              CASE
                WHEN risk_score >= 75 THEN '75-100'
                WHEN risk_score >= 50 THEN '50-74'
                WHEN risk_score >= 25 THEN '25-49'
                ELSE '0-24'
              END AS label,
              COUNT(*) AS count
            FROM detection_results
            {w}
            GROUP BY 1
            ORDER BY 1
        """, p).fetchall()

        top_users = conn.execute(f"""
            SELECT user, COUNT(*) AS count
            FROM detection_results
            {w + " AND is_anomaly=1" if w else "WHERE is_anomaly=1"}
            GROUP BY user
            ORDER BY count DESC
            LIMIT 10
        """, p).fetchall()

        top_ips = conn.execute(f"""
            SELECT source_ip AS ip, COUNT(*) AS count
            FROM detection_results
            {w + " AND is_anomaly=1" if w else "WHERE is_anomaly=1"}
            GROUP BY source_ip
            ORDER BY count DESC
            LIMIT 10
        """, p).fetchall()

        return {
            "status": "ok",
            "total": int(total),
            "anomalies": int(anomalies),
            "buckets": [{"label": x[0], "count": int(x[1])} for x in buckets],
            "top_users": [{"user": x[0], "count": int(x[1])} for x in top_users if x[0] is not None],
            "top_ips": [{"ip": x[0], "count": int(x[1])} for x in top_ips if x[0] is not None],
        }
    finally:
        conn.close()


@router.get("/detection/results")
def detection_results(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_anomalies: bool = True,
    min_risk: float = 25,
    q: str = "",
    sort: str = "risk_desc",
    audit_id: str | None = None,
):
    conn = duckdb.connect(HOT_DB)
    try:
        try:
            conn.execute("SELECT 1 FROM detection_results LIMIT 1")
        except Exception:
            return {"status": "no_results", "total": 0, "items": []}

        wh = []
        p = []

        if audit_id:
            wh.append("audit_id = ?")
            p.append(audit_id)

        if only_anomalies:
            wh.append("is_anomaly = 1")

        wh.append("risk_score >= ?")
        p.append(min_risk)

        if q.strip():
            wh.append("(lower(coalesce(user,'')) LIKE ? OR lower(coalesce(source_ip,'')) LIKE ? OR lower(coalesce(action,'')) LIKE ?)")
            s = f"%{q.strip().lower()}%"
            p.extend([s, s, s])

        where_sql = ("WHERE " + " AND ".join(wh)) if wh else ""

        order_sql = {
            "risk_desc": "ORDER BY risk_score DESC",
            "time_desc": "ORDER BY timestamp DESC NULLS LAST",
            "time_asc": "ORDER BY timestamp ASC NULLS LAST",
        }.get(sort, "ORDER BY risk_score DESC")

        total = conn.execute(f"SELECT COUNT(*) FROM detection_results {where_sql}", p).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM detection_results {where_sql} {order_sql} LIMIT ? OFFSET ?",
            p + [limit, offset],
        ).fetchdf()

        rows = rows.where(pd.notnull(rows), None)

        def _clean(v):
            if v is None:
                return None

            if isinstance(v, (np.integer,)):
                return int(v)

            if isinstance(v, (np.floating,)):
                v = float(v)

            if isinstance(v, float):
                if math.isnan(v) or math.isinf(v):
                    return None
                return v

            if isinstance(v, (pd.Timestamp, np.datetime64)):
                return str(v)

            if isinstance(v, dict):
                return {k: _clean(val) for k, val in v.items()}

            if isinstance(v, (list, tuple)):
                return [_clean(x) for x in v]

            return v

        items = rows.to_dict("records")
        items = [{k: _clean(val) for k, val in r.items()} for r in items]


        return {"status": "ok", "total": int(total), "items": items}
    finally:
        conn.close()
