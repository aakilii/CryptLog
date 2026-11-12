# 🛡️ Architectural Analysis: Guided Playbooks & The Cryptographic Export Lane

**Author:** Lead Forensics Architect & System Designer  
**Target:** Analyzing "Playbook A", "Playbook B", and the "Snapshotting & Deterministic Export Manifest".  

You are aggressively steering this platform away from a generic SIEM and towards an automated, court-admissible Forensic Wizard. The architecture you've proposed—specifically "Snapshotting (not live queries)" and "Gap Detectors"—is the gold standard of digital forensics. 

Here is my brutal, highly detailed analysis of our current status, the gaps, and exactly how we must adopt these features to ensure they are sustainable.

---

## 1. Playbook A: Transfer Reconstruction (Insider Threat)

**The Vision:** An automated guided path connecting Windows files → USB/BT/Email → Destination IPs, without the investigator manually joining the schemas.

### 🛑 Current Status & Needs
*   **What we have:** Our backend normalizes heterogeneous logs into `unified_timeline`. Module 04 (Correlation) establishes standard entity links. 
*   **What we need:** We critically need the **"Gap Detector"**. Currently, if a user filters for Bluetooth, it just returns 0 results. An investigator doesn't know if the suspect *didn't* use Bluetooth, or if the SOC simply forgot to upload the Bluetooth logs.

### 🧠 Honest Opinion & Deep Look Up
*   **Honest Opinion:** The "Files × Channel × Destination" matrix is brilliant. However, IP attribution without guessing is hard because NAT/DHCP obfuscates email IPs. 
*   **How to Adopt (The Gap Detector):** When Playbook A is initialized, the backend must execute a Pre-Flight Check: `SELECT DISTINCT source_system FROM raw_events`. If `source_system` does not contain `Android_ADB` or `BTHPORT`, the UI halts and displays exactly what telemetry is missing. 
*   **Sustainability:** Do not hardcode the Playbooks. Build them as JSON declarative schemas (e.g., `playbook_a.json`) that define the required data sources and the 3 output UI blocks. This allows us to add Playbook C, D, and E without writing new frontend code.

### 🎯 Suggestions & Do's / Don'ts
*   **DO:** Restrict the IP Address Panel strictly to IPs that possess an explicit `evidenceRef`. If the IP came from a Threat Intel guess, it must be hidden or heavily flagged.
*   **DON'T:** Let the investigator proceed blindly. If logs are missing, force them to click "Acknowledge Missing Telemetry" so the final report officially states the blindspots.

---

## 2. Playbook B: Ransomware Reconstruction

**The Vision:** A visual "Infection → Execution → Encryption Burst" storyline that answers the exact questions executives and insurers care about (When did it start? How many files encrypt per minute?).

### 🛑 Current Status & Needs
*   **What we have:** Module 05 (CRUD) analyzes file operations. Module 03 (SHAP) detects anomalies. 
*   **What we need:** We need the **"Files encrypted per minute"** SQL logic and the automated **Critical Path** exporter.

### 🧠 Honest Opinion & Deep Look Up
*   **Honest Opinion:** Trying to track every ransomware file is a fool's errand. Focusing the UI on the *rate of encryption* (files per minute) and the *ancestral process* is exactly what an investigator needs during triage.
*   **How to Adopt:** We build a specific Vega-Lite chart in Augment Studio. The SQL behind it is a DuckDB time-bucket: `SELECT time_bucket(INTERVAL '1 minute', ts) AS minute, COUNT(*) FROM unified_timeline WHERE action='UPDATE' GROUP BY minute`. This feeds the "Files per minute" chart effortlessly.
*   **Sustainability:** Module 04 (Correlation) must be heavily optimized for recursive CTEs. Finding Patient Zero requires walking up the `parent_process_id` tree. DuckDB handles recursion well, but graph depth should be capped to prevent infinite loops on corrupted memory dumps.

---

## 3. Snapshotting and Deterministic Export Lane (The Fortress)

**The Vision:** A tamper-evident export bundle with a signed RFC 8785 manifest, proving the report is derived from preserved evidence. **Crucial Rule:** Exports rely on *snapshots*, not *live queries*.

### 🛑 Current Status & Needs
*   **What we have:** We have a headless PDF exporter (`print/page.tsx`). We have SHA-256 hashing for the `chain_of_custody`.
*   **What we need:** Our current Studio queries DuckDB *live*. This is a fatal flaw for forensics. If an investigator builds a report today ("10 files accessed"), and someone adds a new log file tomorrow, the live query will update to "15". The exported report no longer matches the live canvas.

### 🧠 Honest Opinion & Deep Look Up
*   **Honest Opinion:** The shift to "snapshots (not live queries)" is the single most important architectural decision in this entire specification. A report is a point-in-time reflection of the database.
*   **How to Adopt:** When the investigator creates an `evidenceCard` (as specified in our prior analysis), the backend MUST execute the query at that exact millisecond, render the data (JSON/SVG), and save it immutably to an artifact storage folder (e.g., `cases/c1/artifacts/`). The `evidenceCard` pointers map to *that static snapshot blob*.
*   **The Export Bundle:** The export route must zip the PDF, the Canvas AST, the JSON snapshots, and execute the RFC 8785 canonicalisation to generate the final `manifest.json`.
*   **Alternatives:** If you use live queries, you must version-control the entire DuckDB file (like Git commits) which eats hundreds of gigabytes of storage. Snapshotting the explicit chart outputs is infinitely more sustainable and performant.

### 🎯 Suggestions & Do's / Don'ts
*   **DO:** Implement optional RFC 3161 (Time-Stamp Protocol). By Ping'ing a public TSA server (like FreeTSA or a corporate internal PKI) with the bundle hash, you get a cryptographic signature proving the report existed at that exact nanosecond. This is invincible in court.
*   **DON'T:** Let the PDF generator run DuckDB `SELECT` statements! The PDF generator must only read from the immutable `cases/c1/artifacts/` snapshotted files.

---

## ⚡ Final Verdict & Prioritization

By chaining these components together, you achieve the Holy Grail of DFIR software: **An automated, guided investigation that mathematically locks itself upon export.**

**Immediate Development Priorities:**
1.  **The Snapshot Engine:** We must immediately modify our backend `evidence_card` creation logic. When an evidence card is made, it must generate and save the static JSON/SVG payload to disk, completely divorcing the UI from live DuckDB updates once the card is minted. 
2.  **The Manifest Generator:** Writing the Python script that zips the AST and artifacts, passes them through RFC 8785 canonicalization, and signs the manifest.
3.  **The Gap Detector:** Building the pre-flight check logic for the Playbooks. 
