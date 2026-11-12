# Integration Points — Design Specification

## Purpose

Define how the Case Initialization module interfaces with upstream services and downstream analysis modules.

---

## Upstream: NLP Query Agent

### Interface

```
POST {NLP_AGENT_URL}/query
Content-Type: application/json

{
  "source_type": "AUTH",
  "time_start": "2025-06-01T00:00:00Z",
  "time_end": "2025-06-15T23:59:59Z",
  "target_actors": ["jdoe"],
  "target_systems": ["dc01"],
  "query_text": "optional custom query"
}
```

**Response:** JSON array of log records.

Currently mocked in `services/nlp_agent.py`. To integrate the real agent, replace the function body of `query_nlp_agent()` with an `httpx.AsyncClient.post()` call.

## Upstream: Report-Export Phase

Not directly consumed by Case Init. The Report Writer module (Module 09) produces `report.json` which the export phase converts to PDF.

---

## Downstream: Analysis Modules

Every downstream module reads from the Case Vault via DuckDB:

| Module                 | Reads                                  | Writes                     |
|------------------------|----------------------------------------|----------------------------|
| Timeline Reconstruction | `raw_events`, `scope_definition`      | `unified_timeline`         |
| Anomaly Detection      | `raw_events` (via timeline)            | `anomaly_scores`           |
| Correlation            | `raw_events`, `case_metadata`          | `correlation_graph`        |
| CRUD Analysis          | `raw_events` (DB/API source types)     | `crud_events`              |
| Network / Exfil        | `raw_events` (network source types)    | `network_flows`            |
| Depth & Impact         | Results from correlation, CRUD, network| `depth_matrix`             |
| Augment-Studio         | Any output table                       | `charts/` directory        |
| Report Writer          | All tables + `chain_of_custody`        | `report.json`              |

### Contract

Downstream modules **must**:
1. Open the vault using `database.open_vault(case_id)`
2. Read from shared tables (never modify `raw_events`, `evidence_hashes`)
3. Write results to their own tables/files within the case vault
4. Record a CoC event using `audit_service.record_coc_event()`

### API Base URL

The frontend proxies all `/api/*` requests to `http://localhost:8000` via Next.js rewrites (configured in `next.config.mjs`).

## Adding New Modules

1. Create service file in `backend/app/services/`
2. Create route file in `backend/app/routes/`
3. Register router in `main.py`
4. Create frontend page under `src/app/`
5. Add navigation entry to `Sidebar.js`
6. No changes to existing module code required
