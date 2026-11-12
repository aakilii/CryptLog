---
goal: Canonical Court-Ready Pipeline for Any Cyber Attack Scenario (India)
version: 2.0
date_created: 2026-04-10
last_updated: 2026-04-10
owner: Operation Room Architecture
status: Planned
tags: [architecture, process, forensic, court-ready, evidence-vault, deep-research, export-governance]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a deterministic, scenario-agnostic, India-first canonical pipeline for court-ready forensic reporting with dynamic sectioning, embedded evidence-key citations, autopilot-first execution, and investigator override governance.

## 1. Requirements & Constraints

- **REQ-001**: Canonical progression order is fixed and mandatory: imported logs -> investigator scenario intake -> clarification Q&A -> adaptive report template with estimated page bands -> investigator feedback -> plan revision -> plan approval -> section-by-section execution -> quality/admissibility gates -> export package -> closure audit.
- **REQ-002**: Accept investigator-provided scenario as primary intent and infer subtypes from logs; do not replace user scenario classification.
- **REQ-003**: Support any cyber attack scenario by capability routing (timeline, identity, data movement, network, anomaly, impact), not by scenario-specific scripts.
- **REQ-004**: Unknown log formats continue with partial confidence and explicit uncertainty labels; never fail silently.
- **REQ-005**: Dynamic section and subheading generation must be based on evidence clusters and confidence-weighted findings.
- **REQ-006**: Report length is dynamic; no hard page cap. Generation logic must support 30 to 150+ page outputs based on evidence volume and legal needs.
- **REQ-007**: Every generated sentence must contain embedded evidence-key references for redact-mode traceability and user verification.
- **REQ-008**: Autopilot with final gate is default; human-per-section mode must remain available.
- **REQ-009**: If one section fails validation, continue other independent sections in parallel and aggregate unresolved issues into final gate.
- **REQ-010**: Timeline chart is mandatory; all other visuals are generated when section intent and data support them.
- **REQ-011**: Pixel-perfect fidelity between Studio canvas and exported PDF is mandatory.
- **REQ-012**: LLM usage is provider-agnostic (local/cloud/hybrid), selected dynamically by policy and runtime health.
- **REQ-013**: Unsupported claims are rewritten with uncertainty language and tagged with confidence and evidence insufficiency reasons.
- **REQ-014**: Web UI must expose live telemetry and per-section gate status.
- **REQ-015**: SLA must be enforced for full-run completion with progressive results and resumability.
- **REQ-016**: Identity resolution uses all available sources (AD, IdP, device, email, network) with dynamic confidence scoring.
- **REQ-017**: Normalize timestamps to UTC and preserve original timezone/offset in evidence metadata.
- **REQ-018**: Export is allowed with investigator override even if non-critical gates fail; override must require signed rationale and risk acknowledgement.

- **SEC-001**: Chain-of-custody must log user identity, timestamp, purpose, and hash-before/hash-after for each evidence access and mutation-equivalent operation.
- **SEC-002**: Digital signature on exports is mandatory using PAdES-B-LT with X.509 certificate and RFC3161 trusted timestamp (India-compliant signing profile).
- **SEC-003**: AI mode must always redact sensitive values (PII, credentials, secrets, direct identifiers, IP/device exacts, legal-hold content) and expose only semantic-safe summaries and key references.
- **SEC-004**: Report mode defaults to redacted output; full evidence reveal requires investigator unlock with reason code and audit stamp.

- **POL-001**: Raw evidence retention default is 7 years or legal-hold duration (whichever is longer); key summaries retained for case lifetime + 2 years.
- **POL-002**: LLM prompts/outputs must be stored for replay and reviewer visibility, with role-based access controls.

- **CON-001**: Do not mutate immutable raw evidence (`raw_events`) in any pipeline stage.
- **CON-002**: Keep routes thin; all orchestration logic belongs to service layer/state machine.
- **CON-003**: Reuse existing endpoints: `/deep-research/*`, `/report-evidence/*`, `/api/learning/*`, `/api/v4/studio/*` before adding new ones.

- **GUD-001**: Court-facing final narrative generation pass uses deterministic model settings (`temperature=0.0`, `top_p=1.0`); exploratory drafting may use bounded creativity (`temperature<=0.3`).
- **GUD-002**: Attribution confidence thresholds are dynamic by evidence quality and source agreement, not static constants.

- **PAT-001**: Canonical state machine pattern: `intake -> clarify -> plan_draft -> plan_revised -> plan_approved -> section_execute -> section_verify -> final_gate -> export -> close`.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Lock canonical contracts and remove current architectural blockers.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-001 | Define canonical contract DTOs and enums in `operation-room/backend/app/routes/deep_research.py` and `operation-room/backend/app/services/deep_research/orchestrator.py` with strict status transitions and transition guards. |  |  |
| TASK-002 | Repair SQL compatibility defect in `operation-room/backend/app/services/auto_report_builder.py` where daily aggregation currently uses unsupported `DATE(normalised_ts)` path; update dependent chart and summary builders. |  |  |
| TASK-003 | Add timeline build deterministic diagnostics in `operation-room/backend/app/services/timeline_service.py` and route response at `POST /api/cases/{case_id}/timeline/build` for zero-event outcomes (`normalized_rows`, `rejected_rows`, `schema_mismatch_reasons`). |  |  |
| TASK-004 | Replace scenario-specific script dependency (`operation-room/backend/scripts/generate_mobile_exfiltration_report.py`) with generic run entrypoint contract in deep-research orchestrator; keep script as non-production reference only. |  |  |

### Implementation Phase 2

- GOAL-002: Build scenario-agnostic planning and dynamic template generation.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-005 | Implement scenario interpretation flow in `operation-room/backend/app/services/scenario_analyzer.py` to always anchor investigator intent, infer subtypes, and emit `scenario_capability_map`. |  |  |
| TASK-006 | Implement adaptive template assembler in `operation-room/backend/app/services/report_learning_service.py` combining historical patterns (`/api/learning/recommend-structure`) and live evidence metadata to generate heading/subheading tree with page estimates. |  |  |
| TASK-007 | Add plan revision engine in `operation-room/backend/app/services/deep_research/plan_manager.py` to apply user feedback diffs deterministically and persist revision lineage (`rev_id`, `changed_nodes`, `justification`). |  |  |
| TASK-008 | Enforce plan hash lock in `POST /deep-research/investigations/{investigation_id}/plan/approve` and block section execution when plan has unapproved mutations. |  |  |

### Implementation Phase 3

- GOAL-003: Enforce embedded evidence-key citation model and metadata-rich vault operations.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-009 | Integrate all module findings into `/report-evidence/{case_id}/store-from-finding` through `operation-room/backend/app/services/deep_research/analysis_integration.py` with mandatory fields: `why_recorded`, `decision_context`, `source_module`, `confidence`, `section_id`. |  |  |
| TASK-010 | Extend `operation-room/backend/app/services/report_evidence_service.py` to support sentence-level citation bundles and reverse lookup (sentence -> key_ids -> source findings). |  |  |
| TASK-011 | Update composition services (`operation-room/backend/app/services/report_agent.py`, `operation-room/backend/app/services/auto_report_builder.py`) so each generated sentence includes embedded key refs and confidence tags. |  |  |
| TASK-012 | Implement strict AI-mode redaction resolver in `operation-room/backend/app/services/export_service.py` and `operation-room/backend/app/routes/report_evidence.py` to prevent identifier leakage in AI-facing contexts. |  |  |

### Implementation Phase 4

- GOAL-004: Implement section execution loop with autopilot-first and parallel failure isolation.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-013 | Implement section state machine in `operation-room/backend/app/services/deep_research/orchestrator.py`: `hypothesis -> module_select -> fetch -> evaluate -> conclude -> evidence_bind -> compose -> visualize -> align_verify -> section_gate`. |  |  |
| TASK-014 | Add parallel scheduler in `operation-room/backend/app/services/unified_orchestrator.py` to continue independent sections when one section fails; store blocked section reasons without halting run. |  |  |
| TASK-015 | Implement mode handler in `operation-room/backend/app/routes/deep_research.py`: autopilot default with final approval gate; human mode requires per-section approval endpoint checkpoint. |  |  |
| TASK-016 | Add uncertainty rewrite pass in `operation-room/backend/app/services/deep_research/engine.py` for unsupported claims and attach rationale metadata for reviewer visibility. |  |  |

### Implementation Phase 5

- GOAL-005: Build chart/component strategy with robust fallback and strict layout fidelity.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-017 | Define section-to-visual policy in `operation-room/backend/app/services/chart_renderer.py` with mandatory timeline chart and conditional charts (channel flow, actor graph, IP matrix, anomaly trend, evidence chain). |  |  |
| TASK-018 | Implement visual fallback ladder in `operation-room/backend/app/routes/studio_v4.py`: chart -> table -> narrative summary, with failure reason persisted. |  |  |
| TASK-019 | Add layout verification in `operation-room/backend/app/services/reportlab_pdf_service.py` and export precheck routes to assert coordinate bounds, overlap-free placement, spacing consistency, and page-break safety. |  |  |
| TASK-020 | Persist chart provenance in `chart_registry` (query hash, dataset hash, renderer version, generated_at, section_id) and link to chain-of-custody records. |  |  |

### Implementation Phase 6

- GOAL-006: Enforce admissibility gates, investigator override policy, and export integrity.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-021 | Implement final gate engine in `operation-room/backend/app/services/export_service.py` for citation completeness, contradiction checks, redaction checks, chain completeness, signature readiness, and SLA state. |  |  |
| TASK-022 | Add gate severity classes (`critical`, `major`, `minor`) in final decision: critical blocks export; major/minor may be overridden by investigator with mandatory signed rationale and risk acceptance. |  |  |
| TASK-023 | Generate signed package: PDF, JSON AST, evidence key map, prompt/output replay bundle, manifest hash set, and signature verification record. |  |  |
| TASK-024 | Write closure record to chain-of-custody with full execution digest and unresolved warning list (if override used). |  |  |

### Implementation Phase 7

- GOAL-007: Productionize universal-scenario intelligence and operational governance.

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-025 | Build `scenario_capability_matrix` in `operation-room/backend/app/services/deep_research/analysis_integration.py` mapping scenario subtypes to required modules, optional modules, and confidence dependencies. |  |  |
| TASK-026 | Add SLA policy defaults in config and orchestrator (`standard_run_max_minutes=90`, `expedited_run_max_minutes=45`) with progressive status streaming and resumable checkpointing. |  |  |
| TASK-027 | Define scale baseline and UI stability policy: support up to 10M normalized events per case via server-side aggregation/virtualization; enforce API limits and staged pagination for frontend safety. |  |  |
| TASK-028 | Add operational retries in module runner: `max_retries=3`, `backoff_seconds=[5,15,45]`, escalate to manual intervention queue after terminal failure. |  |  |

## 3. Alternatives

- **ALT-001**: Strict fail-closed export for any failed gate. **Tradeoff**: highest legal conservatism but operationally rigid; rejected because investigator requested conditional export flexibility.
- **ALT-002**: Investigator override for major/minor failures with signed justification (chosen). **Tradeoff**: faster operations and practical field use, but requires robust audit framing to preserve legal defensibility.
- **ALT-003**: Static fixed report template for all scenarios. **Tradeoff**: predictable output but weak contextual relevance and poor scaling to diverse attack types; rejected.
- **ALT-004**: Fully dynamic template from evidence clusters + learned priors (chosen). **Tradeoff**: richer relevance, but requires stronger guardrails and deterministic validation.
- **ALT-005**: Single-pass LLM narrative generation. **Tradeoff**: quick drafts but weak traceability; rejected for court use.
- **ALT-006**: Multi-pass deterministic generation with embedded key refs (chosen). **Tradeoff**: longer runtime, significantly better auditability and legal strength.
- **ALT-007**: AI-mode with partial redaction. **Tradeoff**: more contextual utility but leakage risk; rejected.
- **ALT-008**: AI-mode full semantic redaction and key-only references (chosen). **Tradeoff**: lower detail to AI, maximum privacy/compliance.

## 4. Dependencies

- **DEP-001**: `operation-room/backend/app/routes/deep_research.py` and `operation-room/backend/app/services/deep_research/*` for canonical orchestration.
- **DEP-002**: `operation-room/backend/app/routes/report_evidence.py` and `operation-room/backend/app/services/report_evidence_service.py` for key/value governance.
- **DEP-003**: `operation-room/backend/app/routes/learning.py` and `operation-room/backend/app/services/report_learning_service.py` for adaptive structure learning.
- **DEP-004**: `operation-room/backend/app/routes/studio_v4.py`, `operation-room/backend/app/services/auto_report_builder.py`, `operation-room/backend/app/services/reportlab_pdf_service.py` for composition and export.
- **DEP-005**: `operation-room/backend/app/services/export_service.py` for manifesting, signatures, and final gates.
- **DEP-006**: Existing chain-of-custody storage and audit routes for full replayability.

## 5. Files

- **FILE-001**: `operation-room/backend/app/routes/deep_research.py` — canonical run APIs and mode handling.
- **FILE-002**: `operation-room/backend/app/services/deep_research/orchestrator.py` — state machine and section lifecycle.
- **FILE-003**: `operation-room/backend/app/services/deep_research/plan_manager.py` — revisioned planning and approvals.
- **FILE-004**: `operation-room/backend/app/services/deep_research/engine.py` — hypothesis evaluation and uncertainty rewrite.
- **FILE-005**: `operation-room/backend/app/services/deep_research/analysis_integration.py` — module ingestion and scenario capability matrix.
- **FILE-006**: `operation-room/backend/app/routes/studio_v4.py` — visual generation, report generation, precheck integration.
- **FILE-007**: `operation-room/backend/app/services/auto_report_builder.py` — comprehensive report assembly and SQL compatibility corrections.
- **FILE-008**: `operation-room/backend/app/services/chart_renderer.py` — chart policy and fallback generation.
- **FILE-009**: `operation-room/backend/app/services/reportlab_pdf_service.py` — alignment and pixel-fidelity checks.
- **FILE-010**: `operation-room/backend/app/routes/report_evidence.py` — key/value APIs and access modes.
- **FILE-011**: `operation-room/backend/app/services/report_evidence_service.py` — evidence metadata, citation bundles, audit logs.
- **FILE-012**: `operation-room/backend/app/services/report_agent.py` — sentence-level citation embedding.
- **FILE-013**: `operation-room/backend/app/services/export_service.py` — gate engine, override policy, signature package.
- **FILE-014**: `operation-room/backend/app/routes/learning.py` — report upload, recommendation, and feedback APIs.
- **FILE-015**: `operation-room/backend/app/services/report_learning_service.py` — historical learning and confidence routing.
- **FILE-016**: `operation-room/backend/app/services/timeline_service.py` — ingest normalization and diagnostics.

## 6. Testing

- **TEST-001**: Verify comprehensive report path no longer fails on daily aggregation SQL and completes end-to-end generation.
- **TEST-002**: Verify unknown log formats produce partial-confidence outputs and explicit uncertainty diagnostics.
- **TEST-003**: Verify investigator scenario intake always preserved while subtype inference is added.
- **TEST-004**: Verify sentence-level embedded evidence keys exist for all generated narratives.
- **TEST-005**: Verify AI-mode redaction removes direct identifiers and keeps semantic summaries only.
- **TEST-006**: Verify autopilot default flow with final gate and human mode per-section gate coexist correctly.
- **TEST-007**: Verify one-section failure does not halt independent section execution.
- **TEST-008**: Verify timeline chart mandatory generation and fallback ladder for optional visual failures.
- **TEST-009**: Verify pixel-perfect layout checks between canvas and PDF exports.
- **TEST-010**: Verify chain-of-custody captures identity, timestamp, reason, hash-before/hash-after for each access.
- **TEST-011**: Verify signature package generation with trusted timestamp and verification replay.
- **TEST-012**: Verify override flow allows export on non-critical gate failures only with signed rationale.
- **TEST-013**: Verify LLM prompt/output replay visibility with role-based access.
- **TEST-014**: Verify SLA timers, checkpoint resume, and retry escalation behavior.

## 7. Risks & Assumptions

- **RISK-001**: Overlapping legacy report paths can bypass canonical gates unless fully routed through one state machine.
- **RISK-002**: Sentence-level citation embedding increases processing and storage cost.
- **RISK-003**: Dynamic templates may over-expand output length if section pruning policy is weak.
- **RISK-004**: Provider-agnostic LLM routing may create response-style variance without strict final-pass normalization.
- **RISK-005**: Investigator override, if overused, can reduce legal confidence despite audit logging.
- **ASSUMPTION-001**: Existing data schema can be extended for run-state, citation-bundle, and signature metadata.
- **ASSUMPTION-002**: Organization can provision X.509 signing infrastructure compatible with India legal process.
- **ASSUMPTION-003**: Existing frontend can consume live section telemetry with minor incremental API changes.

## 8. Related Specifications / Further Reading

- `docs/DETAILED_SYSTEM_DESIGN.md`
- `operation-room/backend/README.md`
- `operation-room/backend/app/routes/deep_research.py`
- `operation-room/backend/app/routes/studio_v4.py`
- `operation-room/backend/app/routes/report_evidence.py`
- `operation-room/backend/app/routes/learning.py`
- `operation-room/backend/app/services/auto_report_builder.py`
- `operation-room/backend/scripts/generate_mobile_exfiltration_report.py` (legacy reference only)
