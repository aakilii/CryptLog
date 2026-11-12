# Report Studio Execution Plan (2026)

## Objective
Ship a reliable, investigator-first Report Studio that produces evidence-grounded, court-ready reports with minimal manual stitching.

## Scope
- Frontend Report Studio editor and AI panels
- Backend Report Studio routes and Writer Agent pipeline
- Validation, integrity, and export quality
- Collaboration and performance hardening

## Current Baseline (After Immediate Fixes)
- Generation endpoints aligned between frontend and backend.
- Legacy generation routes added for backward compatibility.
- Suggestions endpoint hardened to support mixed finding payloads.
- Writer pipeline now includes factual validation metadata.
- Section/style normalization added to reduce request drift.

## Phase Plan

### Phase 1: Reliability and Contract Lock (P0)
- Freeze canonical API paths:
  - `POST /api/cases/{case_id}/report-studio/writer/generate`
  - `POST /api/cases/{case_id}/report-studio/writer/generate-custom`
  - `POST /api/cases/{case_id}/report-studio/suggestions`
- Keep legacy aliases temporarily:
  - `POST /api/cases/{case_id}/report-studio/generate`
  - `POST /api/cases/{case_id}/report-studio/generate-custom`
- Add deprecation warnings in responses for legacy aliases.
- Add integration tests for route parity and response schema.

Exit criteria:
- No frontend call uses deprecated aliases.
- Route-level test suite passes for generation and suggestions.

### Phase 2: Trust and Evidence Guarantees (P0)
- Enforce validator result in writer output metadata.
- Add configurable policy gates:
  - block export when `validation.summary.errors > 0` (strict mode)
  - allow export with warnings (standard mode)
- Expand citation fidelity from module-level hashes to block-level evidence references.
- Add visible validation panel in UI (errors, warnings, autofix opportunities).

Exit criteria:
- Every generated section returns `validation` object.
- Export path shows validation status and policy decision.

### Phase 3: Investigator Workflow (P1)
- Add intent-to-section generation:
  - Investigator asks for a topic; system maps to section + modules.
- Add guided evidence insertion flows from insights panel.
- Add completeness checklist with live scoring.

Exit criteria:
- Section authoring can be completed from one panel without tab hopping.
- Completeness score updates as content changes.

### Phase 4: Collaboration and Review (P1)
- Move active editor path to collaborative mode (Yjs-based) or remove legacy-only collaboration references.
- Add comments, mentions, and reviewer states.
- Add conflict-safe version history and compare view.

Exit criteria:
- Two users can co-edit one report with presence indicators.
- Version rollback works for all document states.

### Phase 5: Performance and Scale (P1)
- Parallelize module data fetches in frontend loading flow.
- Add backend memoization/TTL cache for repeated insight aggregation.
- Add latency SLO dashboards for generation and insights APIs.

Exit criteria:
- Initial Report Studio load under target latency for medium-size cases.
- Insight endpoints avoid duplicate heavy queries inside short windows.

### Phase 6: Court-Ready Export Hardening (P2)
- Deterministic export manifests and reproducible output checks.
- Signature/timestamp strategy for evidentiary workflows.
- Evidence appendix quality gates and verification report.

Exit criteria:
- Export package includes manifest, hashes, and verification summary.
- Re-export consistency test passes for unchanged documents.

## Technical Debt Backlog
- Replace ad-hoc section aliasing with typed shared contract package.
- Normalize frontend API usage to one client abstraction.
- Split large page component into domain subcomponents.
- Remove deprecated API aliases after migration window.

## 2-Week Delivery Slice
1. Complete migration away from deprecated generation aliases.
2. Add integration tests for writer/suggestions routes.
3. Ship UI validation panel using writer `validation` output.
4. Parallelize module loading in Report Studio page.
5. Add backend cache for `get_all_insights` with bounded TTL.

## Ownership
- Backend: API contracts, writer pipeline, validation policy, caching
- Frontend: endpoint migration, panel UX, loading strategy
- QA: integration tests, regression coverage, export verification
- Security/Forensics: evidence binding and admissibility controls
