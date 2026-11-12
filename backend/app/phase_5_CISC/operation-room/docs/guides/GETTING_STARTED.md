# Getting Started — How to Run an Investigation

> A step‑by‑step walkthrough for investigators using the Operation Room for the first time.

---

## Prerequisites

| Requirement | Description |
|---|---|
| **Access** | Valid credentials with the `investigator` role in the Operation Room. |
| **NLP Query Agent** | The NLP Query Agent service must be running and accessible. |
| **Log store populated** | Relevant logs must have been ingested and parsed by the upstream Ingestion & Parsing Phase. |
| **Configuration** | Internal IP ranges, data‑sensitivity catalogue and (optionally) threat‑intel API keys configured. |

---

## Step 1 — Create a Case

1. Open the **Operation Room** UI and click **New Case**.
2. Fill in the case form:
   - **Title** — short, descriptive (e.g., *"Suspected Insider Threat — J. Doe"*).
   - **Description** — background context for the investigation.
   - **Classification** — Unclassified / Confidential / Secret / Top Secret.
   - **Priority** — Low / Medium / High / Critical.
   - **Lead Investigator** — auto‑populated from your profile.
3. Click **Create**. A unique `case_id` is generated and the Case Vault (DuckDB file) is initialised.

> 📝 The system logs a `CASE_CREATED` chain‑of‑custody event automatically.

---

## Step 2 — Define Scope & Collect Evidence

1. Navigate to the **Scope** tab.
2. Add one or more scope entries:
   - **Time window** — start and end timestamps.
   - **Target actors** — user accounts, service principals.
   - **Target systems** — hostnames, services, applications.
   - **Log types** — Authentication, VPN, Firewall, DB, Application, Endpoint, File.
3. Click **Collect Evidence**.
   - The system sends queries to the NLP Query Agent for each scope entry.
   - Result sets are imported into the Case Vault.
   - SHA‑256 hashes are computed and stored in `evidence_hashes`.
   - Every import is logged in the chain of custody.
4. Review the import summary — verify record counts and flag any `NO_DATA_FOUND` entries.

> ⚠️ **Do not proceed** until you have confirmed that the imported data covers your investigation scope and that all hashes are recorded.

---

## Step 3 — Build the Timeline

1. Navigate to **Modules → Timeline Reconstruction**.
2. Configure any time‑sync adjustments if needed (usually automatic).
3. Click **Build Timeline**.
4. Review the **Unified Timeline** — look for:
   - Gaps (missing time ranges may indicate log‑collection issues).
   - **Anchor events** — first login, first database query, first outbound transfer.
5. Use filters and zoom controls to explore specific windows.

---

## Step 4 — Detect Anomalies

1. Navigate to **Modules → Anomaly Detection**.
2. Select algorithm (default: Isolation Forest) and adjust contamination rate if desired.
3. Click **Run Detection**.
4. Review the **Anomaly Dashboard**:
   - Score distribution histogram.
   - Top anomalous events table.
   - Anomaly clusters (grouped by similar patterns).
5. Drill into individual anomalies to understand contributing features.

---

## Step 5 — Correlate & Map to ATT&CK

1. Navigate to **Modules → Correlation & Root‑Cause**.
2. The module automatically builds the entity‑relationship graph.
3. Review:
   - **Correlation Graph** — interactive network diagram of actors, IPs, hosts, sessions.
   - **ATT&CK Mapping** — techniques matched to observed events.
   - **Critical Paths** — the most significant chains of events.
4. Click on any node to **pivot** — see all related events and linked entities.
5. Optionally enable **Threat‑Intelligence Enrichment** for external IP/domain lookups.

---

## Step 6 — Analyse Data Access (CRUD)

1. Navigate to **Modules → CRUD Analysis**.
2. The module classifies all database queries and API calls into CRUD categories.
3. Review:
   - CRUD distribution (pie chart).
   - Top accessed data objects with sensitivity levels.
   - Bulk‑read events flagged for potential exfiltration staging.

---

## Step 7 — Analyse Network & Exfiltration

1. Navigate to **Modules → Network & Exfiltration**.
2. Review:
   - Outbound flow summary — top destinations, volume, protocols.
   - Exfiltration indicators — events linking bulk reads to outbound transfers.
   - Geo‑map of external connections.
   - DNS anomalies (if DNS logs are available).

---

## Step 8 — Assess Depth & Impact

1. Navigate to **Modules → Depth & Impact**.
2. Review the **Depth Matrix** — per‑actor scores for account, system, data and control depth.
3. Review the **Impact Summary** — regulatory exposure, estimated records at risk, recommended actions.
4. Examine the **Heat Map** and **Radar Charts** for visual overview.

---

## Step 9 — Create Visualisations

1. Navigate to **Augment‑Studio**.
2. Use **templates** for common charts (login histogram, CRUD pie, network graph) or create **custom charts**.
3. Save charts to the case vault — they will be available for embedding in the report.

---

## Step 10 — Write the Report

1. Navigate to **Modules → Report Writer**.
2. The bot generates a **draft report** from all module outputs.
3. **Review and edit** each section:
   - Executive Summary
   - Scope & Methodology
   - Timeline of Events
   - Findings (Anomalies, Correlation, Data Access, Network/Exfil)
   - Depth & Impact Assessment
   - Chain of Custody *(auto‑generated, review for completeness)*
   - Conclusions & Recommendations
4. Insert any additional charts from Augment‑Studio.
5. Mark the report as **Final**.
6. Click **Export** — the system sends `report.json` to the Report‑Export Phase, which renders a PDF.

---

## Tips & Best Practices

| Tip | Detail |
|---|---|
| **Re‑visit early modules** | If you find new leads in Step 5, go back to Step 2 and expand the scope, then re‑run downstream modules. |
| **Use the Interactive Query Assistant** | Ask questions in natural language anytime (e.g., *"How many logins did jdoe have after midnight?"*). |
| **Document your reasoning** | Add notes and justifications in the report as you go — forensic transparency matters. |
| **Check the Chain of Custody** | Before finalising, review the CoC ledger to ensure there are no gaps. |
| **Hash verification** | Before presenting evidence, re‑verify hashes to confirm integrity. |

---

## Troubleshooting

| Issue | Resolution |
|---|---|
| NLP Query Agent returns no data | Verify the log store contains data for the specified scope. Check credentials and agent connectivity. |
| Timeline shows large gaps | Check whether all relevant log sources are included in the scope. Investigate potential log‑collection failures upstream. |
| Anomaly detection flags too many / too few events | Adjust the contamination rate parameter. Lower = fewer anomalies; higher = more. |
| Charts won't render | Ensure the data source table is non‑empty. Check for NULLs in mapped fields. |
| Report export fails | Validate `report.json` against the expected schema. Check connectivity to the Report‑Export Phase. |

---

> **For deeper technical details, see the [Architecture & Extensibility Guide](ARCHITECTURE.md) and individual module READMEs in the `modules/` directory.**
