# Canonical Court-Ready Pipeline Design & Architecture

> **Goal:** Build a deterministic, legally defensible, and scenario-agnostic reporting data pipeline across any cyber attack scenario.

## 1. The Core Event-Driven State Machine (The Pipeline)

To achieve deterministic scaling without LLM timeouts or hallucinated claims crossing admissibility gates, the system utilizes an **Event-Driven State Machine** orchestration pattern.

1. **Intake & Normalization (STATE: INGESTING)**
   - **Action:** Raw logs uploaded -> Hash generated -> Stored in WORM (Write Once Read Many) storage -> Normalized to UTC.
   - **Engine:** DuckDB for rapid normalization and schema enforcement. 
   - **Output:** Immutable 
aw_events table + contextual baseline.

2. **Scenario Inference & Clarification (STATE: CLARIFYING)**
   - **Action:** System heuristics + AI pass map logs to a scenario_capability_map.
   - **Human-in-the-Loop Gateway:** If scenario confidence < 85%, the system halts and generates clarifying questions for the investigator. 

3. **Dynamic Planning (STATE: PLAN_DRAFT -> PLAN_APPROVED)**
   - **Action:** Historical Learning Service (
report_learning_service.py) proposes a hierarchical report structure based on the inferred scenario and evidence density.
   - **Action:** Investigator reviews the outline, makes modifications, and *cryptographically signs* the approved plan hash.

4. **Parallel Section Execution (STATE: EXECUTING_SECTIONS)**
   - **Action:** Isolated sections (Timeline, Identity, Data Movement) run in parallel worker threads.
   - **AI Workflow per Section:** 
     1. Hypothesis Generation
     2. Evidence Fetch (Querying DuckDB)
     3. Evaluate (Cross-check against evidence constraints)
     4. Compose (LLM drafting)
     5. Bind Evidence (Every sentence mapped to a UUID evidence key).
   - **Resiliency:** If Section C fails, Sections A and B complete. Section C logs a fault but doesn't crash the entire 150-page pipeline.

5. **Admissibility Gates & Zero-Trust Verification (STATE: VERIFYING)**
   - **Action:** Deterministic rules engine verifies:
     - No unreferenced claims (Hallucination check).
     - Strict AI redaction applied (PII sanitized).
     - Visual coordinate bounds (Canvas overlap check).
   - **Output:** Final JSON AST and evidence map.

6. **Cryptographic Export (STATE: EXPORTED)**
   - **Action:** Studio V4 Canvas renders the final PDF.
   - **Action:** PAdES-B-LT X.509 signature applied with RFC3161 trusted timestamping (India-Compliant).
   - **Output:** Court-Ready Signed PDF + Audit Replay Bundle.

---

## 2. Alternate Branches & Trade-Offs

### A. Orchestration: Synchronous API vs. Event-Driven Message Queue (Chosen)
* **Alternate (Synchronous API):** FastAPI routes handle the entire execution loop.
  * *Trade-off:* Easy to build initially, but long-running LLM calls trigger HTTP timeouts. Single section failures fail the whole report.
* **Chosen (Event-Driven + State Machine):** FastAPI registers intent and streams status (/api/cases/{case_id}/status). Background workers (e.g., Celery/Temporal) handle execution.
  * *Reasoning:* AI workloads are highly variable. You need 100% resumability. If a node dies midway through a report, we must resume from the exact section checkpoint.

### B. Evidence Binding: At Generation vs. Post-Generation (Chosen)
* **Alternate (Post-Generation mapping):** Generate the entire narrative, then use an NLP embedding model to link sentences back to evidence.
  * *Trade-off:* High risk of orphaned claims and hallucinations slipping through. Unacceptable for India-compliant court readiness.
* **Chosen (Inline Deterministic Generation):** The LLM is forced to output JSON arrays of [claim, [evidence_uuid_1, ...]]. 
  * *Reasoning:* Forces the LLM to ground *every* assertion. The backend verifier drops any claim array missing a valid UUID.

### C. Output Template: Fixed Types vs. Dynamic AST (Chosen)
* **Alternate (Fixed Template Code):** Hardcoded Python scripts for each scenario type (legacy pattern).
  * *Trade-off:* Impossible to maintain. Cyber capabilities merge (e.g., Ransomware + Exfiltration). 
* **Chosen (Dynamic AST & Scenario Capability Matrix):** DuckDB identifies capabilities present -> dynamically pulls modules -> outputs an Abstract Syntax Tree (AST) -> Studio V4 renders the AST.
  * *Reasoning:* Infinitely scalable to new attack types. UI rendering is strictly decoupled from the legal reporting logic.

---

## 3. Microsoft Well-Architected Framework Application

### Security (Zero Trust focus)
* **Assume Breach / Least Privilege:** AI models *never* have direct access to the raw logs DB. They query a sanitized intermediate view (iew_evidence_redacted).
* **Data Provenance:** The chain-of-custody table logs (user_id, timestamp, action, pre_hash, post_hash) for every operation.

### Reliability
* **Model Fallbacks:** If the primary LLM fails or hallucinates 3 times on a section, the system automatically degrades to a "Data Table Only" output for that section, attaching an empty narrative with an "Unsupported" diagnostic warning.

### Performance Efficiency
* **DuckDB for embedded OLAP:** Used instead of Postgres for analytics, ensuring 10M+ events can be aggregated on a standard node without heavy REST networking overhead.
* **Parallel Execution:** Decoupling the AST generation allows a 100-page report to generate 20 independent sections concurrently.

---

## 4. Architecture Decision Records (ADRs)

### ADR-001: Adopt Event-Driven State Machine for Pipeline Orchestration
* **Context:** Compiling court-ready reports requires 10+ sequential, slow AI interactions, human-in-the-loop checkpoints, and complex visual rendering. Synchronous HTTP requests via FastAPI time out.
* **Decision:** Decouple pipeline from HTTP request life-cycle using a State Machine pattern.
* **Consequences:** 100% resumability on failure and parallel execution, balanced by increased infrastructure overhead.

### ADR-002: Mandatory Inline UUID Evidence Binding
* **Context:** AI generation sometimes hallucinates facts or fails to attribute claims to specific logs, violating admissibility constraints.
* **Decision:** All composition modules must use strict JSON schema enforcement (e.g., Structured Outputs). Admissibility gates run post-generation to strip any sentence lacking a mathematically verified cross-reference.
* **Consequences:** Verifiable chain-of-custody guaranteed, at the cost of higher token usage and stricter parsing logic.

# Architecture Design: Canonical Court-Ready Forensic Pipeline

**Date:** April 10, 2026  
**Status:** Canonical Reference Architecture  

---

## 1. Executive Summary & Core Principle

To achieve deterministic, legally defensible scalability across any cyber attack scenario, the pipeline abandons static report templates and synchronous generation loops. Instead, it utilizes an **Event-Driven State Machine** combined with **Inline Evidence Binding**.

This architecture guarantees that the pipeline completely isolates the fragile, non-deterministic nature of LLM generation behind rigid, zero-trust validation gates, ensuring output is always court-admissible.

---

## 2. The Detailed Canonical Workflow (State Machine)

### Phase 1: Intake & Normalization (`STATE: INGESTING`)
- **Action:** Raw logs (Windows Event, EDR, Network, Mobile) are uploaded and a cryptographically verifiable SHA-256 hash is generated. 
- **Storage Strategy:** Stored in a WORM (Write Once Read Many) compliant raw vault.
- **Engine execution:** DuckDB ingests raw logs and normalizes timestamps to UTC while retaining timezone metadata for localized display.

### Phase 2: Scenario Inference & Clarification (`STATE: CLARIFYING`)
- **Action:** A heuristic/LLM pass maps normalized logs to a `scenario_capability_map` (e.g., assessing if it’s pure insider threat, or ransomware with exfiltration).
- **Human-in-the-Loop Constraint:** If the inferred capability confidence drops below `85%`, the system automatically pauses and outputs Clarification Questions for the primary investigator before proceeding.

### Phase 3: Dynamic Planning (`STATE: PLAN_DRAFT -> PLAN_APPROVED`)
- **Action:** The Orchestrator calls `report_learning_service.py` to generate a hierarchical outline based on both the evidence profile and historical templates.
- **Action:** The Investigator edits the proposed AST (Abstract Syntax Tree), adding or removing sections.
- **Locking:** Once approved, the plan hash is locked in the database. Any structural modifications after this point require a new plan version and re-approval.

### Phase 4: Parallel Section Execution (`STATE: EXECUTING_SECTIONS`)
- **Action:** Distinct sections (Timeline, Identity, Data Movement, Impact) run as isolated backend worker threads.
- **Module Loop (per section):**
  1. `Hypothesis Generation` -> 2. `Evidence Fetch` (DuckDB SQL) -> 3. `Evaluate` -> 4. `Compose Narrative` -> 5. `Bind Evidence`.
- **Fault Tolerance:** If the "Identity Validation" section fails due to missing AD domains, it logs a localized fault and falls back to a "Data Table Only" view. The rest of the report (Timeline, Root Cause) continues unaffected.

### Phase 5: Admissibility Gates & Zero-Trust Validation (`STATE: VERIFYING`)
- **Action:** The system executes a final logic pass over the generated structured AST.
- **Checks applied:**
  - **Hallucination Gateway:** Strips and rewrites any claim lacking a verified evidence UUID.
  - **Redaction Engine:** Sanitizes exact device IDs, IP addresses, or PII based on user viewing clearance or generation mode (AI proxying vs. Investigator readout).
  - **Layout Fidelity:** Asserts Studio V4 Canvas boundary bounds.

### Phase 6: Cryptographic Export (`STATE: EXPORTED`)
- **Action:** The final validated JSON AST is rendered into a PDF via the UI/PDF generator service.
- **Action:** An India-compliant **PAdES-B-LT X.509 signature** combined with an **RFC3161 trusted timestamp** is applied securely on the server.
- **Action:** Chain-of-custody logs are packaged into a final ZIP audit trace accompanying the signed report.

---

## 3. Alternative Branches & Trade-Offs

### A. Orchestration: Synchronous API vs. Event-Driven Message Queue [CHOSEN]
- **Alternate (Synchronous API):** Use FastAPI request/response to manage the life-cycle of a report build.
  - *Trade-off:* Easiest to develop, but entirely lacks resumability. A timeout during a 100-page report generation destroys 30 minutes of work.
- **Chosen (Event-Driven State Machine):** FastAPI only registers intent and updates State objects. Background workers handle the loop.
  - *Reasoning:* Essential for large-scale AI generation. Allows independent modules to resume instantly if rate limits or API outages occur.

### B. Evidence Binding: At Generation vs. Post-Generation Analysis [CHOSEN]
- **Alternate (Post-Generation Reference Mapping):** The LLM generates the text, and a secondary NLP system tries to map sentences back to log entries.
  - *Trade-off:* Cheaper and simpler prompt engineering, but high risk of "implying" facts that don't directly exist in the logs (hallucination).
- **Chosen (Inline Deterministic Generation):** The LLM forces JSON outputs structured as `[claim_text, [evidence_uuid_1, evidence_uuid_2]]`.
  - *Reasoning:* Forces LLM grounding natively. Verifiers can instantly flag unsupported arrays and strip them from the report, natively preventing court-inadmissible outputs.

### C. Output Generation: Fixed AI Scripts vs. Universal AST (Abstract Syntax Tree) [CHOSEN]
- **Alternate (Fixed AI Scripts):** Hardcoded pipelines tailored per-threat (`ransomware_pipeline.py`, `mobile_leak.py`).
  - *Trade-off:* Brittle against hybrid attacks (e.g. ransomware combined with mobile exfiltration).
- **Chosen (Universal AST Strategy):** Dynamic section graphs rendered sequentially.
  - *Reasoning:* Allows dynamic visual inclusion—a Timeline Section generates the same deterministic visual node whether it's network data. Decouples UI perfectly from AI backends.

---

## 4. Microsoft Well-Architected Framework Application

### Security (Zero Trust focus)
- **Assume Breach / Least Privilege:** AI models *never* interface directly with the raw evidence database. They ingest read-only, contextually sanitized partial views (`view_evidence_redacted`).
- **Data Provenance Enforcement:** The `chain-of-custody` service ensures every interaction inserts an immutable `(user, timestamp, purpose, pre_hash, post_hash)` log.

### Reliability (AI Architecture Specific)
- **Model Fallbacks:** Implementation of a strict fallback ladder (`chart + narrative -> chart + table -> table + supported warning`) ensures a report always completes without 3AM runtime crashes.
- **Non-Deterministic Handling:** A `temperature=0.0` bounded response is mandated for evidential conclusions; exploratory drafting tasks utilize localized LLM temperature variances.

### Performance Efficiency
- **Push vs. Pull DB Optimization:** Leveraging embedded DuckDB for direct analytical querying minimizes memory overhead and network payload latency associated with 10M+ event timelines, compared to external database roundtrips.

---

## 5. Required Architecture Decision Records (ADRs)

To formally operationalize this architecture into the `operation-room/docs/architecture` directory, the following ADRs constrain future implementation:

### `ADR-001: Adopt Event-Driven State Machine for Pipeline Orchestration`
- **Context:** Large forensic report assembly requires slow AI generation steps subject to transient network failures. Synchronous systems fail silently.
- **Decision:** Separate the UI invocation out of the generation loop. Maintain a canonical database machine state that tracks progression precisely (`PLAN_APPROVED` -> `SECTION 2 EXECUTING`, etc). 

### `ADR-002: Mandatory Inline UUID Evidence Binding during Composition`
- **Context:** Legal admissibility is paramount. Narrative statements must remain strictly coupled to underlying raw logs.
- **Decision:** Mandate schema-locked structured JSON inference from LLM calls ensuring every output statement embeds an explicit metadata mapping to evidence `key_id` entries within the vault.