# NFLIP Investigation Assistant - Vision vs Architecture Gap Analysis

## Executive Summary

Your vision describes a **Deep Research-style Investigation Assistant** that:
1. Works collaboratively WITH the investigator (human-in-loop)
2. Creates visible "chain of thoughts" like ChatGPT DeepResearch
3. Allows user to modify the plan before/during execution
4. Uses hypothesis-driven investigation with evidence vault tracking
5. Builds reports page-by-page with verification of placement
6. Supports reference documents for alignment/formatting

---

## YOUR VISION (Detailed Breakdown)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        YOUR VISION ARCHITECTURE                            │
└────────────────────────────────────────────────────────────────────────────┘

1. INTAKE
   ├─ Receive scenario + log metadata
   ├─ Analyze available logs (what we have)
   ├─ Get inputs: alerts, lookover items, important things
   ├─ Ask clarification questions
   └─ OUTPUT: Full investigation context

2. CHAIN-OF-THOUGHT PLANNING (ChatGPT DeepResearch style)
   ├─ Create detailed visible plan showing AI reasoning
   ├─ User can UPDATE/ALTER plan before approval
   ├─ Show each planned phase with expected outputs
   └─ OUTPUT: Approved investigation flow

3. PHASE EXECUTION (for each phase)
   ├─ Construct hypothesis for this phase
   ├─ Execute analysis modules (correlation, CRUD, anomaly, etc.)
   ├─ Store ALL outputs in Evidence Vault
   ├─ Analyze extracted evidence
   ├─ Conclude: match/suspicious/inconclusive
   ├─ HUMAN-IN-LOOP: Ask questions if AI needs help
   └─ OUTPUT: Phase summary + stored evidence

4. REPORT BUILDING (page-by-page)
   ├─ Plan report structure (intro to last page)
   ├─ Write each section using Report Studio
   ├─ Verify placement (x, y, width, alignment)
   ├─ Allow reference document for formatting
   ├─ Handle exceptions (new headings, page updates)
   ├─ Update TOC, highlights, page numbers
   └─ OUTPUT: Complete verified report

5. CONTINUOUS LOOP
   ├─ Step-by-step corrections
   ├─ Human feedback integration
   └─ Iterative refinement
```

---

## CURRENT ARCHITECTURE ANALYSIS

### ✅ WHAT WE HAVE (Working)

| Feature | Status | Location |
|---------|--------|----------|
| Scenario parsing & entity extraction | ✅ Complete | `investigation.py` |
| Clarification questions | ✅ Complete | `clarification.py` |
| Investigation plan generation | ✅ Complete | `planning.py`, `planner.py` |
| Hypothesis generation | ✅ Complete | `hypothesis.py`, `hypothesis_tree.py` |
| Hypothesis testing | ✅ Complete | `hypothesis.py` |
| Evidence Vault with SHA-256 | ✅ Complete | `evidence.py`, EvidenceVault class |
| Chain of Custody logging | ✅ Complete | `decorators.py`, CoC tables |
| Analysis modules (6) | ✅ Complete | anomaly, correlation, crud, network, depth, timeline |
| Report document creation | ✅ Complete | `report.py` MCP tools |
| Canvas with x,y positioning | ✅ Complete | Studio V4 frontend |
| Page management | ✅ Complete | PageNavigator, addPage() |
| Widget positioning | ✅ Complete | react-rnd, absolute coords |
| PDF/DOCX export | ✅ Complete | `export_service.py` |
| Evidence citation verification | ✅ Complete | _scan_ast_citations() |
| Content hashing | ✅ Complete | SHA-256 on elements |
| LLM narrative generation | ✅ Complete | `llm.py`, streaming support |

### ⚠️ PARTIAL IMPLEMENTATIONS

| Feature | Status | Gap |
|---------|--------|-----|
| Human-in-loop support | ⚠️ Framework exists | No UI for interrupts/questions |
| Plan modification | ⚠️ API exists | No interactive edit UI |
| Reference document loading | ⚠️ Templates exist | No import existing PDF/DOCX |
| TOC generation | ⚠️ Framework ready | Not implemented |
| Page number auto-update | ⚠️ Basic exists | No dynamic re-flow |
| Highlights page | ⚠️ Focus modes exist | No dedicated page |

### ❌ MISSING (Critical Gaps)

| Feature | Gap Description | Priority |
|---------|-----------------|----------|
| **Chain-of-Thought UI** | No DeepResearch-style thinking display | 🔴 HIGH |
| **Interactive Plan Editor** | Cannot visually edit/reorder phases | 🔴 HIGH |
| **Live Phase Progress Stream** | No real-time "AI is thinking..." output | 🔴 HIGH |
| **Phase Approval Workflow** | No "approve before execute" gate | 🔴 HIGH |
| **Human Question Popup** | No UI for AI to ask user questions | 🔴 HIGH |
| **Report Alignment Verification** | No visual diff for placement check | 🟡 MEDIUM |
| **Reference Document Import** | Cannot load old PDF/DOCX as template | 🟡 MEDIUM |
| **Dynamic TOC Builder** | No automatic table of contents | 🟡 MEDIUM |
| **Page Reflow on Insert** | Adding content doesn't adjust layout | 🟡 MEDIUM |
| **Highlights Summary Page** | No auto-generated key findings page | 🟡 MEDIUM |

---

## DETAILED GAP ANALYSIS

### Gap 1: Chain-of-Thought Display (DeepResearch Style)

**Your Vision:**
> "Create detailed chain of thoughts that gonna be done by our AI assistant inspired from ChatGPT DeepResearch"

**Current State:**
- Backend generates plans but they're returned as final JSON
- No streaming of reasoning steps
- No visible "thinking process"

**What's Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🤔 Investigation Assistant is thinking...                   │
├─────────────────────────────────────────────────────────────┤
│ ▶ Analyzing scenario for key entities...                    │
│   ├─ Found: Windows Computer (Office-PC-001)                │
│   ├─ Found: Android Phone (IMEI: 359847...)                 │
│   └─ Transfer channels: USB, Bluetooth, Email               │
│                                                             │
│ ▶ Checking available log sources...                         │
│   ├─ Windows Event Logs ✓ (45,232 events)                   │
│   ├─ USB Device History ✓ (127 connections)                 │
│   ├─ Email Server Logs ✓ (3,841 messages)                   │
│   └─ Network Flows ✓ (12,492 flows)                         │
│                                                             │
│ ▶ Building investigation phases...                          │
│   ├─ Phase 1: USB transfer timeline [0:00-2:00 priority]    │
│   ├─ Phase 2: Bluetooth pairing analysis                    │
│   └─ Phase 3: Email attachment correlation                  │
│                                                             │
│ [Edit Plan] [Approve & Execute]                             │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Required:**
1. Server-Sent Events (SSE) for streaming reasoning
2. React component for collapsible thought tree
3. Backend "reasoning steps" emission during processing
4. Zustand store for thought accumulation

---

### Gap 2: Interactive Plan Editor

**Your Vision:**
> "The user can update it by giving extra or altering commands, on approving the needed execution flow"

**Current State:**
- Plan generated via `generate_investigation_plan()`
- Returns list of phases
- No UI for modification

**What's Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Investigation Plan                                       │
├─────────────────────────────────────────────────────────────┤
│ ☐ Phase 1: Data Collection                                  │
│   ├─ Import Windows Event Logs                [↕] [×]       │
│   ├─ Import USB Device History                [↕] [×]       │
│   └─ [+ Add Step]                                           │
│                                                             │
│ ☐ Phase 2: Timeline Analysis                                │
│   ├─ Build unified timeline                   [↕] [×]       │
│   ├─ Identify critical events                 [↕] [×]       │
│   └─ [+ Add Step]                                           │
│                                                             │
│ ☐ Phase 3: Hypothesis Testing                               │
│   ├─ H1: USB was primary channel              [↕] [×]       │
│   ├─ H2: Email used for small files           [↕] [×]       │
│   └─ [+ Add Hypothesis]                                     │
│                                                             │
│ [+ Add Phase]                                               │
│                                                             │
│ ⚠️ User added: "Focus on after-hours activity"              │
│                                                             │
│ [Regenerate with Changes] [Approve Plan]                    │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Required:**
1. Phase editor React component with drag-drop reorder
2. Add/remove phase/step capability
3. User command input field
4. Re-planning endpoint that incorporates changes
5. Plan approval state gate

---

### Gap 3: Human-in-Loop Interrupts

**Your Vision:**
> "Ask questions if AI needs anything from user, it should also support human-in-loop whenever it needs"

**Current State:**
- `MCPToolResult.requires_clarification` field exists
- `clarification_questions` list exists
- No UI to display/collect answers during execution

**What's Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🛑 Investigation Paused - AI Needs Your Input               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ While analyzing USB transfers, I found 3 devices with       │
│ similar names:                                              │
│                                                             │
│   • "Samsung Galaxy S21" (connected 2024-03-15)             │
│   • "Samsung Galaxy S21 Ultra" (connected 2024-03-10)       │
│   • "Samsung SM-G991B" (connected 2024-03-12)               │
│                                                             │
│ Which device(s) belong to the suspect?                      │
│                                                             │
│ [ ] Samsung Galaxy S21                                      │
│ [ ] Samsung Galaxy S21 Ultra                                │
│ [ ] Samsung SM-G991B                                        │
│ [ ] All of them                                             │
│ [ ] I'm not sure (continue with all)                        │
│                                                             │
│ [Submit Answer] [Skip - Use All]                            │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Required:**
1. WebSocket channel for real-time question delivery
2. Question popup modal component
3. Backend pause/resume mechanism
4. Answer incorporation into investigation context
5. State persistence during pause

---

### Gap 4: Report Alignment Verification

**Your Vision:**
> "Verify whether it correctly placed the respective component or text summaries with all kind of details, with correct x, y and length of the components are correct and matches the alignment (also allow to feed the old documents and get reference and alignments correctness from it)"

**Current State:**
- x, y, width, height stored per element
- No visual verification
- No reference document comparison

**What's Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📐 Layout Verification                                      │
├─────────────────────────────────────────────────────────────┤
│ Reference: Annual_Report_Template.pdf                       │
│                                                             │
│ ┌─────────────────┐  ┌─────────────────┐                    │
│ │ REFERENCE       │  │ CURRENT         │                    │
│ │ ┌───────────┐   │  │ ┌───────────┐   │                    │
│ │ │ Title     │   │  │ │ Title ✓   │   │  Title: ✓ Match   │
│ │ └───────────┘   │  │ └───────────┘   │                    │
│ │                 │  │                 │                    │
│ │ ┌───────────┐   │  │ ┌───────────┐   │  Margin: ⚠️ 2mm   │
│ │ │ Chart     │   │  │ │ Chart ⚠️  │   │  off left         │
│ │ │           │   │  │ │           │   │                    │
│ │ └───────────┘   │  │ └───────────┘   │                    │
│ └─────────────────┘  └─────────────────┘                    │
│                                                             │
│ Differences Found:                                          │
│ • Chart widget: x=50 (ref: x=48) - Δ2px                     │
│ • Summary text: height=120 (ref: height=150) - Δ30px        │
│                                                             │
│ [Auto-Align to Reference] [Accept Differences]              │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Required:**
1. Reference document parser (PDF → element positions)
2. Position comparison algorithm
3. Visual diff overlay component
4. Auto-align correction action
5. Template extraction from existing docs

---

### Gap 5: Dynamic Report Building

**Your Vision:**
> "It should build the report part by part from intro page to last page... if anything exception like new heading adding, new investigation add on, it should also update the highlights page, page numbers"

**Current State:**
- Pages are static arrays
- No automatic TOC
- No content reflow
- No highlights page generation

**What's Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📖 Report Builder - Live Progress                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Page Structure:                                             │
│ ├─ [✓] Cover Page (auto-generated)                          │
│ ├─ [✓] Table of Contents (auto-updating)                    │
│ ├─ [✓] Executive Summary                                    │
│ │      └─ 3 key findings inserted                           │
│ ├─ [🔄] Timeline Analysis                                   │
│ │      └─ AI writing narrative...                           │
│ ├─ [ ] Anomaly Findings                                     │
│ ├─ [ ] Attack Chain                                         │
│ ├─ [ ] Conclusions                                          │
│ ├─ [ ] Recommendations                                      │
│ └─ [ ] Evidence Appendix                                    │
│                                                             │
│ ⚠️ New section added: "Bluetooth Analysis"                  │
│    → TOC updated (page 8)                                   │
│    → Subsequent pages renumbered                            │
│                                                             │
│ [Preview] [Insert Section] [Finalize]                       │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Required:**
1. Report structure state machine
2. Auto-TOC generation from headings
3. Page number recalculation on insert
4. Section dependency tracking
5. Highlights extraction from findings

---

## COMPARISON MATRIX

| Feature | Your Vision | Current Status | Gap |
|---------|-------------|----------------|-----|
| Scenario intake | ✅ | ✅ Complete | None |
| Log metadata analysis | ✅ | ✅ Via modules | None |
| Clarification questions | ✅ | ✅ Complete | None |
| **Chain-of-thought display** | ✅ | ❌ Missing | 🔴 Major |
| **Interactive plan edit** | ✅ | ❌ Missing | 🔴 Major |
| **Plan approval gate** | ✅ | ❌ Missing | 🔴 Major |
| Hypothesis construction | ✅ | ✅ Complete | None |
| Module analysis | ✅ | ✅ 6 modules | None |
| Evidence vault storage | ✅ | ✅ Complete | None |
| Evidence hashing | ✅ | ✅ SHA-256 | None |
| Confidence scoring | ✅ | ✅ Complete | None |
| **Human-in-loop UI** | ✅ | ❌ Missing | 🔴 Major |
| Phase summaries | ✅ | ✅ SummaryGenerator | None |
| Report Studio canvas | ✅ | ✅ Complete | None |
| x,y,w,h positioning | ✅ | ✅ Complete | None |
| **Placement verification** | ✅ | ❌ Missing | 🟡 Medium |
| **Reference doc import** | ✅ | ❌ Missing | 🟡 Medium |
| **Auto TOC** | ✅ | ❌ Missing | 🟡 Medium |
| **Page reflow** | ✅ | ❌ Missing | 🟡 Medium |
| **Highlights page** | ✅ | ❌ Missing | 🟡 Medium |
| PDF export | ✅ | ✅ Complete | None |
| Chain of Custody | ✅ | ✅ Complete | None |

---

## WHAT WE HAVE EXTRA (Bonus)

These are features in the current system that weren't explicitly in your vision but add value:

1. **Focus Modes** (Story/Evidence/Review/Redact) - Filter views
2. **Cryptographic Evidence Overlay** - Show raw hashes in UI
3. **Document Versioning** - Full version history
4. **90+ Predefined Queries** - Pre-built DuckDB analytics
5. **MITRE ATT&CK Mapping** - Attack vector categorization
6. **Confidence Levels (ODNI ICD 203)** - Intelligence community standard
7. **Cross-Module Correlation** - Auto-link findings across modules
8. **Widget Filter Inspector** - Per-widget topN/minRisk controls
9. **Z-Index Management** - Layer ordering
10. **Auto-Save** - Version snapshots on change

---

## PROPOSED IMPLEMENTATION PLAN

### Phase A: Deep Research UI (2 weeks)
```
A1. Chain-of-Thought Component
    ├─ Streaming SSE endpoint for reasoning steps
    ├─ Collapsible thought tree React component
    ├─ Progress indicators per phase
    └─ Real-time status updates

A2. Interactive Plan Editor
    ├─ Phase/step drag-drop reorder
    ├─ Add/remove/edit capabilities
    ├─ User command integration
    └─ Plan diff visualization

A3. Approval Workflow
    ├─ "Review Plan" state
    ├─ "Approved" state
    ├─ Modification triggers re-plan
    └─ Audit log of changes
```

### Phase B: Human-in-Loop System (1.5 weeks)
```
B1. Question Delivery
    ├─ WebSocket channel for questions
    ├─ Question queue management
    ├─ Priority/blocking classification
    └─ Timeout with default behavior

B2. Question UI
    ├─ Modal popup component
    ├─ Multiple choice support
    ├─ Free text input
    └─ "Skip" and "Later" options

B3. Answer Processing
    ├─ Answer incorporation into context
    ├─ Resume workflow
    ├─ Answer audit logging
    └─ Re-analyze with new info
```

### Phase C: Report Enhancement (1.5 weeks)
```
C1. Reference Document Import
    ├─ PDF parser for layout extraction
    ├─ DOCX parser for structure
    ├─ Position mapping algorithm
    └─ Style extraction

C2. Alignment Verification
    ├─ Visual diff overlay
    ├─ Position comparison logic
    ├─ Auto-align action
    └─ Tolerance configuration

C3. Dynamic TOC & Numbering
    ├─ Auto-scan for headings
    ├─ TOC generation component
    ├─ Page reflow calculator
    └─ Live update on changes

C4. Highlights Page
    ├─ Key findings extraction
    ├─ Auto-summary generation
    ├─ Configurable criteria
    └─ Position after TOC
```

### Phase D: Integration & Testing (1 week)
```
D1. End-to-End Flow
    ├─ Scenario → Report complete path
    ├─ Human interrupt simulation
    ├─ Reference alignment test
    └─ 70+ page report generation

D2. Performance
    ├─ SSE streaming stability
    ├─ Large report handling
    └─ Concurrent investigation support
```

---

## DECISION POINTS FOR YOU

Before implementation, I need your input on:

1. **Chain-of-Thought Style**
   - Real-time streaming text (like ChatGPT)?
   - Structured tree that expands?
   - Both with toggle?

2. **Human-in-Loop Priority**
   - Modal popup (blocks UI)?
   - Side panel (non-blocking)?
   - Notification queue?

3. **Reference Document Format**
   - PDF only?
   - DOCX only?
   - Both?
   - Our own .nflip template format?

4. **Plan Edit Granularity**
   - Phases only?
   - Phases + steps?
   - Full hypothesis tree editing?

5. **Report Building Mode**
   - Sequential (page 1 → page N)?
   - Parallel (all sections at once)?
   - Hybrid (structure first, then fill)?

---

## RECOMMENDED APPROACH

Based on your vision, I recommend:

```
┌─────────────────────────────────────────────────────────────┐
│             RECOMMENDED: HYBRID DEEP RESEARCH               │
└─────────────────────────────────────────────────────────────┘

1. STREAMING + TREE VIEW
   • Stream reasoning text in real-time (like DeepResearch)
   • Simultaneously build a collapsible tree structure
   • User can expand tree to see full reasoning
   • Summary view shows just milestones

2. APPROVAL GATES
   • After intake: Approve plan before execution
   • After each phase: Optional continue/pause
   • Before report: Review all findings
   • Before export: Final verification

3. PROGRESSIVE REPORT BUILD
   • Structure defined first (TOC skeleton)
   • Fill sections as investigation completes
   • AI writes draft → Human reviews → AI refines
   • Real-time preview as sections complete

4. EVIDENCE-FIRST
   • Every claim linked to Evidence Vault
   • Visual indicators for cited vs uncited
   • Automatic citation insertion
   • Hash verification before export
```

This balances automation with control, giving the investigator visibility and control at every step while letting AI do the heavy lifting.

---

## NEXT STEPS

1. **Confirm approach** - Do you agree with the gap analysis and recommendations?
2. **Prioritize gaps** - Which gaps are most critical for your immediate use case?
3. **Start implementation** - Begin with Phase A (Deep Research UI)?

Let me know your thoughts and I'll create a detailed implementation plan with code structure.
