"""
DuckDB connection manager.

Each case has its own DuckDB file (Case Vault) located at
  data/cases/{case_id}/vault.duckdb

This module provides helpers to:
  • Create a new vault and initialise the schema.
  • Open an existing vault for read/write.
"""

import duckdb
import threading
import time
from contextlib import contextmanager
from collections import defaultdict
from typing import Any
from pathlib import Path
from operation_room.config import settings


_CASE_VAULT_LOCKS: dict[str, threading.RLock] = defaultdict(threading.RLock)
_LOCK_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2, 0.4, 0.8)
_CASE_CONNECTIONS: dict[str, duckdb.DuckDBPyConnection] = {}
_CASE_CONNECTION_REFS: dict[str, int] = defaultdict(int)


def _case_lock(case_id: str) -> threading.RLock:
    """Get the process-local lock for a case vault."""
    return _CASE_VAULT_LOCKS[case_id]


def _is_lock_conflict_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "database is locked" in message
        or "conflicting lock" in message
        or ("lock" in message and "held" in message)
    )


class SerializedVaultConnection:
    """DuckDB connection proxy that serializes access per case.

    DuckDB uses file-level locks for writes. This proxy enforces process-local
    mutual exclusion for all connection operations on the same case vault.
    """

    def __init__(self, case_id: str, conn: duckdb.DuckDBPyConnection):
        self._case_id = case_id
        self._conn = conn
        self._lock = _case_lock(case_id)
        self._closed = False

    def _run_with_lock_retry(self, operation):
        last_error = None
        for delay in (0.0, *_LOCK_RETRY_DELAYS_SECONDS):
            with self._lock:
                try:
                    return operation()
                except Exception as error:  # pragma: no cover - backend-specific lock surface
                    if not _is_lock_conflict_error(error):
                        raise
                    last_error = error
            if delay > 0:
                time.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected lock-retry execution path")

    def execute(self, query: str, parameters: Any = None):
        def _operation():
            if parameters is None:
                self._conn.execute(query)
            else:
                self._conn.execute(query, parameters)

        self._run_with_lock_retry(_operation)
        return self

    def executemany(self, query: str, parameters):
        self._run_with_lock_retry(lambda: self._conn.executemany(query, parameters))
        return self

    @contextmanager
    def transaction(self):
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION")
            try:
                yield self
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def fetchall(self):
        with self._lock:
            return self._conn.fetchall()

    def fetchone(self):
        with self._lock:
            return self._conn.fetchone()

    def close(self):
        if self._closed:
            return
        with self._lock:
            refs = _CASE_CONNECTION_REFS.get(self._case_id, 0)
            if refs > 0:
                refs -= 1
            _CASE_CONNECTION_REFS[self._case_id] = refs
            if refs == 0:
                conn = _CASE_CONNECTIONS.pop(self._case_id, None)
                _CASE_CONNECTION_REFS.pop(self._case_id, None)
                if conn is not None:
                    conn.close()
            self._closed = True

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def rollback(self):
        with self._lock:
            return self._conn.rollback()

    def __enter__(self):
        """Support context manager usage: with open_vault(case_id) as conn:"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection when exiting context manager."""
        self.close()
        return False  # Don't suppress exceptions

    def __getattr__(self, item):
        attr = getattr(self._conn, item)
        if not callable(attr):
            return attr

        def _locked_call(*args, **kwargs):
            with self._lock:
                return attr(*args, **kwargs)

        return _locked_call

# ── Schema DDL ───────────────────────────────────────────────────────────

SCHEMA_DDL = """
-- Case metadata (one row per case)
CREATE TABLE IF NOT EXISTS case_metadata (
    case_id          VARCHAR PRIMARY KEY,
    title            VARCHAR NOT NULL,
    description      VARCHAR,
    classification   VARCHAR DEFAULT 'UNCLASSIFIED',
    priority         VARCHAR DEFAULT 'MEDIUM',
    status           VARCHAR DEFAULT 'OPEN',
    lead_investigator VARCHAR NOT NULL,
    suspects         VARCHAR,          -- JSON array string
    investigation_reason VARCHAR,
    log_sources      VARCHAR,          -- JSON array string
    created_at       TIMESTAMP DEFAULT current_timestamp,
    updated_at       TIMESTAMP DEFAULT current_timestamp
);

-- Scope definition (multiple rows per case — one per scope entry)
CREATE TABLE IF NOT EXISTS scope_definition (
    scope_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    source_type      VARCHAR NOT NULL,  -- AUTH, VPN, FW, DB, APP, EPP, FILE
    time_start       TIMESTAMP,
    time_end         TIMESTAMP,
    target_actors    VARCHAR,           -- JSON array string
    target_systems   VARCHAR,           -- JSON array string
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Imported raw events
CREATE TABLE IF NOT EXISTS raw_events (
    event_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    import_batch_id  VARCHAR NOT NULL,
    source_type      VARCHAR,
    timestamp        TIMESTAMP,
    source_system    VARCHAR,
    actor            VARCHAR,
    action           VARCHAR,
    target           VARCHAR,
    detail           VARCHAR,          -- JSON string
    imported_at      TIMESTAMP DEFAULT current_timestamp
);

-- Evidence hashes
CREATE TABLE IF NOT EXISTS evidence_hashes (
    hash_id          VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    import_batch_id  VARCHAR,
    artefact_name    VARCHAR NOT NULL,
    artefact_type    VARCHAR DEFAULT 'QUERY_RESULT',
    hash_algorithm   VARCHAR DEFAULT 'SHA-256',
    hash_value       VARCHAR NOT NULL,
    record_count     INTEGER,
    byte_size        BIGINT,
    created_at       TIMESTAMP DEFAULT current_timestamp,
    created_by       VARCHAR NOT NULL
);

ALTER TABLE evidence_hashes ADD COLUMN IF NOT EXISTS import_batch_id VARCHAR;

-- Chain of custody (append-only)
CREATE TABLE IF NOT EXISTS chain_of_custody (
    event_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    timestamp        TIMESTAMP DEFAULT current_timestamp,
    actor            VARCHAR NOT NULL,
    action           VARCHAR NOT NULL,
    target_artefact  VARCHAR NOT NULL,
    justification    VARCHAR,
    hash_before      VARCHAR,
    hash_after       VARCHAR,
    details          VARCHAR           -- JSON string for extra context
);

-- Unified timeline (normalised, merged events)
CREATE TABLE IF NOT EXISTS unified_timeline (
    tl_event_id      VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    original_event_id VARCHAR,
    normalised_ts    TIMESTAMP NOT NULL,
    utc_offset       VARCHAR DEFAULT '+00:00',
    source_type      VARCHAR,
    source_system    VARCHAR,
    actor            VARCHAR,
    action           VARCHAR,
    target           VARCHAR,
    severity         VARCHAR DEFAULT 'INFO',
    detail           VARCHAR,
    cluster_id       INTEGER,
    is_time_stomped  BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

  -- Backward compat
  ALTER TABLE unified_timeline ADD COLUMN IF NOT EXISTS cluster_id INTEGER;
  ALTER TABLE unified_timeline ADD COLUMN IF NOT EXISTS is_time_stomped BOOLEAN DEFAULT FALSE;  ALTER TABLE unified_timeline ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN DEFAULT FALSE;
  ALTER TABLE unified_timeline ADD COLUMN IF NOT EXISTS anchor_label VARCHAR;
-- Temporal clusters (DBSCAN mathematical density mapping)
CREATE TABLE IF NOT EXISTS temporal_clusters (
    cluster_id       VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    cluster_number   INTEGER NOT NULL,
    start_ts         TIMESTAMP,
    end_ts           TIMESTAMP,
    event_count      INTEGER,
    dominant_action  VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Legacy anchor events (Deprecated, but keeping for backward compatibility in migrations)
CREATE TABLE IF NOT EXISTS anchor_events (
    anchor_id        VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    tl_event_id      VARCHAR,
    label            VARCHAR NOT NULL,
    auto_detected    BOOLEAN DEFAULT TRUE,
    created_by       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Anomaly detection runs (one row per pipeline execution)
CREATE TABLE IF NOT EXISTS anomaly_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    model_type       VARCHAR NOT NULL,       -- 'IsolationForest', 'LOF', 'ensemble'
    model_params     VARCHAR,                -- JSON string of parameters
    source_filters   VARCHAR,                -- JSON array of source types used
    contamination    DOUBLE DEFAULT 0.1,
    total_events     INTEGER,
    anomaly_count    INTEGER,
    summary_json     VARCHAR,                -- JSON aggregated report
    hash_value       VARCHAR,
    version          INTEGER DEFAULT 1,
    status           VARCHAR DEFAULT 'RUNNING',  -- RUNNING, COMPLETED, FAILED
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP,
    created_by       VARCHAR DEFAULT 'analyst'
);

ALTER TABLE anomaly_runs ADD COLUMN IF NOT EXISTS context_status VARCHAR;
ALTER TABLE anomaly_runs ADD COLUMN IF NOT EXISTS context_started_at TIMESTAMP;
ALTER TABLE anomaly_runs ADD COLUMN IF NOT EXISTS context_completed_at TIMESTAMP;
ALTER TABLE anomaly_runs ADD COLUMN IF NOT EXISTS context_error VARCHAR;

-- Per-event anomaly scores
CREATE TABLE IF NOT EXISTS anomaly_scores (
    score_id         VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    tl_event_id      VARCHAR,                -- FK to unified_timeline
    anomaly_score    DOUBLE NOT NULL,         -- raw score from model
    normalised_score DOUBLE,                  -- 0..1 scaled score
    is_anomaly       BOOLEAN DEFAULT FALSE,
    model_type       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Sequence-level anomaly context findings
CREATE TABLE IF NOT EXISTS sequence_anomalies (
    sequence_id           VARCHAR PRIMARY KEY,
    run_id                VARCHAR,
    case_id               VARCHAR,
    actor                 VARCHAR,
    sequence_string       VARCHAR,
    transformer_confidence DOUBLE NOT NULL,
    created_at            TIMESTAMP DEFAULT current_timestamp
);

-- Correlation runs
CREATE TABLE IF NOT EXISTS correlation_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    params_json      VARCHAR,
    llm_provider     VARCHAR DEFAULT 'ollama',
    total_nodes      INTEGER DEFAULT 0,
    total_edges      INTEGER DEFAULT 0,
    status           VARCHAR DEFAULT 'RUNNING',
    hash_value       VARCHAR,
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP,
    created_by       VARCHAR DEFAULT 'analyst'
);

-- Entity graph nodes (users, IPs, hosts, sessions, data objects)
CREATE TABLE IF NOT EXISTS correlation_nodes (
    node_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    entity_type      VARCHAR NOT NULL,       -- USER, IP, HOST, SESSION, PROCESS, DATA_OBJECT
    entity_value     VARCHAR NOT NULL,
    severity_score   DOUBLE DEFAULT 0,
    anomaly_score    DOUBLE DEFAULT 0,
    event_count      INTEGER DEFAULT 0,
    first_seen       TIMESTAMP,
    last_seen        TIMESTAMP,
    metadata_json    VARCHAR
);

-- Entity graph edges (relationships between nodes)
CREATE TABLE IF NOT EXISTS correlation_edges (
    edge_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    source_node_id   VARCHAR,
    target_node_id   VARCHAR,
    relationship     VARCHAR NOT NULL,       -- AUTHENTICATED_FROM, ACCESSED, INITIATED, CONNECTED_VIA, etc.
    weight           DOUBLE DEFAULT 1.0,
    evidence_count   INTEGER DEFAULT 1,
    evidence_ids     VARCHAR,                -- JSON array of tl_event_ids
    first_seen       TIMESTAMP,
                last_seen        TIMESTAMP,
                confidence_score DOUBLE DEFAULT 1.0,
                join_reason      VARCHAR,
    llm_provider     VARCHAR,
    hash_value       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Agent chat logs (audit trail)
CREATE TABLE IF NOT EXISTS agent_chat_logs (
    log_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    run_id           VARCHAR,
    user_query       VARCHAR NOT NULL,
    agent_response   VARCHAR,
    llm_provider     VARCHAR,
    context_used     VARCHAR,                -- JSON
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Pluggable correlation rules
CREATE TABLE IF NOT EXISTS correlation_rules (
    rule_id          VARCHAR PRIMARY KEY,
    name             VARCHAR NOT NULL,
    description      VARCHAR,
    join_field        VARCHAR NOT NULL,       -- actor, source_ip, session_id, target, etc.
    window_seconds   INTEGER DEFAULT 300,    -- time window for correlation
    enabled          BOOLEAN DEFAULT TRUE,
    priority         INTEGER DEFAULT 5,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- CRUD analysis runs
CREATE TABLE IF NOT EXISTS crud_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    params_json      VARCHAR,
    total_events     INTEGER DEFAULT 0,
    crud_counts      VARCHAR,                -- JSON {"C":n,"R":n,"U":n,"D":n}
    high_risk_count  INTEGER DEFAULT 0,
    status           VARCHAR DEFAULT 'RUNNING',
    hash_value       VARCHAR,
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP
);

-- Per-event CRUD classification
CREATE TABLE IF NOT EXISTS crud_events (
    crud_event_id    VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    tl_event_id      VARCHAR,
    crud_type        VARCHAR NOT NULL,       -- CREATE, READ, UPDATE, DELETE
    target_object    VARCHAR,
    sensitivity      VARCHAR DEFAULT 'LOW',  -- LOW, MEDIUM, HIGH, CRITICAL
    volume_bytes     BIGINT DEFAULT 0,
    row_count        INTEGER DEFAULT 0,
    is_high_risk     BOOLEAN DEFAULT FALSE,
    risk_reason      VARCHAR,
    anomaly_score    DOUBLE DEFAULT 0,
    actor            VARCHAR,
    source_type      VARCHAR,
    normalised_ts    TIMESTAMP,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Aggregated CRUD summaries (user × object × operation)
CREATE TABLE IF NOT EXISTS crud_summary (
    summary_id       VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    actor            VARCHAR,
    target_object    VARCHAR,
    crud_type        VARCHAR,
    event_count      INTEGER DEFAULT 0,
    total_bytes      BIGINT DEFAULT 0,
    total_rows       INTEGER DEFAULT 0,
    avg_anomaly      DOUBLE DEFAULT 0,
    max_sensitivity  VARCHAR DEFAULT 'LOW',
    high_risk_count  INTEGER DEFAULT 0,
    first_seen       TIMESTAMP,
    last_seen        TIMESTAMP
);

-- ── Network & Exfiltration Analysis ─────────────────────────

-- Network analysis runs
CREATE TABLE IF NOT EXISTS network_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    params_json      VARCHAR,
    total_flows      INTEGER DEFAULT 0,
    suspicious_count INTEGER DEFAULT 0,
    exfil_candidates INTEGER DEFAULT 0,
    total_bytes_out  BIGINT DEFAULT 0,
    status           VARCHAR DEFAULT 'RUNNING',
    hash_value       VARCHAR,
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP
);

-- Parsed network flows
CREATE TABLE IF NOT EXISTS network_flows (
    flow_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    tl_event_id      VARCHAR,
    src_ip           VARCHAR,
    src_port         INTEGER,
    dst_ip           VARCHAR,
    dst_port         INTEGER,
    protocol         VARCHAR,
    bytes_sent       BIGINT DEFAULT 0,
    bytes_received   BIGINT DEFAULT 0,
    duration_secs    DOUBLE DEFAULT 0,
    direction        VARCHAR,
    actor            VARCHAR,
    source_system    VARCHAR,
    log_source       VARCHAR,
    is_suspicious    BOOLEAN DEFAULT FALSE,
    suspicion_reason VARCHAR,
    threat_score     DOUBLE DEFAULT 0,
    threat_intel     VARCHAR,
    anomaly_score    DOUBLE DEFAULT 0,
    normalised_ts    TIMESTAMP,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Exfiltration candidates (correlated flow + CRUD)
CREATE TABLE IF NOT EXISTS exfil_candidates (
    exfil_id         VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    flow_id          VARCHAR,
    crud_event_id    VARCHAR,
    actor            VARCHAR,
    data_target      VARCHAR,
    dst_ip           VARCHAR,
    bytes_crud       BIGINT DEFAULT 0,
    bytes_network    BIGINT DEFAULT 0,
    time_delta_secs  DOUBLE DEFAULT 0,
    confidence       DOUBLE DEFAULT 0,
    evidence_summary VARCHAR,
    normalised_ts    TIMESTAMP
);

-- Destination risk summary
CREATE TABLE IF NOT EXISTS destination_summary (
    summary_id       VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    dst_ip           VARCHAR,
    total_flows      INTEGER DEFAULT 0,
    total_bytes_out  BIGINT DEFAULT 0,
    unique_actors    INTEGER DEFAULT 0,
    protocols        VARCHAR,
    is_known_bad     BOOLEAN DEFAULT FALSE,
    threat_intel     VARCHAR,
    max_threat_score DOUBLE DEFAULT 0,
    first_seen       TIMESTAMP,
    last_seen        TIMESTAMP
);

-- ── Depth & Impact Assessment ───────────────────────────────

-- Depth analysis runs
CREATE TABLE IF NOT EXISTS depth_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    params_json      VARCHAR,
    account_depth    DOUBLE DEFAULT 0,
    system_depth     DOUBLE DEFAULT 0,
    data_depth       DOUBLE DEFAULT 0,
    control_depth    DOUBLE DEFAULT 0,
    overall_severity DOUBLE DEFAULT 0,
    severity_label   VARCHAR DEFAULT 'LOW',
    llm_provider     VARCHAR,
    status           VARCHAR DEFAULT 'RUNNING',
    hash_value       VARCHAR,
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP
);

-- Per-dimension detail rows
CREATE TABLE IF NOT EXISTS depth_details (
    detail_id        VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    dimension        VARCHAR,
    metric_name      VARCHAR,
    metric_value     DOUBLE DEFAULT 0,
    max_value        DOUBLE DEFAULT 10,
    evidence         VARCHAR,
    normalised_ts    TIMESTAMP DEFAULT current_timestamp
);

-- AI impact narrative
CREATE TABLE IF NOT EXISTS impact_narratives (
    narrative_id     VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    narrative_text   VARCHAR,
    remediation      VARCHAR,
    executive_summary VARCHAR,
    llm_provider     VARCHAR,
    hash_value       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- ── Augment Studio & Report Writer ──────────────────────────

-- Saved studio chart specifications
CREATE TABLE IF NOT EXISTS studio_charts (
    chart_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    chart_type       VARCHAR,          -- bar, line, pie, scatter, radar, heatmap
    title            VARCHAR,
    dataset          VARCHAR,          -- timeline, crud, network, anomaly, correlation, depth
    config_json      VARCHAR,          -- full chart config
    data_snapshot    VARCHAR,          -- aggregated data snapshot
    hash_value       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp,
    updated_at       TIMESTAMP DEFAULT current_timestamp
);

-- Report drafts
CREATE TABLE IF NOT EXISTS report_drafts (
    report_id        VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    template         VARCHAR DEFAULT 'technical',
    title            VARCHAR,
    status           VARCHAR DEFAULT 'DRAFT',
    sections_json    VARCHAR,          -- ordered section list
    metadata_json    VARCHAR,          -- case meta, time range, etc.
    llm_provider     VARCHAR,
    hash_value       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp,
    updated_at       TIMESTAMP DEFAULT current_timestamp
);

-- Report sections
CREATE TABLE IF NOT EXISTS report_sections (
    section_id       VARCHAR PRIMARY KEY,
    report_id        VARCHAR,
    case_id          VARCHAR,
    section_key      VARCHAR,          -- exec_summary, timeline, attack_chain, etc.
    section_title    VARCHAR,
    content          VARCHAR,          -- Markdown content
    chart_ids        VARCHAR,          -- JSON array of chart_ids to embed
    sort_order       INTEGER DEFAULT 0,
    is_ai_generated  BOOLEAN DEFAULT FALSE,
    hash_value       VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- ML Contextual Feedback Loop (threat_intel)
CREATE TABLE IF NOT EXISTS threat_intel (
    intel_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    category         VARCHAR NOT NULL, -- e.g., 'ignore_actor', 'ignore_action'
    value            VARCHAR NOT NULL,
    justification    VARCHAR,
    added_by         VARCHAR,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- ── Data Exfiltration Intelligence Module ───────────────────

-- Exfiltration analysis run metadata
CREATE TABLE IF NOT EXISTS exfil_intel_runs (
    run_id           VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    params_json      VARCHAR,
    total_incidents  INTEGER DEFAULT 0,
    high_risk_count  INTEGER DEFAULT 0,
    affected_actors  INTEGER DEFAULT 0,
    affected_devices INTEGER DEFAULT 0,
    total_bytes_out  BIGINT DEFAULT 0,
    overall_risk     VARCHAR DEFAULT 'LOW',
    status           VARCHAR DEFAULT 'RUNNING',
    hash_value       VARCHAR,
    started_at       TIMESTAMP DEFAULT current_timestamp,
    completed_at     TIMESTAMP
);

-- Configurable detection thresholds (DB-driven, not hardcoded)
CREATE TABLE IF NOT EXISTS exfil_intel_config (
    config_id        VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    engine           VARCHAR NOT NULL,
    param_name       VARCHAR NOT NULL,
    param_value      DOUBLE NOT NULL,
    description      VARCHAR,
    updated_at       TIMESTAMP DEFAULT current_timestamp
);

-- Behaviour graph nodes (User, File, Device, IP, Application)
CREATE TABLE IF NOT EXISTS exfil_graph_nodes (
    node_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    node_type        VARCHAR NOT NULL,
    node_value       VARCHAR NOT NULL,
    event_count      INTEGER DEFAULT 0,
    risk_score       DOUBLE DEFAULT 0,
    first_seen       TIMESTAMP,
    last_seen        TIMESTAMP,
    metadata_json    VARCHAR
);

-- Behaviour graph edges (READ, WRITE, CONNECT, SEND)
CREATE TABLE IF NOT EXISTS exfil_graph_edges (
    edge_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    source_node_id   VARCHAR,
    target_node_id   VARCHAR,
    relationship     VARCHAR NOT NULL,
    weight           DOUBLE DEFAULT 1.0,
    evidence_count   INTEGER DEFAULT 1,
    evidence_ids     VARCHAR,
    first_seen       TIMESTAMP,
    last_seen        TIMESTAMP
);

-- Detected exfiltration incidents (one per data-flow chain)
CREATE TABLE IF NOT EXISTS exfil_intel_incidents (
    incident_id      VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    actor            VARCHAR,
    channel          VARCHAR,
    data_target      VARCHAR,
    dst_ip           VARCHAR,
    bytes_accessed   BIGINT DEFAULT 0,
    bytes_exfil      BIGINT DEFAULT 0,
    confidence       DOUBLE DEFAULT 0,
    risk_category    VARCHAR DEFAULT 'LOW',
    intent_score     DOUBLE DEFAULT 0,
    is_ghost         BOOLEAN DEFAULT FALSE,
    is_staged        BOOLEAN DEFAULT FALSE,
    explanation      VARCHAR,
    contributing_factors VARCHAR,
    timeline_json    VARCHAR,
    normalised_ts    TIMESTAMP,
    created_at       TIMESTAMP DEFAULT current_timestamp
);

-- Channel distribution stats per run
CREATE TABLE IF NOT EXISTS exfil_channel_stats (
    stat_id          VARCHAR PRIMARY KEY,
    run_id           VARCHAR,
    case_id          VARCHAR,
    channel          VARCHAR NOT NULL,
    incident_count   INTEGER DEFAULT 0,
    total_bytes      BIGINT DEFAULT 0,
    avg_confidence   DOUBLE DEFAULT 0,
    actors           VARCHAR
);
"""

def _get_shared_connection(case_id: str, path: Path) -> duckdb.DuckDBPyConnection:
    """Get or create a shared DuckDB connection for a case."""
    with _case_lock(case_id):
        if case_id not in _CASE_CONNECTIONS:
            # Retry loop to survive Uvicorn graceful reload overlap
            max_retries = 20
            delay = 0.5
            conn = None
            last_err = None
            
            for attempt in range(max_retries):
                try:
                    conn = duckdb.connect(str(path), config={'threads': 1})
                    break
                except duckdb.IOException as e:
                    last_err = e
                    if "already open" in str(e) or "lock" in str(e).lower():
                        import time
                        time.sleep(delay)
                        continue
                    raise
            
            if conn is None:
                raise RuntimeError(f"Failed to acquire DuckDB lock for {case_id} after {max_retries * delay}s: {last_err}")
                
            conn.execute(SCHEMA_DDL)
            _CASE_CONNECTIONS[case_id] = conn
        return _CASE_CONNECTIONS[case_id]


def _vault_path(case_id: str) -> Path:
    """
    Return the filesystem path for a case's DuckDB vault.
    
    CRITICAL: This is the single source of truth for vault file naming.
    All code must use this function instead of constructing paths directly.
    """
    return settings.CASES_DIR / case_id / "vault.duckdb"


def get_vault_path(case_id: str) -> Path:
    """
    Public API to get vault path for a case.
    
    Use this instead of manually constructing "vault.db" or "vault.duckdb" paths.
    """
    return _vault_path(case_id)


def create_vault(case_id: str) -> SerializedVaultConnection:
    """Create a new Case Vault and initialise its schema."""
    vault_dir = settings.CASES_DIR / case_id
    vault_dir.mkdir(parents=True, exist_ok=True)
    path = _vault_path(case_id)
    conn = _get_shared_connection(case_id, path)
    with _case_lock(case_id):
        _CASE_CONNECTION_REFS[case_id] += 1
    return SerializedVaultConnection(case_id, conn)


def open_vault(case_id: str) -> SerializedVaultConnection:
    """Open an existing Case Vault.  Raises FileNotFoundError if missing."""
    path = _vault_path(case_id)
    if not path.exists():
        raise FileNotFoundError(f"No vault found for case {case_id}")
    conn = _get_shared_connection(case_id, path)
    with _case_lock(case_id):
        _CASE_CONNECTION_REFS[case_id] += 1
    return SerializedVaultConnection(case_id, conn)


def vault_exists(case_id: str) -> bool:
    """Check whether a vault file exists for the given case."""
    return _vault_path(case_id).exists()

def close_vault(case_id: str) -> None:
    """Close and remove a shared DuckDB connection for a case."""
    with _case_lock(case_id):
        if case_id in _CASE_CONNECTIONS:
            _CASE_CONNECTIONS[case_id].close()
            del _CASE_CONNECTIONS[case_id]
        _CASE_CONNECTION_REFS.pop(case_id, None)
def close_all_vaults() -> None:
    for case_id in list(_CASE_CONNECTIONS.keys()):
        close_vault(case_id)
