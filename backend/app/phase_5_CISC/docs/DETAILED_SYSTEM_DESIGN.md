# NFLIP Detailed System Design and Workflow Atlas

This document provides the requested detailed system design with module-level connections, full workflows, C4-style component views, sequence diagrams, court admissibility controls, and production readiness checklists.

## 1. Design Objective and Constraints

1. Build an evidence-first DFIR platform where all factual report claims are traceable to immutable evidence.
2. Keep investigation modules independently executable and re-entrant.
3. Preserve chain of custody from ingestion to export.
4. Support both interactive human-in-loop investigations and automated execution modes.
5. Keep report rendering deterministic between Studio canvas and exported artifacts.

## 2. Detailed System Diagram with Micro Connections

```mermaid
flowchart LR
  %% User and UI
  subgraph U[User and Experience Layer]
    INV[Investigator]
    REV[Reviewer]
    UI[Next.js Studio V4 UI]
    STORE[Zustand Store]
    PANEL[Canvas Panels and Inspector]
  end

  %% API and orchestration
  subgraph A[API and Orchestration Layer]
    GW[FastAPI Gateway]
    ROUTES[Routes: investigation, tools, augment, report, cases]
    ORCH[Unified Orchestrator]
    PIPE[Pipeline Executor]
    IR[Intent Router Agent]
    SSE[SSE Stream Hub]
  end

  %% Specialized modules
  subgraph M[Specialized Analysis Modules]
    TIM[Timeline Module]
    ANO[Anomaly Module]
    COR[Correlation Module]
    NET[Network Module]
    CRUD[CRUD Module]
    DEP[Depth Impact Module]
    HYP[Hypothesis Agent]
    EVAG[Evidence Agent]
    SYN[Summary Synthesis Agent]
    CONF[Confidence Scoring Agent]
  end

  %% Services
  subgraph S[Core Services]
    LLM[LLM Service and Provider Router]
    AUG[Augment Studio Service]
    WR[Writer Service]
    REP[Report Builder Service]
    EVD[Evidence Service]
    ALIAS[Entity Alias Service]
  end

  %% Data and storage
  subgraph D[Data Layer]
    VLT[(DuckDB Case Vault)]
    RAW[(raw_events immutable)]
    UTL[(unified_timeline)]
    ANS[(anomaly_scores)]
    COC[(chain_of_custody append-only)]
    CRG[(chart_registry)]
    ART[(Artifact Store: MinIO or S3)]
  end

  %% External
  subgraph E[External Integrations]
    TI[Threat Intel APIs]
    MAIL[Mail and SIEM Inputs]
    OLL[Ollama Local]
    GEM[Gemini API]
  end

  INV --> UI
  REV --> UI
  UI --> STORE
  STORE --> PANEL
  UI -->|HTTPS JSON| GW
  UI -->|SSE Subscribe| SSE

  GW --> ROUTES
  ROUTES --> ORCH
  ROUTES --> IR
  ORCH --> PIPE
  PIPE --> TIM
  PIPE --> ANO
  PIPE --> COR
  PIPE --> NET
  PIPE --> CRUD
  PIPE --> DEP

  ORCH --> HYP
  ORCH --> EVAG
  ORCH --> SYN
  ORCH --> CONF
  ORCH --> SSE
  SSE --> UI

  TIM --> EVD
  ANO --> EVD
  COR --> EVD
  NET --> EVD
  CRUD --> EVD
  DEP --> EVD

  ORCH --> ALIAS
  ORCH --> LLM
  ORCH --> AUG
  ORCH --> WR
  ORCH --> REP

  LLM --> OLL
  LLM --> GEM
  NET --> TI
  ROUTES --> MAIL

  EVD --> VLT
  VLT --> RAW
  VLT --> UTL
  VLT --> ANS
  VLT --> COC
  VLT --> CRG
  REP --> ART
  WR --> CRG
  AUG --> CRG

  classDef user fill:#dff3ff,stroke:#005a9c,stroke-width:1px;
  classDef app fill:#ebf8ea,stroke:#1b7f3b,stroke-width:1px;
  classDef mod fill:#fff5e6,stroke:#b85e00,stroke-width:1px;
  classDef data fill:#f4ecff,stroke:#5b2da8,stroke-width:1px;
  classDef ext fill:#f0f0f0,stroke:#4f4f4f,stroke-width:1px;

  class INV,REV,UI,STORE,PANEL user;
  class GW,ROUTES,ORCH,PIPE,IR,SSE app;
  class TIM,ANO,COR,NET,CRUD,DEP,HYP,EVAG,SYN,CONF,LLM,AUG,WR,REP,EVD,ALIAS mod;
  class VLT,RAW,UTL,ANS,COC,CRG,ART data;
  class TI,MAIL,OLL,GEM ext;
```

### 2.1 Micro Connection Contract Map

| Connection | Protocol | Payload Contract | Reliability Rule | Audit Artifact |
|---|---|---|---|---|
| UI to API gateway | HTTPS | JSON DTOs with case_id, run_id, module config | Retry on 5xx with idempotency token | API request log |
| API to SSE hub | In-process event bus | phase_start, finding, confidence, complete | Ordered by sequence number | stream_event log |
| Orchestrator to module tools | Async function calls | capability plus parameters map | Timeout per tool plus fallback | module_execution record |
| Module to Evidence Service | Internal service call | evidence rows, source refs, hashes | Transaction boundary per batch | evidence_write CoC entry |
| Evidence Service to DuckDB | SQL | append or create derived table operations | Never update raw_events | DB statement audit |
| Writer to LLM Service | Prompt RPC | constrained prompt with evidence keys | strict temperature and token limits | prompt and response metadata |
| Report Builder to Artifact Store | Object API | PDF, JSON snapshot, provenance manifest | content hash verification | export manifest |
| Network module to Threat Intel | HTTPS | IOC query bundles | circuit breaker and cache | enrichment log |

### 2.2 Module Working Model

1. Intake parses scenario and input evidence inventory.
2. Planning generates hypotheses and phase order.
3. Execution runs modules in dependency-safe order.
4. Evidence service materializes derived outputs and anchors source references.
5. Confidence service scores findings using weighted factors.
6. Writer service composes narrative from verified evidence keys.
7. Report builder assembles studio layout, citations, and export package.

### 2.3 Complete User Flow Across the Platform

The end-to-end user flow combines human control points with automated system actions so investigators can run either manual, assisted, or near-autopilot investigations.

```mermaid
flowchart TD
  A[User authentication and case selection]
  B[Create or open investigation case]
  C[Upload logs and forensic artifacts]
  D[Hashing, normalization, and chain-of-custody entry]
  E[Scenario and objective definition]
  F{Clarification needed}
  G[Interactive clarification questions]
  H[Plan and hypothesis generation]
  I{Investigator approves plan}
  J[Plan adjustments and constraints update]
  K[Module execution orchestration]
  L[Live progress and findings stream]
  M[Evidence review, pinning, and annotation]
  N{Creation mode selected}
  O[Manual studio authoring]
  P[Assisted or autopilot section generation]
  Q[Citation, admissibility, and quality checks]
  R{Quality gate passes}
  S[Fix unresolved citations or layout issues]
  T[Export package creation with manifests]
  U[Reviewer approval and case closure]

  A --> B --> C --> D --> E --> F
  F -->|Yes| G --> H
  F -->|No| H
  H --> I
  I -->|No| J --> H
  I -->|Yes| K --> L --> M --> N
  N -->|Manual| O --> Q
  N -->|Assisted or Autopilot| P --> Q
  Q --> R
  R -->|No| S --> Q
  R -->|Yes| T --> U
```

### 2.4 Auto Creation Modes and Control Levels

| Mode | Who drives composition | System behavior | Human approval points |
|---|---|---|---|
| Manual | Investigator | Tools and studio assist only | Per action, per section, per export |
| Assisted | Investigator plus AI | AI drafts sections and visuals, human edits | Per section and final export |
| Autopilot | System with governance gates | System generates structure, narrative, visuals, and package | Final approval plus exception handoffs |

### 2.5 Auto Creation Orchestration Sequence

```mermaid
sequenceDiagram
  autonumber
  participant UI as Studio UI
  participant API as Auto Creation API
  participant AO as Auto Orchestrator
  participant PL as Plan and Section Planner
  participant EVD as Evidence Service
  participant AUG as Augment Studio
  participant WR as Writer Service
  participant VAL as Validation Engine
  participant RB as Report Builder
  participant OS as Artifact Store

  UI->>API: Start auto creation with mode and scope
  API->>AO: initialize auto run and lock run config
  AO->>PL: generate section plan and ordering
  AO->>EVD: freeze evidence snapshot by run_id
  loop For each section in approved plan
    AO->>EVD: fetch section evidence bundle
    AO->>AUG: generate section visuals and chart specs
    AO->>WR: generate section narrative with evidence keys
    AO->>VAL: run citation and admissibility checks
    VAL-->>AO: pass or fail with reasons
    alt Section valid
      AO->>RB: append section to report model
    else Section invalid
      AO->>UI: request intervention or auto-retry
    end
  end
  AO->>RB: compile final package and manifests
  RB->>OS: store PDF, JSON snapshot, and integrity manifest
  RB-->>API: export references and hashes
  API-->>UI: auto creation complete
```

### 2.6 Auto Creation Micro Workflow Contracts

| Stage | Input contract | Output contract | Failure handling | Audit evidence |
|---|---|---|---|---|
| Auto run initialization | case_id, mode, scope, run configuration | run_id, locked configuration snapshot | Reject if case lock or policy conflict | run_manifest |
| Section planning | objectives, findings inventory, template profile | ordered section_plan | Fallback to baseline template | planner_log |
| Evidence freeze | run_id, evidence selectors | evidence_snapshot_id, hash manifest | Retry with backoff, then fail closed | evidence_snapshot_log |
| Visual generation | section intent plus evidence bundle | chart specs, layout hints | Degrade to table visualization | chart_generation_log |
| Narrative generation | section plan plus evidence keys | section draft with citation anchors | Reject if citation mismatch | prompt_response_audit |
| Validation gate | draft, charts, citation map | pass_fail plus remediation actions | Open intervention task | admissibility_check_log |
| Package export | validated report model | PDF, JSON, manifest, signature | Keep draft state and block publish | export_manifest |

### 2.7 User Flow by Persona

1. Investigator flow:
- Create or open case.
- Import evidence and define objectives.
- Approve plan and execution mode.
- Review findings and generated sections.
- Approve final export.

2. Reviewer flow:
- Open generated package.
- Verify citation integrity and legal formatting.
- Approve or return for revision.

3. Platform admin flow:
- Monitor pipeline health and queue depth.
- Enforce retention, key rotation, and policy controls.
- Audit exception events and failed admissibility checks.

## 3. C4-Style Component Model

### 3.1 C4 Level 1 - System Context

```mermaid
flowchart TB
  INV[Investigator]
  REV[Reviewer]
  ADMIN[Platform Admin]

  SYS[NFLIP Operation Room]

  LOGS[Log Sources and Evidence Files]
  CTI[Threat Intel Providers]
  AUTH[Identity Provider]
  STORE[Object Storage]

  INV -->|Investigate and author reports| SYS
  REV -->|Review and approve outputs| SYS
  ADMIN -->|Operate and monitor platform| SYS

  LOGS -->|Import forensic artifacts| SYS
  SYS -->|Enrichment lookups| CTI
  SYS -->|User authentication| AUTH
  SYS -->|Store exports and artifacts| STORE
```

### 3.2 C4 Level 2 - Container View

```mermaid
flowchart LR
  subgraph Client[Client Container]
    WEB[Web App Next.js Studio]
  end

  subgraph Platform[NFLIP Platform]
    API[FastAPI API Container]
    ORC[Orchestrator and Agents Container]
    TOOL[Module Tools Container]
    REP[Reporting Container]
  end

  subgraph Data[Data Containers]
    DDB[(DuckDB Case Vault Container)]
    OBJ[(Object Storage Container)]
  end

  WEB -->|HTTPS and SSE| API
  API --> ORC
  ORC --> TOOL
  ORC --> REP
  TOOL --> DDB
  REP --> DDB
  REP --> OBJ
```

### 3.3 C4 Level 3 - Backend Component View

```mermaid
flowchart TB
  subgraph API[FastAPI Container]
    R1[investigation route]
    R2[tools route]
    R3[augment route]
    R4[report route]
  end

  subgraph O[Orchestrator Container]
    O1[UnifiedOrchestrator]
    O2[PipelineExecutor]
    O3[IntentRouterAgent]
    O4[ConfidenceEngine]
  end

  subgraph T[Tool Container]
    T1[timeline_tool]
    T2[anomaly_tool]
    T3[correlation_tool]
    T4[network_tool]
    T5[crud_tool]
    T6[depth_tool]
    T7[vault_tool]
  end

  subgraph SV[Service Components]
    S1[evidence_service]
    S2[augment_studio]
    S3[writer_agent]
    S4[report_builder]
    S5[llm_service]
  end

  DB[(DuckDB Case Vault)]
  OS[(Artifact Storage)]

  R1 --> O1
  R2 --> O2
  R3 --> S2
  R4 --> S4

  O1 --> O2
  O1 --> O3
  O1 --> O4

  O2 --> T1
  O2 --> T2
  O2 --> T3
  O2 --> T4
  O2 --> T5
  O2 --> T6
  O2 --> T7

  T1 --> S1
  T2 --> S1
  T3 --> S1
  T4 --> S1
  T5 --> S1
  T6 --> S1
  T7 --> S1

  O1 --> S3
  O1 --> S4
  S3 --> S5

  S1 --> DB
  S2 --> DB
  S3 --> DB
  S4 --> DB
  S4 --> OS
```

## 4. Sequence Diagrams

### 4.1 Investigation Sequence

```mermaid
sequenceDiagram
  autonumber
  participant I as Investigator
  participant UI as Studio UI
  participant API as FastAPI Route
  participant ORC as UnifiedOrchestrator
  participant EX as PipelineExecutor
  participant MOD as Analysis Modules
  participant EVD as Evidence Service
  participant DB as DuckDB Vault
  participant SSE as SSE Stream

  I->>UI: Submit scenario and objectives
  UI->>API: POST start investigation
  API->>ORC: initialize run(case_id, scenario)
  ORC->>SSE: phase_start:intake
  SSE-->>UI: stream event
  ORC->>EX: build plan and execute phases
  loop For each enabled phase
    EX->>MOD: run capability with parameters
    MOD->>EVD: write findings plus source refs
    EVD->>DB: INSERT derived rows and CoC entries
    MOD-->>EX: phase results
    EX->>SSE: finding and progress event
    SSE-->>UI: live update
  end
  ORC->>ORC: compute confidence and verdicts
  ORC->>SSE: confidence and complete events
  SSE-->>UI: final stream
  ORC-->>API: run summary payload
  API-->>UI: HTTP completion response
```

### 4.2 Report Generation Sequence

```mermaid
sequenceDiagram
  autonumber
  participant I as Investigator
  participant UI as Studio Canvas
  participant API as Report Route
  participant WR as Writer Service
  participant LLM as LLM Service
  participant EVD as Evidence Service
  participant RB as Report Builder
  participant DB as DuckDB Vault
  participant OS as Artifact Store

  I->>UI: Select report sections and request draft
  UI->>API: POST generate section draft
  API->>EVD: fetch evidence keys and citation map
  EVD->>DB: query verified findings
  DB-->>EVD: findings with hashes and refs
  EVD-->>API: evidence bundle
  API->>WR: compose structured prompt
  WR->>LLM: generate narrative using evidence keys only
  LLM-->>WR: draft text
  WR-->>API: section draft plus citation anchors
  API-->>UI: render draft on canvas
  I->>UI: Approve export
  UI->>API: POST export report
  API->>RB: compile pages, charts, manifests
  RB->>DB: fetch final canvas and chart registry
  RB->>OS: write PDF plus provenance package
  RB-->>API: export_id, hashes, storage URI
  API-->>UI: export complete response
```

## 5. Court Admissibility Controls by Service Boundary

| Service Boundary | Admissibility Objective | Mandatory Controls | Proof Artifact | Verification Action |
|---|---|---|---|---|
| Browser to API | Authenticated and attributable user actions | Strong auth, RBAC, request signing, session binding | access log with user and case scope | Verify user id and role for every write |
| API to Orchestrator | Deterministic execution intent | run_id generation, immutable run config snapshot | run_manifest | Recompute run hash and compare |
| Orchestrator to Modules | Reproducible analytical transformations | versioned module id, capability id, parameter capture | module_execution_log | Replay with same inputs and compare outputs |
| Modules to Evidence Service | Traceable source-to-finding lineage | source_ref list, row hash, operation type | evidence_lineage map | Validate all finding rows have source references |
| Evidence Service to DuckDB | Raw evidence immutability and CoC continuity | write guards, append-only CoC, raw_events no update policy | chain_of_custody rows | Assert no UPDATE or DELETE on raw_events |
| Writer Service to LLM Service | No fabricated facts in narrative | evidence-key constrained prompting, low temperature, citation post-check | prompt_response_audit | Reject draft if unresolved citations exist |
| Report Builder to Artifact Store | Export integrity and reproducibility | export manifest hash, digital signature, timestamping | signed_manifest and PDF hash | Verify PDF hash equals manifest hash |
| API to External Intel | Controlled enrichment provenance | source labeling, confidence tagging, cache of responses | enrichment_audit log | Mark non-primary evidence as contextual only |

### 5.1 Evidence Handling Policy

1. raw_events is immutable after ingestion.
2. chain_of_custody is append-only.
3. Derived tables are versioned by run_id.
4. Every report claim must include one or more citation anchors.
5. Reports failing citation integrity are blocked from final export.

## 6. Production Readiness Checklist

### 6.1 Shared Readiness Baseline

- [ ] End-to-end health checks for API, UI, and storage are green.
- [ ] Evidence immutability tests pass.
- [ ] Chain-of-custody append-only tests pass.
- [ ] Module regression suite passes against reference cases.
- [ ] Export reproducibility test passes for golden sample report.
- [ ] Alerting exists for failed runs, export failures, and storage errors.
- [ ] Disaster recovery drills validated restore objective and recovery objective targets.

### 6.2 Self-Hosted Deployment Checklist

- [ ] Network segmentation isolates UI, API, and storage planes.
- [ ] Private key management uses internal HSM or equivalent.
- [ ] Local object storage replication tested across nodes.
- [ ] Offline backup policy covers case vault and export artifacts.
- [ ] Patch management SLA for host OS and containers is enforced.
- [ ] SIEM forwarding for audit and CoC logs is active.
- [ ] Legal hold workflow for exported reports is documented.

### 6.3 SaaS Deployment Checklist

- [ ] Tenant isolation controls validated at API and data layers.
- [ ] Region and data residency controls configured per contract.
- [ ] Managed key service with customer key option enabled where required.
- [ ] Centralized observability with tenant-safe redaction in logs.
- [ ] Autoscaling policies tested under burst investigative workloads.
- [ ] Incident response runbooks include cross-tenant blast radius checks.
- [ ] Compliance evidence package generation is automated per release.

### 6.4 Go-Live Gates

1. Security sign-off.
2. Forensic admissibility sign-off.
3. Performance sign-off under target load.
4. Operations and support handoff completion.
5. Final legal and governance approval for jurisdiction-specific use.

## 7. Traceability Matrix

| Requirement | Section in this document |
|---|---|
| Detailed system design with micro connections | Section 2 and Section 2.1 |
| Complete user flow and auto creation process | Section 2.3 to Section 2.7 |
| C4-style component model | Section 3 |
| Investigation and report sequence diagrams | Section 4 |
| Court admissibility controls per boundary | Section 5 |
| Production readiness for self-hosted and SaaS | Section 6 |
