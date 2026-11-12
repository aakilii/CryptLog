# 🛡️ Operation Room — Forensic Log Analysis Platform

> **AI-powered digital forensics platform that transforms raw logs into actionable intelligence.**
> 8 integrated modules. LangGraph AI pipelines. Real-time visualisations. Forensic-grade integrity.

---

## 🎬 Platform Overview (Video Script)

**Opening:** An investigator opens a case → raw logs from firewalls, VPNs, databases, and endpoints pour in.
**Middle:** AI agents analyse, correlate, and score — revealing hidden attack chains, data exfiltration, and security gaps.
**Closing:** A professional report with interactive charts is generated — ready for executives, regulators, or court.

---

## 🏗️ Architecture Flow

```
📂 Case Init → ⏳ Timeline → 🔍 Anomaly → 🔗 Correlation → 💾 CRUD → 🌐 Network → 📈 Depth → 📊 Studio → 📝 Report
```

```mermaid
graph LR
    A["📂 Case Init"] --> B["⏳ Timeline"]
    B --> C["🔍 Anomaly"]
    C --> D["🔗 Correlation"]
    D --> E["💾 CRUD"]
    E --> F["🌐 Network"]
    F --> G["📈 Depth"]
    G --> H["📊 Studio"]
    H --> I["📝 Report"]

    style A fill:#818cf8,stroke:#818cf8,color:#fff
    style D fill:#f87171,stroke:#f87171,color:#fff
    style G fill:#fb923c,stroke:#fb923c,color:#fff
    style I fill:#22d3ee,stroke:#22d3ee,color:#fff
```

---

## Module 1: 📂 Case Initialization & Evidence Preservation

**What makes it special:**
- **NLP-powered log ingestion** — investigators describe what they need in plain English; the AI query agent translates to SQL and pulls matching logs from any source
- **Per-case DuckDB vault** — every case gets its own isolated database file, ensuring no cross-contamination
- **SHA-256 hashing on ingest** — every log record is cryptographically hashed the moment it enters the vault
- **Append-only chain-of-custody** — every action (create, modify, export) is recorded with actor, timestamp, hash, and justification — immutable audit trail

**Key stat:** Every single action across all 8 modules writes to this chain-of-custody log.

**Video moment:** *Show creating a case → typing a natural language query → logs flowing into the vault with green ✅ hash confirmations*

---

## Module 2: ⏳ Timeline Reconstruction Helper

**What makes it special:**
- **Multi-source normalisation** — takes logs from AUTH, VPN, FW, DB, FILE, PROXY, DNS, EPP (8+ source types) and normalises them into a single unified schema
- **Millisecond-accurate ordering** — events from different systems (with different timestamp formats) are aligned to create a single chronological truth
- **Rich timeline UI** — interactive event cards with severity colour-coding, source icons, expandable JSON detail panels, and filtering

**Key stat:** Supports 8+ log source types with automatic field mapping.

**Video moment:** *Show the unified timeline scrolling through events — firewall logs interleaved with database queries and VPN logins, colour-coded by severity*

---

## Module 3: 🔍 Anomaly Detection Agent (SHAP Explainable AI)

**What makes it special:**
- **LangGraph 4-node pipeline** — Feature Engineering → Isolation Forest + LOF Training → Scoring → Storing results
- **Dual unsupervised algorithms** — Isolation Forest catches global outliers; Local Outlier Factor catches neighbourhood anomalies — no labelled data needed
- **SHAP explainability** — every anomaly score comes with a SHAP waterfall explaining *why* it's anomalous (e.g., "off-hours login from unusual IP contributed +0.4 to anomaly score")
- **Interactive feature importance** — bar charts showing which features (hour, action, source) drive the most anomalies

**Key stat:** Each event gets an anomaly score (0–1) with a full SHAP explanation — not a black box.

**Video moment:** *Show the SHAP waterfall chart for a flagged event — bars showing "hour_of_day: +0.35, action_LOGIN_FAILED: +0.25" — the AI explaining its reasoning*

---

## Module 4: 🔗 Hybrid Correlation & Root-Cause Analysis

**What makes it special:**
- **Entity graph construction** — automatically discovers USERS, IPs, HOSTS, SESSIONS, PROCESSES, DATA_OBJECTS and builds a connected graph
- **MITRE ATT&CK mapping** — maps observed actions to tactics (Initial Access, Lateral Movement, Exfiltration, etc.)
- **Dual graph visualisation** — investigators choose between a 2D force-directed graph (vis-network) or an immersive 3D rotating graph (react-force-graph-3d)
- **AI narrative** — LLM reads the graph and produces a plain-English root-cause analysis with critical path identification
- **Chat interface** — investigators can ask follow-up questions about the correlation findings

**Key stat:** Supports both 2D and 3D interactive graph visualisation with real-time node exploration.

**Video moment:** *Show the 3D graph rotating with entities as coloured spheres connected by edges — click a red high-severity node to see its connections fan out*

---

## Module 5: 💾 CRUD & Data-Access Analysis

**What makes it special:**
- **Automatic CRUD classification** — every database/file operation is classified as Create, Read, Update, or Delete using action keyword mapping
- **Sensitivity tagging** — target objects are automatically tagged CRITICAL/HIGH/MEDIUM/LOW based on name patterns (e.g., `users_pii` → CRITICAL)
- **7 risk heuristics** — flags high-risk patterns like bulk reads (>100 rows), off-hours DELETE operations, sensitive table exports, anomalous CRUD volumes
- **Actor-target matrix** — shows who accessed what, how much, and how risky it was

**Key stat:** 7 built-in risk detection heuristics with automatic sensitivity classification.

**Video moment:** *Show the CRUD matrix heatmap — red cells where an actor did bulk READs on the `payment_cards` table at 3 AM*

---

## Module 6: 🌐 Network & Exfiltration Analysis

**What makes it special:**
- **6-node LangGraph pipeline** — Parse Flows → Extract Features → Detect Exfiltration → Enrich Threat Intel → Correlate with CRUD → Store
- **7 exfiltration heuristics** — large outbound transfers, DNS tunnelling indicators, unusual protocols, sustained connections to unknown IPs, weekend spikes, encrypted-only traffic
- **CRUD cross-reference** — if a user read 5MB from `customer_data` and then sent 5MB to an external IP, the module links these as a confirmed exfiltration candidate with a confidence score
- **Threat intelligence enrichment** — IP reputation scoring, ASN lookup, geolocation, known-bad IP detection

**Key stat:** Cross-references CRUD data reads with network traffic to confirm data exfiltration with confidence scores.

**Video moment:** *Show the exfiltration candidate card — "jsmith read 5.2MB from customer_data, then sent 4.8MB to 185.x.x.x (RU) — Confidence: 0.87"*

---

## Module 7: 📈 Depth & Impact Assessment

**What makes it special:**
- **4-dimensional depth scoring** — Account (privilege escalation, MFA bypass), System (tiers reached, lateral movement), Data (sensitivity, volume), Control (security gaps exploited) — each scored 0–10
- **Interactive weight sliders** — investigators adjust the relative importance of each dimension and see the severity score recalculate in real-time
- **Radar chart profile** — the shape instantly reveals the penetration profile — a spike toward "Data" means data was the primary target
- **Infrastructure tier heat map** — shows exactly which tiers (web, app, DB, storage, identity, network, endpoint, monitoring) the attacker reached — red tiles for breached, green for untouched
- **Business impact classification** — financial, reputational, regulatory, operational — auto-assessed from the data

**Key stat:** Integrates outputs from ALL 6 prior modules to compute a single overall severity score with 4D breakdown.

**Video moment:** *Show the radar chart (diamond shape indicating deep data + account penetration), then drag the Data weight slider from 30% to 50% — watch the severity jump from 5.8 to 7.2 CRITICAL*

---

## Module 8: 📊 Augment Studio & 📝 Report Writer

### Augment Studio
**What makes it special:**
- **Universal chart builder** — pull data from any of the 6 analysis modules and visualise with 6 chart types (Bar, Line, Area, Donut, Scatter, Radar)
- **Live preview** — change the dataset or chart type and the visualisation updates instantly
- **Forensic-grade export** — every saved chart is SHA-256 hashed and recorded in chain-of-custody

### Report Writer Agent
**What makes it special:**
- **5-node LangGraph pipeline** — Gather Context (all 7 modules) → Generate Sections (LLM per section) → Assemble Report → Remediation → Store with CoC
- **3 report templates** — Technical (10 sections, full forensic detail), Executive (4 sections, C-suite friendly), Regulatory (6 sections, compliance-focused)
- **Inline editing** — investigators can edit any AI-generated section; edits are tracked in chain-of-custody with separate hashes
- **Markdown preview + copy** — full report as formatted Markdown, ready for PDF conversion

**Key stat:** AI generates a full forensic report from all 7 module outputs in one click — with 3 audience-specific templates.

**Video moment:** *Show clicking "Generate Technical Report" → sections appearing one by one (Executive Summary, Timeline, Attack Chain...) → editing a section → copying the full Markdown*

---

## 🔑 Platform-Wide Differentiators

| Feature | Description |
|---------|-------------|
| **🤖 LangGraph AI Pipelines** | Every analysis module uses a multi-node LangGraph state machine — not simple scripts |
| **🔒 Forensic Integrity** | SHA-256 hashing + append-only chain-of-custody on EVERY operation |
| **💡 Explainable AI** | SHAP explanations on anomaly detection — the AI shows its reasoning |
| **🔄 All-Module Integration** | Each module feeds into the next — Depth reads from ALL 6 prior modules |
| **🎨 Premium UI** | Dark glassmorphism theme, Recharts visualisations, 3D force graphs, interactive sliders |
| **🔀 Dual LLM Support** | Ollama (local, free) or Google Gemini (API) — investigators toggle per-request |
| **📋 3 Report Templates** | Technical, Executive, Regulatory — each with different section structures |
| **⏳ 8+ Log Sources** | AUTH, VPN, FW, DB, FILE, PROXY, DNS, EPP — all normalised into one timeline |

---

## 🧩 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, LangGraph |
| **AI/ML** | Isolation Forest, LOF, SHAP, Ollama/Gemini |
| **Database** | DuckDB (per-case vault files) |
| **Frontend** | Next.js 14, Recharts, vis-network, react-force-graph-3d |
| **Integrity** | SHA-256, append-only chain-of-custody |

---

## 📊 By the Numbers

| Metric | Value |
|--------|-------|
| Modules | 8 |
| LangGraph pipelines | 6 (Anomaly, Correlation, CRUD, Network, Depth, Report) |
| DuckDB tables | 25+ |
| API endpoints | 50+ |
| Chart types | 6 |
| Report templates | 3 |
| Log source types | 8+ |
| Risk heuristics | 14+ (7 CRUD + 7 Network) |
| Depth dimensions | 4 (Account, System, Data, Control) |

---

## 🎥 Suggested 1-Minute Video Flow

| Time | Scene | What to Show |
|------|-------|-------------|
| 0:00–0:08 | **Hook** | Platform title + "AI-powered forensic log analysis" + case creation |
| 0:08–0:15 | **Ingest** | NLP query pulling logs → unified timeline scrolling |
| 0:15–0:22 | **Detect** | Anomaly scores with SHAP waterfall → red flagged events |
| 0:22–0:32 | **Correlate** | 3D entity graph rotating → MITRE ATT&CK tactics overlay |
| 0:32–0:40 | **Analyse** | CRUD matrix heatmap → Network exfil candidate with confidence |
| 0:40–0:48 | **Assess** | Depth radar chart + weight sliders → severity recalculating |
| 0:48–0:55 | **Report** | Studio chart builder → Report generating sections |
| 0:55–1:00 | **Close** | All 8 modules sidebar → "Forensic-grade. AI-powered. Evidence integrity." |
