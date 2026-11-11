from __future__ import annotations

from datetime import datetime, time as time_of_day, timezone
from pathlib import Path
import duckdb
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditLog, IngestionSession, QuarantineLog
from app.detection.service import load_cold_into_hot


HOT_DB_PATH = Path("data/hot/analytics.duckdb")


def _iso(dt_val):
    if dt_val is None:
        return None
    if isinstance(dt_val, str):
        return dt_val
    try:
        return dt_val.isoformat()
    except Exception:
        return str(dt_val)


def _connect_hot():
    if not HOT_DB_PATH.exists():
        return None
    return duckdb.connect(str(HOT_DB_PATH))


def _analytics_summary() -> dict:
    """Aggregates from analytics DuckDB (Phase 4 pipeline); may be empty."""
    ok = load_cold_into_hot()
    if not ok:
        return {
            "status": "no_data",
            "total_events": 0,
            "earliest_log": None,
            "latest_log": None,
            "critical_threats": 0,
            "source": "cold_empty",
        }

    conn = _connect_hot()
    if conn is None:
        return {
            "status": "no_data",
            "total_events": 0,
            "earliest_log": None,
            "latest_log": None,
            "critical_threats": 0,
            "source": "hot_missing",
        }

    total, earliest, latest = conn.execute("""
        SELECT
          COUNT(*)::BIGINT AS total_events,
          MIN(timestamp) AS earliest_log,
          MAX(timestamp) AS latest_log
        FROM logs
        WHERE timestamp IS NOT NULL
    """).fetchone()

    has_det = conn.execute("""
        SELECT COUNT(*)::INT
        FROM information_schema.tables
        WHERE table_name='detection_results'
    """).fetchone()[0] > 0

    critical = 0
    if has_det:
        critical = conn.execute("""
            SELECT COUNT(*)::BIGINT
            FROM detection_results
            WHERE is_anomaly = 1 AND risk_score >= 80
        """).fetchone()[0]

    conn.close()

    return {
        "status": "ok",
        "total_events": int(total),
        "earliest_log": _iso(earliest),
        "latest_log": _iso(latest),
        "critical_threats": int(critical),
        "source": "detection_results" if has_det else "logs_only",
    }


def get_summary(db: Session) -> dict:
    """
    Dashboard KPIs: ledger counts (SQLite) + analytics aggregates (DuckDB).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total_logs = int(db.query(func.count(AuditLog.id)).scalar() or 0)
    quarantined_files = int(db.query(func.count(QuarantineLog.id)).scalar() or 0)
    total_sessions = int(
        db.query(func.count(IngestionSession.session_id))
        .filter(IngestionSession.expires_at > now, IngestionSession.used.is_(False))
        .scalar()
        or 0
    )

    analytics = _analytics_summary()
    active_alerts = int(analytics.get("critical_threats") or 0)

    return {
        "status": analytics.get("status", "no_data"),
        "total_logs": total_logs,
        "total_sessions": total_sessions,
        "quarantined_files": quarantined_files,
        "active_alerts": active_alerts,
        "total_events": analytics.get("total_events", 0),
        "earliest_log": analytics.get("earliest_log"),
        "latest_log": analytics.get("latest_log"),
        "critical_threats": active_alerts,
        "source": analytics.get("source", "ledger_only"),
    }


def _hourly_timeline_points(series: list[int]) -> list[dict]:
    base_date = datetime.now(timezone.utc).date()
    out = []
    for h in range(24):
        ts = datetime.combine(base_date, time_of_day(hour=h, minute=0, second=0), tzinfo=timezone.utc)
        out.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "count": int(series[h]),
                "event": "hourly",
            }
        )
    return out


def get_timeline():
    ok = load_cold_into_hot()
    if not ok:
        z = [0] * 24
        return {"status": "no_data", "series": z, "timeline": _hourly_timeline_points(z)}

    conn = _connect_hot()
    if conn is None:
        z = [0] * 24
        return {"status": "no_data", "series": z, "timeline": _hourly_timeline_points(z)}

    rows = conn.execute("""
        SELECT EXTRACT('hour' FROM timestamp)::INT AS h, COUNT(*)::BIGINT AS c
        FROM logs
        WHERE timestamp IS NOT NULL
        GROUP BY h
        ORDER BY h
    """).fetchall()
    conn.close()

    series = [0] * 24
    for h, c in rows:
        if h is not None and 0 <= int(h) <= 23:
            series[int(h)] = int(c)

    return {"status": "ok", "series": series, "timeline": _hourly_timeline_points(series)}


def get_severity():
    empty = {
        "status": "no_data",
        "source": "none",
        "critical": 0,
        "warning": 0,
        "info": 0,
        "severity_distribution": [
            {"level": "critical", "count": 0},
            {"level": "warning", "count": 0},
            {"level": "info", "count": 0},
        ],
    }
    ok = load_cold_into_hot()
    if not ok:
        return empty

    conn = _connect_hot()
    if conn is None:
        return empty

    has_det = conn.execute("""
        SELECT COUNT(*)::INT
        FROM information_schema.tables
        WHERE table_name='detection_results'
    """).fetchone()[0] > 0

    if has_det:
        # critical: anomaly + risk>=80
        # warning: anomaly + 60<=risk<80
        # info: everything else
        critical = conn.execute("""
            SELECT COUNT(*)::BIGINT
            FROM detection_results
            WHERE is_anomaly=1 AND risk_score >= 80
        """).fetchone()[0]

        warning = conn.execute("""
            SELECT COUNT(*)::BIGINT
            FROM detection_results
            WHERE is_anomaly=1 AND risk_score >= 60 AND risk_score < 80
        """).fetchone()[0]

        total = conn.execute("SELECT COUNT(*)::BIGINT FROM detection_results").fetchone()[0]
        info = int(total) - int(critical) - int(warning)

        conn.close()
        crit, warn, inf = int(critical), int(warning), int(info)
        return {
            "status": "ok",
            "source": "detection_results",
            "critical": crit,
            "warning": warn,
            "info": inf,
            "severity_distribution": [
                {"level": "critical", "count": crit},
                {"level": "warning", "count": warn},
                {"level": "info", "count": inf},
            ],
        }

    # fallback before running detection: map from logs.status (failed => warning)
    warning = conn.execute("""
        SELECT COUNT(*)::BIGINT
        FROM logs
        WHERE LOWER(COALESCE(status,''))='failed'
    """).fetchone()[0]

    total = conn.execute("SELECT COUNT(*)::BIGINT FROM logs").fetchone()[0]
    conn.close()

    warn = int(warning)
    inf = int(total) - warn
    return {
        "status": "ok",
        "source": "logs_status",
        "critical": 0,
        "warning": warn,
        "info": inf,
        "severity_distribution": [
            {"level": "critical", "count": 0},
            {"level": "warning", "count": warn},
            {"level": "info", "count": inf},
        ],
    }


def get_recent_uploads(db: Session, limit: int = 20):
    items = (
        db.query(AuditLog)
        .order_by(AuditLog.upload_time.desc())
        .limit(limit)
        .all()
    )

    out = []
    for r in items:
        out.append({
            "id": r.id,
            "audit_id": r.id,
            "filename": r.filename,
            "upload_time": r.upload_time.isoformat() if r.upload_time else None,
            "uploader": r.uploader,
            "file_size": r.file_size,
            "status": r.status,
            "sha256_hash": r.sha256_hash,
            "merkle_root": r.merkle_root,
            "ingestion_mode": r.ingestion_mode or "manual",
        })
    return {"status": "ok", "items": out}
