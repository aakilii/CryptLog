# Intelligent Report Generation System - Comprehensive Architecture Plan

## Executive Summary

This document outlines a comprehensive architecture for an **AI-Driven Forensic Report Generation System** that learns from previous reports, adapts dynamically to investigator workflows, and maintains forensic integrity throughout the process.

---

## 1. SCENARIO ANALYSIS

### Current Case: Confidential File Exfiltration Investigation

**Scenario Context:**
- **Devices**: Windows computer (organization-owned) + Android mobile phone (suspect-owned)
- **Allegation**: Unauthorized transfer of confidential files via USB, Bluetooth, and Email
- **Objective**: Create timeline of file transfers with IP addresses for web interface

**Required Log Types:**
1. **Windows Event Logs** - Security, System, Application
2. **USB Device Connection Logs** - Registry, SetupAPI
3. **Bluetooth Pairing/Transfer Logs** - Windows Bluetooth logs
4. **Email Logs** - Outlook PST, SMTP/IMAP headers
5. **Network Logs** - Firewall, Proxy, NetFlow
6. **Android ADB Logs** - Logcat, file system events
7. **File System Artifacts** - NTFS MFT, Android media scanner

---

## 2. REPORT LEARNING ARCHITECTURE

### 2.1 How to Feed Previous Reports for Learning

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REPORT LEARNING PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │  Upload Report  │───▶│  Parse & Extract│───▶│ Store in Vector │        │
│  │  (PDF/DOCX/MD)  │    │    Structure    │    │     Store       │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│          │                      │                      │                   │
│          ▼                      ▼                      ▼                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │ Extract Metadata│    │ Identify Sections│    │ Embed Patterns │        │
│  │ - Page count    │    │ - Headings       │    │ - Structure    │        │
│  │ - Word count    │    │ - Subheadings    │    │ - Flow         │        │
│  │ - Chart types   │    │ - Chart positions│    │ - Style        │        │
│  │ - Layout        │    │ - Content types  │    │ - Terminology  │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                             │
│                    ▼ LEARNING STORAGE ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ChromaDB Collections                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│   │
│  │  │report_structs│ │section_styles│ │chart_patterns│ │terminology  ││   │
│  │  │- Hierarchy   │ │- Writing tone│ │- When to use │ │- Domain     ││   │
│  │  │- Flow        │ │- Length      │ │- Positioning │ │- Forensic   ││   │
│  │  │- Dependencies│ │- Evidence ref│ │- Data types  │ │- Legal      ││   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 API Endpoints for Report Learning

```python
# New endpoints to add:
POST /api/learning/upload-report      # Upload PDF/DOCX for learning
POST /api/learning/extract-structure  # Extract and store structure patterns
GET  /api/learning/similar-reports    # Find similar past reports
GET  /api/learning/recommended-structure  # Get structure recommendation
POST /api/learning/feedback           # Submit quality feedback on generated reports
```

### 2.3 Report Template Learning Schema

```sql
CREATE TABLE report_templates_learned (
    template_id VARCHAR PRIMARY KEY,
    case_type VARCHAR,              -- 'data_exfiltration', 'ransomware', 'fraud'
    source_report_id VARCHAR,       -- Original report this was learned from
    structure_json TEXT,            -- Learned structure
    avg_page_count INTEGER,
    avg_sections INTEGER,
    chart_patterns TEXT,            -- JSON of chart type -> frequency
    success_rating FLOAT,           -- User feedback 1-5
    times_used INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE section_patterns (
    pattern_id VARCHAR PRIMARY KEY,
    section_type VARCHAR,           -- 'executive_summary', 'timeline', 'findings'
    typical_position INTEGER,       -- Order in report
    typical_length_words INTEGER,
    chart_types TEXT,               -- JSON array of typical charts
    evidence_density FLOAT,         -- Evidence references per 100 words
    example_content TEXT,           -- Anonymized example
    embedding BLOB                  -- Vector embedding for similarity
);
```

---

## 3. COMPLETE REPORT GENERATION WORKFLOW

### 3.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 INTELLIGENT REPORT GENERATION PHASES                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1: LOG IMPORT & METADATA EXTRACTION                                  │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Import logs (Windows Events, USB, Bluetooth, Email, Network)     │    │
│  │ • Extract metadata: time ranges, users, devices, file types        │    │
│  │ • Build unified timeline with all events                           │    │
│  │ • Generate log summary dashboard                                   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 2: SCENARIO ANALYSIS & CLARIFICATION                                 │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Parse investigator's scenario description                        │    │
│  │ • Identify entities: suspect, victim, devices, files               │    │
│  │ • Detect missing information → Ask clarification questions         │    │
│  │ • Determine timeline scope (full logs vs. specified range)         │    │
│  │ • Extract investigation objectives and success criteria            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 3: STRUCTURE RECOMMENDATION (LEARNING-BASED)                         │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Query long-term memory for similar case reports                  │    │
│  │ • Retrieve learned structure patterns from vector store            │    │
│  │ • Generate recommended heading/subheading hierarchy                │    │
│  │ • Estimate page count based on evidence volume                     │    │
│  │ • Present template to investigator for approval/modification       │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 4: INVESTIGATOR PLAN REVIEW                                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Display proposed structure with section descriptions             │    │
│  │ • Allow add/remove/reorder sections                                │    │
│  │ • Validate structure against forensic best practices               │    │
│  │ • Lock plan after confirmation (versioned snapshot)                │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 5: SECTION-BY-SECTION GENERATION                                     │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ For each section in plan:                                          │    │
│  │   1. Generate hypotheses relevant to section                       │    │
│  │   2. Query modules for findings (anomaly, timeline, network, etc.) │    │
│  │   3. Store findings in Evidence Vault with KEY-VALUE pairs         │    │
│  │   4. Generate AI summary using KEYS only (redaction support)       │    │
│  │   5. Create charts/visualizations from findings                    │    │
│  │   6. Position elements with learned spacing/coordinates            │    │
│  │   7. Verify alignment against learned patterns                     │    │
│  │   8. [Human Mode] Request approval | [Autopilot] Self-verify       │    │
│  │   9. Store section in canvas with audit trail                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 6: VERIFICATION & QUALITY ASSURANCE                                  │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Cross-reference all evidence keys used                           │    │
│  │ • Verify chart data matches underlying findings                    │    │
│  │ • Check coordinate consistency (no overlaps)                       │    │
│  │ • Validate against learned patterns from similar reports           │    │
│  │ • Generate integrity hashes for audit trail                        │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  PHASE 7: EXPORT & LEARNING FEEDBACK                                        │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ • Export to PDF with cryptographic signing                         │    │
│  │ • Store report structure for future learning                       │    │
│  │ • Collect investigator feedback (quality rating)                   │    │
│  │ • Update learning weights based on feedback                        │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. DETAILED IMPLEMENTATION SPECIFICATIONS

### 4.1 Phase 1: Log Import & Metadata Extraction

**Input:** Raw log files (EVTX, JSON, CSV, PST, PCAP)

**Process:**
```python
class LogMetadataExtractor:
    def extract(self, log_path: str) -> LogMetadata:
        return LogMetadata(
            log_type="windows_security",
            file_name="Security.evtx",
            start_time="2026-03-01T08:00:00Z",
            end_time="2026-03-15T18:30:00Z",
            total_events=125847,
            users_involved=["john.doe", "admin", "SYSTEM"],
            devices=["WORKSTATION-01", "DC-01"],
            ip_addresses=["192.168.1.100", "10.0.0.5"],
            event_types_breakdown={
                "4624": 5420,  # Logon
                "4663": 8934,  # File access
                "4688": 12340, # Process creation
            },
            unique_files_accessed=847,
            suspicious_indicators=["After-hours access", "Bulk file copy"],
        )
```

**Output:** Unified timeline + metadata dashboard

### 4.2 Phase 2: Scenario Analysis

**Scenario Parsing NLP:**
```python
class ScenarioAnalyzer:
    def analyze(self, scenario_text: str) -> ScenarioContext:
        # Use LLM to extract structured information
        return ScenarioContext(
            case_type="data_exfiltration",
            suspect_entities=["john.doe"],
            victim_organization="TechCorp",
            devices=[
                Device(type="windows", owner="organization", identifier="WORKSTATION-01"),
                Device(type="android", owner="suspect", identifier="Galaxy-S23"),
            ],
            transfer_channels=["USB", "Bluetooth", "Email"],
            files_of_interest="confidential files",
            timeline_specified=False,  # User didn't specify, ask or use full range
            objectives=[
                "Create file transfer timeline",
                "Identify IP addresses involved",
                "Establish chain of custody"
            ]
        )
```

**Clarification Questions Engine:**
```python
clarification_questions = [
    {
        "id": "timeline_scope",
        "condition": "timeline_specified == False",
        "question": "The scenario doesn't specify a time range. Should I analyze the entire log timeline (2026-03-01 to 2026-03-15) or a specific period?",
        "options": ["Full timeline", "Specify date range"]
    },
    {
        "id": "file_types",
        "condition": "'confidential files' in scenario",
        "question": "What types of files are considered confidential? (e.g., .docx, .xlsx, .pdf, .dwg)",
        "options": ["All documents", "Specify extensions", "Any file > 1MB"]
    },
    {
        "id": "known_entities",
        "question": "Are there specific usernames or IP addresses we should focus on?",
        "options": ["Use auto-detected", "Specify manually"]
    }
]
```

### 4.3 Phase 3: Structure Recommendation (Learning-Based)

**Query Similar Reports:**
```python
class ReportStructureLearner:
    def recommend_structure(self, case_type: str, evidence_volume: dict) -> ReportStructure:
        # 1. Query vector store for similar reports
        similar = self.vector_store.query(
            collection="report_structures",
            query=f"forensic report {case_type} data exfiltration USB Bluetooth email",
            n_results=5
        )
        
        # 2. Aggregate common patterns
        common_sections = self.find_common_sections(similar)
        
        # 3. Adjust based on evidence volume
        estimated_pages = self.estimate_pages(evidence_volume, common_sections)
        
        return ReportStructure(
            title="Digital Forensics Investigation Report - Confidential Data Exfiltration",
            estimated_pages=estimated_pages,
            sections=[
                Section(
                    heading="1. Executive Summary",
                    subheadings=[],
                    estimated_pages=2,
                    charts=[],
                    description="High-level findings and conclusions"
                ),
                Section(
                    heading="2. Case Background",
                    subheadings=[
                        "2.1 Investigation Scope",
                        "2.2 Seized Devices",
                        "2.3 Investigation Objectives"
                    ],
                    estimated_pages=3,
                    charts=["devices_table"],
                    description="Context and scope of investigation"
                ),
                # ... more sections
            ]
        )
```

### 4.4 Phase 4: Plan Approval Workflow

**Structure Validation:**
```python
class StructureValidator:
    def validate(self, structure: ReportStructure) -> ValidationResult:
        issues = []
        warnings = []
        
        # Check required sections
        required = ["Executive Summary", "Methodology", "Findings", "Conclusion"]
        for req in required:
            if not any(req.lower() in s.heading.lower() for s in structure.sections):
                issues.append(f"Missing required section: {req}")
        
        # Check logical flow
        if not self.is_chronological(structure):
            warnings.append("Consider chronological ordering for timeline-heavy reports")
        
        # Check chart distribution
        chart_count = sum(len(s.charts) for s in structure.sections)
        if chart_count < 3:
            warnings.append("Consider adding more visualizations for clarity")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            suggestions=self.generate_suggestions(structure)
        )
```

### 4.5 Phase 5: Section-by-Section Generation

**Core Generation Loop:**
```python
async def generate_section(
    section: Section,
    case_id: str,
    mode: str  # "human" or "autopilot"
) -> GeneratedSection:
    
    # Step 1: Generate hypotheses for this section
    hypotheses = await hypothesis_generator.generate_for_section(
        section_type=section.heading,
        case_context=get_case_context(case_id)
    )
    
    # Step 2: Query relevant modules for findings
    findings = await gather_findings(section, case_id)
    # - anomaly_agent: suspicious patterns
    # - timeline_service: chronological events
    # - network_agent: IP addresses, connections
    # - correlation_agent: entity relationships
    
    # Step 3: Store in Evidence Vault with KEY-VALUE
    evidence_refs = []
    for finding in findings:
        key = await evidence_vault.store(
            case_id=case_id,
            value=finding.raw_data,
            metadata={
                "section": section.heading,
                "finding_type": finding.type,
                "timestamp": finding.timestamp
            }
        )
        evidence_refs.append(EvidenceRef(key=key, label=finding.summary))
    
    # Step 4: Generate AI summary using KEYS only (redaction-safe)
    summary_prompt = build_summary_prompt(
        section=section,
        evidence_keys=[ref.key for ref in evidence_refs],
        style_guide=get_learned_style(section.heading)
    )
    summary = await llm.generate(summary_prompt)
    
    # Step 5: Create charts from findings
    charts = []
    for chart_spec in section.charts:
        chart = await chart_renderer.create(
            chart_type=chart_spec.type,
            data=extract_chart_data(findings, chart_spec),
            style=get_learned_chart_style(chart_spec.type)
        )
        charts.append(chart)
    
    # Step 6: Position elements with learned coordinates
    layout = await position_elements(
        text_blocks=[summary],
        charts=charts,
        learned_patterns=get_layout_patterns(section.heading)
    )
    
    # Step 7: Verify alignment
    alignment_ok, issues = verify_alignment(layout)
    
    # Step 8: Approval
    if mode == "human":
        approval = await request_human_approval(section, layout)
        if not approval.approved:
            return await regenerate_with_feedback(section, approval.feedback)
    else:  # autopilot
        if not alignment_ok:
            layout = await auto_fix_alignment(layout, issues)
    
    # Step 9: Store in canvas
    await canvas.add_section(
        section_id=section.id,
        layout=layout,
        evidence_refs=evidence_refs,
        audit_entry={
            "action": "section_generated",
            "timestamp": now(),
            "mode": mode,
            "verification": "passed" if alignment_ok else "auto_fixed"
        }
    )
    
    return GeneratedSection(
        section=section,
        layout=layout,
        evidence_refs=evidence_refs,
        page_range=(layout.start_page, layout.end_page)
    )
```

### 4.6 Evidence Vault Key-Value System

**Key Benefits:**
1. **Redaction Mode**: AI sees only keys, reviewers see values
2. **Audit Trail**: Every evidence reference is tracked
3. **Story Mode**: Replace keys with narrative-friendly values
4. **Legal Compliance**: Sensitive data accessed only when needed

```python
class EvidenceVaultService:
    def store(self, case_id: str, value: Any, metadata: dict) -> str:
        """Store evidence and return a unique key."""
        key = f"EVD-{uuid.uuid4().hex[:8].upper()}"
        
        # Store in vault with full chain of custody
        vault = open_vault(case_id)
        vault.execute("""
            INSERT INTO evidence_vault (
                evidence_key, evidence_value, metadata_json,
                created_at, access_mode, hash_value
            ) VALUES (?, ?, ?, now(), 'restricted', ?)
        """, [key, json.dumps(value), json.dumps(metadata), hash_value(value)])
        
        # Log access for audit
        record_coc_event(case_id, "evidence_stored", key)
        
        return key
    
    def get_value(self, case_id: str, key: str, mode: str = "full") -> Any:
        """Retrieve evidence value with access control."""
        if mode == "redacted":
            return f"[REDACTED: {key}]"
        elif mode == "key_only":
            return key
        else:  # full access
            record_coc_event(case_id, "evidence_accessed", key)
            return self._fetch_value(case_id, key)
```

### 4.7 Chart Generation Decision Engine

**When to Generate Charts:**
```python
class ChartDecisionEngine:
    def decide_charts(self, section: Section, findings: List[Finding]) -> List[ChartSpec]:
        charts = []
        
        # Timeline sections → Timeline/Gantt charts
        if "timeline" in section.heading.lower():
            if len(findings) > 5:
                charts.append(ChartSpec(
                    type="timeline",
                    data_source="unified_timeline",
                    title="Event Timeline"
                ))
        
        # Network/Transfer sections → Sankey/Flow diagrams
        if any(t in section.heading.lower() for t in ["transfer", "network", "connection"]):
            charts.append(ChartSpec(
                type="sankey",
                data_source="network_flows",
                title="Data Transfer Flow"
            ))
        
        # Statistical findings → Bar/Pie charts
        if any(f.type == "statistical" for f in findings):
            charts.append(ChartSpec(
                type="bar",
                data_source="aggregated_stats",
                title="Event Distribution"
            ))
        
        # Anomaly findings → Scatter/Heatmap
        if any(f.type == "anomaly" for f in findings):
            charts.append(ChartSpec(
                type="scatter",
                data_source="anomaly_scores",
                title="Anomaly Detection Results"
            ))
        
        return charts
```

### 4.8 Alignment Verification System

**Coordinate Validation:**
```python
class AlignmentVerifier:
    def verify(self, layout: Layout) -> Tuple[bool, List[AlignmentIssue]]:
        issues = []
        
        # Check for overlaps
        for i, elem1 in enumerate(layout.elements):
            for elem2 in layout.elements[i+1:]:
                if self.overlaps(elem1, elem2):
                    issues.append(AlignmentIssue(
                        type="overlap",
                        elements=[elem1.id, elem2.id],
                        severity="error"
                    ))
        
        # Check margins (learned from previous reports)
        learned_margins = self.get_learned_margins(layout.section_type)
        for elem in layout.elements:
            if elem.x < learned_margins.left:
                issues.append(AlignmentIssue(
                    type="margin_violation",
                    element=elem.id,
                    message=f"Element too close to left margin",
                    severity="warning"
                ))
        
        # Check spacing between elements
        for i, elem in enumerate(layout.elements[:-1]):
            next_elem = layout.elements[i+1]
            spacing = next_elem.y - (elem.y + elem.height)
            if spacing < learned_margins.min_spacing:
                issues.append(AlignmentIssue(
                    type="insufficient_spacing",
                    elements=[elem.id, next_elem.id],
                    severity="warning"
                ))
        
        return len([i for i in issues if i.severity == "error"]) == 0, issues
    
    def auto_fix(self, layout: Layout, issues: List[AlignmentIssue]) -> Layout:
        """Automatically fix alignment issues."""
        fixed = layout.copy()
        
        for issue in issues:
            if issue.type == "overlap":
                fixed = self.resolve_overlap(fixed, issue.elements)
            elif issue.type == "margin_violation":
                fixed = self.adjust_margin(fixed, issue.element)
            elif issue.type == "insufficient_spacing":
                fixed = self.increase_spacing(fixed, issue.elements)
        
        return fixed
```

---

## 5. SAMPLE REPORT STRUCTURE FOR CURRENT SCENARIO

### Recommended Structure (35-45 pages)

```
DIGITAL FORENSICS INVESTIGATION REPORT
Confidential Data Exfiltration - Case #2026-EXFIL-001

1. EXECUTIVE SUMMARY (2-3 pages)
   - Key findings overview
   - Timeline summary (infographic)
   - Recommendations

2. CASE BACKGROUND (3-4 pages)
   2.1 Investigation Scope
   2.2 Seized Devices Description
       [TABLE: Device inventory with specs]
   2.3 Investigation Objectives
   2.4 Legal Authority

3. METHODOLOGY (2-3 pages)
   3.1 Forensic Acquisition Process
   3.2 Analysis Tools Used
   3.3 Chain of Custody Procedures
       [CHART: CoC timeline]

4. LOG ANALYSIS OVERVIEW (4-5 pages)
   4.1 Windows Event Log Summary
       [CHART: Event distribution by type]
   4.2 USB Device Connection History
       [TABLE: USB device timeline]
   4.3 Bluetooth Activity Analysis
       [CHART: Bluetooth pairing events]
   4.4 Email Communication Summary
       [TABLE: Email metadata with attachments]
   4.5 Network Traffic Analysis
       [CHART: IP address connections]

5. FILE TRANSFER TIMELINE (6-8 pages)
   5.1 USB Transfer Events
       [TIMELINE: USB file copies]
       [TABLE: Files transferred via USB]
   5.2 Bluetooth Transfer Events
       [TIMELINE: Bluetooth file transfers]
   5.3 Email Attachment Analysis
       [TABLE: Sent attachments with recipients]
   5.4 Combined Transfer Timeline
       [GANTT: All transfer channels]

6. IP ADDRESS ANALYSIS (3-4 pages)
   6.1 Source IP Addresses
   6.2 Destination IP Addresses
   6.3 Geographic Analysis
       [MAP: IP geolocation]
   6.4 Network Flow Diagram
       [SANKEY: Data flow visualization]

7. ANOMALY DETECTION RESULTS (4-5 pages)
   7.1 Detected Anomalies
       [CHART: Anomaly score distribution]
   7.2 After-Hours Activity
   7.3 Bulk Transfer Patterns
   7.4 SHAP Explainability Analysis
       [CHART: Feature importance]

8. ENTITY CORRELATION (3-4 pages)
   8.1 User Activity Timeline
       [CHART: User actions over time]
   8.2 Device Relationships
       [GRAPH: Entity relationship diagram]
   8.3 File Access Patterns

9. KEY FINDINGS (4-5 pages)
   9.1 Finding 1: USB Transfer Chain
   9.2 Finding 2: Bluetooth Exfiltration
   9.3 Finding 3: Email Leakage
   9.4 Finding 4: IP Address Trail
   [Each finding with evidence references]

10. CONCLUSIONS (2 pages)
    10.1 Summary of Evidence
    10.2 Attribution Confidence
    10.3 Impact Assessment

11. RECOMMENDATIONS (2 pages)
    11.1 Immediate Actions
    11.2 Long-term Security Improvements

APPENDICES (5-8 pages)
    A. Evidence Integrity Hashes
    B. Full Device Specifications
    C. Detailed IP Address List
    D. Glossary of Terms
```

---

## 6. IMPLEMENTATION ROADMAP

### Iteration 1: Report Learning Infrastructure (2-3 days)
- [ ] Create report upload endpoint
- [ ] Implement PDF/DOCX structure parser
- [ ] Add ChromaDB collections for patterns
- [ ] Build structure embedding pipeline

### Iteration 2: Scenario Analysis Engine (2-3 days)
- [ ] Build scenario NLP parser
- [ ] Create clarification question engine
- [ ] Implement timeline scope detection
- [ ] Add entity extraction from scenario

### Iteration 3: Dynamic Structure Generator (2-3 days)
- [ ] Query similar reports from vector store
- [ ] Build section aggregation logic
- [ ] Create page estimation algorithm
- [ ] Implement structure validation

### Iteration 4: Evidence Vault Integration (2-3 days)
- [ ] Implement KEY-VALUE storage
- [ ] Add redaction mode support
- [ ] Build audit trail for access
- [ ] Create story mode value substitution

### Iteration 5: Section Generation Pipeline (3-4 days)
- [ ] Build hypothesis generator per section
- [ ] Integrate all analysis modules
- [ ] Create chart decision engine
- [ ] Implement positioning system

### Iteration 6: Verification & Approval (2-3 days)
- [ ] Build alignment verifier
- [ ] Create auto-fix algorithms
- [ ] Implement human approval UI
- [ ] Add autopilot verification mode

### Iteration 7: Learning Feedback Loop (2 days)
- [ ] Create feedback collection API
- [ ] Build quality rating system
- [ ] Implement learning weight updates
- [ ] Add report structure storage

---

## 7. TECHNICAL ENHANCEMENTS

### 7.1 Suggested Improvements

1. **Multi-Model LLM Strategy**
   - Use fast model (Haiku) for structure suggestions
   - Use quality model (Sonnet) for final summaries
   - Use premium model (Opus) for complex hypothesis generation

2. **Progressive Rendering**
   - Stream section generation to UI
   - Show partial results while processing
   - Enable real-time collaboration

3. **Template Versioning**
   - Git-like versioning for report structures
   - Diff visualization between versions
   - Rollback capability

4. **Cross-Case Learning**
   - Aggregate patterns across organizations
   - Privacy-preserving federated learning
   - Benchmark against industry standards

5. **Quality Metrics Dashboard**
   - Track generation quality over time
   - A/B test different prompt strategies
   - Measure investigator satisfaction

### 7.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INTELLIGENT REPORT GENERATION SYSTEM                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         FRONTEND LAYER                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │ Scenario │ │Structure │ │ Section  │ │ Approval │ │ Export   │ │   │
│  │  │  Input   │ │ Preview  │ │Generation│ │   UI     │ │  Panel   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       ORCHESTRATION LAYER                            │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │              UNIFIED REPORT ORCHESTRATOR                        │ │   │
│  │  │  • Phase Management    • Progress Tracking   • Error Recovery   │ │   │
│  │  │  • Human/Autopilot     • Verification Loop   • Audit Logging    │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      INTELLIGENCE LAYER                              │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │ Scenario │ │Structure │ │Hypothesis│ │  Chart   │ │Alignment │ │   │
│  │  │ Analyzer │ │ Learner  │ │Generator │ │ Decider  │ │ Verifier │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       ANALYSIS LAYER                                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │ Timeline │ │ Anomaly  │ │ Network  │ │Correlation│ │ Evidence│ │   │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Vault  │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        MEMORY LAYER                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │ Session  │ │Long-Term │ │Procedural│ │Validation│ │ Learning │ │   │
│  │  │ Memory   │ │ Memory   │ │ Memory   │ │ Memory   │ │   Loop   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       STORAGE LAYER                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │   │
│  │  │    DuckDB      │  │   ChromaDB     │  │   File System  │        │   │
│  │  │  (Case Vaults) │  │ (Vector Store) │  │   (Exports)    │        │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. NEXT STEPS

To proceed with implementation:

1. **Confirm this architecture plan** - Any modifications needed?
2. **Choose implementation iteration** - Start with Iteration 1 (Learning Infrastructure)?
3. **Provide sample reports** - Upload existing forensic reports for learning
4. **Generate demo logs** - I'll create realistic Windows/Android logs for the scenario

**Ready to begin implementation when you approve this plan.**
