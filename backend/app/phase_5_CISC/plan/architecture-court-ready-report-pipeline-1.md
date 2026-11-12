---
goal: Canonical Court-Ready Report Pipeline Contract for Any Forensic Scenario
version: 1.0
date_created: 2026-04-10
last_updated: 2026-04-10
owner: Operation Room Architecture
status: Planned
tags: [architecture, feature, process, forensic, report, evidence, automation]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a deterministic, scenario-agnostic canonical pipeline to generate court-ready forensic reports with text, charts, components, evidence-key binding, admissibility gates, and export integrity verification.

## 1. Requirements & Constraints

- **REQ-001**: Pipeline input contract order is fixed: imported logs -> scenario intake -> clarification questions -> plan/template draft -> user feedback -> plan approval -> section execution -> quality gates -> export package.
- **REQ-002**: Pipeline must work for any scenario class by capability detection and module routing, not by scenario-specific scripts.
- **REQ-003**: Each report claim must map to one or more evidence vault keys and include machine-verifiable provenance metadata.
- **REQ-004**: Report generation must support human mode (per-section approval) and autopilot mode (per-section auto-advance after verification).
- **REQ-005**: Report structure must include dynamic headings/subheadings with approximate page planning and section-level completion state.
- **REQ-006**: Every section must include required artifacts for that section type: narrative text, chart/table component, findings block, and citation anchors.
- **REQ-007**: Final output must include PDF + JSON snapshot + integrity manifest + verification metadata.
- **SEC-001**: Enforce evidence access policy: AI consumers receive key-only or summary; report generation uses redacted/full according to purpose and role.
- **SEC-002**: Preserve append-only chain-of-custody records for all evidence reads/writes and gate decisions.
- **SEC-003**: Fail closed on admissibility/citation failures for publish/export actions.
- **QLT-001**: Fix DuckDB query incompatibility in `app/services/auto_report_builder.py` daily aggregation path (`SELECT DATE(normalised_ts)`) using DuckDB-compatible expression.
- **QLT-002**: Eliminate zero-event timeline false-success path by explicit diagnostics and non-empty build assertions.
- **CON-001**: Do not mutate raw evidence records under case vault data stores.
- **CON-002**: Maintain FastAPI thin-route pattern; move business logic to service layer.
- **CON-003**: Reuse existing routes and services before introducing new API surfaces.
- **GUD-001**: Use deterministic prompts/config for court-facing narrative generation.
- **GUD-002**: Persist all planning, clarification, and section decisions with run IDs and timestamps.
- **PAT-001**: Canonical orchestration pattern: Intake -> Clarification -> Planning -> Approval -> Execution -> Validation -> Export -> Audit closure.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Establish canonical contracts and remove blocking defects in report generation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Define canonical pipeline request/response schemas in `app/routes/deep_research.py` and `app/routes/studio_v4.py` for intake, clarification, plan preview, plan approval, section execution, and finalization states. Add explicit status enums: `pending_clarification`, `plan_draft`, `plan_approved`, `section_in_progress`, `section_verified`, `quality_blocked`, `ready_to_export`, `exported`. |  |  |
| TASK-002 | Fix DuckDB daily aggregation incompatibility in `app/services/auto_report_builder.py` function path used by `generate_comprehensive_report` by replacing unsupported `DATE(normalised_ts)` expression with DuckDB-compatible date extraction expression and update all dependent chart builders. |  |  |
| TASK-003 | Add deterministic failure contract for empty timeline in `app/services/timeline_service.py` and route `POST /api/cases/{case_id}/timeline/build`: return structured diagnostics (`event_count`, `source_counts`, `normalization_errors`, `recommendations`) when `event_count=0`. |  |  |
| TASK-004 | Introduce canonical `ScenarioContext` completeness scoring in `app/services/scenario_analyzer.py` and route integration in `app/routes/learning.py` + `app/routes/deep_research.py`; enforce mandatory clarification when score < threshold constant `SCENARIO_COMPLETENESS_THRESHOLD=0.85`. |  |  |

### Implementation Phase 2

- GOAL-002: Implement scenario-agnostic planning and adaptive report template generation from learning + live evidence metadata.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Build template recommendation aggregator in `app/services/report_learning_service.py` combining historical report patterns (`/api/learning/upload-report`, `/api/learning/recommend-structure`) and current case metadata (`timeline stats`, `anomaly summary`, `network summary`). |  |  |
| TASK-006 | Create deterministic plan-preview payload in `app/routes/deep_research.py` endpoint flow (`/deep-research/investigations/{investigation_id}/plan`) including section order, subsection map, per-section objective, required modules, estimated pages, and required chart types. |  |  |
| TASK-007 | Add feedback-diff application function in `app/services/deep_research/plan_manager.py` to transform user edits into validated plan revisions with immutable revision history (`revision_id`, `changed_sections`, `reason`). |  |  |
| TASK-008 | Enforce plan lock on approval in `/deep-research/investigations/{investigation_id}/plan/approve`; prevent execution with unapproved plan hash mismatch. |  |  |

### Implementation Phase 3

- GOAL-003: Enforce evidence-vault-first finding workflow with key/value separation and section-level evidence chains.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Integrate finding-to-key creation calls from analysis modules (`timeline`, `anomaly`, `correlation`, `crud`, `network`, `depth`) into `app/services/deep_research/analysis_integration.py` using `/report-evidence/{case_id}/store-from-finding` contract. |  |  |
| TASK-010 | Add mandatory metadata schema for each stored evidence item in `app/services/report_evidence_service.py`: `why_recorded`, `source_module`, `finding_id`, `confidence`, `section_id`, `decision_context`, `created_by`, `created_at`. |  |  |
| TASK-011 | Implement citation resolver in `app/services/report_agent.py` and `app/services/auto_report_builder.py` to bind section claims to `key_id` list only during AI composition and resolve redacted/full value only during export paths. |  |  |
| TASK-012 | Add automated evidence chain construction per section using `/report-evidence/{case_id}/chain` and verify chain completeness before section verification transition. |  |  |

### Implementation Phase 4

- GOAL-004: Build deterministic section execution loop with hypothesis evaluation, module orchestration, and approval gates.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Implement section state machine in `app/services/deep_research/orchestrator.py`: `init -> hypothesis -> module_fetch -> finding_eval -> evidence_bind -> compose -> layout_verify -> approval -> finalized`. |  |  |
| TASK-014 | Define module selection policy in `app/services/unified_orchestrator.py` using section objective tags; support parallel module execution with declared dependencies. |  |  |
| TASK-015 | Add hypothesis rubric in `app/services/deep_research/engine.py` with explicit outputs: `supported`, `partially_supported`, `not_supported`, confidence score, contradictory evidence list. |  |  |
| TASK-016 | Implement mode-aware progression policy in `app/routes/deep_research.py`: human mode requires explicit section approval; autopilot mode advances after verification and logs auto-approval actor `system_autopilot`. |  |  |

### Implementation Phase 5

- GOAL-005: Standardize chart/component generation and enforce layout integrity across canvas and export.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Define section-to-visual contract in `app/services/chart_renderer.py` and `app/routes/studio_v4.py` with required chart families and fallback rules (`chart -> table -> narrative fallback`). |  |  |
| TASK-018 | Add layout validator in `app/services/reportlab_pdf_service.py` + Studio V4 export precheck routes to assert bounds, overlap, min readability, and page break integrity. |  |  |
| TASK-019 | Persist chart generation metadata (query hash, inputs, timestamp, renderer version) in `chart_registry` and attach to section audit records. |  |  |
| TASK-020 | Add section-level alignment verification endpoint invocation before approval using existing report section verification routes; reject transition on failed coordinates/spacing constraints. |  |  |

### Implementation Phase 6

- GOAL-006: Enforce admissibility, audit closure, and export integrity for court-ready output.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Implement admissibility gate bundle in `app/services/export_service.py` and `app/services/report_agent.py`: citation completeness, unsupported claim detection, contradiction scan, redaction compliance, and chain completeness checks. |  |  |
| TASK-022 | Add explicit fail-closed publish policy for any gate failure in `/api/cases/{case_id}/export` and Studio V4 export routes. |  |  |
| TASK-023 | Generate canonical export package manifest with hash set for PDF, JSON AST, chart specs, evidence key map, and audit digest; store verification result and retrieval links. |  |  |
| TASK-024 | Add end-of-run closure record to chain-of-custody with run summary (`sections_total`, `sections_passed`, `gates_passed`, `export_hash`). |  |  |

### Implementation Phase 7

- GOAL-007: Productionize learning loop and governance for adaptive heading/subheading quality.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | Expand `app/routes/learning.py` upload path validation and parsing diagnostics to support reliable ingestion of historical PDF/DOCX report libraries. |  |  |
| TASK-026 | Add recommendation confidence thresholds in `app/services/report_learning_service.py`; if below threshold, fallback to canonical baseline template and log reason. |  |  |
| TASK-027 | Implement post-export feedback capture into `/api/learning/feedback` and feed into template weighting updates with versioned recommendation model metadata. |  |  |
| TASK-028 | Add governance dashboard API fields for learning influence: `%sections_from_baseline`, `%sections_from_learned_patterns`, `recommendation_confidence_mean`. |  |  |

## 3. Alternatives

- **ALT-001**: Keep scenario-specific script strategy (example: `scripts/generate_mobile_exfiltration_report.py`) for each case type. Rejected because it does not generalize and causes maintenance drift.
- **ALT-002**: Use single-pass LLM report generation without section state machine. Rejected because it is non-deterministic and weak for admissibility and auditability.
- **ALT-003**: Store full evidence directly in prompts for convenience. Rejected due to redaction, privacy, and court defensibility risk.

## 4. Dependencies

- **DEP-001**: DuckDB SQL compatibility across all analytic queries used by `app/services/auto_report_builder.py` and chart generation services.
- **DEP-002**: Evidence key/value services in `app/routes/report_evidence.py` and `app/services/report_evidence_service.py`.
- **DEP-003**: Deep Research orchestration routes and services in `app/routes/deep_research.py` and `app/services/deep_research/*`.
- **DEP-004**: Studio V4 report/export endpoints in `app/routes/studio_v4.py` and export services.
- **DEP-005**: Historical report learning stack in `app/routes/learning.py` and `app/services/report_learning_service.py`.

## 5. Files

- **FILE-001**: `operation-room/backend/app/routes/studio_v4.py` — comprehensive report route, visual report route, pre-export verification invocation.
- **FILE-002**: `operation-room/backend/app/services/auto_report_builder.py` — data extraction, section composition, daily aggregation query compatibility fix, claim-to-evidence binding hooks.
- **FILE-003**: `operation-room/backend/app/routes/deep_research.py` — intake/clarification/plan/approval/report orchestration APIs.
- **FILE-004**: `operation-room/backend/app/services/deep_research/orchestrator.py` — section state machine and mode-based progression.
- **FILE-005**: `operation-room/backend/app/services/deep_research/analysis_integration.py` — module finding ingestion and evidence vault storage integration.
- **FILE-006**: `operation-room/backend/app/routes/report_evidence.py` — key/value retrieval modes, chain creation, audit endpoints.
- **FILE-007**: `operation-room/backend/app/services/report_evidence_service.py` — metadata schema, access logging, chain verification.
- **FILE-008**: `operation-room/backend/app/services/report_agent.py` — section persistence, citation resolver, admissibility gate integration.
- **FILE-009**: `operation-room/backend/app/services/export_service.py` — redact mode resolution, fail-closed export gate, manifest generation.
- **FILE-010**: `operation-room/backend/app/routes/learning.py` — historical report upload, recommendation APIs, feedback loop.
- **FILE-011**: `operation-room/backend/app/services/report_learning_service.py` — structure extraction, similarity recommendation, confidence model.
- **FILE-012**: `operation-room/backend/app/services/timeline_service.py` — zero-event diagnostics and normalization assertions.

## 6. Testing

- **TEST-001**: Add integration test for `/api/v4/studio/cases/{case_id}/comprehensive-report` proving no SQL function error and successful report generation with non-empty daily aggregation.
- **TEST-002**: Add timeline ingest test asserting `timeline/build` returns non-zero events for valid imports and structured diagnostics for zero-event cases.
- **TEST-003**: Add evidence vault test: finding -> key creation -> AI key-only retrieval -> report redacted/full retrieval -> audit log entry.
- **TEST-004**: Add deep research flow test: clarification required -> plan draft -> user feedback -> revised plan -> approval lock -> section state transitions.
- **TEST-005**: Add section verification test for human mode and autopilot mode progression behavior.
- **TEST-006**: Add export gate test blocking publish when citation/admissibility checks fail.
- **TEST-007**: Add export package verification test validating manifest hashes and chain-of-custody closure entry.
- **TEST-008**: Add learning pipeline test for `/api/learning/upload-report` + `/api/learning/recommend-structure` + confidence fallback behavior.

## 7. Risks & Assumptions

- **RISK-001**: Current architecture has overlapping report generation paths (Studio V4 comprehensive, auto-report builder, deep-research report flow), creating behavior divergence and inconsistent gate enforcement.
- **RISK-002**: Route handlers currently expose orchestration decisions that should be centralized in service-layer state machines.
- **RISK-003**: Without strict schema/versioning for plan and section states, cross-module regressions will remain hard to detect.
- **RISK-004**: If learning confidence is low and fallback policy is absent, generated structures may be unstable and legally weak.
- **RISK-005**: If evidence-key binding is optional in any composition path, admissibility can be bypassed silently.
- **ASSUMPTION-001**: Existing DB schema can be extended for additional state/audit fields without breaking current case data.
- **ASSUMPTION-002**: Existing report-evidence and learning endpoints remain supported and are the canonical integration surfaces.
- **ASSUMPTION-003**: Court-ready policy requires deterministic outputs and fail-closed export behavior.

## 8. Related Specifications / Further Reading

- `docs/DETAILED_SYSTEM_DESIGN.md`
- `operation-room/docs/architecture/REPORT_STUDIO_V4_CANVA_ARCHITECTURE.md`
- `operation-room/backend/README.md`
- `operation-room/backend/app/routes/report_evidence.py`
- `operation-room/backend/app/routes/learning.py`
- `operation-room/backend/scripts/generate_mobile_exfiltration_report.py` (reference only; not canonical strategy)
