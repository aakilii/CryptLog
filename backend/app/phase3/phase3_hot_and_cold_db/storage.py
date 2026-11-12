from __future__ import annotations

import datetime as dt
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb

from .s3_client import (
    cold_s3_key,
    configure_duckdb_s3,
    delete_parquet,
    is_s3_enabled,
    list_parquets,
    s3_parquet_uri,
    upload_parquet,
)


@dataclass(frozen=True)
class StorageConfig:
    hot_db_path: str
    cold_dir: str
    ttl_seconds: int = 30


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def ensure_dirs(cfg: StorageConfig) -> None:
    Path(cfg.cold_dir).mkdir(parents=True, exist_ok=True)


def connect_hot(cfg: StorageConfig) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(cfg.hot_db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS live_events (
          lineage VARCHAR PRIMARY KEY,
          target_user VARCHAR,
          notes VARCHAR,
          notes_redacted VARCHAR,
          vector DOUBLE[],
          created_at TIMESTAMPTZ,
          ttl_seconds INTEGER,
          is_locked BOOLEAN,
          is_tombstoned BOOLEAN,
          pii_redactions INTEGER,
          privacy_confidence DOUBLE,
          audit_id VARCHAR,
          source_type VARCHAR,
          extracted_variables JSON,
          ner_tags JSON,
          normalized_timestamp TIMESTAMPTZ,
          row_hash VARCHAR
        )
        """
    )
    _new_cols = {
        "audit_id": "VARCHAR DEFAULT ''",
        "source_type": "VARCHAR DEFAULT ''",
        "extracted_variables": "JSON DEFAULT '{}'",
        "ner_tags": "JSON DEFAULT '{}'",
        "normalized_timestamp": "TIMESTAMPTZ",
        "row_hash": "VARCHAR DEFAULT ''",
    }
    for col, typedef in _new_cols.items():
        try:
            con.execute(f"ALTER TABLE live_events ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_audit (
          event_id VARCHAR,
          lineage VARCHAR,
          created_at TIMESTAMPTZ,
          status VARCHAR,
          detail VARCHAR
        )
        """
    )
    return con


COLD_PARQUET_COLUMNS = """
    Target_User VARCHAR,
    Notes VARCHAR,
    Notes_Redacted VARCHAR,
    Lineage VARCHAR,
    audit_id VARCHAR,
    source_type VARCHAR,
    extracted_variables VARCHAR,
    ner_tags VARCHAR,
    normalized_timestamp TIMESTAMPTZ,
    row_hash VARCHAR,
    created_at TIMESTAMPTZ
"""


def _cold_paths(cfg: StorageConfig, lineage: str) -> Tuple[Path, Path]:
    date = _now_utc().date().isoformat()
    stage_dir = Path(cfg.cold_dir) / "_staging" / date
    final_dir = Path(cfg.cold_dir) / "events" / date
    stage_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    stage = stage_dir / f"{lineage}.parquet"
    final = final_dir / f"{lineage}.parquet"
    return stage, final


def stage_to_cold(cfg: StorageConfig, event: Dict[str, Any]) -> Path:
    """Write a single-event Parquet to local staging (used by both S3 and local modes)."""
    lineage = str(event.get("Lineage") or event.get("lineage") or "")
    stage_path, _ = _cold_paths(cfg, lineage)
    tmp_con = duckdb.connect(":memory:")
    tmp_con.execute(f"CREATE TABLE e ({COLD_PARQUET_COLUMNS})")
    tmp_con.execute(
        "INSERT INTO e VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(event.get("Target_User") or ""),
            str(event.get("Notes") or ""),
            str(event.get("Notes_Redacted") or ""),
            lineage,
            str(event.get("audit_id") or ""),
            str(event.get("source_type") or ""),
            str(event.get("extracted_variables") or "{}"),
            str(event.get("ner_tags") or "{}"),
            event.get("normalized_timestamp"),
            str(event.get("row_hash") or ""),
            event.get("created_at"),
        ),
    )
    tmp_con.execute(f"COPY e TO '{stage_path.as_posix()}' (FORMAT 'parquet')")
    tmp_con.close()
    return stage_path


def commit_cold(cfg: StorageConfig, lineage: str) -> Optional[str]:
    """
    Commit staged Parquet.
    - S3 mode: upload to S3, delete local staging file, return S3 key.
    - Local mode: rename staging -> final, return local path.
    """
    stage_path, final_path = _cold_paths(cfg, lineage)
    if not stage_path.exists():
        return None

    if is_s3_enabled():
        date_str = _now_utc().date().isoformat()
        key = cold_s3_key(date_str, lineage, staging=False)
        upload_parquet(key, stage_path)
        stage_path.unlink(missing_ok=True)
        return s3_parquet_uri(key)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.replace(final_path)
    return str(final_path)


def rollback_cold(cfg: StorageConfig, lineage: str) -> None:
    stage_path, _ = _cold_paths(cfg, lineage)
    try:
        if stage_path.exists():
            stage_path.unlink()
    except Exception:
        pass


def insert_hot_event(
    con: duckdb.DuckDBPyConnection,
    *,
    lineage: str,
    target_user: str,
    notes: str,
    notes_redacted: str,
    vector: List[float],
    created_at: dt.datetime,
    ttl_seconds: int,
    pii_redactions: int,
    privacy_confidence: float,
    audit_id: str = "",
    source_type: str = "",
    extracted_variables: str = "{}",
    ner_tags: str = "{}",
    normalized_timestamp: Optional[dt.datetime] = None,
    row_hash: str = "",
) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO live_events
        (lineage, target_user, notes, notes_redacted, vector, created_at, ttl_seconds,
         is_locked, is_tombstoned, pii_redactions, privacy_confidence,
         audit_id, source_type, extracted_variables, ner_tags, normalized_timestamp, row_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, FALSE, FALSE, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lineage,
            target_user,
            notes,
            notes_redacted,
            vector,
            created_at,
            ttl_seconds,
            pii_redactions,
            privacy_confidence,
            audit_id,
            source_type,
            extracted_variables,
            ner_tags,
            normalized_timestamp,
            row_hash,
        ),
    )


def lock_lineage(con: duckdb.DuckDBPyConnection, lineage: str) -> None:
    con.execute("UPDATE live_events SET is_locked = TRUE WHERE lineage = ?", (lineage,))


def extend_lineage(con: duckdb.DuckDBPyConnection, lineage: str, seconds: int) -> None:
    con.execute("UPDATE live_events SET ttl_seconds = ttl_seconds + ? WHERE lineage = ?", (int(seconds), lineage))


def remove_lineage(con: duckdb.DuckDBPyConnection, lineage: str) -> None:
    con.execute("DELETE FROM live_events WHERE lineage = ?", (lineage,))
    con.execute("VACUUM")


def remove_lineage_s3(lineage: str) -> None:
    """Delete all S3 Parquet objects for a lineage (best-effort)."""
    if not is_s3_enabled():
        return
    try:
        keys = list_parquets(f"phase3/events/")
        for k in keys:
            if k.endswith(f"/{lineage}.parquet"):
                delete_parquet(k)
    except Exception:
        pass


def tombstone_lineage(con: duckdb.DuckDBPyConnection, lineage: str) -> None:
    con.execute("UPDATE live_events SET is_tombstoned = TRUE WHERE lineage = ?", (lineage,))


def query_hot(
    con: duckdb.DuckDBPyConnection,
    *,
    target_user: str = "",
    source_type: str = "",
    time_start: str = "",
    time_end: str = "",
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Query hot DuckDB live_events with the same filters as query_cold."""
    conditions = ["is_tombstoned = FALSE"]
    params: list = []

    if target_user:
        conditions.append("target_user = ?")
        params.append(target_user)
    if source_type:
        conditions.append("source_type = ?")
        params.append(source_type)
    if time_start:
        conditions.append("COALESCE(normalized_timestamp, created_at) >= ?::TIMESTAMPTZ")
        params.append(time_start)
    if time_end:
        conditions.append("COALESCE(normalized_timestamp, created_at) <= ?::TIMESTAMPTZ")
        params.append(time_end)

    where = f"WHERE {' AND '.join(conditions)}"
    params.extend([int(limit), int(offset)])

    sql = (
        "SELECT target_user AS Target_User, notes_redacted AS Notes, lineage AS Lineage, "
        "audit_id, source_type, extracted_variables, ner_tags, "
        "normalized_timestamp, row_hash, created_at "
        f"FROM live_events {where} "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )

    try:
        rows = con.execute(sql, params).fetchall()
    except Exception:
        return []

    cols = [
        "Target_User", "Notes", "Lineage", "audit_id",
        "source_type", "extracted_variables", "ner_tags",
        "normalized_timestamp", "row_hash", "created_at",
    ]
    return [
        {c: (str(v) if v is not None and c in ("created_at", "normalized_timestamp") else v) for c, v in zip(cols, row)}
        for row in rows
    ]


def select_live_rows(con: duckdb.DuckDBPyConnection) -> List[tuple]:
    return con.execute("SELECT lineage, created_at, ttl_seconds, is_locked FROM live_events").fetchall()


def query_cold(
    cfg: StorageConfig,
    *,
    target_user: str = "",
    source_type: str = "",
    time_start: str = "",
    time_end: str = "",
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Query cold Parquet storage. Uses S3 httpfs when enabled, local glob otherwise.
    Supports filtering by target_user, source_type, and time range.
    """
    if is_s3_enabled():
        return _query_cold_s3(
            target_user=target_user,
            source_type=source_type,
            time_start=time_start,
            time_end=time_end,
            limit=limit,
            offset=offset,
        )
    return _query_cold_local(
        cfg,
        target_user=target_user,
        source_type=source_type,
        time_start=time_start,
        time_end=time_end,
        limit=limit,
        offset=offset,
    )


def _query_cold_s3(
    *,
    target_user: str,
    source_type: str,
    time_start: str,
    time_end: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    bucket = os.getenv("S3_BUCKET_NAME", "")
    con = duckdb.connect(":memory:")
    try:
        configure_duckdb_s3(con)
    except Exception:
        con.close()
        return []

    glob_uri = f"s3://{bucket}/phase3/events/*/*.parquet"
    return _run_cold_query(con, glob_uri, target_user, source_type, time_start, time_end, limit, offset)


def _query_cold_local(
    cfg: StorageConfig,
    *,
    target_user: str,
    source_type: str,
    time_start: str,
    time_end: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    events_root = Path(cfg.cold_dir) / "events"
    if not events_root.is_dir():
        return []
    if not any(events_root.glob("*/*.parquet")):
        return []

    con = duckdb.connect(":memory:")
    glob_path = str(events_root / "*" / "*.parquet")
    return _run_cold_query(con, glob_path, target_user, source_type, time_start, time_end, limit, offset)


def _run_cold_query(
    con: duckdb.DuckDBPyConnection,
    source: str,
    target_user: str,
    source_type: str,
    time_start: str,
    time_end: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    """Shared query logic for both S3 and local cold storage."""
    conditions = []
    params: list = []

    if target_user:
        conditions.append("Target_User = ?")
        params.append(target_user)
    if source_type:
        conditions.append("source_type = ?")
        params.append(source_type)
    if time_start:
        conditions.append("COALESCE(normalized_timestamp, created_at) >= ?::TIMESTAMPTZ")
        params.append(time_start)
    if time_end:
        conditions.append("COALESCE(normalized_timestamp, created_at) <= ?::TIMESTAMPTZ")
        params.append(time_end)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([int(limit), int(offset)])

    sql = (
        "SELECT Target_User, Notes_Redacted AS Notes, Lineage, audit_id, "
        "source_type, extracted_variables, ner_tags, normalized_timestamp, row_hash, created_at "
        f"FROM read_parquet('{source}', union_by_name=True) "
        f"{where} "
        "ORDER BY created_at DESC "
        "LIMIT ? OFFSET ?"
    )

    try:
        rows = con.execute(sql, params).fetchall()
    except Exception:
        con.close()
        return []

    con.close()
    cols = [
        "Target_User", "Notes", "Lineage", "audit_id",
        "source_type", "extracted_variables", "ner_tags",
        "normalized_timestamp", "row_hash", "created_at",
    ]
    return [
        {c: (str(v) if v is not None and c in ("created_at", "normalized_timestamp") else v) for c, v in zip(cols, row)}
        for row in rows
    ]
