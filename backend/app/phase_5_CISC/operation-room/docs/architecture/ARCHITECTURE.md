# Architecture & Extensibility Guide

> How to keep the Operation Room **dynamic, modular and future‑proof**.

---

## 1. Guiding Principles

| Principle | Description |
|---|---|
| **Module independence** | Every module is a self‑contained unit with defined inputs and outputs. Modules can be run in any order, skipped or re‑run. |
| **Standardised contracts** | All inter‑module communication uses **JSON schemas** and DuckDB tables with documented column definitions. |
| **Non‑destructive analysis** | Modules read from shared evidence tables and write to their own output tables. Raw data is never altered. |
| **Audit‑first design** | Every action is logged in the chain of custody before execution. |
| **Plug‑and‑play extensibility** | New modules or agents can be added without modifying existing code. |

---

## 2. Module Contract

Every module — core or auxiliary — implements the following contract:

```
Module Interface
├── metadata
│     ├── module_id      : string
│     ├── module_name    : string
│     ├── version        : semver
│     ├── description    : string
│     ├── input_schema   : JSON Schema
│     └── output_schema  : JSON Schema
│
├── configure(config: JSON) → void
│     Validates and applies configuration parameters.
│
├── execute(case_id, input: JSON) → output: JSON
│     Runs the module's analysis logic. Reads from and writes to DuckDB.
│     Logs all actions via the CoC service.
│
├── validate_inputs(case_id) → { valid: bool, missing: string[] }
│     Checks whether required input tables / artefacts exist before execution.
│
└── get_outputs(case_id) → output_manifest: JSON
      Returns a manifest of all artefacts produced by this module for the given case.
```

### Schema Versioning

* Input and output schemas carry a `schema_version` field.
* Modules declare which schema versions they can consume.
* If a schema upgrade introduces breaking changes, a migration adapter converts old‑format tables.

---

## 3. Module Registry

A central **Module Registry** tracks all installed modules:

```
module_id           TEXT PRIMARY KEY
module_name         TEXT
version             TEXT
status              TEXT            -- ACTIVE, DEPRECATED, DISABLED
input_schema_ref    TEXT            -- path to JSON Schema file
output_schema_ref   TEXT            -- path to JSON Schema file
config_schema_ref   TEXT            -- path to JSON Schema file
entrypoint          TEXT            -- module executable / class path
dependencies        TEXT[]          -- list of module_ids this module reads from
```

### Adding a New Module

1. **Create** the module implementation conforming to the contract.
2. **Define** JSON schemas for input, output and configuration.
3. **Register** the module by inserting into the Module Registry.
4. **Document** the module in a new `modules/NN_module_name/README.md`.
5. **Test** with the standard test harness (see § 7).

No changes to existing modules are required.

---

## 4. Data Flow Architecture

```
                ┌────────────────────────────────────────┐
                │           Module Orchestrator           │
                │                                          │
                │  ┌──────┐  ┌──────┐  ┌──────┐           │
                │  │ Mod 1│  │ Mod 2│  │Mod N │  …        │
                │  └──┬───┘  └──┬───┘  └──┬───┘           │
                │     │         │         │                │
                │     ▼         ▼         ▼                │
                │  ┌────────────────────────────────────┐  │
                │  │       Case Vault (DuckDB)          │  │
                │  │                                    │  │
                │  │  raw_events   (immutable)          │  │
                │  │  evidence_hashes (immutable)       │  │
                │  │  chain_of_custody (append‑only)    │  │
                │  │  unified_timeline (derived)        │  │
                │  │  anomaly_scores (derived)          │  │
                │  │  … output tables per module …      │  │
                │  └────────────────────────────────────┘  │
                │                                          │
                │  ┌────────────────────────────────────┐  │
                │  │   CoC Service (append‑only ledger) │  │
                │  └────────────────────────────────────┘  │
                └────────────────────────────────────────┘
```

### Key Patterns

| Pattern | Description |
|---|---|
| **Source‑of‑truth separation** | `raw_events` and `evidence_hashes` are immutable. Derived tables are regenerable. |
| **Module output namespacing** | Each module writes to its own tables (e.g., `anomaly_scores`, `crud_events`). No cross‑module writes. |
| **Lazy execution** | Modules are invoked on demand — not all modules run for every case. |
| **Re‑entrant execution** | Re‑running a module replaces its output tables (after creating a backup and CoC record). |

---

## 5. Running Modules in Any Order

The Orchestrator resolves dependencies at run time:

```
Investigator requests: "Run Network Analysis"
    │
    Orchestrator checks network_module.dependencies → ["unified_timeline", "crud_events"]
    │
    ├── unified_timeline exists? YES → proceed
    │
    └── crud_events exists? NO → warn investigator:
           "CRUD Analysis has not been run. Network Analysis can proceed
            without CRUD data, but exfiltration cross‑referencing
            will be limited. Run CRUD first?"
           [ Run CRUD First ]  [ Proceed Anyway ]
```

If the investigator proceeds without a dependency, the module gracefully degrades (uses `NULL` / empty for missing inputs).

---

## 6. Re‑Running Modules with Updated Data

When an investigator re‑imports data (wider time window) or updates configuration:

1. **Backup** existing output tables for the module (rename with timestamp suffix).
2. **Record** CoC event: `MODULE_RERUN` with justification.
3. **Execute** the module with new inputs.
4. **Compare** (optionally) new vs. old outputs and log differences.
5. **Downstream notification:** Flag dependent modules that their inputs may have changed.

---

## 7. Standardised I/O Schemas

### Event Record (Shared)

Every event flowing through the system conforms to a base schema:

```json
{
  "event_id": "uuid",
  "case_id": "uuid",
  "normalised_ts": "ISO 8601",
  "source_type": "AUTH | VPN | FW | DB | APP | EPP | FILE",
  "source_system": "string",
  "actor": "string",
  "action": "string",
  "target": "string",
  "detail": { "...arbitrary source‑specific fields..." }
}
```

### Module Output Envelope

Every module output is wrapped in:

```json
{
  "module_id": "string",
  "module_version": "semver",
  "case_id": "uuid",
  "generated_at": "ISO 8601",
  "generated_by": "string",
  "schema_version": "semver",
  "artefacts": [
    {
      "type": "TABLE | FILE | JSON",
      "name": "string",
      "location": "string",
      "hash": "SHA‑256",
      "record_count": "integer (if table)"
    }
  ]
}
```

---

## 8. Security & Access Control

| Layer | Mechanism |
|---|---|
| **Case Vault file** | File‑system ACLs; only assigned investigators have read/write. |
| **DuckDB access** | Application‑level role enforcement (investigator, reviewer, admin). |
| **CoC table** | Append‑only (*); delete and update operations are blocked at the application layer. |
| **API keys** | Stored in a secret manager; never embedded in configuration or logs. |
| **Audit log** | Separate from CoC; captures system‑level events (login, config changes). |

(*) In practice, DuckDB does not natively enforce append‑only constraints. The application layer must enforce this.

---

## 9. Testing & Validation

### Module Test Harness

Each module should include:

* **Unit tests** — validate classification rules, scoring formulas, schema compliance.
* **Integration tests** — run against a reference case vault with known data and verify outputs match expected results.
* **Regression tests** — re‑run after code changes; compare outputs hash‑by‑hash.

### End‑to‑End Smoke Test

A scripted test that:

1. Creates a case with synthetic data.
2. Runs all modules in default order.
3. Verifies all output tables are populated.
4. Generates a report and validates its JSON schema.
5. Checks CoC completeness.

---

## 10. Future Extension Ideas

| Extension | Description |
|---|---|
| **ML Feedback Loop** | Allow investigators to label anomaly false positives / true positives to improve future scoring. |
| **Automated Playbooks** | Pre‑defined sequences of module executions for common incident types (ransomware, insider threat, BEC). |
| **Multi‑Case Intelligence** | Cross‑case correlation — detect patterns spanning multiple investigations. |
| **Real‑Time Mode** | Continuous ingestion and analysis for active incident response (streaming from log store). |
| **Collaboration Features** | Multi‑investigator case sharing, comments, task assignment. |

---
