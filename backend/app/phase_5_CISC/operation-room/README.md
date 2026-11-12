# 🛡️ NFLIP Operation Room — Complete AI Agent Onboarding Guide & Architecture

**Target Audience:** Autonomous AI Assistants, LLM Agents, and Senior Forensic Engineers.
**Purpose:** Provide maximum context on the architecture, workflows, unique selling propositions (USPs), and internal state management of the NFLIP (National Forensic Log Intelligence Platform) Operation Room. Read this document before executing any code changes or generating features.


---

## 1. Application Identity & USP

**NFLIP Operation Room** is an enterprise-grade, subpoena-proof digital forensics and incident response (DFIR) platform. It orchestrates heterogeneous log ingestion, timeline reconstruction, machine-learning anomaly detection, and automated report generation.

### Unique Selling Propositions (USPs)
1. **Admissible by Design (The Vault):** All raw logs are ingested into a per-case embedded **DuckDB** file. The `raw_events` table is strictly **immutable**. Every action an investigator (or AI) takes is recorded in an append-only `chain_of_custody` (CoC) ledger with SHA-256 hashes.
2. **Re-entrant Modular Pipeline:** The investigation is not linear. It consists of 10 independent modules (Timeline, Anomaly, Correlation, CRUD, Network, Depth, Augment-Studio). Modules strictly define dependency graphs but run iteratively. If new logs are imported, dependent modules degrade gracefully or warn the user to re-run.
3. **White-Box ML (SHAP):** We do not just detect anomalies; we explain them. We use an Isolation Forest + LOF ensemble, then apply **SHAP** (SHapley Additive exPlanations) to prove mathematically *why* an event was flagged (e.g., "Time-of-day contributed +0.4 to anomaly score").
4. **The Canva-Style Forensic Studio (Studio V4):** Our reporting interface is not a static text document. It is an absolute-positioned, drag-and-drop workspace (Next.js + `react-rnd`). Investigators drop live Vega-Lite charts, depth radars, and correlation graphs directly onto an A4-bounded canvas. The layout is rigorously mapped to a headless PDF Python export engine.

---

## 2. How We Handle Log Investigation Scenarios

When a SOC Analyst responds to a breach (e.g., Ransomware or Insider Threat), the workflow maps to our backend modules:

### Phase 1: Ingestion & Normalization (`01_import` & `02_timeline`)
- **Action:** Heterogeneous logs (AWS CloudTrail, Windows Event Logs, Active Directory) are imported.
- **System:** The `NLP Agent` parses the CSV/JSON into uniform schemas. Timestamps are forcefully cast to UTC ISO-8601 while preserving timezone offsets. Data lands in the `unified_timeline`.

### Phase 2: Threat Hunting & ML Detection (`03_anomaly` & `05_crud`)
- **Action:** Find the needle in the haystack.
- **System:** The backend extracts 10 features per event and runs unsupervised ML. Every event receives an `anomaly_score`. Concurrently, the CRUD module classifies database/file actions to detect massive `READ` spikes (Exfiltration prep) or `DELETE` spikes (Ransomware encryption prep).

### Phase 3: Contextual Enrichment (`04_correlation` & `06_network`)
- **Action:** Who did it, and where did it go?
- **System:** The Correlation module joins timeline + anomalies into a Graph (Nodes = Users/IPs, Edges = Actions) mapped to the MITRE ATT&CK framework. The Network module parses NetFlows for beaconing or lateral movement. 

### Phase 4: Blast Radius Quantification (`07_depth_impact`)
- **Action:** Executive translation. How bad is the breach?
- **System:** Computes a 4-dimensional depth matrix:
  - **Account Depth:** Did they reach Domain Admin?
  - **System Depth:** How many VLANS were crossed?
  - **Data Depth:** Were PII/PCI databases touched?
  - **Control Depth:** How many EDRs were bypassed?
- **Result:** Yields a normalized risk score (0.0–1.0) and generates regulatory impact narratives (e.g., "GDPR Art 33 Violation").

### Phase 5: The Glass & Reporting (`08_augment_studio` & `09_report_writer`)
- **Action:** Build the final court-ready artefact.
- **System:** **Augment-Studio** executes live SQL aggregations against DuckDB to generate Vega-Lite JSON specs. In the **Studio V4 Frontend**, the investigator drags these charts onto the canvas. The **AI Report Writer** natively reads the JSON outputs of the charts to ghost-write highly accurate summaries on the canvas without hallucinating.

---

## 3. High-Level Architecture & Tech Stack

```text
[ Raw Logs ] -> [ FastAPI (Python) + LangGraph + scikit-learn ] -> [ DuckDB Vault ]
                                                                        |
[ Next.js 14 Frontend ] <- [ API Calls / Live SQL via Augment-Studio ] -+
   - React-RND (Canvas)
   - TipTap (Text Editor)
   - Recharts / Vega-Lite (Data Viz)
```

- **Backend:** Python 3.12, FastAPI. Machine Learning via `scikit-learn` and `shap`. LLM routing via LangGraph (supporting Ollama 3 local logic or Gemini API).
- **Database:** DuckDB. Chosen for its extreme OLAP performance on analytical queries. Each case is a separate `.duckdb` file, protecting tenant boundaries and ensuring portability.
- **Frontend:** Next.js 14 (App Router), Zustand (State Management), TailwindCSS.

---

## 4. The UI / UX Philosophy

Our interface adopts a **Dark Forensic Theme**. 
- Deep navy/slate backgrounds (`bg-slate-950`), glassmorphism panels, and specific severity colored badges (Critical=Rose, High=Orange, Info=Cyan).
- **The Right Inspector:** The right sidebar in the Studio V4 acts as a live Query Builder. When an investigator clicks a chart on the canvas, the Inspector reveals its `config`. Adjusting a "Top N" slider dispatches a query to Augment-Studio to recalculate the DuckDB aggregation and repaint the widget.

## 5. Standardized Data Contracts

For AI Agents interacting with the codebase, understand these schema mappings:

1. **The Canvas Store (`useStudioStore.ts`)**
   - `PageMeta[]`: Defines an array of A4 pages.
   - `CanvasElement`: The atomic unit of the report. Contains `id, x, y, width, height, data.filters, config`. Bounding logic is extremely strict to guarantee the Headless PDF exporter (`print/page.tsx`) renders exactly what the DOM shows.

2. **DuckDB Core Tables**
   - `raw_events`: Untouched truth.
   - `chain_of_custody`: Ledger of system actions.
   - `unified_timeline`: The operational battlefield.
   - `anomaly_scores`: Joined against the timeline for risk sorting.
   - `chart_registry`: Logs the SQL query and configuration used to generate a Vega-Lite chart.

## 6. How to Assist as an AI Developer Context

When writing code for this repository:
1. **Never mutate `raw_events`.** Always write derived data to a new Module table.
2. **Strict Bounding:** If modifying the Frontend Report Studio, respect the `calculateElementMinHeight` mathematical bounds. We utilize strict physics to match the Playwright PDF exporter.
3. **Database Efficiency:** Push heavy computations (aggregations, counts, time-bucketing) down to DuckDB. Do not send millions of rows to the Node.js frontend.
4. **Log Everything:** Ensure any configuration change or module execution is stamped into the `chain_of_custody` ledger via the backend API.

---

## 7. Directory Structure

Over time, numerous Markdown and scripting files were used to scope and test NFLIP. These have been cleanly organised so your workspace remains highly readable:

```text
CISC/operation-room/
 ├── backend/                   # Python FastAPI, DuckDB Vaults, LangGraph Agents
 ├── frontend/                  # Next.js 14 Studio V4 UI, TipTap, useStudioStore
 ├── packages/                  # Shared libraries across services
 ├── docs/                      # Centralized Project Documentation
 │    ├── architecture/         # Architectural Maps (ARCHITECTURE.md, REPORT_STUDIO_V4_CANVA_ARCHITECTURE.md)
 │    ├── guides/               # Quickstart and Environment details (STARTUP.md, DEPENDENCIES.md, GETTING_STARTED.md)
 │    ├── features/             # Core functional specification documents (Log ingestion, UI, Case Wizard)
 │    ├── modules/              # Detailed execution guides for all 10 independent modules
 │    ├── crud/, timeline/      # Deep-dive specs regarding isolated Agent modules
 │    └── archive/              # Outdated V3 Master Plans, old UX Analysis Scenarios, and Video Scripts
 └── README.md
```

Testing scripts like `script2.py` or `.txt` logs previously scattered across the root are now moved to `CISC/archive_scripts/` to ensure the core workspace is untethered and easily navigable!

