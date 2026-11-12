# Report Studio V3 — Full Redesign Master Plan

## Executive Vision

**Goal:** Build the most advanced forensic report builder that makes investigators feel like they have a team of expert assistants, impresses enterprise clients, and withstands the scrutiny of the most demanding judges in court.

**Philosophy:** 
- Every pixel must have purpose
- Every interaction must feel effortless
- Every feature must serve the investigator's mission
- Every output must be court-admissible

---

## The 6 Phases

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        REPORT STUDIO V3 — IMPLEMENTATION ROADMAP                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  PHASE 1          PHASE 2          PHASE 3          PHASE 4          PHASE 5       │
│  Foundation       Dynamic          Intelligence     Premium          Court-Ready   │
│  ─────────        Components       Layer            Experience       System        │
│                                                                                     │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐   │
│  │ shadcn  │      │ Live    │      │ AI      │      │ Micro-  │      │ Legal   │   │
│  │ /ui     │ ───► │ Evidence│ ───► │ Agents  │ ───► │ Inter-  │ ───► │ Export  │   │
│  │ Setup   │      │ Blocks  │      │ System  │      │ actions │      │ Suite   │   │
│  └─────────┘      └─────────┘      └─────────┘      └─────────┘      └─────────┘   │
│       │                │                │                │                │        │
│       ▼                ▼                ▼                ▼                ▼        │
│  • Tailwind       • SHAP Charts    • Writer Agent   • Animations    • PDF/DOCX     │
│  • TypeScript     • Timeline       • Fact Checker   • Transitions   • Signatures   │
│  • Components     • Network Graph  • Suggestions    • Hover States  • Audit Trail  │
│  • Theme System   • Correlation    • Auto-cite      • Loading UX    • Timestamps   │
│  • Icon Library   • Metrics Cards  • Completeness   • Empty States  • Hash Chain   │
│                                                                                     │
│                                    PHASE 6                                          │
│                                    Polish & Ship                                    │
│                                    ─────────────                                    │
│                                    ┌─────────┐                                      │
│                                    │ Testing │                                      │
│                                    │ & QA    │                                      │
│                                    └─────────┘                                      │
│                                         │                                           │
│                                         ▼                                           │
│                                    • E2E Tests                                      │
│                                    • Performance                                    │
│                                    • Accessibility                                  │
│                                    • Documentation                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

# Phase 1: Foundation — shadcn/ui + Design System

## Objective
Transform the frontend from inline-styled chaos into a world-class component system that rivals Notion, Linear, and enterprise forensic tools.

## Why shadcn/ui?

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **shadcn/ui** | Copy-paste components, full control, Radix accessibility, Tailwind native | Need TypeScript | ✅ CHOSEN |
| **Material UI** | Comprehensive, well-documented | Heavy, Google aesthetic, less customizable | ❌ |
| **Chakra UI** | Great DX, themeable | Less sophisticated look | ❌ |
| **Ant Design** | Enterprise-ready | Chinese documentation bias, heavy | ❌ |
| **Custom** | Full control | Months of work, accessibility issues | ❌ |

## Tasks

### 1.1 TypeScript Migration
```
Current: JavaScript (.js, .jsx)
Target: TypeScript (.ts, .tsx)
```

**Why TypeScript?**
- shadcn/ui requires it
- Catch bugs at compile time
- Better IDE support
- Self-documenting code
- Enterprise standard

**Migration Strategy:**
1. Rename files incrementally (.js → .tsx)
2. Add types progressively (start with `any`, refine)
3. Create shared type definitions
4. No big-bang rewrite

### 1.2 Tailwind CSS Setup
```bash
# Install Tailwind
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Install dependencies for shadcn
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge
npm install @radix-ui/react-slot
npm install lucide-react
```

### 1.3 shadcn/ui Initialization
```bash
npx shadcn-ui@latest init

# Questions:
# Style: Default
# Base color: Slate
# CSS variables: Yes
# Where is your global CSS?: src/app/globals.css
# Import alias for components: @/components
# Import alias for utilities: @/lib/utils
```

### 1.4 Design Tokens

```typescript
// tailwind.config.ts
const config = {
  theme: {
    extend: {
      colors: {
        // Brand
        brand: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          900: '#1e3a8a',
        },
        // Severity (forensic standard)
        severity: {
          critical: '#dc2626',
          high: '#ea580c',
          medium: '#ca8a04',
          low: '#16a34a',
          info: '#3b82f6',
        },
        // Module identification
        module: {
          timeline: '#8b5cf6',
          anomaly: '#ef4444',
          correlation: '#06b6d4',
          crud: '#f59e0b',
          network: '#10b981',
          depth: '#6366f1',
          case: '#64748b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
};
```

### 1.5 Core Components to Install

```bash
# Essential UI
npx shadcn-ui@latest add button
npx shadcn-ui@latest add card
npx shadcn-ui@latest add input
npx shadcn-ui@latest add label
npx shadcn-ui@latest add select
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add tooltip
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add dropdown-menu
npx shadcn-ui@latest add popover
npx shadcn-ui@latest add command  # For @-mentions
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add separator
npx shadcn-ui@latest add scroll-area
npx shadcn-ui@latest add skeleton
npx shadcn-ui@latest add toast
npx shadcn-ui@latest add alert

# Data Display
npx shadcn-ui@latest add table
npx shadcn-ui@latest add accordion
npx shadcn-ui@latest add collapsible
npx shadcn-ui@latest add avatar

# Navigation
npx shadcn-ui@latest add navigation-menu
npx shadcn-ui@latest add breadcrumb
npx shadcn-ui@latest add sidebar

# Forms
npx shadcn-ui@latest add form
npx shadcn-ui@latest add textarea
npx shadcn-ui@latest add switch
npx shadcn-ui@latest add slider
npx shadcn-ui@latest add checkbox
```

### 1.6 Custom Forensic Components

Beyond shadcn defaults, we'll create:

```typescript
// src/components/forensic/
├── EvidenceBlock.tsx       // Dynamic evidence container
├── ModuleCard.tsx          // Module insight card with live data
├── SeverityBadge.tsx       // Critical/High/Medium/Low badges
├── HashDisplay.tsx         // SHA-256 with copy button
├── TimestampDisplay.tsx    // ISO timestamp with relative time
├── CitationMark.tsx        // [EVD-AN-001] inline citation
├── FigureContainer.tsx     // Figure with caption and metadata
├── MetricCard.tsx          // KPI display (count, trend, sparkline)
├── ChartContainer.tsx      // Unified chart wrapper
├── LoadingState.tsx        // Module-specific skeleton
└── EmptyState.tsx          // No data illustration
```

### 1.7 Icon System

Replace ALL emojis with Lucide icons:

```typescript
// src/components/icons/ModuleIcons.tsx
import {
  Clock,           // Timeline
  AlertTriangle,   // Anomaly
  GitBranch,       // Correlation
  Database,        // CRUD
  Globe,           // Network
  Layers,          // Depth
  Briefcase,       // Case
  FileText,        // Report
  Shield,          // Security
  Hash,            // Hash/Integrity
  CheckCircle,     // Success
  XCircle,         // Error
  AlertCircle,     // Warning
  Info,            // Info
  Sparkles,        // AI/Magic
  Bot,             // Agent
  Download,        // Export
  Save,            // Save
  Undo,            // Undo
  Redo,            // Redo
} from 'lucide-react';

export const MODULE_ICONS = {
  timeline: Clock,
  anomaly: AlertTriangle,
  correlation: GitBranch,
  crud: Database,
  network: Globe,
  depth: Layers,
  case: Briefcase,
} as const;
```

## Deliverables

- [ ] TypeScript configured (tsconfig.json, strict mode)
- [ ] Tailwind CSS installed with custom theme
- [ ] shadcn/ui initialized with 20+ components
- [ ] Design tokens defined (colors, fonts, spacing)
- [ ] Lucide icons integrated
- [ ] Base layout components built
- [ ] Dark mode support configured

## Success Criteria

1. **Zero inline styles** in new code
2. **100% TypeScript** for new files
3. **Consistent spacing** using Tailwind classes
4. **Accessible** (keyboard nav, screen reader)
5. **Responsive** (works on 1024px to 4K)

---

# Phase 2: Dynamic Evidence Components

## Objective
Replace static image insertion with **live, interactive evidence blocks** that render actual components, maintain data binding, and export gracefully.

## The Innovation: Evidence Blocks

### What's Wrong with Images?
- ❌ Static — can't interact
- ❌ Stale — doesn't update with new data
- ❌ Large — bloats document size
- ❌ Lossy — compression artifacts
- ❌ Inaccessible — screen readers can't parse

### What We're Building: Dynamic Evidence Blocks

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           EVIDENCE BLOCK ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           TipTap Editor                                     │   │
│  │                                                                             │   │
│  │   This investigation found 45 anomalous events. The SHAP analysis          │   │
│  │   revealed the primary driver was after-hours activity:                    │   │
│  │                                                                             │   │
│  │   ┌─────────────────────────────────────────────────────────────────────┐   │   │
│  │   │  ╔═══════════════════════════════════════════════════════════════╗ │   │   │
│  │   │  ║  EVIDENCE BLOCK: SHAP Feature Importance                     ║ │   │   │
│  │   │  ╠═══════════════════════════════════════════════════════════════╣ │   │   │
│  │   │  ║                                                               ║ │   │   │
│  │   │  ║  [LIVE RECHARTS COMPONENT RENDERS HERE]                      ║ │   │   │
│  │   │  ║                                                               ║ │   │   │
│  │   │  ║  hour_of_day    ████████████████████████████ 35.4%           ║ │   │   │
│  │   │  ║  actor_encoded  ██████████████████░░░░░░░░░░ 22.1%           ║ │   │   │
│  │   │  ║  action_encoded █████████████░░░░░░░░░░░░░░░ 15.8%           ║ │   │   │
│  │   │  ║                                                               ║ │   │   │
│  │   │  ╠═══════════════════════════════════════════════════════════════╣ │   │   │
│  │   │  ║  📊 Figure 2 | Source: Anomaly Module                        ║ │   │   │
│  │   │  ║  Run: AN-2025-06-08-003 | Hash: sha256:e3b0c44...            ║ │   │   │
│  │   │  ║  [🔄 Refresh] [📋 Copy Data] [⚙️ Settings] [🗑️ Remove]        ║ │   │   │
│  │   │  ╚═══════════════════════════════════════════════════════════════╝ │   │   │
│  │   └─────────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                             │   │
│  │   As shown above, the hour_of_day feature contributed 35.4% to the         │   │
│  │   anomaly classification...                                                │   │
│  │                                                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  EVIDENCE BLOCK INTERNALS:                                                          │
│  ─────────────────────────                                                          │
│                                                                                     │
│  TipTap Node Extension:                                                             │
│  {                                                                                  │
│    type: "evidenceBlock",                                                           │
│    attrs: {                                                                         │
│      blockId: "eb-uuid-001",                                                        │
│      blockType: "shap-feature-importance",   // Component type                      │
│      module: "anomaly",                       // Source module                      │
│      runId: "AN-2025-06-08-003",             // Specific analysis run              │
│      figureNumber: 2,                         // Auto-assigned                      │
│      caption: "SHAP Feature Importance...",   // User-editable                      │
│      dataQuery: {                             // How to fetch data                  │
│        endpoint: "/api/cases/{caseId}/anomalies/summary",                           │
│        field: "shap_global_importance"                                              │
│      },                                                                             │
│      dataSnapshot: {...},                     // Cached data at insert time         │
│      dataHash: "sha256:...",                  // Hash of data for integrity         │
│      settings: {                              // Component-specific settings        │
│        colorScheme: "default",                                                      │
│        showLabels: true,                                                            │
│        maxFeatures: 10                                                              │
│      },                                                                             │
│      metadata: {                                                                    │
│        insertedAt: "2026-03-28T14:00:00Z",                                          │
│        insertedBy: "sarah.chen",                                                    │
│        lastRefreshed: "2026-03-28T14:30:00Z"                                        │
│      }                                                                              │
│    }                                                                                │
│  }                                                                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Evidence Block Types

### 2.1 SHAP Visualizations

```typescript
// src/components/evidence/SHAPFeatureImportance.tsx
interface SHAPFeatureImportanceProps {
  data: {
    feature: string;
    importance: number;
    importance_pct: number;
    description: string;
  }[];
  settings: {
    maxFeatures?: number;
    showPercentages?: boolean;
    colorScheme?: 'default' | 'severity' | 'monochrome';
  };
  figureNumber: number;
  onSettingsChange: (settings: any) => void;
}

// src/components/evidence/SHAPWaterfall.tsx
interface SHAPWaterfallProps {
  eventId: string;
  baseValue: number;
  contributions: {
    feature: string;
    shap_value: number;
    direction: 'anomalous' | 'normal';
    description: string;
  }[];
  finalScore: number;
  settings: {
    showDescriptions?: boolean;
    highlightTop?: number;
  };
}
```

### 2.2 Timeline Visualizations

```typescript
// src/components/evidence/TimelineChart.tsx
interface TimelineChartProps {
  events: TimelineEvent[];
  chartType: 'area' | 'bar' | 'scatter';
  groupBy: 'hour' | 'day' | 'source' | 'actor';
  settings: {
    dateRange?: { start: Date; end: Date };
    showSeverity?: boolean;
    showAnomalies?: boolean;
  };
}

// src/components/evidence/TimelineSeverityPie.tsx
// src/components/evidence/TimelineHourlyHeatmap.tsx
// src/components/evidence/TimelineActorBar.tsx
```

### 2.3 Network Visualizations

```typescript
// src/components/evidence/NetworkGraph.tsx
interface NetworkGraphProps {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  layout: 'force' | 'hierarchical' | 'circular';
  settings: {
    nodeSize: 'degree' | 'betweenness' | 'uniform';
    edgeColor: 'weight' | 'type' | 'uniform';
    showLabels: boolean;
    highlight?: string[];  // Node IDs to highlight
  };
}

// src/components/evidence/DataFlowSankey.tsx
// src/components/evidence/ExfilCandidateTable.tsx
```

### 2.4 Correlation Visualizations

```typescript
// src/components/evidence/CorrelationGraph.tsx
interface CorrelationGraphProps {
  entities: Entity[];
  relationships: Relationship[];
  focusEntity?: string;
  settings: {
    depthLimit: number;
    showWeights: boolean;
    layout: 'force' | 'tree';
  };
}

// src/components/evidence/AttackChainTimeline.tsx
// src/components/evidence/EntityCard.tsx
```

### 2.5 Metrics & KPIs

```typescript
// src/components/evidence/MetricCard.tsx
interface MetricCardProps {
  title: string;
  value: number | string;
  change?: { value: number; direction: 'up' | 'down' };
  sparkline?: number[];
  module: ModuleType;
}

// src/components/evidence/MetricGrid.tsx
// Displays multiple metrics in a responsive grid
```

### 2.6 Data Tables

```typescript
// src/components/evidence/EvidenceTable.tsx
interface EvidenceTableProps {
  columns: ColumnDef[];
  data: any[];
  settings: {
    pageSize: number;
    sortable: boolean;
    filterable: boolean;
    exportable: boolean;
  };
  figureNumber: number;
  caption: string;
}
```

## TipTap Node Extension

```typescript
// src/components/editor/extensions/EvidenceBlockNode.tsx
import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { EvidenceBlockComponent } from './EvidenceBlockComponent';

export const EvidenceBlock = Node.create({
  name: 'evidenceBlock',
  group: 'block',
  atom: true,
  draggable: true,
  selectable: true,

  addAttributes() {
    return {
      blockId: { default: null },
      blockType: { default: null },
      module: { default: null },
      runId: { default: null },
      figureNumber: { default: null },
      caption: { default: '' },
      dataQuery: { default: {} },
      dataSnapshot: { default: null },
      dataHash: { default: null },
      settings: { default: {} },
      metadata: { default: {} },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-evidence-block]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, {
      'data-evidence-block': '',
      class: 'evidence-block-wrapper',
    })];
  },

  addNodeView() {
    return ReactNodeViewRenderer(EvidenceBlockComponent);
  },
});
```

## Export Strategy

When exporting to PDF/DOCX, evidence blocks are rendered to images:

```typescript
// src/lib/export/renderEvidenceBlock.ts
export async function renderEvidenceBlockToImage(
  block: EvidenceBlockAttrs,
  format: 'png' | 'svg'
): Promise<{ blob: Blob; width: number; height: number }> {
  // 1. Create offscreen container
  const container = document.createElement('div');
  container.style.width = '800px';
  container.style.position = 'absolute';
  container.style.left = '-9999px';
  document.body.appendChild(container);

  // 2. Render React component to container
  const root = createRoot(container);
  root.render(<EvidenceBlockRenderer {...block} exportMode />);
  
  // 3. Wait for charts to render
  await new Promise(resolve => setTimeout(resolve, 500));

  // 4. Capture with html-to-image
  const blob = await toBlob(container, { quality: 0.95 });

  // 5. Cleanup
  root.unmount();
  document.body.removeChild(container);

  return { blob, width: 800, height: container.offsetHeight };
}
```

## Figure Registry Integration

```typescript
// src/lib/figureRegistry.ts
class FigureRegistry {
  private figures: Map<string, FigureInfo> = new Map();
  private nextNumber: number = 1;

  register(blockId: string, module: string, caption: string): number {
    const figureNumber = this.nextNumber++;
    this.figures.set(blockId, {
      figureNumber,
      module,
      caption,
      pageEstimate: null,
    });
    return figureNumber;
  }

  updatePageEstimate(blockId: string, page: number): void {
    const figure = this.figures.get(blockId);
    if (figure) figure.pageEstimate = page;
  }

  getTableOfFigures(): FigureInfo[] {
    return Array.from(this.figures.values())
      .sort((a, b) => a.figureNumber - b.figureNumber);
  }

  getCrossReference(blockId: string): string {
    const figure = this.figures.get(blockId);
    if (!figure) return '[Figure ?]';
    const page = figure.pageEstimate ? ` (page ${figure.pageEstimate})` : '';
    return `Figure ${figure.figureNumber}${page}`;
  }
}
```

## Deliverables

- [ ] TipTap EvidenceBlock node extension
- [ ] 6 SHAP visualization components
- [ ] 5 Timeline visualization components
- [ ] 4 Network visualization components
- [ ] 4 Correlation visualization components
- [ ] Metric cards and grids
- [ ] Evidence tables with sorting/filtering
- [ ] Figure registry with auto-numbering
- [ ] Cross-reference system (@fig mentions)
- [ ] Export renderer (component → image)

---

# Phase 3: Intelligence Layer (AI Agents)

## Objective
Elevate the AI from "generate text" button to a **team of specialized agents** that actively assist the investigator.

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           AI AGENT ECOSYSTEM                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│                              ┌─────────────────┐                                    │
│                              │  ORCHESTRATOR   │                                    │
│                              │     AGENT       │                                    │
│                              └────────┬────────┘                                    │
│                                       │                                             │
│           ┌───────────────────────────┼───────────────────────────┐                 │
│           │                           │                           │                 │
│           ▼                           ▼                           ▼                 │
│   ┌───────────────┐           ┌───────────────┐           ┌───────────────┐         │
│   │    WRITER     │           │    ANALYST    │           │    CHECKER    │         │
│   │    AGENT      │           │    AGENT      │           │    AGENT      │         │
│   └───────┬───────┘           └───────┬───────┘           └───────┬───────┘         │
│           │                           │                           │                 │
│           ▼                           ▼                           ▼                 │
│   • Generate prose           • Find patterns            • Verify facts             │
│   • Section drafts           • Correlate data           • Check citations          │
│   • Style matching           • Identify gaps            • Detect contradictions    │
│   • Citation injection       • Suggest evidence         • Validate logic           │
│                                                                                     │
│   ┌───────────────┐           ┌───────────────┐           ┌───────────────┐         │
│   │   RESEARCH    │           │   COMPLETENESS│           │    STYLE      │         │
│   │    AGENT      │           │    AGENT      │           │    AGENT      │         │
│   └───────┬───────┘           └───────┬───────┘           └───────┬───────┘         │
│           │                           │                           │                 │
│           ▼                           ▼                           ▼                 │
│   • Query evidence           • Template check            • Tone consistency        │
│   • Find related            • Section coverage          • Terminology             │
│   • Pull statistics         • Missing elements          • Formality level         │
│   • Gather context          • Unused evidence           • Court language          │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Agent Specifications

### 3.1 Writer Agent (Enhanced)

**Current State:** Single-shot text generation
**Target State:** Multi-turn, context-aware, citation-injecting writer

```python
# backend/app/agents/writer_agent.py
from langgraph.graph import StateGraph
from typing import TypedDict, List, Annotated
import operator

class WriterState(TypedDict):
    # Input
    section_type: str
    module_data: dict
    existing_content: str
    style_guide: str
    
    # Working memory
    gathered_evidence: List[dict]
    draft_versions: List[str]
    citations_to_inject: List[dict]
    
    # Output
    final_content: str
    citations: List[dict]
    confidence_score: float
    suggestions: List[str]

def build_writer_agent():
    graph = StateGraph(WriterState)
    
    # Node 1: Gather relevant evidence
    graph.add_node("gather_evidence", gather_evidence_node)
    
    # Node 2: Generate initial draft
    graph.add_node("generate_draft", generate_draft_node)
    
    # Node 3: Inject citations with verification
    graph.add_node("inject_citations", inject_citations_node)
    
    # Node 4: Self-critique and refine
    graph.add_node("self_critique", self_critique_node)
    
    # Node 5: Final polish
    graph.add_node("polish", polish_node)
    
    # Edges
    graph.add_edge("gather_evidence", "generate_draft")
    graph.add_edge("generate_draft", "inject_citations")
    graph.add_edge("inject_citations", "self_critique")
    graph.add_conditional_edges(
        "self_critique",
        should_refine,
        {
            "refine": "generate_draft",
            "accept": "polish"
        }
    )
    graph.add_edge("polish", END)
    
    return graph.compile()
```

### 3.2 Fact Checker Agent

```python
# backend/app/agents/fact_checker_agent.py
class FactCheckerState(TypedDict):
    content: str
    citations: List[dict]
    evidence_data: dict
    
    # Results
    verified_claims: List[dict]
    unverified_claims: List[dict]
    contradictions: List[dict]
    suggestions: List[str]

def build_fact_checker_agent():
    graph = StateGraph(FactCheckerState)
    
    # Node 1: Extract claims from content
    graph.add_node("extract_claims", extract_claims_node)
    
    # Node 2: Match claims to evidence
    graph.add_node("match_evidence", match_evidence_node)
    
    # Node 3: Verify numerical claims
    graph.add_node("verify_numbers", verify_numbers_node)
    
    # Node 4: Detect contradictions
    graph.add_node("detect_contradictions", detect_contradictions_node)
    
    # Node 5: Generate report
    graph.add_node("generate_report", generate_report_node)
    
    return graph.compile()
```

### 3.3 Completeness Analyzer Agent

```python
# backend/app/agents/completeness_agent.py
REPORT_TEMPLATE_REQUIREMENTS = {
    "executive_summary": {
        "required_elements": [
            "incident_description",
            "date_range",
            "key_findings_count",
            "severity_assessment",
            "recommendations_summary"
        ],
        "suggested_evidence": ["timeline_summary", "anomaly_count", "top_actors"]
    },
    "methodology": {
        "required_elements": [
            "tools_used",
            "data_sources",
            "analysis_techniques",
            "limitations"
        ],
        "suggested_evidence": ["module_list", "run_parameters"]
    },
    # ... more sections
}

class CompletenessState(TypedDict):
    document_ast: dict
    template_type: str
    available_evidence: dict
    
    # Results
    section_scores: dict
    missing_elements: List[dict]
    unused_evidence: List[dict]
    overall_score: float
    recommendations: List[str]
```

### 3.4 Research Agent

```python
# backend/app/agents/research_agent.py
class ResearchState(TypedDict):
    query: str
    context: str
    available_modules: List[str]
    
    # Results
    relevant_findings: List[dict]
    statistics: dict
    suggested_visualizations: List[str]
    related_queries: List[str]

def build_research_agent():
    """
    Agent that autonomously queries all modules to find
    relevant evidence for a given research question.
    
    Example query: "What suspicious activities occurred after hours?"
    
    Agent will:
    1. Query timeline for events between 18:00-06:00
    2. Query anomaly for after-hours flagged events
    3. Query CRUD for database access patterns
    4. Synthesize findings
    """
    pass
```

## Smart Suggestions Panel

```typescript
// src/components/editor/SmartSuggestionsPanel.tsx
interface Suggestion {
  id: string;
  type: 'completeness' | 'evidence' | 'citation' | 'improvement' | 'contradiction';
  priority: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  action?: {
    label: string;
    handler: () => void;
  };
  affectedSection?: string;
  relatedEvidence?: string[];
}

// Example suggestions:
const exampleSuggestions: Suggestion[] = [
  {
    type: 'completeness',
    priority: 'high',
    title: 'Missing methodology section',
    description: 'Your report lacks a methodology section. This is required for court admissibility.',
    action: {
      label: 'Generate methodology',
      handler: () => generateSection('methodology')
    }
  },
  {
    type: 'evidence',
    priority: 'medium',
    title: 'Unused anomaly data',
    description: 'You have 45 anomalous events that haven\'t been referenced in the report.',
    action: {
      label: 'View anomalies',
      handler: () => openModulePanel('anomaly')
    }
  },
  {
    type: 'contradiction',
    priority: 'high',
    title: 'Conflicting timestamps',
    description: 'Page 3 says "June 5" but Figure 2 shows data from June 6.',
    action: {
      label: 'Review conflict',
      handler: () => highlightConflict('conflict-001')
    }
  },
  {
    type: 'citation',
    priority: 'medium',
    title: 'Unverified claim',
    description: '"The attacker accessed 1,000 records" has no supporting citation.',
    action: {
      label: 'Add citation',
      handler: () => openCitationPicker('claim-001')
    }
  }
];
```

## Deliverables

- [ ] Enhanced Writer Agent (5-node pipeline)
- [ ] Fact Checker Agent
- [ ] Completeness Analyzer Agent
- [ ] Research Agent
- [ ] Smart Suggestions Panel
- [ ] Real-time suggestion updates
- [ ] Agent orchestration system
- [ ] Agent activity indicators

---

# Phase 4: Premium Experience (Micro-interactions)

## Objective
Add the polish that makes the difference between "functional software" and "software people love to use."

## 4.1 Loading States

```typescript
// Every async action has a proper loading state
// src/components/ui/LoadingStates.tsx

// Skeleton for evidence blocks
<EvidenceBlockSkeleton module="anomaly" />

// Inline loading for buttons
<Button loading={isGenerating}>
  <Sparkles className="mr-2 h-4 w-4" />
  Generate
</Button>

// Progress for multi-step operations
<ProgressSteps 
  steps={['Gathering evidence', 'Generating draft', 'Adding citations', 'Polishing']}
  current={2}
/>

// Streaming text animation
<StreamingText content={streamedContent} />
```

## 4.2 Transitions & Animations

```typescript
// src/lib/animations.ts
import { motion } from 'framer-motion';

// Panel slide-in
export const slideIn = {
  initial: { x: 300, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: 300, opacity: 0 },
  transition: { type: 'spring', damping: 25, stiffness: 300 }
};

// Evidence block insert
export const blockInsert = {
  initial: { opacity: 0, scale: 0.95, y: -10 },
  animate: { opacity: 1, scale: 1, y: 0 },
  transition: { duration: 0.2 }
};

// Suggestion appear
export const suggestionAppear = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
  transition: { duration: 0.3, delay: 0.1 }
};

// Success flash (after save, verify, etc.)
export const successFlash = {
  initial: { backgroundColor: 'transparent' },
  animate: { backgroundColor: ['transparent', '#dcfce7', 'transparent'] },
  transition: { duration: 0.5 }
};
```

## 4.3 Hover States & Tooltips

```typescript
// Rich tooltips with context
<Tooltip>
  <TooltipTrigger asChild>
    <Badge variant="outline" className="cursor-help">
      <AlertTriangle className="h-3 w-3 mr-1" />
      45 anomalies
    </Badge>
  </TooltipTrigger>
  <TooltipContent className="w-80 p-4">
    <div className="space-y-2">
      <p className="font-semibold">Anomaly Detection Results</p>
      <div className="text-sm text-muted-foreground">
        <p>Model: Ensemble (IF + LOF)</p>
        <p>Contamination: 10%</p>
        <p>Top driver: hour_of_day (35.4%)</p>
      </div>
      <Button size="sm" variant="outline" className="w-full">
        View Details
      </Button>
    </div>
  </TooltipContent>
</Tooltip>
```

## 4.4 Empty States

```typescript
// src/components/ui/EmptyStates.tsx
const EmptyState = {
  NoAnomalies: () => (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <div className="rounded-full bg-emerald-100 p-3 mb-4">
        <CheckCircle className="h-6 w-6 text-emerald-600" />
      </div>
      <h3 className="font-semibold text-lg">No anomalies detected</h3>
      <p className="text-muted-foreground text-sm mt-1 max-w-sm">
        The analysis found no anomalous events in the selected time range.
        Try adjusting the contamination threshold or date filters.
      </p>
      <Button variant="outline" className="mt-4">
        Adjust Parameters
      </Button>
    </div>
  ),
  
  NoEvidence: () => (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <div className="rounded-full bg-slate-100 p-3 mb-4">
        <FileText className="h-6 w-6 text-slate-600" />
      </div>
      <h3 className="font-semibold text-lg">No evidence added yet</h3>
      <p className="text-muted-foreground text-sm mt-1 max-w-sm">
        Start by running analysis modules or drag evidence blocks
        from the sidebar into your report.
      </p>
    </div>
  ),
};
```

## 4.5 Success & Error Feedback

```typescript
// Toast notifications with actions
toast({
  title: "Report saved",
  description: "Version 12 • sha256:e3b0c44298fc...",
  action: <ToastAction altText="View history">View history</ToastAction>,
});

toast({
  variant: "destructive",
  title: "Citation verification failed",
  description: "The data hash has changed since this citation was added.",
  action: <ToastAction altText="Review">Review</ToastAction>,
});

// Inline success indicators
<Button onClick={handleSave} disabled={isSaving}>
  {isSaved ? (
    <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
      <CheckCircle className="h-4 w-4 text-emerald-500" />
    </motion.div>
  ) : (
    <Save className="h-4 w-4" />
  )}
  {isSaving ? 'Saving...' : isSaved ? 'Saved' : 'Save'}
</Button>
```

## 4.6 Keyboard Shortcuts

```typescript
// src/lib/shortcuts.ts
const SHORTCUTS = {
  // Document
  'cmd+s': 'Save document',
  'cmd+shift+s': 'Save as new version',
  'cmd+z': 'Undo',
  'cmd+shift+z': 'Redo',
  
  // Editing
  'cmd+b': 'Bold',
  'cmd+i': 'Italic',
  'cmd+u': 'Underline',
  'cmd+shift+x': 'Strikethrough',
  
  // Evidence
  'cmd+shift+e': 'Open evidence panel',
  'cmd+shift+a': 'Open AI assistant',
  'cmd+shift+c': 'Insert citation',
  'cmd+shift+f': 'Insert figure reference',
  
  // Navigation
  'cmd+shift+o': 'Open outline',
  'cmd+\\': 'Toggle sidebar',
  'cmd+p': 'Quick search',
  
  // Export
  'cmd+shift+p': 'Export to PDF',
  'cmd+shift+d': 'Export to DOCX',
};

// Command palette (cmd+k)
<CommandDialog>
  <CommandInput placeholder="Type a command or search..." />
  <CommandList>
    <CommandGroup heading="Actions">
      <CommandItem onSelect={() => generateSection('executive_summary')}>
        <Sparkles className="mr-2 h-4 w-4" />
        Generate Executive Summary
      </CommandItem>
      <CommandItem onSelect={() => runFactCheck()}>
        <CheckCircle className="mr-2 h-4 w-4" />
        Run Fact Check
      </CommandItem>
    </CommandGroup>
    <CommandGroup heading="Insert">
      <CommandItem onSelect={() => insertEvidenceBlock()}>
        <Plus className="mr-2 h-4 w-4" />
        Insert Evidence Block
      </CommandItem>
    </CommandGroup>
  </CommandList>
</CommandDialog>
```

## Deliverables

- [ ] Loading skeletons for all components
- [ ] Framer Motion animations
- [ ] Rich tooltips with context
- [ ] Empty state illustrations
- [ ] Toast notification system
- [ ] Keyboard shortcuts
- [ ] Command palette (cmd+k)
- [ ] Focus management

---

# Phase 5: Court-Ready Export System

## Objective
Generate exports that can be submitted as evidence in legal proceedings, with full audit trails, integrity verification, and professional formatting.

## 5.1 Export Formats

### PDF Export
```typescript
// src/lib/export/pdfExporter.ts
interface PDFExportOptions {
  // Metadata
  title: string;
  author: string;
  caseId: string;
  organization: string;
  classification: 'Public' | 'Internal' | 'Confidential' | 'Restricted';
  
  // Formatting
  pageSize: 'A4' | 'Letter';
  orientation: 'portrait' | 'landscape';
  margins: { top: number; right: number; bottom: number; left: number };
  
  // Features
  includeTableOfContents: boolean;
  includeTableOfFigures: boolean;
  includeEvidenceAppendix: boolean;
  includeIntegrityManifest: boolean;
  
  // Branding
  headerLogo?: string;
  footerText?: string;
  
  // Security
  password?: string;
  allowPrinting: boolean;
  allowCopying: boolean;
}
```

### DOCX Export
```typescript
// src/lib/export/docxExporter.ts
interface DOCXExportOptions {
  // Similar to PDF but with:
  trackChanges: boolean;
  templateFile?: string;  // Use organization template
  includeComments: boolean;
}
```

### HTML Export
```typescript
// Self-contained HTML with embedded CSS and images
// Can be opened offline in any browser
interface HTMLExportOptions {
  embedImages: boolean;  // Base64 encode images
  embedFonts: boolean;   // Include font files
  minify: boolean;
}
```

## 5.2 Integrity Manifest

Every export includes a manifest proving document integrity:

```json
{
  "manifest_version": "1.0",
  "document_id": "doc-uuid-001",
  "document_title": "Corporate Data Breach Investigation Report",
  "case_id": "CORP-2025-001",
  
  "export": {
    "format": "pdf",
    "exported_at": "2026-03-28T15:30:00Z",
    "exported_by": "sarah.chen@company.com",
    "file_hash": "sha256:a1b2c3d4e5f6...",
    "file_size_bytes": 2458624
  },
  
  "content_integrity": {
    "document_hash": "sha256:9f8e7d6c5b4a...",
    "version_number": 12,
    "last_modified": "2026-03-28T15:25:00Z",
    "total_sections": 8,
    "total_figures": 12,
    "total_citations": 45
  },
  
  "evidence_chain": [
    {
      "figure_number": 1,
      "type": "timeline_chart",
      "source_module": "timeline",
      "source_run_id": "TL-2025-06-08-001",
      "data_hash": "sha256:1a2b3c4d...",
      "data_timestamp": "2026-03-28T10:00:00Z"
    },
    {
      "figure_number": 2,
      "type": "shap_feature_importance",
      "source_module": "anomaly",
      "source_run_id": "AN-2025-06-08-003",
      "data_hash": "sha256:5e6f7g8h...",
      "data_timestamp": "2026-03-28T11:30:00Z"
    }
  ],
  
  "chain_of_custody": [
    {
      "action": "document_created",
      "actor": "sarah.chen@company.com",
      "timestamp": "2026-03-28T09:00:00Z"
    },
    {
      "action": "evidence_added",
      "actor": "sarah.chen@company.com",
      "timestamp": "2026-03-28T10:30:00Z",
      "details": { "figure_number": 1, "module": "timeline" }
    },
    {
      "action": "ai_generation",
      "actor": "writer_agent",
      "timestamp": "2026-03-28T12:00:00Z",
      "details": { "section": "executive_summary" }
    },
    {
      "action": "document_exported",
      "actor": "sarah.chen@company.com",
      "timestamp": "2026-03-28T15:30:00Z",
      "details": { "format": "pdf" }
    }
  ],
  
  "verification": {
    "verify_url": "https://nflip.example.com/verify",
    "verification_code": "NFLIP-2026-03-28-XXXXX"
  }
}
```

## 5.3 Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ [LOGO]  CONFIDENTIAL - Corporate Data Breach Investigation     │ │
│ │         Case #CORP-2025-001                                    │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│                                                                     │
│   1. Executive Summary                                              │
│   ═══════════════════                                               │
│                                                                     │
│   This report documents the forensic investigation of a corporate   │
│   data breach discovered on June 1, 2025. The investigation        │
│   analyzed 245 events across 7 log sources over a 7-day period.    │
│                                                                     │
│   Key Findings:                                                     │
│   • 45 anomalous events detected (18.4% anomaly rate)              │
│   • Primary attack vector: after-hours database access             │
│   • Affected systems: HR database, file server                     │
│   • Data potentially exfiltrated: ~1,000 employee records          │
│                                                                     │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                                                             │   │
│   │            [Figure 1: Event Timeline]                       │   │
│   │                                                             │   │
│   │   ▃▃▃▃▃▃▃▃▃▅▅▅▅▅▇▇▇▇▇▅▅▅▃▃                                 │   │
│   │   ─────────────────────────                                 │   │
│   │   Jun 1  Jun 2  Jun 3  Jun 4  Jun 5  Jun 6  Jun 7          │   │
│   │                                                             │   │
│   ├─────────────────────────────────────────────────────────────┤   │
│   │ Figure 1: Timeline of events showing peak activity on       │   │
│   │ June 6, 2025 at 21:00 local time.                          │   │
│   │ Source: Timeline Module, Run #TL-2025-06-08-001            │   │
│   │ Data Hash: sha256:1a2b3c4d...                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Page 3 of 28 │ v12 │ Generated: 2026-03-28 │ sha256:a1b2c3...  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## 5.4 Evidence Appendix

Auto-generated appendix with all evidence details:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPENDIX A                                  │
│                    EVIDENCE INVENTORY                               │
│═════════════════════════════════════════════════════════════════════│
│                                                                     │
│ FIGURE 1: Event Timeline                                            │
│ ─────────────────────────                                           │
│ Module: Timeline Analysis                                           │
│ Run ID: TL-2025-06-08-001                                          │
│ Run Parameters:                                                     │
│   • Date range: 2025-06-01 to 2025-06-07                           │
│   • Sources: AUTH, VPN, FW, DB, APP, EPP, FILE                     │
│   • Filters: None                                                   │
│ Data Points: 245 events                                             │
│ Data Hash: sha256:1a2b3c4d5e6f7g8h9i0j...                          │
│ Generated: 2026-03-28T10:00:00Z                                    │
│ Page(s): 3, 5, 12                                                   │
│                                                                     │
│ FIGURE 2: SHAP Feature Importance                                   │
│ ─────────────────────────────────                                   │
│ Module: Anomaly Detection                                           │
│ Run ID: AN-2025-06-08-003                                          │
│ Run Parameters:                                                     │
│   • Model: Ensemble (60% IF, 40% LOF)                              │
│   • Contamination: 0.10                                            │
│   • n_estimators: 100                                              │
│ Data Points: 10 features analyzed                                   │
│ Data Hash: sha256:5e6f7g8h9i0j1k2l3m4n...                          │
│ Generated: 2026-03-28T11:30:00Z                                    │
│ Page(s): 12                                                         │
│                                                                     │
│ ... (continues for all figures)                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Deliverables

- [ ] PDF export with full formatting
- [ ] DOCX export with styles
- [ ] HTML export (self-contained)
- [ ] Integrity manifest generation
- [ ] Table of Contents generation
- [ ] Table of Figures generation
- [ ] Evidence Appendix generation
- [ ] Page numbering
- [ ] Figure cross-references
- [ ] Chain of Custody log
- [ ] Digital signatures (optional)
- [ ] Export history tracking

---

# Phase 6: Polish & Ship

## Objective
Ensure the system is production-ready through comprehensive testing, performance optimization, accessibility compliance, and documentation.

## 6.1 Testing

### Unit Tests
```typescript
// Components
describe('EvidenceBlock', () => {
  it('renders SHAP chart with correct data');
  it('displays figure number and caption');
  it('handles missing data gracefully');
  it('updates when data changes');
  it('exports to image correctly');
});

// Agents
describe('WriterAgent', () => {
  it('generates coherent prose');
  it('includes relevant citations');
  it('follows style guide');
  it('handles edge cases');
});
```

### Integration Tests
```typescript
// Full workflow tests
describe('Report Creation Flow', () => {
  it('creates new report from template');
  it('adds evidence from multiple modules');
  it('generates AI content with citations');
  it('exports to PDF with integrity');
  it('maintains version history');
});
```

### E2E Tests (Playwright)
```typescript
// Critical user journeys
test('investigator creates full report', async ({ page }) => {
  await page.goto('/cases/test-case/report-studio');
  
  // Create new report
  await page.click('[data-testid="new-report"]');
  await page.fill('[data-testid="title-input"]', 'Test Report');
  
  // Add evidence
  await page.click('[data-testid="evidence-panel"]');
  await page.dragAndDrop('[data-testid="anomaly-shap"]', '[data-testid="editor"]');
  
  // Generate content
  await page.click('[data-testid="generate-executive-summary"]');
  await page.waitForSelector('[data-testid="generation-complete"]');
  
  // Export
  await page.click('[data-testid="export-pdf"]');
  const download = await page.waitForEvent('download');
  expect(download.suggestedFilename()).toContain('.pdf');
});
```

## 6.2 Performance

### Targets
- **Time to Interactive (TTI):** < 2s
- **First Contentful Paint (FCP):** < 1s
- **Editor input latency:** < 50ms
- **Chart render time:** < 500ms
- **Export generation:** < 10s

### Optimizations
```typescript
// Lazy load heavy components
const NetworkGraph = dynamic(() => import('./NetworkGraph'), {
  loading: () => <GraphSkeleton />,
  ssr: false
});

// Virtualize long lists
import { useVirtualizer } from '@tanstack/react-virtual';

// Memoize expensive calculations
const processedData = useMemo(() => processLargeDataset(data), [data]);

// Debounce real-time operations
const debouncedSave = useDebouncedCallback(saveDocument, 1000);
```

## 6.3 Accessibility (WCAG 2.1 AA)

### Checklist
- [ ] Keyboard navigation for all interactive elements
- [ ] Screen reader announcements for dynamic content
- [ ] Color contrast ratios ≥ 4.5:1
- [ ] Focus indicators visible
- [ ] Alt text for all images/charts
- [ ] ARIA labels for complex widgets
- [ ] Reduced motion support
- [ ] Resize up to 200% without loss

### Testing
```bash
# Automated accessibility testing
npm install -D @axe-core/playwright

# In tests
const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
expect(accessibilityScanResults.violations).toEqual([]);
```

## 6.4 Documentation

### User Documentation
- Getting Started Guide
- Feature Walkthrough Videos
- Keyboard Shortcuts Reference
- FAQ

### Developer Documentation
- Architecture Overview
- Component API Reference
- Agent System Design
- Export Format Specifications
- Contributing Guide

### API Documentation
- OpenAPI/Swagger for all endpoints
- Example requests/responses
- Authentication guide

## Deliverables

- [ ] 80%+ test coverage
- [ ] Performance benchmarks met
- [ ] WCAG 2.1 AA compliance
- [ ] User documentation
- [ ] Developer documentation
- [ ] API documentation
- [ ] Changelog
- [ ] Release notes

---

# Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| **Phase 1:** Foundation | 2 weeks | TypeScript, Tailwind, shadcn/ui, design system |
| **Phase 2:** Dynamic Components | 2 weeks | Evidence blocks, SHAP charts, figure registry |
| **Phase 3:** Intelligence Layer | 2 weeks | AI agents, smart suggestions, fact checking |
| **Phase 4:** Premium Experience | 1 week | Animations, micro-interactions, polish |
| **Phase 5:** Court-Ready Export | 1 week | PDF/DOCX, integrity manifest, audit trail |
| **Phase 6:** Polish & Ship | 2 weeks | Testing, performance, accessibility, docs |

**Total: 10 weeks**

---

# Success Metrics

## Investigator Satisfaction
- [ ] Report creation time reduced by 50%
- [ ] Zero manual screenshot/paste operations needed
- [ ] All evidence traceable to source with one click
- [ ] AI-generated content requires < 20% manual editing

## Enterprise Ready
- [ ] Passes security audit
- [ ] Meets compliance requirements (SOC 2, GDPR)
- [ ] Scales to 100+ concurrent users
- [ ] 99.9% uptime

## Court Admissibility
- [ ] Complete chain of custody for all evidence
- [ ] Tamper-evident exports with hash verification
- [ ] Full audit trail of all modifications
- [ ] Professional formatting meets legal standards

## Judge Approval (The Ultimate Test)
> "Your Honor, this report was generated using NFLIP's Report Studio. Every piece of evidence is cryptographically linked to its source data, with a complete audit trail of who accessed what and when. The integrity manifest on page 2 contains the SHA-256 hashes that can be independently verified."

---

*Ready to begin Phase 1. Awaiting your go-ahead.*
