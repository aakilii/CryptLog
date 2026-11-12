# NFLIP / CSIC — Agent context (Phases 1–5)

Condensed reference for AI assistants and developers. The product UI brand is **NFLIP Forensic Intelligence** (`csic_frontend`).

## Pipeline overview

| Phase | Role | Primary API / mount |
|-------|------|---------------------|
| **1** | Secure ingestion: JIT session, WebSocket chunks, Merkle, sandbox, WORM ledger | `POST /api/ingestion/*`, `WS /ws/secure-stream/{session_id}` |
| **2** | Universal Translator: lineage → deobf → DRAIN3 → NER → chronograph → staging → human commit → DuckDB `normalized_logs` | `/api/phase2/*` |
| **3** | Hot/cold gateway: Phase 2 webhook → Parquet cold (S3 or local) + DuckDB hot, TTL janitor, `GET /query-logs` | Mounted at `/api/phase3` (optional deps) |
| **4** | Magic Query UI: NL→SQL (Next route) + **live** rows via backend | `GET /api/phase4/parsed-logs?audit_id=…`; Next routes `POST /api/magic-query/generate` + `POST /api/magic-query/run` live in **Operation Room** (`app/phase_5_CISC/operation-room/frontend`) at case route **`/cases/{id}/import`** |
| **5** | Operation Room: case management, evidence import from Phase 3 S3 cold, analysis modules, Report Studio | Mounted at `/api/phase5`, frontend at `/operation-room` |

## Integration contracts

1. **Audit identity**  
   Phase 1 writes `latest_ingestion_audit` in `localStorage`. The app also keeps **`csic_active_audit_id`** (React context: `activeAuditId` / `setActiveAuditId` in `csic_frontend/lib/app-context.tsx`) so Phases 3–4 know which ledger UUID to use.

2. **Phase 2 → Phase 3**  
   On successful `commit_staging`, `app/phase2/node6_staging.py` POSTs to **`PHASE3_WEBHOOK_URL`** (default `http://127.0.0.1:8000/api/phase3/phase2_webhook`) with enriched payload: `Lineage`, `Target_User`, `Notes`, `audit_id`, `extracted_variables`, `ner_tags`, `normalized_timestamp`, `row_hash`. Phase 3 stores to DuckDB hot + Parquet cold (S3 when `S3_BUCKET_NAME` is set, else local `data/phase3_cold`).

3. **Phase 2 → Phase 4**  
   Committed rows land in DuckDB table **`normalized_logs`** (same DB file as `app/db/duckdb.py`: `data/analytics.duckdb`).  
   **`GET /api/phase4/parsed-logs`** maps those rows to the Magic Query shape (`parsed_logs` columns).

4. **Phase 3 → Phase 5 (Operation Room evidence import)**  
   Evidence import uses `POST /api/phase5/.../evidence/import` (e.g. from automation or other clients). The backend's `nlp_agent.py` queries **`GET /api/phase3/query-logs`**. The **case route `/cases/{id}/import`** in the Operation Room UI is **Magic Query (Phase 4)**, not this import form.

5. **Phase 4 Magic Query (Operation Room)**  
   `app/phase_5_CISC/operation-room/frontend/src/app/api/magic-query/run/route.ts` calls **`GET /api/phase4/parsed-logs?audit_id=…`** on the **FastAPI monolith root** (not under `/api/phase5`), using **`audit_id`** from `localStorage` key **`csic_active_audit_id`**. The server route uses **`getMonolithApiBaseForPhase4()`** so if **`NEXT_PUBLIC_API_URL`** is set to `http://…:8000/api/phase5`, Phase 4 is still reached. Prefer monolith root for clarity: `http://127.0.0.1:8000`. Also set **`GEMINI_API_KEY`** for NL→SQL where needed.

6. **Magic Query → case vault (Phase 5)**  
   After a successful Magic Query run, the UI can **`POST /api/cases/{case_id}/evidence/import-magic-query`** (Phase 5 app: `operation_room/routes/evidence.py`) with `{ "rows": [ … ], "audit_id": "<optional>", "justification": "…" }`. Rows use the **parsed_logs** column shape from Phase 4. The backend maps them to **`raw_events`** with **`source_type` = `MAGIC_QUERY`**, hashes the batch, writes **`evidence_hashes`**, and records chain-of-custody—same integrity pattern as Phase 3 import. Timeline, analysis modules, and Report Studio then consume vault data like any other import.

## S3 cold storage (Phase 3)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_ACCESS_KEY_ID` | (none) | S3 auth |
| `AWS_SECRET_ACCESS_KEY` | (none) | S3 auth |
| `AWS_REGION` | `us-east-1` | S3 region |
| `S3_BUCKET_NAME` | (none, disables S3) | Target bucket |
| `S3_ENDPOINT_URL` | (none) | MinIO/localstack override |

S3 key layout: `s3://{bucket}/phase3/events/{YYYY-MM-DD}/{lineage}.parquet`

## Run commands

- Backend: `uvicorn app.main:new_app --host 0.0.0.0 --port 8000 --reload`
- Main shell: `cd csic_frontend && npm run dev` — set `NEXT_PUBLIC_API_URL` to the backend base (e.g. `http://127.0.0.1:8000`).
- Operation Room (Magic Query + cases): `cd app/phase_5_CISC/operation-room/frontend && npm run dev` — for Phase 4 `parsed-logs`, set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` (FastAPI root, not `/api/phase5`); optional `GEMINI_API_KEY` for NL→SQL.

## Related docs

- Full Phase 1 security write-up: repository `README.md`.
