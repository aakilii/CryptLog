# AI-POWERED REPORT STUDIO - UI/UX DESIGN PLAN

**Version:** 1.0  
**Date:** 2026-04-04  
**Status:** Design Specification

---

## 🎯 Design Philosophy

**Core Principle:** Make AI investigation as intuitive as ChatGPT while providing forensic-grade transparency and control.

**User Experience Goals:**
1. **Conversational** - Users interact with AI like chatting with an expert analyst
2. **Transparent** - Every AI action, decision, and finding is visible and explainable
3. **Controllable** - Users can approve, reject, or modify AI's plan at any stage
4. **Progressive** - Interface reveals complexity gradually as needed
5. **Persistent** - All work is auto-saved with version control

---

## 📐 Layout Architecture

### Main Canvas (60% width)
```
┌─────────────────────────────────────────────────────────┐
│  REPORT CANVAS                                          │
│  - Report Studio V4 (existing)                          │
│  - Shows generated report                               │
│  - Real-time updates as AI writes                       │
│  - Evidence blocks appear with citations                │
│  - Visual diff highlights when content changes          │
└─────────────────────────────────────────────────────────┘
```

### AI Assistant Panel (Right Side, 40% width, Expandable)
```
┌────────────────────────────────────────────────────┐
│  🤖 AI INVESTIGATION ASSISTANT                     │
├────────────────────────────────────────────────────┤
│  [TABS]                                            │
│  • Chat   • Progress   • Plan   • Evidence   • … │
├────────────────────────────────────────────────────┤
│                                                    │
│  [DYNAMIC CONTENT BASED ON ACTIVE TAB]             │
│                                                    │
│                                                    │
│  ... scrollable content ...                        │
│                                                    │
│                                                    │
│  ... more content ...                              │
│                                                    │
│                                                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Panel Expansion States
```
State 1: Collapsed (Hidden)
├─ Canvas: 100% width
└─ Panel: Hidden
   [< Show AI Assistant] button on right edge

State 2: Normal (40% width) — DEFAULT
├─ Canvas: 60% width
└─ Panel: 40% width
   Tabs visible, content scrollable

State 3: Expanded (60% width)
├─ Canvas: 40% width
└─ Panel: 60% width
   For detailed plan editing, evidence review

State 4: Fullscreen Panel
├─ Canvas: Hidden
└─ Panel: 100% width
   For focused conversation or deep dive
```

---

## 🗂️ Tab System (Multi-View Interface)

### Tab 1: 💬 Chat (Primary Interface)

**Purpose:** Natural conversation with AI investigator

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  💬 Chat                                           │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ 👤 User:                                     │ │
│  │ "Investigate data exfiltration on            │ │
│  │  DESKTOP-ABC and Samsung phone via USB,      │ │
│  │  Bluetooth, and email."                      │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ 🤖 AI Assistant:                             │ │
│  │ I understand. I'll investigate:              │ │
│  │ • Data transfers via USB to phone            │ │
│  │ • Bluetooth file sharing                     │ │
│  │ • Email attachments sent externally          │ │
│  │                                              │ │
│  │ I need to clarify a few things:              │ │
│  │                                              │ │
│  │ 🔍 Question 1 (HIGH PRIORITY)                │ │
│  │ What time period should I focus on?          │ │
│  │ ○ Last 24 hours                              │ │
│  │ ○ Last 7 days                                │ │
│  │ ○ Custom: [____] to [____]                   │ │
│  │                                              │ │
│  │ [Answer] or type your response ⬇️             │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  [Type your message or answer...]                 │
│  [📎 Attach Evidence] [🎤 Voice] [Send]          │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Features:**
- **Auto-scroll to latest message**
- **Typing indicators** when AI is thinking
- **Rich message types:**
  - Text with markdown support
  - Questions with multiple choice
  - Code blocks (evidence hashes, SQL queries)
  - Tables (evidence summaries)
  - Cards (hypothesis cards with approve/reject)
  - Inline approvals (✅ Approve Plan | ❌ Modify)

**Message Types:**

1. **Clarification Question**
   ```
   🔍 Question 2 (MEDIUM PRIORITY)
   Are there any specific confidential files I should look for?
   
   [Text input field]
   [Skip] [Answer]
   ```

2. **Hypothesis Card**
   ```
   💡 Hypothesis Generated
   
   H1: Data exfiltration via USB device
   Confidence Threshold: 85%
   Required Evidence: usb_connect, file_copy, usb_disconnect
   
   ✅ Include in investigation
   ❌ Reject
   ✏️ Modify
   ```

3. **Progress Update**
   ```
   ⚙️ Parsing Windows Event Logs...
   Found 1,245 security events
   [████████░░] 80%
   ```

4. **Finding Summary**
   ```
   ✅ CONFIRMED: USB Data Exfiltration
   Confidence: 92%
   
   Evidence:
   • 3 USB connections on 2024-03-14
   • 127 files copied (2.3 GB)
   • Device: SanDisk Ultra (SN: AA123456)
   
   [View Details] [Add to Report]
   ```

---

### Tab 2: 📊 Progress (Live Investigation Status)

**Purpose:** Real-time view of AI's work progress

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  📊 Progress                                       │
├────────────────────────────────────────────────────┤
│                                                    │
│  Overall Progress                                  │
│  [█████████████████████░░░░░░░░] 75%               │
│                                                    │
│  Current Phase: Hypothesis Evaluation              │
│  Estimated Time: 2 minutes remaining               │
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ Timeline View                                  ││
│ │                                                ││
│ │ ✅ 1. Scenario Analysis       [10s]            ││
│ │ ✅ 2. Log Parsing              [45s]            ││
│ │ ✅ 3. Hypothesis Generation    [8s]             ││
│ │ 🔄 4. Evidence Evaluation      [in progress]    ││
│ │    └─ H1: USB Exfiltration     [███░░] 60%     ││
│ │    └─ H2: Bluetooth Transfer   [████░] 80%     ││
│ │    └─ H3: Email Exfiltration   [█░░░░] 20%     ││
│ │ ⏳ 5. Report Generation         [waiting]       ││
│ │ ⏳ 6. Quality Review            [waiting]       ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│  Statistics                                        │
│  • Events Parsed: 2,456 / 3,000                    │
│  • Hypotheses: 4 total (2 confirmed, 1 testing)    │
│  • Evidence Collected: 234 items                   │
│  • Report Progress: 45% (35 / 78 pages)            │
│                                                    │
│  [Pause Investigation] [Cancel]                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Features:**
- **Real-time updates** via WebSocket
- **Phase-by-phase breakdown** with timings
- **Sub-task progress bars** (per hypothesis)
- **Pause/Resume capability**
- **Estimated time remaining**

---

### Tab 3: 📋 Plan (Investigation Execution Plan)

**Purpose:** View and modify AI's investigation plan before execution

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  📋 Investigation Plan                             │
├────────────────────────────────────────────────────┤
│                                                    │
│  Status: ⏸️ Awaiting Your Approval                 │
│                                                    │
│  [Approve & Execute] [Modify Plan] [Reject]        │
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ Null Hypothesis (H0)                           ││
│ │ No unauthorized data transfer occurred         ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ Alternative Hypotheses                         ││
│ │                                                ││
│ │ ✅ H1: USB Data Exfiltration [HIGH]            ││
│ │    Evidence: usb_connect, file_copy, ...       ││
│ │    Confidence: 85%                             ││
│ │    [✏️ Edit] [🗑️ Remove]                        ││
│ │                                                ││
│ │ ✅ H2: Bluetooth Transfer [MEDIUM]             ││
│ │    Evidence: bluetooth_pair, bt_transfer       ││
│ │    Confidence: 80%                             ││
│ │    [✏️ Edit] [🗑️ Remove]                        ││
│ │                                                ││
│ │ ✅ H3: Email Exfiltration [HIGH]               ││
│ │    Evidence: email_send, email_attach          ││
│ │    Confidence: 85%                             ││
│ │    [✏️ Edit] [🗑️ Remove]                        ││
│ │                                                ││
│ │ [+ Add Hypothesis]                             ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ Execution Phases                               ││
│ │                                                ││
│ │ Phase 1: Log Parsing                           ││
│ │  • Parse Windows EVTX (Security, USB, System)  ││
│ │  • Parse Android logs (logcat, Bluetooth)      ││
│ │  • Parse email logs (Exchange, Outlook)        ││
│ │  Estimated: 1-2 minutes                        ││
│ │                                                ││
│ │ Phase 2: Evidence Extraction                   ││
│ │  • Query for USB events                        ││
│ │  • Query for Bluetooth events                  ││
│ │  • Query for email events                      ││
│ │  Estimated: 30 seconds                         ││
│ │                                                ││
│ │ ... (5 more phases)                            ││
│ │                                                ││
│ │ [Reorder Phases] [Add Custom Phase]            ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│  Changes Made: 0                                   │
│  [Reset to AI's Suggested Plan]                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Features:**
- **Drag-and-drop hypothesis reordering**
- **Edit hypothesis parameters** (confidence threshold, evidence types)
- **Add/remove hypotheses manually**
- **Modify execution phases**
- **Version comparison** (show diff from AI's original plan)
- **Approval workflow** with comments

---

### Tab 4: 🔍 Evidence (Evidence Vault Browser)

**Purpose:** Explore collected evidence with search and filtering

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  🔍 Evidence Vault                                 │
├────────────────────────────────────────────────────┤
│                                                    │
│  [🔎 Search evidence...] [Filters ▼] [Sort ▼]     │
│                                                    │
│  Showing 234 items                                 │
│  Filters: USB events • High severity              │
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ EV-001 | USB Device Connected                  ││
│ │ 2024-03-14 10:15:23 UTC                        ││
│ │ Source: Security.evtx Event 2003               ││
│ │ Device: SanDisk Ultra (SN: AA123456)           ││
│ │ Hash: sha256:abc123def456...                   ││
│ │ Status: ✅ Verified                             ││
│ │ [View Full] [Mark as Key Evidence]             ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ EV-002 | File Copy Operation                   ││
│ │ 2024-03-14 10:16:45 UTC                        ││
│ │ Source: USBStor Parser                         ││
│ │ File: Confidential_Q1_Report.pdf (2.3 MB)      ││
│ │ Hash: sha256:def789ghi012...                   ││
│ │ Status: ✅ Verified                             ││
│ │ [View Full] [Mark as Key Evidence]             ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│  ... (232 more items)                              │
│                                                    │
│  [Export Evidence List] [Generate CoC]             │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Features:**
- **Full-text search** across all evidence
- **Filters:**
  - Event type (USB, Bluetooth, Email, Network, etc.)
  - Severity (Critical, High, Medium, Low, Info)
  - Time range
  - Source log
  - Verification status
- **Sort options:**
  - Timestamp (newest/oldest)
  - Severity
  - Event type
  - Relevance (to current hypothesis)
- **Evidence details modal** with full JSON
- **Chain of Custody** view
- **Export** (CSV, JSON)

---

### Tab 5: 📝 Findings (Summary of AI Discoveries)

**Purpose:** Review confirmed/rejected hypotheses with supporting evidence

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  📝 Findings Summary                               │
├────────────────────────────────────────────────────┤
│                                                    │
│  Hypotheses Evaluated: 4                           │
│  ✅ Confirmed: 3  |  ❌ Rejected: 1                 │
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ ✅ CONFIRMED                                    ││
│ │                                                ││
│ │ H1: USB Data Exfiltration                      ││
│ │ Confidence: 92%                                ││
│ │                                                ││
│ │ Summary:                                       ││
│ │ Suspect connected SanDisk Ultra USB drive      ││
│ │ on 2024-03-14 at 10:15 and copied 127 files   ││
│ │ (2.3 GB) including confidential documents.     ││
│ │                                                ││
│ │ Evidence (8 items):                            ││
│ │ • EV-001: USB connect @ 10:15:23               ││
│ │ • EV-002: File copy @ 10:16:45                 ││
│ │ • EV-008: USB disconnect @ 10:22:10            ││
│ │ ... 5 more                                     ││
│ │                                                ││
│ │ [View Full Analysis] [Export] [Add to Report]  ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ ✅ CONFIRMED                                    ││
│ │                                                ││
│ │ H3: Email Exfiltration                         ││
│ │ Confidence: 88%                                ││
│ │ ... (similar layout)                           ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ ❌ REJECTED                                     ││
│ │                                                ││
│ │ H2: Bluetooth Data Transfer                    ││
│ │ Confidence: 12%                                ││
│ │                                                ││
│ │ Summary:                                       ││
│ │ No evidence of Bluetooth pairing or file       ││
│ │ transfer found in logs. Hypothesis rejected.   ││
│ │                                                ││
│ │ [View Details]                                 ││
│ └────────────────────────────────────────────────┘│
│                                                    │
└────────────────────────────────────────────────────┘
```

---

### Tab 6: 📄 Report (Report Generation Status)

**Purpose:** Monitor report writing progress with live preview

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  📄 Report Generation                              │
├────────────────────────────────────────────────────┤
│                                                    │
│  Report Progress: [████████████░░░] 75% (58/78 pp)│
│                                                    │
│  Current Section: 6.3 Email Analysis               │
│  Quality Score: Alignment 0.98 | Completeness 0.85│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ Report Structure                               ││
│ │                                                ││
│ │ ✅ 1. Title Page                [1 page]       ││
│ │ ✅ 2. Table of Contents         [2 pages]      ││
│ │ ✅ 3. Executive Summary         [3 pages]      ││
│ │ ✅ 4. Case Background           [2 pages]      ││
│ │ ✅ 5. Evidence Inventory        [5 pages]      ││
│ │ ✅ 6. Analysis                  [35 pages]     ││
│ │    ✅ 6.1 USB Analysis          [12 pages]     ││
│ │    ✅ 6.2 Bluetooth Analysis    [8 pages]      ││
│ │    🔄 6.3 Email Analysis        [in progress]  ││
│ │    ⏳ 6.4 Timeline              [waiting]      ││
│ │ ⏳ 7. Findings Summary           [5 pages]      ││
│ │ ⏳ 8. Conclusions                [3 pages]      ││
│ │ ⏳ 9. Recommendations            [2 pages]      ││
│ │ ⏳ 10-12. Appendices             [20 pages]     ││
│ │                                                ││
│ │ [Jump to Section] [Regenerate] [Export PDF]    ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│  Issues Detected: 2 warnings                       │
│  ⚠️ Evidence EV-042 cited twice in different      │
│     contexts - please review                       │
│  ⚠️ Page 34 has slight margin overflow            │
│                                                    │
│  [Auto-Fix Issues] [Review Manually]               │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

### Tab 7: 🕐 History (Version Control & Audit Trail)

**Purpose:** View all changes with Git-like version control

**Layout:**
```
┌────────────────────────────────────────────────────┐
│  🕐 Version History                                │
├────────────────────────────────────────────────────┤
│                                                    │
│  Branch: main ▼  |  [Create Branch]                │
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ v-20260404-135000-0004 (HEAD)                  ││
│ │ 📝 "Added Email analysis section"              ││
│ │ By: AI Assistant | 2 minutes ago               ││
│ │                                                ││
│ │ Changes:                                       ││
│ │ + Section 6.3: Email Analysis (8 pages)        ││
│ │ ~ Executive Summary updated                    ││
│ │ + 12 new evidence items                        ││
│ │                                                ││
│ │ Metrics:                                       ││
│ │ Alignment: 0.98 | Completeness: 0.85           ││
│ │                                                ││
│ │ [View] [Diff] [Rollback]                       ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│ ┌────────────────────────────────────────────────┐│
│ │ v-20260404-134500-0003                         ││
│ │ 📝 "Fixed alignment issues in USB section"     ││
│ │ By: analyst@lab.com | 10 minutes ago           ││
│ │ [View] [Diff] [Rollback]                       ││
│ └────────────────────────────────────────────────┘│
│                                                    │
│  ... (older versions)                              │
│                                                    │
│  [Compare Versions] [Export History]               │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 🎨 Visual Design System

### Color Palette

**Semantic Colors:**
```
Success (Confirmed):  #10B981 (Green)
Warning (Inconclusive): #F59E0B (Amber)
Danger (Rejected):    #EF4444 (Red)
Info (Processing):    #3B82F6 (Blue)
Neutral:              #6B7280 (Gray)
```

**Status Indicators:**
```
✅ Confirmed / Complete
🔄 In Progress
⏳ Waiting / Queued
❌ Rejected / Failed
⚠️ Warning / Needs Review
💡 Suggestion / Insight
🔍 Question / Clarification
```

### Typography

```
Headings:    Inter, 18-24px, Bold
Body:        Inter, 14px, Regular
Code/Hashes: JetBrains Mono, 12px
Timestamps:  Inter, 12px, Medium
Labels:      Inter, 12px, Semibold, Uppercase
```

### Component Library

**Cards:**
```
┌─────────────────────────────────────────┐
│ [Icon] Title                 [Actions]  │
├─────────────────────────────────────────┤
│ Content area with padding               │
│ • List items                            │
│ • Paragraphs                            │
│                                         │
│ [Primary Button] [Secondary Button]     │
└─────────────────────────────────────────┘
```

**Progress Bars:**
```
Standard: [████████████████░░░░] 80%
Success:  [████████████████████] 100% ✅
Error:    [████████░░░░░░░░░░░░] 40% ❌
```

**Badges:**
```
HIGH      MEDIUM    LOW
CONFIRMED TESTING  REJECTED
USB       EMAIL    NETWORK
```

---

## 🎭 Interaction Patterns

### 1. Approval Workflow

**Step 1: AI presents plan**
```
┌──────────────────────────────────────────┐
│ 🤖 I've created an investigation plan.   │
│                                          │
│ I'll test 4 hypotheses:                  │
│ • USB exfiltration                       │
│ • Bluetooth transfer                     │
│ • Email exfiltration                     │
│ • Network transfer                       │
│                                          │
│ [View Full Plan] to review details.      │
│                                          │
│ ✅ Approve & Start  ✏️ Modify  ❌ Reject │
└──────────────────────────────────────────┘
```

**Step 2: User approval**
```
USER CLICKS: ✅ Approve & Start

┌──────────────────────────────────────────┐
│ 🤖 Great! Starting investigation...      │
│                                          │
│ Phase 1: Parsing logs                    │
│ [████░░░░░░] 40%                         │
│                                          │
│ [Switch to Progress Tab to watch] ➡️     │
└──────────────────────────────────────────┘
```

### 2. Human-in-Loop Questions

**Question appears in Chat:**
```
┌──────────────────────────────────────────┐
│ 🔍 I need your input (HIGH PRIORITY)     │
│                                          │
│ I found 3 USB devices in the logs.       │
│ Which one belongs to the suspect?        │
│                                          │
│ ○ SanDisk Ultra (SN: AA123456)           │
│ ○ Kingston DT100 (SN: BB789012)          │
│ ○ WD MyPassport (SN: CC345678)           │
│ ○ All of them                            │
│ ○ None - they're all legitimate          │
│                                          │
│ [Answer] [Skip for now]                  │
└──────────────────────────────────────────┘
```

**User answers, AI continues:**
```
USER SELECTS: SanDisk Ultra (SN: AA123456)

┌──────────────────────────────────────────┐
│ 🤖 Got it. Focusing on SanDisk Ultra.    │
│                                          │
│ I found 127 files copied to this device. │
│ Analyzing now...                         │
└──────────────────────────────────────────┘
```

### 3. Live Report Writing

**Canvas shows real-time updates:**
```
Page 25: [New content appears with fade-in animation]

┌─────────────────────────────────────────┐
│ 6.1 USB Device Analysis                 │
│                                         │
│ On March 14, 2024 at 10:15:23 UTC,      │
│ a SanDisk Ultra USB device...           │
│ [typing cursor appears]                  │
│                                         │
│ [Evidence block fades in]                │
│ ┌──────────────────────┐                │
│ │ Evidence: EV-001     │                │
│ │ Type: USB Connect    │                │
│ │ Time: 10:15:23 UTC   │                │
│ │ Hash: sha256:abc...  │                │
│ └──────────────────────┘                │
└─────────────────────────────────────────┘
```

**Panel shows writing progress:**
```
Chat Tab:
┌──────────────────────────────────────────┐
│ 🤖 Writing Section 6.1: USB Analysis...  │
│ [████████░░] 80%                         │
│                                          │
│ Added 3 evidence blocks                  │
│ Generated timeline chart                 │
│ Writing conclusions...                   │
└──────────────────────────────────────────┘
```

### 4. Error Handling & Corrections

**AI detects issue:**
```
┌──────────────────────────────────────────┐
│ ⚠️ Issue Detected                         │
│                                          │
│ Evidence EV-042 is cited in both USB     │
│ and Email sections with different        │
│ timestamps. This might be a duplicate.   │
│                                          │
│ Suggested Fix:                           │
│ Remove duplicate from Email section      │
│ and update reference.                    │
│                                          │
│ ✅ Auto-Fix  ✏️ Fix Manually  ❌ Ignore  │
└──────────────────────────────────────────┘
```

---

## 🔔 Notifications & Alerts

### Toast Notifications (Bottom-right corner)

**Success:**
```
┌──────────────────────────────────┐
│ ✅ Investigation Complete!       │
│ Report generated: 78 pages       │
│ [View Report] [Dismiss]          │
└──────────────────────────────────┘
```

**Warning:**
```
┌──────────────────────────────────┐
│ ⚠️ Your approval needed           │
│ Investigation plan ready          │
│ [Review Plan] [Dismiss]          │
└──────────────────────────────────┘
```

**Error:**
```
┌──────────────────────────────────┐
│ ❌ Log parsing failed             │
│ File: Security.evtx corrupted    │
│ [Retry] [Skip] [Dismiss]         │
└──────────────────────────────────┘
```

### Badge Counters

**Panel Tabs with Notifications:**
```
💬 Chat (2)     ← 2 new AI messages
📊 Progress     
📋 Plan (!!)    ← Needs approval
🔍 Evidence     
📝 Findings (3) ← 3 new findings
```

---

## 📱 Responsive Behavior

### Desktop (1920x1080)
```
Canvas: 60% | Panel: 40% (default)
Canvas: 100% | Panel: 0% (collapsed)
Canvas: 40% | Panel: 60% (expanded)
Canvas: 0% | Panel: 100% (fullscreen)
```

### Tablet (1024x768)
```
Canvas: 50% | Panel: 50% (default)
Stack vertically when panel expanded
```

### Mobile (375x667)
```
Stack vertically always
Canvas on top, Panel below
Swipe gestures to switch
```

---

## ⚡ Performance Optimizations

### Real-time Updates

**WebSocket Events:**
```javascript
// Client subscribes to investigation updates
ws.on('investigation_progress', (data) => {
  updateProgressBar(data.percentage);
  addChatMessage(data.message);
  if (data.requires_approval) {
    showApprovalDialog(data);
  }
});

ws.on('report_section_written', (data) => {
  animateNewContent(data.section_id);
  updateReportPreview(data.html);
});

ws.on('evidence_found', (data) => {
  addEvidenceToVault(data.evidence);
  updateEvidenceCounter();
});
```

### Lazy Loading

**Evidence list virtualizes for 1000+ items:**
```
Only render visible items (30)
Pre-load next 30 items
Infinite scroll pagination
```

**Report pages load on-demand:**
```
Render current page + prev/next
Cache 5 recently viewed pages
Unload pages outside viewport
```

---

## 🧪 User Testing Scenarios

### Scenario 1: First-time User

**Goal:** Complete an investigation from scenario to report

1. User enters scenario in Chat
2. AI asks clarifying questions
3. User answers via multiple choice
4. AI presents plan
5. User approves plan
6. Progress tab auto-opens
7. User watches live progress
8. Findings appear in real-time
9. Report tab shows writing progress
10. Toast notification: "Report Complete!"
11. User reviews report in canvas
12. User exports PDF

**Success Criteria:**
- No confusion about next steps
- Clear understanding of AI's actions
- Feels in control throughout

### Scenario 2: Expert User (Customization)

**Goal:** Modify AI's plan before execution

1. User enters complex scenario
2. AI generates 7 hypotheses
3. User switches to Plan tab
4. User removes 2 hypotheses
5. User edits confidence threshold on H3
6. User adds custom hypothesis
7. User reorders phases
8. User approves modified plan
9. Investigation runs with custom plan
10. User compares results to AI's original plan

**Success Criteria:**
- Plan modification is intuitive
- Changes are clearly visible
- Can revert to AI's plan easily

### Scenario 3: Error Recovery

**Goal:** Handle log parsing failure gracefully

1. Investigation starts
2. Log parsing fails (corrupted file)
3. Toast notification appears
4. Chat shows error message with details
5. User clicks "Skip" to continue without that log
6. AI adjusts plan based on available evidence
7. Investigation completes with caveat noted in report

**Success Criteria:**
- Error is clearly explained
- Recovery options are obvious
- Investigation can continue

---

## 📐 Technical Implementation

### Frontend Stack

```
Framework: React 18
State: Zustand (lightweight, fast)
Real-time: Socket.IO
Styling: Tailwind CSS
Components: shadcn/ui
Charts: Recharts
Markdown: react-markdown
Code: Prism.js
Animations: Framer Motion
```

### State Management

```javascript
// Investigation Store
const useInvestigationStore = create((set) => ({
  investigationId: null,
  phase: 'idle',
  progress: 0,
  plan: null,
  findings: [],
  evidence: [],
  chatMessages: [],
  
  // Actions
  startInvestigation: (scenario) => {...},
  updateProgress: (data) => {...},
  addFinding: (finding) => {...},
  approvePlan: () => {...},
}));
```

### Component Structure

```
<ReportStudio>
  <CanvasArea>
    <ReportCanvas /> {/* Existing V4 canvas */}
  </CanvasArea>
  
  <AIPanel collapsed={false} width={40}>
    <TabBar>
      <Tab icon="💬">Chat</Tab>
      <Tab icon="📊">Progress</Tab>
      <Tab icon="📋">Plan</Tab>
      ...
    </TabBar>
    
    <TabContent>
      {activeTab === 'chat' && <ChatInterface />}
      {activeTab === 'progress' && <ProgressView />}
      {activeTab === 'plan' && <PlanEditor />}
      ...
    </TabContent>
  </AIPanel>
</ReportStudio>
```

---

## 🎯 Success Metrics

### User Satisfaction
- **Task Completion Rate**: > 90%
- **Time to First Report**: < 5 minutes
- **Error Recovery Rate**: > 95%
- **User Confusion Score**: < 10%

### Performance
- **WebSocket Latency**: < 100ms
- **Chat Response Time**: < 500ms
- **Report Rendering**: < 2s for 78 pages
- **Progress Update Frequency**: Every 500ms

### Engagement
- **Active Tab Switches**: 5-10 per investigation
- **Plan Modifications**: 30% of users
- **Evidence Review**: 80% of users
- **Version History Views**: 40% of users

---

## 🚀 Implementation Phases

### Phase 1: Core Chat Interface (Week 1-2)
- [ ] Chat tab with message types
- [ ] WebSocket connection
- [ ] Basic progress updates
- [ ] Question/answer flow

### Phase 2: Progress & Plan Tabs (Week 3-4)
- [ ] Progress timeline view
- [ ] Plan editor with drag-and-drop
- [ ] Approval workflow
- [ ] Real-time statistics

### Phase 3: Evidence & Findings (Week 5-6)
- [ ] Evidence vault browser
- [ ] Filtering and search
- [ ] Findings summary cards
- [ ] Export capabilities

### Phase 4: Report Integration (Week 7-8)
- [ ] Live report writing animation
- [ ] Report progress tracking
- [ ] Version history viewer
- [ ] Diff visualization

### Phase 5: Polish & Testing (Week 9-10)
- [ ] Error handling
- [ ] Animations and transitions
- [ ] Responsive design
- [ ] User acceptance testing

---

## 📝 Conclusion

This UI/UX design creates a **ChatGPT-like experience** for forensic investigation while maintaining:
- ✅ **Full transparency** - Every AI action is visible
- ✅ **Complete control** - Users can modify or reject AI's plan
- ✅ **Progressive disclosure** - Complexity revealed as needed
- ✅ **Real-time feedback** - Live progress and streaming content
- ✅ **Professional output** - Production-quality forensic reports

**The right panel becomes the AI's "face"** - a conversational, helpful assistant that shows its work, asks for help when needed, and produces transparent, auditable results.

---

*AI-Powered Report Studio - UI/UX Design Plan v1.0*  
*NFLIP Deep Research Investigation Assistant*  
*Date: 2026-04-04*
