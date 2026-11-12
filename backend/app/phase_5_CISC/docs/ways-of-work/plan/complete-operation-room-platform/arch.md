# Epic Architecture Specification: Complete Operation Room Platform

## 1. Epic Architecture Overview

This epic delivers a unified, evidence-first investigation platform that combines forensic ingestion, AI-assisted planning, modular analytics, human-in-loop workflows, and court-ready reporting into a single production architecture.

The technical approach uses a domain-driven modular system:
- Frontend application for investigation and report studio workflows.
- Type-safe API gateway and domain services for investigation execution.
- Specialized analysis modules for timeline, anomaly, correlation, CRUD, network, and impact-depth computation.
- Evidence and chain-of-custody foundation to ensure cryptographic integrity and admissibility.
- Asynchronous orchestration for long-running tasks and interactive approval gates.

The architecture supports both self-hosted and SaaS deployment models, with all services containerized using Docker and orchestrated as independently scalable components.

## 2. System Architecture Diagram

```mermaid
flowchart TB
  %% =============================
  %% USER LAYER
  %% =============================
  subgraph UL[User Layer]
    U1[Investigator Web Client\nNext.js App Router]
    U2[Admin Console\nOperations and Governance]
    U3[Mobile Reviewer\nRead-Only Views]
  end

  %% =============================
  %% APPLICATION LAYER
  %% =============================
  subgraph AL[Application Layer]
    LB[Ingress and Load Balancer]
    AUTH[Stack Auth\nSSO, RBAC, Session]
    FE[Frontend Runtime\nNext.js and UI Gateway]
  end

  %% =============================
  %% SERVICE LAYER
  %% =============================
  subgraph SL[Service Layer]
    TRPC[tRPC API Gateway\nType-Safe Procedures]
    ORCH[Investigation Orchestrator\nPlan, Approve, Execute]
    IR[Intent Router\nPrompt to Specialized Agent]
    SVC1[Timeline Service]
    SVC2[Anomaly Service]
    SVC3[Correlation Service]
    SVC4[CRUD Analysis Service]
    SVC5[Network Analysis Service]
    SVC6[Impact Depth Service]
    EV[Evidence Vault Service\nCitation, Snapshot, Verify]
    REP[Report Builder Service\nStudio Assembly and Export]
    WF[n8n Workflow Engine\nIntegrations and Automation]
    JOB[Background Workers\nQueue Consumers]
    MCP[MCP Tool Surface\nTool Discovery and Invocation]
  end

  %% =============================
  %% DATA LAYER
  %% =============================
  subgraph DL[Data Layer]
    PG[(PostgreSQL\nCases, Metadata, Users)]
    DDB[(DuckDB Case Vaults\nForensic Event and CoC Data)]
    QD[(Qdrant\nEmbeddings and Semantic Recall)]
    RD[(Redis\nCache, Rate Limit, Queue State)]
    OBJ[(Object Storage\nRaw Logs and Exports)]
    EXT[External APIs\nThreat Intel, Email, SIEM]
  end

  %% =============================
  %% INFRASTRUCTURE LAYER
  %% =============================
  subgraph IL[Infrastructure Layer]
    DOC[Docker Containers\nFrontend, API, Workers, n8n]
    OBS[Observability Stack\nLogs, Metrics, Traces]
    SEC[Secrets and Key Management]
    DEP[Deployment Targets\nSelf-Hosted or SaaS]
  end

  %% Sync request path
  U1 --> LB
  U2 --> LB
  U3 --> LB
  LB --> FE
  FE --> AUTH
  FE --> TRPC
  TRPC --> ORCH
  TRPC --> IR
  IR --> SVC1
  IR --> SVC2
  IR --> SVC3
  IR --> SVC4
  IR --> SVC5
  IR --> SVC6
  ORCH --> EV
  ORCH --> REP

  %% Data interactions
  TRPC --> PG
  SVC1 --> DDB
  SVC2 --> DDB
  SVC3 --> DDB
  SVC4 --> DDB
  SVC5 --> DDB
  SVC6 --> DDB
  EV --> DDB
  REP --> DDB
  SVC3 --> QD
  TRPC --> RD
  ORCH --> RD
  REP --> OBJ
  ORCH --> EXT
  SVC5 --> EXT

  %% Async flows
  ORCH -. enqueue jobs .-> JOB
  JOB -. status and events .-> RD
  JOB --> WF
  WF --> EXT
  MCP --> ORCH
  MCP --> EV
  MCP --> REP

  %% Infra bindings
  FE --> DOC
  TRPC --> DOC
  JOB --> DOC
  WF --> DOC
  DOC --> DEP
  DOC --> OBS
  DOC --> SEC

  %% Visual classes
  classDef user fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
  classDef app fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
  classDef svc fill:#fff8e1,stroke:#ef6c00,color:#e65100;
  classDef data fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c;
  classDef infra fill:#eceff1,stroke:#37474f,color:#263238;

  class U1,U2,U3 user;
  class LB,AUTH,FE app;
  class TRPC,ORCH,IR,SVC1,SVC2,SVC3,SVC4,SVC5,SVC6,EV,REP,WF,JOB,MCP svc;
  class PG,DDB,QD,RD,OBJ,EXT data;
  class DOC,OBS,SEC,DEP infra;
```

## 3. High-Level Features and Technical Enablers

### High-Level Features

1. Evidence-first investigation intake with scenario-aware context initialization.
2. Deep Research-style visible planning with editable investigation phases.
3. Approval-gated phase execution with real-time progress updates.
4. Intent-routed domain chat across timeline, anomaly, correlation, CRUD, network, and depth analysis.
5. Integrated Evidence Vault operations: ingest, verify, cite, query, snapshot, and anchor.
6. Chain-of-custody-preserving analytics over immutable forensic event history.
7. Studio-based report authoring with canvas placement validation and deterministic exports.
8. Continuous hypothesis generation and testing against collected evidence.
9. Multi-source forensic parsing and normalization with cryptographic event hashing.
10. Compliance-ready final report generation with traceable claim-to-evidence linkage.

### Technical Enablers

1. Domain service decomposition aligned to bounded contexts (Investigation, Evidence, Analysis, Reporting, Auth).
2. tRPC contract layer for end-to-end typed request/response between frontend and services.
3. Stack Auth integration for SSO, user identity, case-level RBAC, and auditable sessions.
4. Redis-backed asynchronous job orchestration and streaming execution state.
5. n8n workflow engine for external integration automation and enrichment.
6. Qdrant semantic retrieval for context expansion and evidence-aware narrative support.
7. Containerized runtime profile for frontend, API, workers, and workflow services.
8. Observability baseline (metrics, traces, structured logs, operation audit trails).
9. Deployment topology parity for self-hosted and SaaS modes.
10. Governance controls including hook guardrails, risky-command interception, and sensitive-path protection.

## 4. Technology Stack

1. Frontend: Next.js (App Router), TypeScript, Zustand, TailwindCSS, Studio canvas components.
2. API and Service Layer: TypeScript server with tRPC procedures and domain modules.
3. Authentication and Authorization: Stack Auth with RBAC and session enforcement.
4. Workflow and Automation: n8n for event-driven and scheduled workflows.
5. Data Stores:
- PostgreSQL for product metadata, users, and operational records.
- DuckDB for case-scoped forensic vault data and analytical queries.
- Qdrant for vector indexing and semantic evidence retrieval.
- Redis for cache, queue state, and short-lived coordination data.
6. AI and Analysis Runtime: LLM provider abstraction, ML anomaly pipelines, explainability workflows.
7. Infrastructure: Dockerized services, reverse proxy/load balancing, observability, secrets management.
8. Dev Productivity: VS Code customization set, MCP integration surface, guarded automation hooks.

## 5. Technical Value

Technical Value: High

Justification:
1. Consolidates currently distributed investigation and reporting capabilities into a cohesive, modular architecture.
2. Reduces operational risk with strong chain-of-custody and evidence integrity guarantees.
3. Increases developer velocity via typed contracts, containerized parity, and standardized workflows.
4. Enables scalable enterprise adoption across both on-prem and SaaS deployment models.
5. Improves trustworthiness through transparent planning, approval gates, and evidence-backed outputs.

## 6. T-Shirt Size Estimate

Estimate: XL

Rationale:
1. Multi-domain service integration with strict forensic integrity constraints.
2. Significant frontend and workflow orchestration scope (interactive planning, interrupts, report assembly).
3. Dual deployment model requirements (self-hosted and SaaS) with secure operational posture.
4. High testing and verification burden across analytics correctness, evidence provenance, and export fidelity.

## Context Source (Epic PRD Basis)

This architecture specification is based on the existing project PRD-equivalent and gap-analysis artifacts for the complete application scope:
1. Operation Room product architecture and workflow guide.
2. Deep research complete architecture guide.
3. Vision versus architecture gap analysis and execution priorities.
