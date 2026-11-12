# Ransomware & Data Exfiltration Scans — Current State, Gaps & Optimisation Guide

**Applies to:** NFLIP Operation Room · Backend (`operation-room/backend`)  
**Audience:** Developers extending the forensic analysis modules.

---

## Table of Contents

1. [Executive Summary — What Actually Exists Right Now](#1-executive-summary--what-actually-exists-right-now)
2. [Ransomware Scan — How It Works Today](#2-ransomware-scan--how-it-works-today)
3. [Data Exfiltration Scan — How It Works Today](#3-data-exfiltration-scan--how-it-works-today)
4. [The Playbook — What Triggers Each Scan](#4-the-playbook--what-triggers-each-scan)
5. [Critical Gaps You Must Fix](#5-critical-gaps-you-must-fix)
6. [Full Implementation Roadmap](#6-full-implementation-roadmap)
7. [Optimisation Checklist](#7-optimisation-checklist)
8. [Quick Wins You Can Do Right Now](#8-quick-wins-you-can-do-right-now)

---

## 1. Executive Summary — What Actually Exists Right Now

Neither scan is a self-contained, dedicated module. Both are **partial implementations spread
across multiple services**, triggered by the frontend playbook buttons.

| What the UI promises | What actually runs | Honest status |
|---|---|---|
| **Ransomware Fast-Triage** | Timeline → Network → CRUD → Depth modules, in sequence | Partial placeholder |
| **Data Exfiltration Scan** | Timeline → Anomaly → Network → Correlation modules | Partial placeholder |

The ransomware detection is a **single SQL query** checking for `UPDATE`/`DELETE` bursts over
5,000 events per 5-minute window. The exfiltration detection is a **heuristic threshold check**
on network flow byte counts with no content inspection, no DNS tunneling detection, and no
cloud-service fingerprinting.

Both scans produce results but will miss real-world attacks and produce false positives on any
busy enterprise log set.

---

## 2. Ransomware Scan — How It Works Today

### 2.1 Entry Point

The "Ransomware Fast-Triage" playbook button in the frontend (`cases/[id]/page.js`) calls
these backend endpoints in order:

```
POST /api/cases/{id}/timeline/run
POST /api/cases/{id}/network/run
POST /api/cases/{id}/crud/run
POST /api/cases/{id}/depth/run
```

After those complete, the Studio canvas banner is populated from:

```
GET /api/cases/{id}/crud/heuristics/ransomware
```

### 2.2 The Core Detection Logic

**File:** `app/routes/crud.py` — lines 94–132

The entire ransomware detection is this SQL query:

```sql
WITH bucketed AS (
    SELECT
        time_bucket(INTERVAL '5 MINUTE', try_cast(timestamp AS TIMESTAMP)) as time_window,
        action,
        COUNT(*) as event_count
    FROM timeline
    WHERE tool = 'CRUD' AND action IN ('UPDATE', 'DELETE')
    GROUP BY 1, 2
)
SELECT * FROM bucketed WHERE event_count > 5000 ORDER BY time_window ASC
```

It returns windows where more than 5,000 `UPDATE` or `DELETE` events occurred in a 5-minute
bucket. That is the **entirety of ransomware detection**.

### 2.3 What the CRUD Agent Adds

**File:** `app/services/crud_agent.py`

The CRUD pipeline (5 nodes) provides supporting data, not ransomware detection itself:

- `load_and_classify` — pulls from `unified_timeline` and joins anomaly scores
- `compute_metrics` — counts per actor/action type
- `detect_patterns` — generic burst heuristics (10+ events in 5 min per actor)
- `build_matrix` — enriched event list for the UI table
- `store_and_audit` — persists `crud_events` and `crud_summary` tables

### 2.4 The Ancestry Heuristic (Correlation Module)

**File:** `app/routes/correlation.py`

```
GET /api/cases/{id}/correlation/heuristics/ransomware_ancestry
```

This runs a recursive CTE on `crud_events` — it seeds on `DELETE`/`CREATE` events then
walks backward through the same user's activity within 5 minutes to build an attack ancestry
chain, up to depth 5. This is meaningful but isolated and not surfaced in the main scan
results.

### 2.5 What Is Missing from Ransomware Detection

| Required signal | Current status |
|---|---|
| File extension churn (`.jpg` → `.enc`, `.locked`) | Not implemented |
| Shadow copy deletion (`vssadmin delete`) | Not implemented |
| Registry modification for persistence | Not implemented |
| Process anomaly (mass child processes) | Not implemented |
| EPP `MALWARE_DETECTED` correlation | Not implemented |
| Cryptographic entropy spike in written files | Not implemented |
| Lateral movement before encryption | Not implemented |
| Ransom note creation (file named `README.txt`) | Not implemented |

---

## 3. Data Exfiltration Scan — How It Works Today

### 3.1 Entry Point

The "Data Exfiltration Scan" playbook button calls:

```
POST /api/cases/{id}/timeline/run
POST /api/cases/{id}/anomaly/run
POST /api/cases/{id}/network/run
POST /api/cases/{id}/correlation/run
```

Results are surfaced from:

```
GET /api/cases/{id}/network/exfil
```

### 3.2 The Core Detection Logic

**File:** `app/services/network_agent.py` — `detect_exfiltration()` function

The pipeline:

1. **Parse flows** from `raw_events` where `source_type IN ('FW', 'VPN', 'NET')`
2. **Extract features** per flow: `bytes_out`, `duration`, `packet_ratio`, `unique_destinations`,
   `off_hours_flag`, `known_bad_ip`
3. **Apply thresholds:**
   - Bytes transferred > configurable threshold (default varies by source)
   - Sessions to non-whitelisted external IPs
   - Traffic at off-hours (outside 08:00–18:00)
4. **Correlate with CRUD** — joins flows against `crud_events` by actor + time window
5. **Persist `exfil_candidates`** table with columns: `event_id`, `case_id`, `actor`, `dst_ip`,
   `bytes_out`, `confidence`, `threat_label`, `run_id`

### 3.3 What the Depth Agent Adds

**File:** `app/services/depth_agent.py`

After the network run, the depth agent reads `exfil_candidates` to:
- Count high-confidence exfil events (confidence > 0.7)
- Sum total bytes exfiltrated
- Map to a data sensitivity score
- Generate regulatory impact text (GDPR Art. 33, PCI DSS, etc.)

This is the most complete part of the exfiltration pipeline.

### 3.4 What Is Missing from Exfiltration Detection

| Required signal | Current status |
|---|---|
| DNS tunneling detection (high-entropy subdomains) | Not implemented |
| HTTP/S covert channel (steganography, base64 body) | Not implemented |
| Cloud storage uploads (S3, OneDrive, Dropbox APIs) | Not implemented |
| USB / removable media transfers | Not implemented |
| Email attachment exfiltration (SMTP large attachments) | Not implemented |
| Staged compression before transfer (7z, zip, tar) | Partially in EPP events only |
| DLP content classification (PII, PCI, credentials) | Not implemented |
| Beaconing pattern detection (periodic small transfers) | Not implemented |

---

## 4. The Playbook — What Triggers Each Scan

**File:** `frontend/src/app/(main)/cases/[id]/page.js`

The playbooks are defined in the frontend as ordered arrays of module runs:

```javascript
// Ransomware Fast-Triage
["timeline", "network", "crud", "depth"]

// Data Exfiltration Scan
["timeline", "anomaly", "network", "correlation"]
```

Each module calls `POST /api/cases/{id}/{module}/run` sequentially. There is **no dedicated
ransomware or exfiltration backend route**. Both scans are just aliases for chaining the
existing generic modules.

**The "scan" is entirely a frontend concept.** The backend has no `POST /ransomware/run` or
`POST /exfil/run` endpoint. The scans have no dedicated summary, no combined result object,
and no single API to check if a scan succeeded.

---

## 5. Critical Gaps You Must Fix

These are issues that will cause broken results or crashes right now, not just missing features.

### Gap 1 — Stale `binding_service.py` Column Names

**File:** `app/services/binding_service.py`

The `ransomware_burst` and `exfil_candidates` chart bindings reference columns that do **not
match** the actual DuckDB schema in `database.py`. Specifically:

- Bindings reference `destination_ip`, `risk_score`, `threat_label`
- Actual `exfil_candidates` columns are `dst_ip`, `confidence`, `threat_label`

**Fix required:** Open `binding_service.py`, find the `ransomware_burst` and
`exfil_candidates` binding SQL, and align column names with `database.py`.

### Gap 2 — Ransomware Heuristic Uses `timeline`, CRUD Agent Uses `unified_timeline`

The burst query in `crud.py` queries the `timeline` table directly.
The `crud_agent.py` populates `crud_events` from `unified_timeline`.

These two tables are **not guaranteed to be in sync**. If you run only the ransomware
heuristic without running the CRUD pipeline first, the results come from `timeline` which
may have stale or missing data.

**Fix required:** The ransomware heuristic endpoint should query `crud_events` (populated by
the CRUD agent) instead of querying `timeline` directly. Add a guard that raises an
informative error if `crud_events` does not exist yet.

### Gap 3 — No Single Scan Result Object

Currently the scan results are spread across `crud_summary`, `anomaly_scores`,
`exfil_candidates`, and `correlation_graph` tables. The frontend has to call 4–5 endpoints
to assemble a picture.

**Fix required:** Add dedicated summary endpoints (see Section 6, Step 1).

### Gap 4 — Threshold of 5,000 Events per 5 Minutes is Too High

The ransomware burst detection threshold (`event_count > 5000`) will never trigger on any
realistic dataset under 1 million events. The demo case has 257 events total.

**Fix required:** Change the threshold to `> 10` for development and expose it as a
configurable parameter.

---

## 6. Full Implementation Roadmap

### Step 1 — Add Dedicated Scan Summary Endpoints (1–2 hours)

Create `app/routes/scans.py` with two endpoints:

```python
from fastapi import APIRouter
router = APIRouter(prefix="/api/cases/{case_id}/scans", tags=["scans"])

@router.get("/ransomware/summary")
def ransomware_summary(case_id: str):
    """Aggregate CRUD bursts + EPP events + ancestry into one result."""
    ...

@router.get("/exfiltration/summary")
def exfiltration_summary(case_id: str):
    """Aggregate exfil_candidates + depth data_depth + correlation into one result."""
    ...
```

Register the router in `app/main.py`.

---

### Step 2 — Improve Ransomware Detection (4–8 hours)

Add the following signals to the ransomware heuristic by extending the SQL query against
`crud_events` and `raw_events`:

**A. File extension churn detection**

```sql
-- Detects actor writing many files with encryption-like extensions
SELECT actor, COUNT(*) as enc_writes
FROM raw_events
WHERE source_type = 'FILE'
  AND action IN ('FILE_WRITE', 'FILE_RENAME')
  AND (target LIKE '%.enc' OR target LIKE '%.locked' OR target LIKE '%.crypt'
       OR target LIKE '%.crypto' OR target LIKE '%.ransom')
GROUP BY actor
HAVING COUNT(*) > 5
```

**B. Shadow copy / backup deletion**

```sql
SELECT actor, action, target, timestamp
FROM raw_events
WHERE action IN ('FILE_DELETE', 'DELETE')
  AND (target LIKE '%shadow%' OR target LIKE '%backup%'
       OR target LIKE '%vssadmin%' OR target LIKE '%wbadmin%')
```

**C. EPP correlation**

```sql
SELECT r.actor, r.timestamp, r.action AS epp_action,
       JSON_EXTRACT(r.detail, '$.threat') AS threat
FROM raw_events r
WHERE r.source_type = 'EPP'
  AND r.action IN ('MALWARE_DETECTED', 'QUARANTINE', 'PROCESS_BLOCKED')
```

Combine these into a `RansomwareSignals` object and return a confidence score:

```python
def score_ransomware(bursts, ext_churn, shadow_deletes, epp_hits):
    score = 0.0
    if bursts:         score += 0.3
    if ext_churn > 10: score += 0.3
    if shadow_deletes: score += 0.25
    if epp_hits:       score += 0.15
    return min(score, 1.0)
```

---

### Step 3 — Improve Exfiltration Detection (4–8 hours)

Extend `network_agent.py` `detect_exfiltration()` with:

**A. Beaconing detection** — periodic small transfers to the same IP

```python
def detect_beaconing(flows: list[dict]) -> list[dict]:
    """Flag destinations with regular intervals (variance < threshold)."""
    from collections import defaultdict
    import statistics
    grouped = defaultdict(list)
    for f in flows:
        grouped[f["dst_ip"]].append(f["timestamp_epoch"])
    
    beacons = []
    for ip, times in grouped.items():
        if len(times) < 5:
            continue
        times.sort()
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        if statistics.stdev(intervals) < 30:  # very regular — beacon
            beacons.append({"dst_ip": ip, "interval_mean": statistics.mean(intervals)})
    return beacons
```

**B. DNS tunneling heuristic** — detect high-entropy subdomain requests

```python
import math, collections

def shannon_entropy(s: str) -> float:
    freq = collections.Counter(s)
    return -sum((c/len(s)) * math.log2(c/len(s)) for c in freq.values())

def detect_dns_tunneling(events: list[dict]) -> list[dict]:
    """Flag DNS queries where subdomain entropy > 3.5 (typical tunnel threshold)."""
    suspicious = []
    for e in events:
        if e.get("source_type") != "NET":
            continue
        target = e.get("target", "")
        subdomain = target.split(".")[0]
        if len(subdomain) > 20 and shannon_entropy(subdomain) > 3.5:
            suspicious.append({"target": target, "actor": e["actor"], "entropy": shannon_entropy(subdomain)})
    return suspicious
```

**C. Staged compression correlation**

```python
# Flag actors who both ran 7z/zip AND had large outbound FW flows within 30 minutes
```

---

### Step 4 — Fix the Binding Column Mismatch (30 minutes)

Open `app/services/binding_service.py` and find the `exfil_candidates` binding. Change:

```python
# Wrong (old):
"destination_ip", "risk_score"

# Correct (matches database.py):
"dst_ip", "confidence"
```

Do the same for `ransomware_burst` — ensure the SQL column names match `crud_events`.

---

### Step 5 — Fix the Burst Threshold (10 minutes)

In `app/routes/crud.py`, line 117, change the hardcoded threshold:

```python
# Before:
WHERE event_count > 5000

# After (make it configurable):
WHERE event_count > :threshold
```

And expose a query parameter on the endpoint:

```python
@router.get("/heuristics/ransomware")
async def detect_ransomware_burst(case_id: str, threshold: int = Query(default=10, ge=1)):
```

---

## 7. Optimisation Checklist

Work through these in order from most impactful to least:

- [ ] **Fix column name mismatch in `binding_service.py`** — dashboard charts are broken without this
- [ ] **Lower burst threshold to configurable param** — nothing fires at > 5,000 on typical data
- [ ] **Query `crud_events` in heuristic** instead of raw `timeline` — ensure CRUD pipeline ran first
- [ ] **Add file extension churn query** to ransomware scan — catches encryption prep phase
- [ ] **Add EPP correlation** to ransomware scan — EPP events are already in `raw_events`
- [ ] **Add beaconing detection** to exfiltration scan — catches C2 and slow-drip exfil
- [ ] **Add DNS tunneling heuristic** — high-entropy subdomain check on NET events
- [ ] **Add dedicated `/scans/ransomware/summary` endpoint** — the frontend needs one place to GET results
- [ ] **Add dedicated `/scans/exfiltration/summary` endpoint** — same reason
- [ ] **Surface ancestry chain in scan results** — `ransomware_ancestry` endpoint result is never shown in the main scan UI
- [ ] **Add confidence scoring** to both scans (0.0–1.0 float) — needed for the Depth module to consume meaningfully
- [ ] **Write unit tests** for burst detection and beaconing functions

---

## 8. Quick Wins You Can Do Right Now

These require minimal code changes and immediately improve the scans:

### Fix 1 — Lower Ransomware Threshold (5 minutes)

In `app/routes/crud.py` line 117, change `> 5000` to `> 10`.

### Fix 2 — Connect EPP Events to Ransomware (30 minutes)

Add this to the `detect_ransomware_burst` route response in `app/routes/crud.py`:

```python
# Add after existing query
epp_query = """
    SELECT actor, action, target,
           JSON_EXTRACT(detail, '$.threat') as threat,
           timestamp
    FROM raw_events
    WHERE source_type = 'EPP'
      AND action IN ('MALWARE_DETECTED', 'QUARANTINE', 'PROCESS_BLOCKED')
    ORDER BY timestamp DESC
    LIMIT 50
"""
epp_results = con.execute(epp_query).fetchall()

return {
    "bursts": [...],                # existing
    "epp_alerts": [
        {"actor": r[0], "action": r[1], "target": r[2],
         "threat": r[3], "timestamp": str(r[4])}
        for r in epp_results
    ],
    "ransomware_confidence": min(0.3 * bool(results) + 0.3 * bool(epp_results), 1.0)
}
```

### Fix 3 — Add File Extension Churn to Exfil Scan (30 minutes)

Add this query to `network_agent.py` inside `detect_exfiltration()`:

```python
ext_churn = conn.execute("""
    SELECT actor, COUNT(*) as enc_writes
    FROM raw_events
    WHERE source_type = 'FILE'
      AND action IN ('FILE_WRITE', 'FILE_RENAME')
      AND (target LIKE '%.enc' OR target LIKE '%.locked'
           OR target LIKE '%.crypt' OR target LIKE '%.7z')
    GROUP BY actor HAVING COUNT(*) > 3
""").fetchall()
```

Store it in the exfil run results as `staged_compression_actors`.

### Fix 4 — Show Ancestry in the UI (Frontend only, 20 minutes)

In `frontend/src/app/(main)/cases/[id]/network/page.js`, add a call to:

```
GET /api/cases/{id}/correlation/heuristics/ransomware_ancestry
```

And display the results in a collapsible "Attack Ancestry Chain" section. The endpoint already
exists and returns data — it just is not surfaced anywhere in the UI.

---

## Architecture After Full Implementation

```
POST /api/cases/{id}/scans/ransomware/run
  └── [1] timeline/run       — build unified_timeline
  └── [2] crud/run           — populate crud_events
  └── [3] anomaly/run        — score events
  └── [4] network/run        — find suspicious flows
  └── [5] ransomware heuristics:
        ├── burst_detection()      (crud_events: DELETE/UPDATE spikes)
        ├── ext_churn_detection()  (raw_events: FILE source, .enc/.locked writes)
        ├── shadow_delete()        (raw_events: vssadmin/backup deletions)
        ├── epp_correlation()      (raw_events: EPP MALWARE_DETECTED)
        └── ancestry_chain()       (crud_events: recursive CTE)
  └── [6] confidence_score()  → 0.0–1.0
  └── [7] depth/run           — blast radius + GDPR impact

POST /api/cases/{id}/scans/exfiltration/run
  └── [1] timeline/run        — build unified_timeline
  └── [2] anomaly/run         — anomaly scores
  └── [3] network/run         — exfil_candidates + beaconing + DNS tunneling
  └── [4] correlation/run     — actor-IP graph, MITRE TA0010 mapping
  └── [5] exfil heuristics:
        ├── large_outbound()       (FW events: bytes_out threshold)
        ├── beaconing()            (periodic small transfers to same IP)
        ├── dns_tunneling()        (high-entropy subdomain entropy check)
        ├── staged_compression()   (FILE .7z/.zip writes before FW outbound)
        └── crud_correlation()     (bulk SELECT/EXPORT before outbound)
  └── [6] confidence_score()  → 0.0–1.0
  └── [7] depth/run           — data depth + regulatory narrative
```
