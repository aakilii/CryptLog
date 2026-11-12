# Report Studio — NFLIP Forensic Report Builder

> **Canva/Word-like WYSIWYG report builder** for forensic investigations.  
> Evidence-bound blocks · Real-time collaboration · Deterministic exports · Tamper-evident integrity.

---

## Overview

The Report Studio replaces the existing markdown-based report writer with a full
**TipTap/ProseMirror block editor** that lets investigators build structured
forensic reports by composing text, tables, charts, diagrams, and graphs — all
bound to evidence data from the 7 analysis modules.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **WYSIWYG Editing** | TipTap block editor with rich text, headings, lists, tables, images |
| **Evidence Blocks** | Vega-Lite charts, Mermaid diagrams, correlation graphs, timeline embeds |
| **Data Bindings** | Blocks pull live data from DuckDB modules with SHA-256 integrity tracking |
| **Real-Time Collab** | Yjs CRDT + WebSocket — multiple investigators, cursor presence |
| **Version Control** | Full version history, diff view, restore, comments |
| **Deterministic Export** | PDF (Playwright), DOCX (python-docx), HTML, WEB bundle |
| **Tamper Evidence** | RFC 8785 canonicalisation + SHA-256 + append-only CoC log |
| **Signed Exports** | Sigstore (Cosign) + optional RFC 3161 timestamps (Phase 5) |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Browser (Next.js)                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ TipTap   │  │ Vega-Lite│  │ Mermaid/Graph │  │
│  │ Editor   │  │ Charts   │  │ Renderers     │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │              │                │          │
│       └──────────────┴────────────────┘          │
│                      │ REST + WS                 │
└──────────────────────┼───────────────────────────┘
                       │
┌──────────────────────┼───────────────────────────┐
│              FastAPI Backend                      │
│  ┌──────────┐  ┌─────────┐  ┌──────────────────┐ │
│  │ Doc API  │  │ Binding │  │ Export Engine     │ │
│  │ /studio  │  │ API     │  │ (PDF/DOCX/HTML)  │ │
│  └────┬─────┘  └────┬────┘  └───────┬──────────┘ │
│       │              │                │           │
│  ┌────┴────┐    ┌────┴────┐    ┌─────┴────────┐  │
│  │Postgres │    │ DuckDB  │    │ File Storage  │  │
│  │(docs)   │    │(evidence│    │ (local → S3)  │  │
│  └─────────┘    └─────────┘    └──────────────┘  │
└──────────────────────────────────────────────────┘
```

### Data Flow

1. **Edit** — Investigator types in TipTap → ProseMirror AST updated in memory
2. **Bind** — Insert evidence block → DuckDB query → data snapshot + hash
3. **Save** — AST canonicalised (RFC 8785) → SHA-256 → Postgres + CoC event
4. **Collaborate** — Yjs CRDT syncs via WebSocket → all cursors visible
5. **Export** — Freeze AST → render all blocks to static assets → assemble output
6. **Verify** — Re-hash every artifact → compare to manifest → signature check

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Editor | TipTap 2 + ProseMirror |
| Charts (Studio) | Vega-Lite 5 + vega-embed |
| Charts (Dashboards) | Recharts 3 (unchanged) |
| Diagrams | Mermaid 10 |
| Collaboration | Yjs + y-websocket |
| Frontend | Next.js 14 (React 18) |
| Backend | FastAPI (Python 3.11) |
| Doc Database | PostgreSQL 16 |
| Evidence Database | DuckDB (file-per-case, read-only) |
| PDF Export | Playwright (headless Chromium) |
| DOCX Export | python-docx |
| Integrity | SHA-256 + RFC 8785 canonicalisation |
| Signing (Phase 5) | Sigstore (Cosign) + Rekor |
| Storage | Local filesystem → S3/MinIO |

---

## Build Phases

| Phase | Scope | Status |
|-------|-------|--------|
| **P1** | AST + Postgres + TipTap shell + basic blocks | 🔲 Planned |
| **P2** | Evidence blocks (Vega-Lite, Mermaid, Graph) + DuckDB bindings | 🔲 Planned |
| **P3** | Yjs collaboration + versioning + comments + diff | 🔲 Planned |
| **P4** | PDF/DOCX/HTML/WEB export engine | 🔲 Planned |
| **P5** | Sigstore signing + S3 migration + verifier + Docker | 🔲 Planned |

---

## Quick Start

```bash
# Backend
cd backend
pip install psycopg2-binary asyncpg playwright python-docx
python -m uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-table vega-lite vega vega-embed
npm run dev -- --port 3001

# Collaboration server (Phase 3)
npx y-websocket --port 4001

# Postgres
createdb nflip_studio
```

---

## AST Document Model

Every report is stored as a **JSON AST** (Abstract Syntax Tree) compatible with
TipTap/ProseMirror's document schema. The AST is the single source of truth —
all exports (PDF, DOCX, HTML) are deterministic transformations of the same AST.

```json
{
  "schema": "report-ast/1.0",
  "caseId": "case_xxx",
  "docId": "doc_yyy",
  "content": {
    "type": "doc",
    "content": [
      { "type": "heading", "attrs": { "level": 1 }, "content": [{ "type": "text", "text": "Findings" }] },
      { "type": "vegaChart", "attrs": { "spec": "...", "binding": { "module": "network" } } },
      { "type": "mermaid", "attrs": { "source": "flowchart LR; A-->B" } }
    ]
  },
  "integrity": { "contentHash": "sha256:...", "version": 5 }
}
```

---

## Integration with Existing Modules

The Report Studio binds to data produced by all 7 investigation modules:

| Module | Bindable Data | Example Block |
|--------|-------------|---------------|
| Timeline | Event counts, severity distribution | Area chart: events over time |
| Anomaly | Score histogram, SHAP values | Bar chart: top anomalies with SHAP |
| Correlation | Entity graph, MITRE tactics | Graph block: interactive entity network |
| CRUD | Operation counts, sensitivity tags | Table: high-risk data access events |
| Network | Protocol distribution, exfil candidates | Donut: traffic by protocol |
| Depth | 4D severity scores | Radar: penetration dimensions |
| Case | Evidence hashes, CoC entries | Evidence table: hash verification status |
