# UI Specification — Dashboard & Case Management

## Design Language

- **Theme:** Dark forensic — deep navy backgrounds, glassmorphism cards, gradient accents
- **Typography:** Inter (Google Fonts), weights 400–800
- **Colours:** Indigo/violet primary, cyan/emerald accents, rose for danger
- **Effects:** Backdrop blur, subtle glow borders, card hover lift, fadeInUp animations

## Pages

### Dashboard (`/`)

```
┌─────────────────────────────────────────────────────────────┐
│ [Sidebar]  │  Investigation Dashboard          [+ New Case] │
│            │                                                │
│  📊 Dash   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  ➕ New    │  │Total │ │Open  │ │Crit  │ │Evid  │          │
│            │  │Cases │ │/Act  │ │ical  │ │ence  │          │
│ ── Modules │  └──────┘ └──────┘ └──────┘ └──────┘          │
│  🔍 Time.. │                                                │
│  ⚠️ Anom.. │  ┌─ Case Card ──┐ ┌─ Case Card ──┐            │
│  🔗 Corr.. │  │ Title        │ │ Title        │            │
│  📋 CRUD.. │  │ Priority/Stat│ │ Priority/Stat│            │
│  🌐 Net..  │  │ Meta         │ │ Meta         │            │
│  📈 Depth. │  └──────────────┘ └──────────────┘            │
│  📊 Aug..  │                                                │
│  📝 Report │  (or empty state with CTA)                     │
└─────────────────────────────────────────────────────────────┘
```

**Components:**  
- `StatsCard` — icon, value, label  
- `CaseCard` — priority bar, title, badges, metadata  
- Empty state with shield icon and "Create First Case" CTA

### New Case Wizard (`/cases/new`)

4-step wizard with progress indicator. Steps: Details → Scope → Sources → Review.

### Case Detail (`/cases/[id]`)

Two-column layout:  
- Left: case metadata table  
- Right: description + mini stat cards (evidence count, CoC count)  
- Bottom: full-width evidence artefacts table with truncated hashes  
- Actions: "Import Logs", "Chain of Custody"

### Log Import (`/cases/[id]/import`)

Two-column layout:  
- Left: import configuration form  
- Right: result panel (empty → populated after import)

### Chain of Custody (`/cases/[id]/chain-of-custody`)

Timeline display with vertical line, event cards, action icons, actor names, hashes.

## Responsive Behaviour

- Sidebar hidden below 900px
- Grids collapse to single column
- Tables become horizontally scrollable
