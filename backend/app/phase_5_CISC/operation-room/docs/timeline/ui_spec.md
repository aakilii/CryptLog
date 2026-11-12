# Timeline UI Specification

## Layout

```
┌──────────────────────────────────────────────────────────┐
│ Timeline Reconstruction        [Rebuild] [← Back to Case]│
│ Normalised, chronologically merged event timeline        │
├──────────────────────────────────────────────────────────┤
│  📋 Total  │  📌 Anchors  │  📡 Sources  │  👥 Actors   │
│    31      │      5       │      3       │      4       │
├──────────────────────────────────────────────────────────┤
│ [Actor___] [Source ▾] [Severity ▾] [Keyword___] ☐ Anch  │
├────┬────────────┬──────┬───────┬────────┬──────┬────────┤
│ ⚓ │ Timestamp   │Source│ Actor │ Action │Target│Severity│
│ 📌 │ Jun 1 00:12│ AUTH │ jdoe  │LOGIN_F │ dc01 │  HIGH  │
│ ○  │ Jun 1 00:13│ AUTH │ jdoe  │LOGIN_S │ dc01 │  INFO  │
│ 📌 │ Jun 1 01:02│ VPN  │ jdoe  │VPN_CON │ gw01 │  INFO  │
│ …  │            │      │       │        │      │        │
└──────────────────────────────────────────────────────────┘
```

## Interactions
- **Click ○** → Mark event as manual anchor (📌)
- **Click 📌** → Remove anchor
- **Filter** → Live query with actor, source, severity, keyword, anchors-only
- **Rebuild** → Wipe and re-normalise from raw_events

## Colour Coding
- **Source types:** AUTH=indigo, VPN=cyan, FW=rose, DB=amber, APP=emerald
- **Severity:** HIGH=red, MEDIUM=amber, INFO=default
- **Anchor rows:** Subtle amber background highlight
