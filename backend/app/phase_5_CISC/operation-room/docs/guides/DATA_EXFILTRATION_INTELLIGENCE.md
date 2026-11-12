# Data Exfiltration Intelligence — Complete Technical Reference

> **Module location**: `operation-room/backend/app/services/exfiltration_agent.py` (backend) · `operation-room/frontend/src/app/(main)/cases/[id]/exfiltration/page.js` (frontend)
> **API routes**: `operation-room/backend/app/routes/exfiltration.py`
> **Database**: 6 DuckDB tables (per-case vault)

---

## Table of Contents

1. [What It Does](#1-what-it-does)
2. [Architecture Overview](#2-architecture-overview)
3. [The 9-Engine Pipeline](#3-the-9-engine-pipeline)
4. [Database Schema (6 Tables)](#4-database-schema-6-tables)
5. [REST API Endpoints (7 Routes)](#5-rest-api-endpoints-7-routes)
6. [Frontend Tabs (8 Views)](#6-frontend-tabs-8-views)
7. [How to Use It](#7-how-to-use-it)
8. [Configuration & Tuning](#8-configuration--tuning)
9. [Scoring Model Explained](#9-scoring-model-explained)
10. [Detection Techniques Deep Dive](#10-detection-techniques-deep-dive)
11. [Data Flow Through the System](#11-data-flow-through-the-system)
12. [Limitations & Known Gaps](#12-limitations--known-gaps)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. What It Does

The Data Exfiltration Intelligence module is a **production-grade forensic analysis feature** that detects, scores, and visualises data exfiltration attempts from ingested forensic case logs. It answers the core question:

> *"Did anyone move sensitive data out of this environment, through what channel, and how confident are we?"*

It does this by running a **9-engine sequential pipeline** that:

- Normalises heterogeneous log events into a unified schema
- Constructs a directed **behaviour graph** (User → File → Device → IP)
- Detects **READ → SEND data flow chains** with time-window correlation
- Clusters activity across **6 exfiltration channels** (USB, Email, Cloud, Web, Bluetooth, Inferred)
- Scores each actor's **exfiltration intent** via behavioural signals
- Detects **ghost transfers** — inferred exfiltration without direct transfer logs
- Detects **staging activity** — compression/encryption before transfer
- Produces a **composite risk score** per incident (0–1 confidence, CRITICAL/HIGH/MEDIUM/LOW)
- Generates **explainable AI** reasoning with human-readable contributing factors

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 14)               │
│                                                        │
│  ExfiltrationPage (page.js)                            │
│  ├── PipelineStepper ← SSE stream (EventSource)       │
│  ├── ForceGraph ← Canvas 2D + force simulation         │
│  ├── CinematicTimeline ← day-grouped cards             │
│  ├── Overview dashboard ← Recharts (Area/Pie/Bar)      │
│  ├── Incidents list ← filterable + expandable           │
│  ├── Channels breakdown                                 │
│  ├── Risk Heatmap                                       │
│  ├── Novelty Showcase                                   │
│  └── Runs history table                                 │
│                                                        │
│  API calls via: /api/cases/{id}/exfiltration/*          │
└───────────────────────┬───────────────────────────────┘
                        │ HTTP (Next.js rewrite → :8001)
┌───────────────────────▼───────────────────────────────┐
│                   BACKEND (FastAPI)                     │
│                                                        │
│  routes/exfiltration.py — 7 endpoints                  │
│  services/exfiltration_agent.py — 9 engines + queries  │
│                                                        │
│  Data pipeline:                                        │
│  unified_timeline → normalise → graph → flows →        │
│  channels → intent → ghosts → staging → score →        │
│  explain → persist to DuckDB                           │
└───────────────────────┬───────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────┐
│               DuckDB (per-case vault)                  │
│                                                        │
│  INPUT TABLES (pre-existing):                          │
│  · unified_timeline — normalised log events            │
│  · anomaly_scores — ML anomaly run results             │
│  · crud_events — data sensitivity classification       │
│                                                        │
│  OUTPUT TABLES (this module writes):                   │
│  · exfil_intel_runs — run metadata & summary           │
│  · exfil_intel_config — per-engine tuning params       │
│  · exfil_graph_nodes — behaviour graph vertices        │
│  · exfil_graph_edges — behaviour graph relationships   │
│  · exfil_intel_incidents — scored detection results     │
│  · exfil_channel_stats — per-channel aggregates        │
│                                                        │
│  AUDIT:                                                │
│  · chain_of_custody — forensic integrity log           │
└───────────────────────────────────────────────────────┘
```

### Dependencies Between Modules

| Prerequisite            | Required? | What It Provides                                |
|-------------------------|-----------|-------------------------------------------------|
| **Timeline built**      | YES       | `unified_timeline` table with normalised events |
| **Anomaly run**         | Optional  | ML anomaly scores feed into composite scoring   |
| **CRUD run**            | Optional  | Data sensitivity labels improve risk scoring    |

Without Timeline data, the pipeline will produce 0 events. Anomaly and CRUD data enrich scoring but are not mandatory.

---

## 3. The 9-Engine Pipeline

Each engine executes sequentially. The pipeline takes ~1–5 seconds depending on data volume.

### Engine 1: Normalisation

**Function**: `_normalise(conn, case_id)`

Pulls all rows from `unified_timeline` and maps them into a flat internal schema:

| Field       | Source                                             |
|-------------|----------------------------------------------------|
| `id`        | `tl_event_id`                                      |
| `timestamp` | `normalised_ts`                                    |
| `actor`     | `actor` column                                     |
| `action`    | `action` column                                    |
| `file_name` | Extracted from `target` or `detail` JSON           |
| `src`       | `detail.source_ip`                                 |
| `dst`       | `detail.destination_ip` or `detail.dest_ip`        |
| `bytes`     | `detail.bytes` or `detail.response_bytes`          |
| `severity`  | `severity` column                                  |

**Output**: A flat `list[dict]` of normalised events used by all downstream engines.

---

### Engine 2: Behaviour Graph

**Function**: `_build_graph(events)`

Constructs a **directed interaction graph** with 5 node types and 7 edge types.

**Node types**:

| Type        | Created when                              | Example value              |
|-------------|-------------------------------------------|----------------------------|
| `USER`      | `actor` field is present                  | `admin`, `jdoe`            |
| `FILE`      | `file_name` contains `/` path separator   | `/data/exports/report.csv` |
| `DEVICE`    | `device_type` (source system) is present  | `syslog`, `epp_log`        |
| `IP`        | `src` or `dst` is an external IP          | `185.220.101.42`           |
| `APPLICATION` | (reserved for future enrichment)        | —                          |

**Edge types** (relationship between nodes):

| Edge              | Meaning                           | Trigger actions                  |
|-------------------|-----------------------------------|----------------------------------|
| `READ`            | Actor read a file/resource        | SELECT, FILE_READ, HTTP_GET      |
| `WRITE`           | Actor wrote/modified data         | INSERT, FILE_WRITE, FILE_COPY    |
| `SEND`            | Data sent to external destination | UPLOAD, HTTP_POST, VPN_CONNECT   |
| `CONNECT`         | Actor connected to an external IP | Any event with external `dst`    |
| `USED`            | Actor used a device/system        | Any event with `device_type`     |
| `AUTHENTICATED_FROM` | Source IP authenticated as actor | Event has `src` and `actor`   |
| `INTERACT`        | Catch-all for other actions       | Any action not in above groups   |

Each node tracks `event_count`, `first_seen`, `last_seen`, and `risk_score`.
Each edge tracks `weight`, `evidence_count`, and a JSON array of `evidence_ids` linking back to original events.

---

### Engine 3: Data Flow Detection

**Function**: `_detect_data_flows(events, config)`

Detects **READ → SEND/WRITE chains** that indicate data movement:

1. Groups events by `actor`
2. For each actor, finds all READ events and SEND/WRITE events with external destinations
3. Pairs every READ with every subsequent SEND within `window_secs` (default: **1800 seconds / 30 minutes**)
4. Filters pairs where `bytes_read >= min_bytes` OR `bytes_sent >= min_bytes` (default: **50,000 bytes / ~50 KB**)

Each detected flow captures: actor, read event, send event, time delta, bytes, channel, and destination IP.

**Channel classification**: Each flow is classified into a channel by scanning event JSON for keywords:

| Channel     | Keywords                                          |
|-------------|---------------------------------------------------|
| `USB`       | usb, removable, /media/usb                        |
| `EMAIL`     | smtp, email, outlook, exchange, mail              |
| `CLOUD`     | s3, onedrive, dropbox, gdrive, sharepoint, blob   |
| `BLUETOOTH` | bluetooth, bt:, obex                              |
| `WEB`       | http, https, 443, web, upload                     |
| `UNKNOWN`   | Fallback when no keyword matches                  |

---

### Engine 4: Multi-Channel Correlation

**Function**: `_correlate_channels(data_flows, config)`

Groups data flows by actor into **temporal clusters**:

1. Sorts each actor's flows by send timestamp
2. Groups consecutive flows within `window_secs` (default: **600 seconds / 10 minutes**) into clusters
3. Records which channels appear in each cluster

This detects actors who use **multiple exfiltration channels** within a short window (e.g., USB + Web + Email), which is a strong exfiltration signal.

---

### Engine 5: Intent Detection

**Function**: `_detect_intent(events, data_flows, config)`

Scores each actor's **exfiltration intent** from 0.0 to 1.0 using 4 weighted behavioural signals:

| Signal          | Weight | How it's calculated                                                                       |
|-----------------|--------|-------------------------------------------------------------------------------------------|
| `bulk_access`   | 0.30   | `min(1.0, read_count / (bulk_threshold × 10))` — how many files the actor read            |
| `off_hours`     | 0.25   | Ratio of events outside 07:00–18:00 (configurable), doubled for sensitivity               |
| `new_device`    | 0.20   | `min(1.0, (unique_devices − 2) / 3)` — actors using more than 2 device types are flagged  |
| `staging`       | 0.25   | Binary: 1.0 if actor has data flows or touched staging-extension files, else 0.0           |

**Formula**: `intent = w_bulk × bulk + w_offhours × offhours + w_new_device × new_device + w_staging × staging`

---

### Engine 6: Ghost Transfer Detection

**Function**: `_detect_ghost_transfers(events, data_flows, config)`

Detects **inferred exfiltration** where no direct transfer was logged:

1. Finds READ events that are **not already part of a detected data flow**
2. For each orphan READ, checks if there is **no local WRITE** within `max_gap_secs` (default: 3600s)
3. If no local write exists, checks for **outbound network activity** within the same window
4. If outbound traffic exists → flags as a **ghost transfer** with a reasoning string

Ghost transfers are especially forensically interesting because they indicate the actor may have used a tool or method that bypasses standard file-write logging.

---

### Engine 7: Staging Detection

**Function**: `_detect_staging(events)`

Detects **pre-exfiltration preparation** by scanning for:

1. **Staging file extensions**: `.zip`, `.tar`, `.gz`, `.7z`, `.rar`, `.enc`, `.locked`, `.crypt`, `.gpg`, `.aes` being written or created
2. **Staging tool processes**: `7z.exe`, `zip.exe`, `tar`, `gzip`, `rar.exe`, `gpg`, `openssl` appearing in event metadata
3. **EPP quarantine events**: Endpoint protection blocking archiver tools (event `action` = QUARANTINE/PROCESS_BLOCKED with "archiver" in threat name)

---

### Engine 8: Scoring

**Function**: `_score_incidents(data_flows, ghost_transfers, staging, intent_scores, anomaly_lookup, sensitivity_lookup, config)`

Produces a **composite confidence score (0–1)** for every incident using 4 weighted signals:

| Signal          | Weight | Source                                                                     |
|-----------------|--------|----------------------------------------------------------------------------|
| `flow_signal`   | 0.30   | `min(1.0, (bytes_read + bytes_sent) / 5,000,000)` — data volume           |
| `intent`        | 0.25   | Actor's intent score from Engine 5                                         |
| `anomaly`       | 0.20   | Max anomaly score from ML anomaly run (0 if no anomaly run exists)         |
| `sensitivity`   | 0.25   | Target sensitivity: LOW=0.1, MEDIUM=0.4, HIGH=0.7, CRITICAL=1.0           |

**Risk categorisation**:

| Confidence    | Risk Level |
|---------------|------------|
| ≥ 0.75        | CRITICAL   |
| ≥ 0.50        | HIGH       |
| ≥ 0.25        | MEDIUM     |
| < 0.25        | LOW        |

Ghost transfers receive a fixed base confidence: `0.3 + 0.3×intent + 0.2×anomaly + 0.2×(staging? 1 : 0)`.

---

### Engine 9: Explainable AI

**Function**: `_explain_incidents(incidents, staging, ghost_transfers)`

Attaches three output fields to each incident:

1. **`explanation`** — Single human-readable sentence summarising all contributing factors
2. **`contributing_factors`** — JSON array of individual factor strings, e.g.:
   - "Large data movement detected (500000B read → 200000B sent)"
   - "High behavioural intent score (0.65): bulk access, off-hours, or new devices"
   - "Ghost transfer: Actor read file but no local write logged"
   - "Staging activity: File 'archive.zip' written with staging extension '.zip'"
   - "Exfiltration channel: EMAIL"
3. **`timeline_json`** — JSON array of event chain steps with timestamps:
   - Step 1: "Data Access" — what was read
   - Step 2: "Transfer" — where it was sent and via what channel

---

## 4. Database Schema (6 Tables)

All tables are created in the per-case DuckDB vault (`data/cases/{case_id}/vault.duckdb`).

### `exfil_intel_runs`
Stores metadata for each pipeline execution.

| Column            | Type      | Description                              |
|-------------------|-----------|------------------------------------------|
| `run_id`          | VARCHAR PK| UUID for this analysis run               |
| `case_id`         | VARCHAR   | Parent case ID                           |
| `params_json`     | VARCHAR   | Input parameters (source_filters, etc.)  |
| `total_incidents`  | INTEGER  | Number of incidents detected             |
| `high_risk_count`  | INTEGER  | Incidents rated HIGH or CRITICAL         |
| `affected_actors`  | INTEGER  | Unique actors involved                   |
| `affected_devices` | INTEGER  | Unique external destinations             |
| `total_bytes_out`  | BIGINT   | Sum of bytes exfiltrated                 |
| `overall_risk`     | VARCHAR  | CRITICAL, HIGH, MEDIUM, or LOW           |
| `status`           | VARCHAR  | RUNNING, COMPLETED, or FAILED            |
| `hash_value`       | VARCHAR  | SHA-256 of canonical incident JSON       |
| `started_at`       | TIMESTAMP| Pipeline start time                      |
| `completed_at`     | TIMESTAMP| Pipeline completion time                 |

### `exfil_intel_config`
Per-engine tuning parameters (optional — defaults used if empty).

| Column        | Type    | Description                |
|---------------|---------|----------------------------|
| `config_id`   | VARCHAR PK | UUID                    |
| `case_id`     | VARCHAR | Parent case ID             |
| `engine`      | VARCHAR | Engine name (e.g. "data_flow") |
| `param_name`  | VARCHAR | Parameter key              |
| `param_value` | DOUBLE  | Parameter value            |
| `description` | VARCHAR | Human description          |

### `exfil_graph_nodes`
Behaviour graph vertices.

| Column         | Type    | Description                    |
|----------------|---------|--------------------------------|
| `node_id`      | VARCHAR PK | UUID                        |
| `run_id`       | VARCHAR | Analysis run                   |
| `case_id`      | VARCHAR | Parent case                    |
| `node_type`    | VARCHAR | USER, FILE, DEVICE, IP, APPLICATION |
| `node_value`   | VARCHAR | The identifier (e.g. username, IP) |
| `event_count`  | INTEGER | Number of events for this node |
| `risk_score`   | DOUBLE  | Computed risk (0–1)            |
| `first_seen`   | TIMESTAMP | Earliest event timestamp     |
| `last_seen`    | TIMESTAMP | Latest event timestamp       |
| `metadata_json`| VARCHAR | Additional metadata            |

### `exfil_graph_edges`
Behaviour graph relationships.

| Column            | Type    | Description                     |
|-------------------|---------|---------------------------------|
| `edge_id`         | VARCHAR PK | UUID                         |
| `run_id`          | VARCHAR | Analysis run                    |
| `case_id`         | VARCHAR | Parent case                     |
| `source_node_id`  | VARCHAR | Source node UUID                |
| `target_node_id`  | VARCHAR | Target node UUID                |
| `relationship`    | VARCHAR | READ, WRITE, SEND, CONNECT, etc. |
| `weight`          | DOUBLE  | Edge weight                     |
| `evidence_count`  | INTEGER | Number of supporting events     |
| `evidence_ids`    | VARCHAR | JSON array of event IDs         |
| `first_seen`      | TIMESTAMP | Earliest edge timestamp       |
| `last_seen`       | TIMESTAMP | Latest edge timestamp         |

### `exfil_intel_incidents`
The core output — one row per detected exfiltration incident.

| Column                | Type    | Description                        |
|-----------------------|---------|------------------------------------|
| `incident_id`         | VARCHAR PK | UUID                            |
| `run_id`              | VARCHAR | Analysis run                       |
| `case_id`             | VARCHAR | Parent case                        |
| `actor`               | VARCHAR | Who did it                         |
| `channel`             | VARCHAR | USB, EMAIL, CLOUD, WEB, BLUETOOTH, INFERRED, UNKNOWN |
| `data_target`         | VARCHAR | What was accessed                  |
| `dst_ip`              | VARCHAR | Where it was sent                  |
| `bytes_accessed`      | BIGINT  | Bytes read from source             |
| `bytes_exfil`         | BIGINT  | Bytes sent outbound                |
| `confidence`          | DOUBLE  | Composite score 0–1                |
| `risk_category`       | VARCHAR | CRITICAL, HIGH, MEDIUM, LOW        |
| `intent_score`        | DOUBLE  | Actor's intent score 0–1           |
| `is_ghost`            | BOOLEAN | True if ghost transfer (inferred)  |
| `is_staged`           | BOOLEAN | True if staging activity detected  |
| `explanation`         | VARCHAR | Human-readable explanation         |
| `contributing_factors`| VARCHAR | JSON array of factor strings       |
| `timeline_json`       | VARCHAR | JSON event chain with timestamps   |
| `normalised_ts`       | TIMESTAMP | When the exfiltration occurred   |

### `exfil_channel_stats`
Aggregated statistics per exfiltration channel.

| Column           | Type    | Description                   |
|------------------|---------|-------------------------------|
| `stat_id`        | VARCHAR PK | UUID                       |
| `run_id`         | VARCHAR | Analysis run                  |
| `case_id`        | VARCHAR | Parent case                   |
| `channel`        | VARCHAR | Channel name                  |
| `incident_count` | INTEGER | Incidents via this channel    |
| `total_bytes`    | BIGINT  | Total bytes via this channel  |
| `avg_confidence` | DOUBLE  | Mean confidence for channel   |
| `actors`         | VARCHAR | JSON array of actor names     |

---

## 5. REST API Endpoints (7 Routes)

All routes are prefixed with `/api/cases/{case_id}/exfiltration`.

### `POST /run`
Run the full 9-engine pipeline synchronously.

**Request body** (all optional):
```json
{
  "source_filters": ["syslog", "epp_log"],
  "time_start": "2024-01-01T00:00:00Z",
  "time_end": "2024-12-31T23:59:59Z"
}
```

**Response**: Summary with run_id, incident counts, risk level, graph stats.

---

### `GET /run/stream`
Run the pipeline via **Server-Sent Events** (SSE) for real-time progress.

The browser opens an `EventSource` connection and receives events:

| Event type  | When                           | Payload                           |
|-------------|--------------------------------|-----------------------------------|
| `start`     | Pipeline begins                | `run_id`, engine list, total      |
| `engine`    | Each engine starts/completes   | `index`, `name`, `status`, `detail` |
| `persist`   | Writing results to DB          | `status: "running"`              |
| `complete`  | Pipeline finished              | Full summary (same as POST /run)  |
| `error`     | Something failed               | `message`                        |

---

### `GET /summary`
Returns the latest (or specific) run's summary metadata.

**Query params**: `?run_id=<uuid>` (optional — defaults to latest run)

---

### `GET /incidents`
Returns all scored incidents, ordered by confidence descending.

**Query params**: `?run_id=<uuid>` (optional)

Each incident includes pre-parsed `contributing_factors` (array) and `timeline_json` (array).

---

### `GET /graph`
Returns the behaviour graph as `{ nodes: [...], edges: [...] }`.

**Query params**: `?run_id=<uuid>` (optional)

---

### `GET /channels`
Returns per-channel aggregate statistics.

**Query params**: `?run_id=<uuid>` (optional)

---

### `GET /runs`
Returns all past analysis runs for this case, newest first.

---

## 6. Frontend Tabs (8 Views)

The frontend is a single React page with 8 tabs, each rendering a different view of the analysis results.

### Tab 1: Overview

A dashboard with:
- **6 stat cards**: Total Incidents, High/Critical count, Affected Users, External Destinations, Bytes Exfiltrated, Overall Risk
- **Exfiltration Timeline chart** (Recharts AreaChart): incidents and high-risk counts per hour
- **Channel Distribution** (Recharts PieChart): donut chart of incidents by channel
- **Top 5 Incidents**: highest confidence detections with badges and explanations

### Tab 2: Incidents

Full list of all detected incidents with:
- **Risk filter toolbar**: filter by CRITICAL, HIGH, MEDIUM, LOW
- **Channel filter toolbar**: filter by USB, EMAIL, CLOUD, WEB, etc.
- **Expandable cards**: click to reveal Contributing Factors and Event Timeline
- Each card shows: confidence %, actor, risk badge, ghost/staged badges, channel badge, explanation, data target → destination IP, bytes read/sent, intent score, confidence bar

### Tab 3: Behaviour Graph

An **interactive force-directed graph** rendered on HTML5 Canvas:

- **Node types**: USER (blue), FILE (purple), DEVICE (amber), IP (red), APPLICATION (green)
- **Edge types**: READ (blue), WRITE (green), CONNECT (amber), SEND (red)
- **Interactions**:
  - **Drag nodes** to reposition them individually
  - **Scroll** to zoom in/out
  - **Drag background** to pan the viewport
  - **Click a node** to select it and show a detail panel (type, value, event count, connections, timestamps)
  - **Hover** for a tooltip with event count and date range
- **Type filter toolbar**: filter to show only USER, FILE, DEVICE, or IP nodes (others are dimmed)
- **Layout**: Pre-computed stable positions via 80 force-simulation iterations, then a smooth 1-second animation from centre to final positions. No continuous bouncing.
- **Visual features**: Radial gradient fills, glow effects on hover/selection, grid background, direction arrows on highlighted edges

### Tab 4: Timeline

A **cinematic event timeline** displayed as a card:

- **Case Period bar**: horizontal gradient bar from first to last event date, with dots for each active day
- **Day grouping**: events grouped by date with a prominent date header (day name, month, day, year)
- **Per-day stats**: event count, target count, time range for the day
- **Vertical spine**: coloured line with severity dots and horizontal connectors to event cards
- **Event cards**: clickable to expand, showing:
  - Exact HH:MM:SS timestamp (or "same time" for simultaneous events)
  - Confidence %, actor, risk badge, ghost/staged/channel badges
  - Data target → destination IP
  - Explanation text
  - Bytes read/sent, intent score
  - Confidence bar
  - **Expanded view**: Contributing Factors list and Event Chain (Data Access → Transfer with timestamps)
- **Day correlation summary**: if multiple targets were accessed on the same day, shown at the end of that day group

### Tab 5: Channels

- **Channel stat cards**: one card per channel (USB, EMAIL, CLOUD, WEB, etc.) showing incident count, bytes, average confidence, and actor count
- **Channel Comparison bar chart** (Recharts BarChart): side-by-side comparison of incident volumes

### Tab 6: Risk Heatmap

- **Actor risk bars**: each actor gets a horizontal stacked bar showing CRITICAL (red), HIGH (orange), MEDIUM (amber), LOW (green) incident distribution
- Sorted by maximum confidence score (most dangerous actors first)
- Shows incident count and max confidence percentage

### Tab 7: Novelty Showcase

Highlights the 4 novel detection techniques with counts and detailed explanations:

1. **Ghost Transfer Detection**: count of inferred exfiltration events, explanation of temporal correlation method
2. **Multi-Channel Exfiltration**: YES/NO indicator, explanation of cross-channel detection
3. **Staging Activity**: count of staging events, explanation of extension and tool detection
4. **Behavioral Anomaly**: count of high-intent actors, explanation of weighted scoring model

### Tab 8: Runs

A history table of all past analysis executions:
- Run ID, incident count, high risk count, affected actors, bytes out, overall risk, status (COMPLETED/FAILED), start timestamp

---

## 7. How to Use It

### Prerequisites

1. **A case must exist** with ingested log data
2. **Timeline must be built** (the `unified_timeline` table must have rows)
3. **Anomaly detection** (optional) enriches scoring with ML anomaly signals
4. **CRUD analysis** (optional) enriches scoring with data sensitivity labels

### Running the Analysis

1. Navigate to a case: `http://localhost:3001/cases/{case_id}/exfiltration`
2. The pipeline **auto-runs on first visit** if no previous results exist
3. You'll see the **PipelineStepper** — a live dashboard showing each engine's progress via SSE
4. After completion (~1–5 seconds), all tabs populate automatically
5. Click **"Run Exfiltration Analysis"** to re-run at any time (overwrites graph/incidents, but preserves run history)

### Reading the Results

- **Start with the Overview tab** to see summary stats, timeline chart, and top incidents
- **Switch to Incidents** to filter and drill into individual detections
- **Use the Behaviour Graph** to visually explore actor-to-resource-to-IP relationships
- **Check the Timeline** for a chronological view of all events, grouped by day
- **Review Channels** to see which exfiltration vectors were detected
- **Use the Risk Heatmap** to identify the highest-risk actors
- **Visit Novelty Showcase** to understand the novel detection techniques applied

---

## 8. Configuration & Tuning

All engine parameters are configurable per-case via the `exfil_intel_config` table. If no config rows exist, defaults are used.

### Default Parameters

```
Engine: data_flow
  window_secs  = 1800    # Max seconds between READ and SEND to form a flow pair
  min_bytes    = 50000   # Minimum bytes for a flow to be considered significant

Engine: channel
  window_secs  = 600     # Max seconds between flows to cluster in same group

Engine: intent
  bulk_access_threshold = 5      # Base threshold for bulk access detection
  off_hours_start       = 18     # Off-hours begin (6 PM)
  off_hours_end         = 7      # Off-hours end (7 AM)
  w_bulk                = 0.30   # Weight: bulk data access
  w_offhours            = 0.25   # Weight: off-hours activity
  w_new_device          = 0.20   # Weight: new/unusual device usage
  w_staging             = 0.25   # Weight: staging activity detected

Engine: ghost
  max_gap_secs = 3600    # Max seconds between READ and outbound traffic for ghost detection

Engine: scoring
  w_flow        = 0.30   # Weight: data volume signal
  w_intent      = 0.25   # Weight: behavioural intent
  w_anomaly     = 0.20   # Weight: ML anomaly score
  w_sensitivity = 0.25   # Weight: target data sensitivity
```

### How to Change Parameters

Insert rows into `exfil_intel_config` via DuckDB:

```sql
INSERT INTO exfil_intel_config (config_id, case_id, engine, param_name, param_value, description)
VALUES (
  'custom-1',
  'your-case-id',
  'data_flow',
  'window_secs',
  3600,
  'Increase flow window to 1 hour for slow exfiltration'
);
```

Then re-run the analysis. The pipeline will pick up the new config automatically.

---

## 9. Scoring Model Explained

The scoring model is a **weighted linear combination** of 4 normalised signals (each 0–1):

```
confidence = w_flow × flow_signal
           + w_intent × intent_score
           + w_anomaly × anomaly_signal
           + w_sensitivity × sensitivity_signal
```

### Signal Breakdown

**flow_signal** = `min(1.0, (bytes_read + bytes_sent) / 5,000,000)`
- Linearly scales data volume up to 5 MB, then caps at 1.0
- A 500 KB transfer scores 0.1; a 5 MB transfer scores 1.0

**intent_score** = weighted average of 4 behavioural features (see Engine 5)
- Captures the "how suspicious is this actor's overall behaviour" question

**anomaly_signal** = max ML anomaly score for this actor from the anomaly detection module
- 0.0 if no anomaly run exists; up to 1.0 if ML model flagged the actor strongly

**sensitivity_signal** = based on the target resource's sensitivity label:
- LOW → 0.1, MEDIUM → 0.4, HIGH → 0.7, CRITICAL → 1.0
- Comes from the CRUD analysis module's `sensitivity` column

### Ghost Transfer Scoring

Ghost transfers use a different formula since there's no direct flow measurement:

```
confidence = 0.3 (base) + 0.3 × intent + 0.2 × anomaly + 0.2 × (staging ? 1 : 0)
```

The 0.3 base acknowledges inherent uncertainty in inferred transfers.

---

## 10. Detection Techniques Deep Dive

### Internal vs External IP Classification

The module classifies IPs as **internal** if they start with any of:
- `10.` (Class A private)
- `172.16.` through `172.18.` (Class B private subset)
- `192.168.` (Class C private)
- `127.` (loopback)

Everything else is considered **external** and potentially an exfiltration destination.

### Shannon Entropy Calculation

Available (though not yet used in scoring) for detecting encrypted/compressed filenames:

```
H(s) = -Σ (count_i / length) × log₂(count_i / length)
```

Higher entropy suggests the filename may be obfuscated or the content encrypted.

### Action Classification Mapping

The module maps log actions to graph edge types:

| READ actions        | WRITE actions          | SEND actions          |
|---------------------|------------------------|-----------------------|
| SELECT              | INSERT                 | SEND                  |
| FILE_READ           | FILE_WRITE             | UPLOAD                |
| HTTP_GET            | HTTP_POST (also SEND)  | HTTP_POST             |
| READ                | HTTP_PUT               | VPN_CONNECT           |
| EXPORT              | UPDATE                 |                       |
|                     | CREATE                 |                       |
|                     | CREATE_TABLE           |                       |
|                     | FILE_COPY              |                       |

Note: `HTTP_POST` can be classified as both WRITE and SEND depending on context.

---

## 11. Data Flow Through the System

```
User clicks "Run Exfiltration Analysis"
       │
       ▼
Frontend calls api.streamExfilIntel(caseId)
       │
       ▼
Browser opens EventSource → GET /api/cases/{id}/exfiltration/run/stream
       │
       ▼
Backend: run_exfiltration_analysis_streamed(case_id)
       │
       ├── INSERT into exfil_intel_runs (status=RUNNING)
       │
       ├── Engine 1: SELECT from unified_timeline → normalised events[]
       ├── Engine 2: Build graph nodes{} and edges[]
       ├── Engine 3: Detect data flow chains → flows[]
       ├── Engine 4: Cluster flows by actor+time → clusters[]
       ├── Engine 5: Score intent per actor → intent_scores{}
       ├── Engine 6: Find ghost transfers → ghosts[]
       ├── Engine 7: Detect staging patterns → staging[]
       ├── Engine 8: Composite scoring → incidents[]
       ├── Engine 9: Generate explanations → incidents[] (enriched)
       │
       ├── _persist() → write to 4 tables:
       │     ├── exfil_graph_nodes (DELETE + INSERT)
       │     ├── exfil_graph_edges (DELETE + INSERT)
       │     ├── exfil_intel_incidents (DELETE + INSERT)
       │     └── exfil_channel_stats (DELETE + INSERT)
       │
       ├── UPDATE exfil_intel_runs (status=COMPLETED, hash, stats)
       ├── INSERT into chain_of_custody (forensic audit trail)
       │
       └── yield {type: "complete", ...summary}
              │
              ▼
       Frontend receives SSE "complete" event
       Frontend calls loadData() → 5 parallel GET requests
       Frontend populates all 8 tabs
```

---

## 12. Limitations & Known Gaps

| Gap | Description | Impact |
|-----|-------------|--------|
| **No real-time NLP** | Explanations are template-based, not LLM-generated | Explanations are accurate but formulaic |
| **No DPI content** | Can't inspect file contents, only metadata and filenames | Encrypted exfiltration of small files may be missed |
| **IP classification is basic** | Only prefix-based internal/external check | May miss VPN tunnel IPs or cloud NAT gateways |
| **No user baseline** | Intent scoring doesn't compare against user's historical norm | A normally active user may be scored the same as a new user |
| **Graph risk_score unused** | Node `risk_score` is always 0.0 (reserved) | Future: propagate incident confidence back to graph nodes |
| **No pagination** | Incidents list loads all at once | May be slow with thousands of incidents |
| **Shannon entropy** | Function exists but isn't used in scoring | Could detect obfuscated filenames in future |
| **Private IP ranges** | Only checks 3 private ranges + loopback | `172.19–172.31` ranges are not classified as internal |
| **Single vault connection** | DuckDB single-writer limitation | Concurrent analysis runs on same case will fail |

---

## 13. Future Roadmap

### Short Term
- [ ] **LLM-powered explanations**: Replace template explanations with Ollama/Gemini-generated natural language
- [ ] **Node risk propagation**: Propagate incident confidence scores back to graph nodes for visual risk highlighting
- [ ] **Incident pagination**: Add server-side pagination for large result sets
- [ ] **Export to PDF**: Generate a forensic report from analysis results

### Medium Term
- [ ] **User baseline modelling**: Compare current activity against historical patterns for the same user
- [ ] **Content-aware detection**: Integrate with DLP APIs to check actual file content sensitivity
- [ ] **Custom detection rules**: Allow analysts to define custom YARA-like rules for exfiltration patterns
- [ ] **Graph analytics**: Add PageRank-style centrality scoring to identify key nodes

### Long Term
- [ ] **Real-time streaming**: Ingest events continuously and update the graph/incidents live
- [ ] **MITRE ATT&CK mapping**: Map detected techniques to ATT&CK data exfiltration sub-techniques
- [ ] **Cross-case correlation**: Compare exfiltration patterns across multiple cases
- [ ] **Automated response**: Trigger alerts or containment actions based on confidence thresholds

---

## File Map

```
operation-room/
├── backend/
│   └── app/
│       ├── database.py                  # Schema DDL (6 exfil tables)
│       ├── main.py                      # Router registration
│       ├── routes/
│       │   └── exfiltration.py          # 7 API endpoints
│       └── services/
│           └── exfiltration_agent.py    # 9 engines + query functions (928 lines)
└── frontend/
    └── src/
        ├── lib/
        │   └── api.js                   # 7 API client methods
        ├── components/
        │   ├── Sidebar.js               # "Exfil Intelligence" nav item
        │   └── TopHeader.js             # Page title injection
        └── app/(main)/cases/[id]/
            └── exfiltration/
                └── page.js              # Full UI: 8 tabs, ~1590 lines
```
