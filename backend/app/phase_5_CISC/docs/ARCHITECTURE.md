# NFLIP Architecture Documentation

## System Overview

NFLIP (Network Forensics & Log Investigation Platform) is a multi-agent AI-powered forensic investigation system that automates evidence analysis and report generation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NFLIP SYSTEM ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FRONTEND (Next.js 14)                         │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐                  │   │
│  │  │  Report     │  │   Canvas     │  │   AI        │                  │   │
│  │  │  Studio V4  │  │   Editor     │  │   Panel     │                  │   │
│  │  └─────────────┘  └──────────────┘  └─────────────┘                  │   │
│  │        │                  │                │                          │   │
│  │        └──────────────────┴────────────────┘                          │   │
│  │                           │                                           │   │
│  │                    useStudioStore (Zustand)                           │   │
│  │                           │                                           │   │
│  │         ┌─────────────────┴─────────────────┐                         │   │
│  │         │                                   │                         │   │
│  │  useInvestigationStream           useCanvasStream                     │   │
│  │         │  (SSE Consumer)           (Auto-populate)                   │   │
│  └─────────┼───────────────────────────────────┼────────────────────────┘   │
│            │                                   │                            │
│            │              HTTP/SSE             │                            │
│            └───────────────────┬───────────────┘                            │
│                                │                                            │
│  ┌─────────────────────────────┴────────────────────────────────────────┐   │
│  │                         BACKEND (FastAPI)                             │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     API ROUTES (197 endpoints)                   │ │   │
│  │  │  /investigation  /augment  /tools  /aliases  /studio  /cases    │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                │                                      │   │
│  │  ┌─────────────────────────────┴───────────────────────────────────┐ │   │
│  │  │                    ORCHESTRATION LAYER                          │ │   │
│  │  │                                                                 │ │   │
│  │  │  ┌──────────────────┐  ┌──────────────────┐                    │ │   │
│  │  │  │   Unified        │  │  Pipeline        │                    │ │   │
│  │  │  │  Orchestrator    │◄─┤  Executor        │                    │ │   │
│  │  │  │  (7 phases)      │  │  (Agent coord)   │                    │ │   │
│  │  │  └──────────────────┘  └──────────────────┘                    │ │   │
│  │  │           │                     │                               │ │   │
│  │  │           └─────────┬───────────┘                               │ │   │
│  │  │                     │                                           │ │   │
│  │  │  ┌──────────────────┴───────────────────────────────────────┐  │ │   │
│  │  │  │                  SPECIALIZED AGENTS                       │  │ │   │
│  │  │  │                                                           │  │ │   │
│  │  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │  │ │   │
│  │  │  │  │ Hypothesis  │ │  Evidence   │ │     Summary         │ │  │ │   │
│  │  │  │  │   Agent     │ │   Agent     │ │     Synthesis       │ │  │ │   │
│  │  │  │  │ (ACH)       │ │ (Collection)│ │     Agent           │ │  │ │   │
│  │  │  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │  │ │   │
│  │  │  │                                                           │  │ │   │
│  │  │  │  ┌─────────────────────────────────────────────────────┐ │  │ │   │
│  │  │  │  │            Confidence Scoring Agent                  │ │  │ │   │
│  │  │  │  │         (6-factor ODNI ICD 203 framework)            │ │  │ │   │
│  │  │  │  └─────────────────────────────────────────────────────┘ │  │ │   │
│  │  │  └───────────────────────────────────────────────────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                │                                      │   │
│  │  ┌─────────────────────────────┴───────────────────────────────────┐ │   │
│  │  │                    UNIVERSAL TOOLS LAYER                        │ │   │
│  │  │                                                                 │ │   │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │ │   │
│  │  │  │ Timeline  │ │ Anomaly   │ │Correlation│ │  Network  │       │ │   │
│  │  │  │   Tool    │ │   Tool    │ │   Tool    │ │   Tool    │       │ │   │
│  │  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │ │   │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐                     │ │   │
│  │  │  │   CRUD    │ │   Depth   │ │   Vault   │                     │ │   │
│  │  │  │   Tool    │ │   Tool    │ │   Tool    │                     │ │   │
│  │  │  └───────────┘ └───────────┘ └───────────┘                     │ │   │
│  │  │                                                                 │ │   │
│  │  │  Total: 7 tools, 37 capabilities                               │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                │                                      │   │
│  │  ┌─────────────────────────────┴───────────────────────────────────┐ │   │
│  │  │                      SERVICES LAYER                             │ │   │
│  │  │                                                                 │ │   │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │ │   │
│  │  │  │   LLM         │ │   Entity      │ │   Evidence    │         │ │   │
│  │  │  │   Service     │ │   Aliasing    │ │   Service     │         │ │   │
│  │  │  │ (Gemini/Qwen) │ │   Service     │ │   (SHA-256)   │         │ │   │
│  │  │  └───────────────┘ └───────────────┘ └───────────────┘         │ │   │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │ │   │
│  │  │  │   Augment     │ │   Writer      │ │   Report      │         │ │   │
│  │  │  │   Studio      │ │   Agent       │ │   Builder     │         │ │   │
│  │  │  └───────────────┘ └───────────────┘ └───────────────┘         │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                │                                      │   │
│  │  ┌─────────────────────────────┴───────────────────────────────────┐ │   │
│  │  │                      DATA LAYER                                  │ │   │
│  │  │                                                                 │ │   │
│  │  │  ┌───────────────────────┐  ┌───────────────────────┐          │ │   │
│  │  │  │      Case Vault       │  │      MinIO/S3         │          │ │   │
│  │  │  │    (DuckDB per case)  │  │   (Artifact Store)    │          │ │   │
│  │  │  │                       │  │                       │          │ │   │
│  │  │  │  • evidence_files     │  │  • Raw log files      │          │ │   │
│  │  │  │  • timeline_events    │  │  • PDF exports        │          │ │   │
│  │  │  │  • anomaly_scores     │  │  • Evidence snapshots │          │ │   │
│  │  │  │  • entity_aliases     │  │                       │          │ │   │
│  │  │  │  • chain_of_custody   │  │                       │          │ │   │
│  │  │  └───────────────────────┘  └───────────────────────┘          │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Frontend Architecture

```
frontend/src/
├── app/                              # Next.js 14 App Router
│   ├── (studio)/                     # Studio route group
│   │   └── cases/[id]/studio-v4/     # Report Studio V4
│   └── page.tsx                      # Landing page
│
├── components/
│   └── studio-v4/                    # Studio components
│       ├── CanvaLayout.tsx           # 7-panel canvas layout
│       ├── TopBar.tsx                # Toolbar with AI button
│       ├── GhostWriter/              # Export wizard
│       ├── panels/                   # Evidence, Timeline, etc.
│       ├── dialogs/                  # Modals
│       │   ├── InvestigationConfigDialog.tsx
│       │   └── ReportPreviewPanel.tsx
│       ├── hooks/
│       │   └── useCanvasStream.ts    # SSE to canvas
│       └── store/
│           └── useStudioStore.ts     # Zustand state
│
├── hooks/
│   └── useInvestigationStream.ts     # SSE consumption
│
└── types/
    └── studio.ts                     # TypeScript types
```

### 2. Backend Architecture

```
app/
├── main.py                           # FastAPI entry (197 routes)
├── config.py                         # Configuration
├── database.py                       # DuckDB vault management
│
├── routes/                           # API endpoints
│   ├── investigation.py              # SSE investigation streaming
│   ├── augment.py                    # Chart generation
│   ├── tools.py                      # Universal tools API
│   ├── aliases.py                    # Entity aliasing
│   ├── studio_v4.py                  # Canvas operations
│   ├── deep_research.py              # Research assistant
│   └── ...                           # (cases, evidence, etc.)
│
├── agents/                           # AI agents
│   ├── integration_layer.py          # PipelineExecutor (main)
│   ├── hypothesis.py                 # HypothesisAnalysisAgent
│   ├── evidence_agent.py             # EvidenceCollectionAgent
│   ├── confidence.py                 # ConfidenceScoringAgent
│   └── synthesis.py                  # SummarySynthesisAgent
│
├── services/                         # Business logic
│   ├── unified_orchestrator.py       # 7-phase orchestration
│   ├── augment_studio.py             # Chart generator
│   ├── entity_alias_service.py       # Aliasing
│   ├── llm_service.py                # LLM provider switching
│   └── ...                           # (writer, evidence, etc.)
│
├── tools/                            # Universal Module Tools
│   ├── base_tool.py                  # Framework
│   ├── timeline_tool.py              # 6 capabilities
│   ├── anomaly_tool.py               # 4 capabilities
│   ├── correlation_tool.py           # 5 capabilities
│   ├── network_tool.py               # 5 capabilities
│   ├── crud_tool.py                  # 5 capabilities
│   ├── depth_tool.py                 # 5 capabilities
│   └── vault_tool.py                 # 7 capabilities
│
└── llm/                              # LLM providers
    ├── base.py                       # Abstract provider
    ├── gemini.py                     # Google Gemini
    └── ollama.py                     # Local Qwen3
```

---

## Data Flow

### Investigation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INVESTIGATION DATA FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. USER INPUT                                                               │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  Scenario: "Ransomware attack on production servers..."         │     │
│     │  Objectives: ["Find initial access", "Assess damage"]           │     │
│     │  Time Range: 2024-01-01 to 2024-01-05                           │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  2. INTAKE PHASE                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  • Parse scenario with LLM                                      │     │
│     │  • Extract entities (IPs, users, systems)                       │     │
│     │  • Auto-generate aliases                                        │     │
│     │  OUTPUT: EntitySet, AliasMap                                    │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  3. HYPOTHESIS GENERATION                                                    │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  • H0: No incident occurred (NULL baseline)                     │     │
│     │  • H1: External phishing attack                                 │     │
│     │  • H2: RDP brute force                                          │     │
│     │  • H3: Insider threat                                           │     │
│     │  Each has: prior_confidence, evidence_required, tests_needed    │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  4. PLANNING PHASE                                                           │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  Investigation Plan:                                            │     │
│     │  Phase 1: Timeline Construction (Timeline Tool)                 │     │
│     │  Phase 2: Anomaly Detection (Anomaly Tool)                      │     │
│     │  Phase 3: Entity Correlation (Correlation Tool)                 │     │
│     │  Phase 4: Network Analysis (Network Tool)                       │     │
│     │  ...                                                            │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  5. EXECUTION PHASE (BFS then DFS)                                          │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │                                                                 │     │
│     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │     │
│     │  │  Timeline   │  │   Anomaly   │  │ Correlation │             │     │
│     │  │    Tool     │  │    Tool     │  │    Tool     │             │     │
│     │  │             │  │             │  │             │             │     │
│     │  │  156 events │  │  23 anomaly │  │  45 edges   │             │     │
│     │  │  found      │  │  detected   │  │  built      │             │     │
│     │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │     │
│     │         │                │                │                     │     │
│     │         └────────────────┼────────────────┘                     │     │
│     │                          │                                      │     │
│     │                          ▼                                      │     │
│     │                   SSE Streaming                                 │     │
│     │                   to Frontend                                   │     │
│     │                                                                 │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  6. HYPOTHESIS TESTING                                                       │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  For each hypothesis:                                           │     │
│     │    • Match evidence to required evidence                        │     │
│     │    • Calculate Bayesian posterior                               │     │
│     │    • Update confidence score                                    │     │
│     │                                                                 │     │
│     │  Results:                                                       │     │
│     │    H0: 0.05 (REJECTED)                                          │     │
│     │    H1: 0.82 (HIGH CONFIDENCE)                                   │     │
│     │    H2: 0.23 (LOW)                                               │     │
│     │    H3: 0.15 (VERY LOW)                                          │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  7. CONFIDENCE SCORING                                                       │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  6-Factor Weighted Scoring (ODNI ICD 203):                      │     │
│     │                                                                 │     │
│     │  Factor                    Weight    Score                      │     │
│     │  ─────────────────────────────────────────                      │     │
│     │  Evidence Coverage          0.25     0.85                       │     │
│     │  Module Agreement           0.20     0.90                       │     │
│     │  Temporal Consistency       0.15     0.75                       │     │
│     │  Cross Validation           0.20     0.80                       │     │
│     │  Pattern Match              0.10     0.70                       │     │
│     │  Research Alignment         0.10     0.65                       │     │
│     │                                                                 │     │
│     │  Final: 0.81 → "HIGH CONFIDENCE"                                │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│                                    ▼                                         │
│  8. REPORT GENERATION                                                        │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │  • Generate executive summary                                   │     │
│     │  • Build timeline visualization                                 │     │
│     │  • Insert evidence blocks with hashes                           │     │
│     │  • Create charts (Augment Studio)                               │     │
│     │  • Compile appendices                                           │     │
│     │                                                                 │     │
│     │  OUTPUT: Canvas document → PDF export                           │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Universal Tools Framework

### Tool Architecture

```python
# Base class for all tools
class ModuleTool(ABC):
    tool_id: str
    name: str
    description: str
    capabilities: List[ToolCapability]
    
    @abstractmethod
    async def execute(
        self,
        case_id: str,
        capability: str,
        parameters: Dict[str, Any]
    ) -> ToolOutput:
        """Execute a specific capability"""
        pass
```

### Tool Capabilities

| Tool | Capabilities |
|------|--------------|
| **Timeline** | `build_timeline`, `find_clusters`, `detect_gaps`, `find_bursts`, `filter_events`, `get_anchors` |
| **Anomaly** | `detect_anomalies`, `score_events`, `explain_shap`, `get_top_anomalies` |
| **Correlation** | `build_graph`, `find_communities`, `shortest_path`, `central_nodes`, `mitre_mapping` |
| **Network** | `analyze_flows`, `detect_exfil`, `protocol_breakdown`, `geo_mapping`, `threat_intel` |
| **CRUD** | `analyze_access`, `sensitivity_map`, `high_risk_ops`, `volume_analysis`, `user_patterns` |
| **Depth** | `impact_scoring`, `account_impact`, `system_impact`, `data_impact`, `business_impact` |
| **Vault** | `query_evidence`, `create_snapshot`, `verify_hash`, `list_artifacts`, `export_card`, `search`, `chain_of_custody` |

---

## SSE Streaming Protocol

### Event Types

```typescript
// Investigation events streamed to frontend
interface StreamEvent {
  type: 'phase_start' | 'phase_complete' | 'finding' | 
        'hypothesis' | 'visualization' | 'confidence' | 
        'error' | 'complete';
  
  timestamp: string;
  data: PhaseData | FindingData | HypothesisData | 
        VisualizationData | ConfidenceData;
}

// Phase events
interface PhaseData {
  phase: 'intake' | 'hypothesis' | 'planning' | 
         'execution' | 'testing' | 'confidence' | 'reporting';
  status: 'started' | 'completed';
  message?: string;
}

// Finding events (from tool execution)
interface FindingData {
  tool_id: string;
  capability: string;
  finding_type: string;
  data: any;
  evidence_hash: string;
}

// Visualization events
interface VisualizationData {
  viz_type: 'chart' | 'timeline' | 'graph' | 'table';
  chart_type?: 'pie' | 'bar' | 'line' | 'radar';
  title: string;
  data: any;
  suggested_panel?: string;
}
```

### Frontend Consumption

```typescript
// Hook usage
const { 
  findings,
  hypotheses,
  visualizations,
  confidence,
  progress,
  isRunning,
  startInvestigation 
} = useInvestigationStream();

// Auto-add to canvas
useCanvasStream(findings, visualizations, canvasId);
```

---

## Confidence Scoring

### ODNI ICD 203 Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CONFIDENCE LEVEL MAPPING                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Score Range     Level           Description                                 │
│  ────────────    ─────           ───────────                                 │
│  0.90 - 1.00     VERY HIGH       Near certain, multiple corroborating       │
│  0.75 - 0.89     HIGH            Strong evidence, few gaps                   │
│  0.50 - 0.74     MODERATE        Mixed evidence, some gaps                   │
│  0.25 - 0.49     LOW             Limited evidence, significant gaps          │
│  0.00 - 0.24     VERY LOW        Speculative, contradictory evidence         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Scoring Formula

```
CONFIDENCE = Σ(Wi × Fi) / Σ(Wi)

Where:
- Wi = Weight for factor i
- Fi = Score for factor i (0-1)

Factors:
- Evidence Coverage (W=0.25): What % of required evidence exists?
- Module Agreement (W=0.20): Do multiple modules agree?
- Temporal Consistency (W=0.15): Is the timeline coherent?
- Cross Validation (W=0.20): External corroboration?
- Pattern Match (W=0.10): Matches known attack patterns?
- Research Alignment (W=0.10): Aligns with MITRE/CTI?
```

---

## Evidence Integrity

### Hash Chain

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EVIDENCE HASH CHAIN                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Log Import                                                               │
│     ┌───────────────────────────────────────────────────────────────────┐   │
│     │  File: auth.log                                                    │   │
│     │  SHA-256: a1b2c3d4e5f6...                                          │   │
│     │  Imported: 2024-01-15T10:00:00Z                                    │   │
│     │  CoC Entry: coc-001                                                │   │
│     └───────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  2. Evidence Processing                                                      │
│     ┌───────────────────────────────────────────────────────────────────┐   │
│     │  Parse → Normalize → Index                                         │   │
│     │  Each row gets: row_hash = SHA-256(canonical_json(row))            │   │
│     │  CoC Entry: coc-002                                                │   │
│     └───────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  3. Analysis Results                                                         │
│     ┌───────────────────────────────────────────────────────────────────┐   │
│     │  Anomaly Detection Results:                                        │   │
│     │  result_hash = SHA-256(canonical_json(results))                    │   │
│     │  Input refs: [row_hash_1, row_hash_2, ...]                         │   │
│     │  CoC Entry: coc-003                                                │   │
│     └───────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  4. Evidence Card                                                            │
│     ┌───────────────────────────────────────────────────────────────────┐   │
│     │  Frozen snapshot of evidence state                                 │   │
│     │  card_hash = SHA-256(snapshot_data + all_input_hashes)             │   │
│     │  Immutable after creation                                          │   │
│     │  CoC Entry: coc-004                                                │   │
│     └───────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  5. Report Citation                                                          │
│     ┌───────────────────────────────────────────────────────────────────┐   │
│     │  Citation in report links to evidence card                         │   │
│     │  Hover shows: original value, hash, timestamp                      │   │
│     │  Verification: recompute hash, compare to stored                   │   │
│     └───────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment

### Requirements

- Python 3.11+
- Node.js 18+
- DuckDB
- MinIO (optional, for artifacts)

### Quick Start

```bash
# Backend
cd operation-room/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend  
cd operation-room/frontend
npm install
npm run dev
```

### Environment Variables

```env
# Backend
GEMINI_API_KEY=your-api-key
OLLAMA_HOST=http://localhost:11434
DATA_DIR=./data
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Security Considerations

1. **Evidence Integrity**: All evidence hashed with SHA-256
2. **Chain of Custody**: Append-only audit log
3. **No AI Hallucination**: AI reasons about evidence, doesn't generate facts
4. **Human-in-Loop**: Decision points require human approval
5. **Access Control**: Case-level isolation

---

## Detailed System Design Companion

For the full detailed system design with requested deep diagrams and operational controls, see:

- [DETAILED_SYSTEM_DESIGN.md](DETAILED_SYSTEM_DESIGN.md)

It includes:

1. Detailed system diagram with micro-level module connections.
2. C4-style component model (context, container, and component views).
3. Sequence diagrams for investigation and report generation.
4. Court admissibility controls mapped to each service boundary.
5. Production readiness checklists for self-hosted and SaaS deployment.

---

*Architecture Documentation v1.0*
*Last Updated: April 2026*
