# Log Import — Design Specification

## Purpose

Import logs from the centralised log store (via the NLP Query Agent) into a case's DuckDB vault. Every import is cryptographically hashed and chain‑of‑custody logged.

---

## Workflow

```
Investigator selects source type, time range, actors, systems
        │
        ▼
POST /api/cases/{id}/evidence/import
        │
        ▼
Backend calls NLP Query Agent (or mock)
        │
        ▼
Receives JSON result set
        │
        ▼
Computes SHA‑256 hash of canonical JSON
        │
        ▼
Inserts records into raw_events table
        │
        ▼
Inserts hash into evidence_hashes
        │
        ▼
Records IMPORT event in chain_of_custody
        │
        ▼
Returns: artefact name, record count, byte size, hash, batch ID
```

## Inputs

| Field          | Required | Description                                 |
|----------------|----------|---------------------------------------------|
| source_type    | ✅       | AUTH, VPN, FW, DB, APP, EPP, FILE           |
| time_start     | ✅       | ISO-8601 timestamp                          |
| time_end       | ✅       | ISO-8601 timestamp                          |
| target_actors  | ❌       | Filter to specific users/IPs                |
| target_systems | ❌       | Filter to specific hosts                    |
| query_text     | ❌       | Custom NLP query override                   |
| justification  | ❌       | Reason for import (stored in CoC)           |

## Outputs

| Field           | Description                            |
|-----------------|----------------------------------------|
| import_batch_id | UUID for this import batch             |
| artefact_name   | Generated name (e.g., `AUTH_2025-06-01_to_2025-06-15`) |
| record_count    | Number of records imported             |
| byte_size       | Size of the canonical JSON payload     |
| hash_algorithm  | SHA-256 (default)                      |
| hash_value      | Hex digest of the payload              |
| coc_event_id    | UUID of the CoC entry created          |

## Iterative Imports

Investigators can re-visit this page and import additional data at any time. Each import:
- Creates a new batch ID  
- Appends (never overwrites) to `raw_events`  
- Generates a new hash entry  
- Logs a new CoC event  

## Handling No Data

If the NLP agent returns zero records, the backend:
1. Records a `NO_DATA_FOUND` CoC event
2. Returns a result with `record_count: 0` and empty hash
3. The UI displays a warning message
