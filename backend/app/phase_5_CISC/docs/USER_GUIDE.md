# NFLIP Forensic Investigation Platform - User Guide

## Complete Documentation for Automated Report Generation

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Report Studio V4](#report-studio-v4)
4. [AI Investigation](#ai-investigation)
5. [Understanding the 7-Phase Pipeline](#understanding-the-7-phase-pipeline)
6. [Working with Modules](#working-with-modules)
7. [Evidence Vault & Entity Aliasing](#evidence-vault--entity-aliasing)
8. [Charts & Visualizations](#charts--visualizations)
9. [Export & Preview](#export--preview)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The NFLIP (Network Forensic Log Investigation Platform) is an AI-powered forensic investigation system that automates the process of analyzing security incidents and generating comprehensive investigation reports.

### Key Features

- **Multi-Agent Architecture**: Specialized AI agents for hypothesis generation, evidence collection, confidence scoring, and report synthesis
- **Real-Time Streaming**: Watch your report build in real-time as the AI analyzes evidence
- **7-Phase Investigation Pipeline**: Structured approach from intake to final report
- **Universal Module Tools**: 7 forensic analysis modules (Timeline, Anomaly, Correlation, Network, CRUD, Depth, Vault)
- **Entity Aliasing**: Automatic friendly names for technical identifiers
- **Chain of Custody**: Cryptographic hashing and audit trails for legal defensibility

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Report Studio V4 (Frontend)                  │
├─────────────────────────────────────────────────────────────────┤
│  TopBar [AI Investigate] → InvestigationConfigDialog            │
│  Canvas (Real-time element streaming)                           │
│  Preview Panel → Export (PDF/DOCX/HTML)                         │
└─────────────────────────────────────────────────────────────────┘
                              │ SSE Stream
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Unified Investigation Orchestrator             │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: INTAKE      → Parse scenario, extract entities        │
│  Phase 2: HYPOTHESIS  → Generate hypotheses (ACH framework)     │
│  Phase 3: PLANNING    → Create investigation plan               │
│  Phase 4: EXECUTION   → Run all 7 Universal Tools               │
│  Phase 5: TESTING     → Test hypotheses with Bayesian scoring   │
│  Phase 6: CONFIDENCE  → Compute 6-factor confidence (ODNI)      │
│  Phase 7: REPORTING   → Generate canvas layout, stream to UI    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Core AI Agents                               │
├─────────────────────────────────────────────────────────────────┤
│  HypothesisAnalysisAgent  │  EvidenceCollectionAgent            │
│  ConfidenceScoringAgent   │  SummarySynthesisAgent              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.10+ with FastAPI backend
- Node.js 18+ with Next.js frontend
- DuckDB for evidence storage
- Ollama or Google Gemini API for LLM

### Starting the System

1. **Start the Backend**
   ```bash
   cd operation-room/backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start the Frontend**
   ```bash
   cd operation-room/frontend
   npm install
   npm run dev
   ```

3. **Access the Application**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/docs

### Creating Your First Case

1. Navigate to the Cases dashboard
2. Click "New Case"
3. Enter case details (ID, title, description)
4. Upload evidence files (logs, network captures, etc.)
5. Open Report Studio V4

---

## Report Studio V4

The Report Studio is your canvas for building forensic reports with drag-and-drop components.

### Interface Layout

```
┌────────────────────────────────────────────────────────────────────┐
│ TopBar: [← Back] [Title] [Story|Evidence|Review|Redact] [AI] [Export] │
├─────┬──────────────────────────────────────────────────────────────┤
│     │                                                              │
│ I   │                                                              │
│ C   │                    Document Canvas                           │
│ O   │                    (Drag & Drop)                             │
│ N   │                                                              │
│     │                                                              │
│ R   │                                                              │
│ A   │                                                              │
│ I   │                                                              │
│ L   │                                                              │
│     │                                                              │
├─────┴──────────────────────────────────────────────────────────────┤
│ Footer: [Page Navigator] [Zoom Controls]                          │
└────────────────────────────────────────────────────────────────────┘
```

### Icon Rail Panels

| Icon | Panel | Description |
|------|-------|-------------|
| 📋 | Templates | Pre-built report templates |
| ⏱️ | Timeline | Event timeline analysis |
| 📊 | Anomaly | Statistical anomaly detection |
| 🔗 | Correlation | Entity relationship mapping |
| 🌐 | Network | Network flow analysis |
| 💾 | CRUD | Data access patterns |
| 🎯 | Depth | Blast radius assessment |
| 🔒 | Vault | Evidence repository |
| 📤 | Uploads | Attach files |
| 📝 | Text | Text blocks & headings |
| 🔷 | Elements | Shapes & annotations |

### Focus Modes

| Mode | Purpose | Export Behavior |
|------|---------|-----------------|
| **Story** | Executive summary | Only high-confidence findings (≥80%) |
| **Evidence** | Internal only | BLOCKED - contains sensitive data |
| **Review** | Analyst review | All findings with confidence tiers |
| **Redact** | Legal/external | IPs, MACs replaced with [REDACTED] |

### Adding Content to Canvas

**Drag & Drop Method:**
1. Click a panel icon in the rail
2. Drag a component onto the canvas
3. Position and resize as needed

**AI Investigation Method:**
1. Click "AI Investigate" button
2. Configure investigation parameters
3. Watch content stream in automatically

---

## AI Investigation

The AI Investigation feature automates the entire report generation process.

### Starting an Investigation

1. **Click "AI Investigate"** in the TopBar (purple sparkles button)

2. **Configure Investigation:**

   | Field | Description |
   |-------|-------------|
   | Scenario | Describe the incident (e.g., "Suspected ransomware attack on server farm") |
   | LLM Provider | Choose Ollama (local) or Gemini (cloud) |
   | Traversal Strategy | BFS (breadth-first), DFS (depth-first), or BFS→DFS hybrid |
   | Auto-Answer Timeout | Seconds to wait before auto-proceeding |
   | Modules | Select which tools to run |

3. **Click "Start Investigation"**

### Real-Time Progress

During investigation, you'll see:
- Progress percentage in TopBar
- Current phase indicator
- Elements appearing on canvas as they're generated

### Stopping an Investigation

Click the stop button (⏹️) next to the progress indicator to halt the investigation.

---

## Understanding the 7-Phase Pipeline

### Phase 1: INTAKE

**Purpose:** Parse the scenario and extract entities

**What happens:**
- Scenario text is analyzed
- Key entities extracted (IPs, usernames, hostnames, file paths)
- Entities aliased to friendly names
- Initial context established

**Output:** Entity map, investigation context

### Phase 2: HYPOTHESIS

**Purpose:** Generate testable hypotheses using ACH framework

**What happens:**
- AI generates 3-5 competing hypotheses
- Each hypothesis assigned prior probability (0.5 default)
- Null hypothesis (H0: Nothing happened) included

**Example hypotheses:**
```
H1: Ransomware attack via phishing email (Prior: 0.50)
H2: Insider threat with privileged access (Prior: 0.50)
H3: External APT lateral movement (Prior: 0.50)
H0: Normal operational activity (Prior: 0.50)
```

### Phase 3: PLANNING

**Purpose:** Create detailed investigation plan

**What happens:**
- Investigation phases defined
- Steps assigned to each phase
- Module dependencies mapped

**Output:** Structured plan with phases/steps

### Phase 4: EXECUTION

**Purpose:** Run all forensic analysis modules

**Modules executed:**

| Module | Capability | Findings |
|--------|------------|----------|
| Timeline | Event reconstruction | Chronological events |
| Anomaly | Statistical analysis | Outliers, unusual patterns |
| Correlation | Entity mapping | Relationships, connections |
| Network | Flow analysis | Traffic patterns, connections |
| CRUD | Access patterns | Data access anomalies |
| Depth | Impact assessment | Blast radius, affected systems |
| Vault | Evidence query | Supporting evidence |

**Output:** Findings streamed to canvas in real-time

### Phase 5: TESTING

**Purpose:** Test hypotheses against evidence

**What happens:**
- Each finding evaluated against each hypothesis
- Bayesian posterior probability calculated
- Verdicts assigned:
  - ✅ CONFIRMED (>0.75)
  - ❌ REJECTED (<0.25)
  - ⚪ INCONCLUSIVE (0.25-0.75)

### Phase 6: CONFIDENCE

**Purpose:** Compute overall investigation confidence

**6-Factor ODNI ICD 203 Formula:**
```
CONFIDENCE = Σ(Wi × Fi) / Σ(Wi)

Where:
- Evidence Coverage (0.25 weight)
- Module Agreement (0.20 weight)
- Temporal Consistency (0.15 weight)
- Cross Validation (0.20 weight)
- Pattern Match (0.10 weight)
- Research Alignment (0.10 weight)
```

**Confidence Levels:**

| Score | Level | Meaning |
|-------|-------|---------|
| 0.85+ | HIGH | Strong evidence, high certainty |
| 0.65-0.84 | MODERATE | Good evidence, some gaps |
| 0.45-0.64 | LOW | Limited evidence, uncertainty |
| <0.45 | VERY LOW | Insufficient evidence |

### Phase 7: REPORTING

**Purpose:** Generate final report layout

**What happens:**
- Sections organized by importance
- Charts and visualizations generated
- Summary narrative synthesized
- Canvas layout finalized

---

## Working with Modules

### Timeline Module

**Capabilities:**
- `build_timeline` - Construct event timeline from logs
- `find_clusters` - Identify event clusters
- `detect_gaps` - Find suspicious time gaps
- `correlate_events` - Link related events
- `generate_heatmap` - Create activity heatmap
- `swimlane` - Multi-entity timeline view

**Canvas Components:**
- Timeline Heatmap
- Swimlane Chart
- Event List
- Gap Analysis

### Anomaly Module

**Capabilities:**
- `detect_anomalies` - Statistical outlier detection
- `score_events` - Calculate anomaly scores
- `explain_shap` - SHAP feature importance
- `baseline_compare` - Compare to baseline
- `trend_analysis` - Identify trends

**Canvas Components:**
- Anomaly Scatter Plot
- SHAP Waterfall
- Score Distribution
- Trend Chart

### Correlation Module

**Capabilities:**
- `find_correlations` - Entity relationships
- `build_graph` - Network graph
- `identify_pivots` - Key connecting entities
- `cluster_entities` - Group related entities
- `timeline_overlay` - Temporal relationships

**Canvas Components:**
- Entity Graph
- Correlation Matrix
- Pivot Analysis
- Cluster Visualization

### Network Module

**Capabilities:**
- `analyze_flows` - Network traffic analysis
- `detect_beaconing` - C2 communication patterns
- `geolocation` - IP geolocation
- `protocol_analysis` - Protocol breakdown
- `bandwidth_analysis` - Data transfer patterns

**Canvas Components:**
- Network Flow Diagram
- Geo Map
- Protocol Pie Chart
- Traffic Timeline

### CRUD Module

**Capabilities:**
- `analyze_operations` - Create/Read/Update/Delete patterns
- `detect_bulk_ops` - Mass operations detection
- `privilege_analysis` - Access privilege review
- `schema_changes` - Database modifications
- `temporal_patterns` - Access time patterns

**Canvas Components:**
- CRUD Operations Chart
- Access Heatmap
- Privilege Matrix
- Bulk Operation Timeline

### Depth Module

**Capabilities:**
- `blast_radius` - Impact assessment
- `dependency_map` - System dependencies
- `criticality_score` - Asset criticality
- `propagation_path` - Attack path analysis
- `recovery_estimate` - Recovery time estimate

**Canvas Components:**
- Blast Radius Diagram
- Dependency Graph
- Criticality Heatmap
- Attack Path Visualization

### Vault Module

**Capabilities:**
- `query_evidence` - Search evidence vault
- `verify_hash` - Cryptographic verification
- `chain_of_custody` - Audit trail
- `export_artifact` - Evidence export
- `link_evidence` - Cross-reference evidence

---

## Evidence Vault & Entity Aliasing

### Evidence Vault

The Evidence Vault stores all forensic artifacts with cryptographic integrity.

**Vault Structure:**
```
cases/{case_id}/
├── vault.duckdb          # DuckDB database
├── uploads/              # Raw evidence files
├── exports/              # Generated reports
└── audit_log.jsonl       # Chain of custody log
```

**Adding Evidence:**
1. Open Vault panel from Icon Rail
2. Click "Upload Evidence"
3. Select files (logs, captures, images)
4. Evidence is hashed (SHA-256) and stored

**Querying Evidence:**
```sql
SELECT * FROM evidence 
WHERE timestamp BETWEEN '2024-01-01' AND '2024-01-02'
AND source_ip = '192.168.1.100'
```

### Entity Aliasing

Entity Aliasing creates human-readable names for technical identifiers.

**How it works:**

| Original | Alias | Type |
|----------|-------|------|
| 192.168.1.100 | host_internal_01 | IP Address |
| 52.94.76.1 | aws_us_east_01 | External IP |
| john.smith@corp.com | user_jsmith | Email |
| AB:CD:EF:12:34:56 | device_printer_01 | MAC Address |

**Aliasing Rules:**
1. Internal IPs → `host_internal_{N}`
2. External IPs → Geographic/provider prefix
3. Usernames → `user_{first_initial}{last}`
4. MAC addresses → `device_{type}_{N}`

**In Reports:**
- Hover over aliased name to see original value
- Original values restored in final PDF export

---

## Charts & Visualizations

### Augment Studio

The Augment Studio generates charts dynamically based on data.

**Chart Types:**

| Type | Use Case | Data Format |
|------|----------|-------------|
| Pie | Categorical distribution | `[{label, value}]` |
| Bar | Comparisons | `[{category, value}]` |
| Line | Trends over time | `[{x, y}]` |
| Radar | Multi-dimensional comparison | `[{axis, value}]` |

**Auto-Generate:**
The system automatically selects the best chart type based on data characteristics.

### Chart Inspector

1. Click any chart on the canvas
2. Use the Chart Inspector panel to:
   - Change chart type
   - Modify colors
   - Toggle labels
   - Filter data
   - Export as image

### Custom Configurations

Each chart supports filters:
```javascript
{
  topN: 10,           // Limit to top N items
  minValue: 100,      // Filter by minimum value
  excludeInfo: true,  // Exclude INFO severity
  sortOrder: 'desc',  // Sort direction
}
```

---

## Export & Preview

### Preview Panel

Before exporting, review your report:

1. Click "Export" in TopBar
2. Preview panel opens with:
   - Page thumbnails (left sidebar)
   - Full-size page view (center)
   - Validation checklist (right sidebar)

**Validation Checks:**
- ✅ Has content
- ✅ Focus mode set
- ⚠️ Empty pages warning
- ⚠️ Unverified elements warning

### Export Formats

| Format | Best For | Features |
|--------|----------|----------|
| **PDF** | Legal/Formal | Full fidelity, signatures |
| **DOCX** | Editing | Editable in Word |
| **HTML** | Sharing | Browser viewable |

### Export Modes

| Mode | Description |
|------|-------------|
| **Standard** | Direct export with current settings |
| **Dynamite** | Full formal report with cover page |

### Export Process

1. **Preview** → Review all pages
2. **Validate** → Check for issues
3. **Configure** → Select format and options
4. **Export** → Generate file
5. **Download** → Save to local machine

### Chain of Custody

Every export is logged:
```json
{
  "event": "EXPORT_PDF",
  "timestamp": "2024-01-15T10:30:00Z",
  "actor": "analyst@corp.com",
  "document_id": "doc-123",
  "content_hash": "sha256:abc123...",
  "focus_mode": "Story"
}
```

---

## API Reference

### Investigation API

**Start Investigation:**
```http
POST /api/investigation/start
Content-Type: application/json

{
  "case_id": "CASE-001",
  "scenario": "Suspected ransomware attack...",
  "objectives": ["Identify entry point", "Determine scope"],
  "modules_to_run": ["timeline", "anomaly", "network"],
  "initial_hypotheses": ["Phishing email", "Insider threat"]
}
```

**Response:** Server-Sent Events (SSE) stream

### Augment Studio API

**Generate Chart:**
```http
POST /api/augment/generate
Content-Type: application/json

{
  "case_id": "CASE-001",
  "chart_type": "pie",
  "title": "Event Distribution",
  "data": [
    {"label": "Login", "value": 150},
    {"label": "Logout", "value": 120}
  ]
}
```

**Auto-Generate:**
```http
POST /api/augment/auto
Content-Type: application/json

{
  "case_id": "CASE-001",
  "data": [...],
  "context": "Show severity distribution"
}
```

### Universal Tools API

**Execute Tool:**
```http
POST /api/tools/{tool_id}/execute
Content-Type: application/json

{
  "case_id": "CASE-001",
  "capability": "build_timeline",
  "parameters": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z"
  }
}
```

### Entity Alias API

**Create Alias:**
```http
POST /api/aliases
Content-Type: application/json

{
  "case_id": "CASE-001",
  "original": "192.168.1.100",
  "alias": "server_db_primary",
  "entity_type": "ip_address"
}
```

**Resolve Alias:**
```http
GET /api/aliases/resolve?case_id=CASE-001&alias=server_db_primary
```

### Export API

**Export PDF:**
```http
POST /api/v4/studio/cases/{case_id}/exports/pdf
Content-Type: application/json

{
  "doc_id": "doc-123",
  "actor": "analyst@corp.com",
  "focus_mode": "Story"
}
```

---

## Troubleshooting

### Common Issues

**Issue: "Timeline service not available"**
- This is informational - mock data is used when DuckDB timeline table is empty
- Solution: Import log data into the case

**Issue: Investigation stuck at 0%**
- Check LLM provider configuration
- For Ollama: Ensure `ollama serve` is running
- For Gemini: Verify API key in environment

**Issue: Canvas elements not appearing**
- Check browser console for errors
- Verify SSE connection is established
- Try refreshing the page

**Issue: Export fails**
- Check that all pages have content
- Ensure focus mode is not "Evidence"
- Verify backend is running

### Debug Mode

Enable debug logging:
```bash
# Backend
export LOG_LEVEL=DEBUG
uvicorn app.main:app --reload

# Frontend
NEXT_PUBLIC_DEBUG=true npm run dev
```

### Getting Help

- Check API documentation: http://localhost:8000/docs
- Review audit logs: `cases/{case_id}/audit_log.jsonl`
- Backend logs: Terminal running uvicorn

---

## Appendix

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save document |
| `Ctrl+E` | Export document |
| `Ctrl+\` | Toggle AI panel |
| `Ctrl+1-6` | Switch panels (Timeline, Anomaly, etc.) |
| `←/→` | Navigate pages (in preview) |
| `Esc` | Close dialogs |

### Confidence Score Formula

```
CONFIDENCE = Σ(Wi × Fi) / Σ(Wi)

Factors:
- F1: Evidence Coverage (W=0.25) - % of hypotheses with evidence
- F2: Module Agreement (W=0.20) - Cross-module consistency
- F3: Temporal Consistency (W=0.15) - Timeline coherence
- F4: Cross Validation (W=0.20) - Multiple evidence sources
- F5: Pattern Match (W=0.10) - Known attack pattern match
- F6: Research Alignment (W=0.10) - MITRE ATT&CK alignment
```

### Supported Log Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| JSON Lines | .jsonl | Native |
| CSV | .csv | Pandas |
| Syslog | .log | Regex |
| Windows Event | .evtx | evtx library |
| PCAP | .pcap | PyShark |

### MITRE ATT&CK Integration

The system maps findings to MITRE ATT&CK techniques:
- Tactics: TA0001-TA0043
- Techniques: T1001-T1600+
- Sub-techniques: .001-.999

---

*Document Version: 1.0*  
*Last Updated: April 2026*  
*Platform Version: 0.2.0*
