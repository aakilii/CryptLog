# CRUD API Specification

## Base Path: `/api/cases/{case_id}/crud`

### POST `/run`
Execute the 5-node CRUD analysis pipeline.

**Request Body:**
```json
{
  "source_filters": ["DB", "FILE"],       // optional: filter by log source type
  "sensitivity_threshold": "LOW",          // optional: minimum sensitivity to include
  "time_start": "2025-01-15T00:00:00",    // optional: start of time range
  "time_end": "2025-01-16T00:00:00"       // optional: end of time range
}
```

**Response (200):**
```json
{
  "run_id": "uuid",
  "status": "completed",
  "total_events": 385,
  "crud_counts": {"CREATE": 45, "READ": 210, "UPDATE": 78, "DELETE": 52},
  "high_risk_count": 42,
  "summaries_count": 127
}
```

---

### GET `/events`
Get classified CRUD events with optional filters.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `run_id` | string | Specific run (default: latest) |
| `high_risk_only` | bool | Only return flagged events |
| `sensitivity` | string | Filter: LOW, MEDIUM, HIGH, CRITICAL |
| `crud_type` | string | Filter: CREATE, READ, UPDATE, DELETE |

**Response (200):** Array of `CrudEvent` objects:
```json
[
  {
    "crud_event_id": "uuid",
    "tl_event_id": "uuid",
    "crud_type": "DELETE",
    "target_object": "/data/customers",
    "sensitivity": "HIGH",
    "volume_bytes": 0,
    "is_high_risk": true,
    "risk_reason": "Delete on HIGH-sensitivity data",
    "anomaly_score": 0.823,
    "actor": "jdoe",
    "source_type": "DB",
    "normalised_ts": "2025-01-15T02:14:33"
  }
]
```

---

### GET `/summary`
Get aggregated user × object × operation matrix.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `run_id` | string | Specific run (default: latest) |

**Response (200):** Array of summary rows:
```json
[
  {
    "summary_id": "uuid",
    "actor": "jdoe",
    "target_object": "/data/payroll",
    "crud_type": "READ",
    "event_count": 15,
    "total_bytes": 245000,
    "avg_anomaly": 0.654,
    "max_sensitivity": "CRITICAL",
    "high_risk_count": 3,
    "first_seen": "2025-01-15T01:00:00",
    "last_seen": "2025-01-15T02:30:00"
  }
]
```

---

### GET `/runs`
List past CRUD analysis runs.

**Response (200):** Array of run objects with CRUD count breakdown.
