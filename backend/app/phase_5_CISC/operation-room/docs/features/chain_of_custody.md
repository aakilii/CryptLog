# Chain of Custody — Design Specification

## Purpose

Maintain a tamper-evident, append-only record of every action taken on evidence throughout a case's lifecycle. An unbroken chain of custody is essential for court admissibility.

---

## Two-Layer Audit

### Layer 1 — Per-Case CoC Table

Stored inside each Case Vault (DuckDB). Records all actions related to that specific case.

```sql
chain_of_custody (
    event_id         VARCHAR PRIMARY KEY,
    case_id          VARCHAR,
    timestamp        TIMESTAMP DEFAULT current_timestamp,
    actor            VARCHAR NOT NULL,
    action           VARCHAR NOT NULL,
    target_artefact  VARCHAR NOT NULL,
    justification    VARCHAR,
    hash_before      VARCHAR,
    hash_after       VARCHAR,
    details          VARCHAR   -- JSON string
)
```

### Layer 2 — Global Audit Log

`data/audit_log.jsonl` — a single JSONL file outside case directories. Every action from every case is appended here.

```json
{"timestamp":"...","actor":"analyst","action":"IMPORT","case_id":"...","target":"AUTH_logs","details":{}}
```

This file is **append-only** — the application never seeks backward or overwrites.

## Action Types

| Action          | Trigger                                          |
|-----------------|--------------------------------------------------|
| `CASE_CREATED`  | New case created                                 |
| `CASE_UPDATED`  | Case metadata modified                           |
| `IMPORT`        | Logs imported into case vault                    |
| `NO_DATA_FOUND` | NLP query returned zero records                  |
| `VERIFY_HASH`   | Integrity verification performed                 |
| `VIEW`          | Evidence viewed (optional, verbose mode)         |
| `EXPORT`        | Data exported from case vault                    |
| `ANALYSE`       | Downstream module analysis run                   |

## Tamper Evidence

- Each CoC event includes `hash_before` and `hash_after` where applicable.
- The global audit log can be verified by checking that entries are monotonically timestamped.
- Future enhancement: HMAC chaining — each entry's hash includes the previous entry's hash.

## Verbosity Levels

Configurable via `OPROOM_COC_VERBOSITY`:

| Level    | Records                              |
|----------|--------------------------------------|
| MINIMAL  | IMPORT, EXPORT only                  |
| STANDARD | All write operations (default)       |
| VERBOSE  | All read and write operations        |

## Legal Standards

- **NIST SP 800-86** — "An examiner should document each step of the process"
- **ISO/IEC 27037** §7.3 — Chain of custody documentation requirements
- **RFC 3227** §2.4 — Chain of custody maintenance
