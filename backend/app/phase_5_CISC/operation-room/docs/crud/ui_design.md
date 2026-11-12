# CRUD UI Design — Next.js Component Specs

## Page: `/cases/[id]/crud/page.js`

### Layout: 5-Tab Interface

```
┌─────────────────────────────────────────────────────────────┐
│  📋 CRUD & Data-Access Analysis        [🔗 Correlation]    │
│  LangGraph 5-Node Pipeline · Sensitivity · Pattern Detection│
├─────────────────────────────────────────────────────────────┤
│ [📊 Overview] [📋 Matrix] [📝 Events][🚨 High-Risk] [📜] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────┐ ┌──────┐ ┌─────┐ ┌─────┐ ┌──────┐ ┌──────┐         │
│  │ 385 │ │  42  │ │  45 │ │ 210 │ │  78  │ │  52  │         │
│  │Total│ │Risk  │ │ C   │ │  R  │ │  U   │ │  D   │         │
│  └─────┘ └──────┘ └─────┘ └─────┘ └──────┘ └──────┘         │
│                                                             │
│  ████████████████████████████████████████████████           │
│  (CRUD distribution bar — CREATE/READ/UPDATE/DELETE)        │
│                                                             │
│  [Tab Content Area]                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `Tip` | `text, children` | Hover tooltip with forensic explanation |
| `CrudChip` | `type` | Color-coded CRUD type badge (CREATE=green, READ=indigo, UPDATE=amber, DELETE=red) |
| `SensChip` | `level` | Sensitivity level pill (LOW=gray, MEDIUM=yellow, HIGH=orange, CRITICAL=red) |
| `CrudBar` | `counts` | Stacked horizontal bar showing CRUD distribution |

### Tab: Overview
- **Stats cards** (6): Total, High-Risk, Creates, Reads, Updates, Deletes
- **Sensitivity breakdown** chart with proportional bars
- **Top actors** leaderboard with event count + risk count

### Tab: CRUD Matrix
- Aggregated `<table>` with columns: Actor, Target, Type, Events, Bytes, Sensitivity, Avg Anomaly, High-Risk, First/Last Seen
- Sorted by high_risk_count desc, event_count desc
- Risk rows highlighted with red background tint

### Tab: Events
- Full event list with inline filter buttons:
  - CRUD type: All | CREATE | READ | UPDATE | DELETE
  - Sensitivity: All | LOW | MEDIUM | HIGH | CRITICAL
- Max 100 rows visible (scrollable)

### Tab: High-Risk
- Expandable cards for each flagged event
- Shows: CRUD type chip, actor, target, sensitivity chip, anomaly score
- **Risk reason** box with amber background explaining why it was flagged

### Tab: Runs
- Historical table: Run ID, Total Events, C/R/U/D counts, High-Risk, Status, Started
