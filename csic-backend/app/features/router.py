from typing import Optional
import duckdb
import pandas as pd
from fastapi import APIRouter, Query
import numpy as np
import math

from app.features.service import compute_features

router = APIRouter()

HOT_DB = "data/hot/analytics.duckdb"


@router.post("/generate-features")
def generate(audit_id: Optional[str] = None):
    return compute_features(audit_id=audit_id)


def _has_features(conn) -> bool:
    x = conn.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'features'
    """).fetchone()[0]
    return x > 0


@router.get("/features/preview")
def features_preview(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    audit_id: Optional[str] = None,
):
    conn = duckdb.connect(HOT_DB)
    try:
        if not _has_features(conn):
            return {"status": "no_features", "total": 0, "items": []}

        cols = conn.execute("PRAGMA table_info('features')").fetchall()
        names = [c[1] for c in cols]

        q = "SELECT * FROM features"
        ps = []

        if audit_id and "audit_id" in names:
            q += " WHERE audit_id = ?"
            ps.append(audit_id)

        if "timestamp" in names:
            q += " ORDER BY timestamp DESC NULLS LAST"
        else:
            q += " ORDER BY 1"

        q += f" LIMIT {limit} OFFSET {offset}"

        df = conn.execute(q, ps).fetchdf()
        df = df.where(pd.notnull(df), None)
        items = df.to_dict(orient="records")

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

        items = [_clean(r) for r in items]

        total_q = "SELECT COUNT(*) FROM features"
        total_ps = []
        if audit_id and "audit_id" in names:
            total_q += " WHERE audit_id = ?"
            total_ps.append(audit_id)

        total = int(conn.execute(total_q, total_ps).fetchone()[0])

        return {"status": "ok", "total": total, "items": items}
    finally:
        conn.close()
