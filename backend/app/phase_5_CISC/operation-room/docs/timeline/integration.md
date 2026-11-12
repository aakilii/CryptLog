# Integration Points

## Upstream: Case Initialization
The timeline module reads from the `raw_events` table populated by Case Init. It **never modifies** raw_events — only reads.

## Downstream Consumers

| Module               | What it reads                          | How                                       |
|----------------------|----------------------------------------|-------------------------------------------|
| Anomaly Detection    | `unified_timeline` (time-ordered)      | Scans for statistical outliers by hour     |
| Correlation          | `unified_timeline` + `anchor_events`   | Builds event graphs, links actors          |
| CRUD Analysis        | `unified_timeline` (DB source_type)    | Extracts CREATE/READ/UPDATE/DELETE patterns|
| Network / Exfil      | `unified_timeline` (FW/VPN types)      | Session analysis, volume tracking          |
| Depth & Impact       | All downstream outputs + timeline      | Cross-module aggregation                   |
| Report Writer        | `unified_timeline` + `anchor_events`   | Narrative timeline section in reports      |

## API Endpoints

| Method | Endpoint                                | Purpose                     |
|--------|------------------------------------------|-----------------------------|
| POST   | `/api/cases/{id}/timeline/build`        | Build / rebuild timeline     |
| GET    | `/api/cases/{id}/timeline`              | Query events (with filters)  |
| GET    | `/api/cases/{id}/timeline/anchors`      | List anchor events           |
| POST   | `/api/cases/{id}/timeline/anchors`      | Toggle anchor on/off         |
| GET    | `/api/cases/{id}/timeline/stats`        | Summary statistics           |

## Chain of Custody
- `TIMELINE_BUILT` event with hash of the complete normalised dataset.
- `ANCHOR_TOGGLED` event when investigators manually pin/unpin events.
