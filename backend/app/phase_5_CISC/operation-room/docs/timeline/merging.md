# Event Merging & Ordering

## Purpose
Combine events from all log sources into a single, chronologically ordered timeline.

## Algorithm

```
1. SELECT * FROM raw_events WHERE case_id = ? ORDER BY timestamp ASC
2. For each event:
   a. Parse & normalise timestamp → UTC
   b. Classify severity from action
   c. Generate tl_event_id (UUID)
   d. INSERT INTO unified_timeline
3. Run anchor detection on sorted events
4. Hash the full timeline → evidence_hashes + CoC
```

## Re-run Behaviour
- **New evidence imported:** Investigators click "Rebuild" → `force_rebuild = true` wipes and rebuilds.
- **Scope change:** Same rebuild path, optionally filtering by new source_types / time range.
- Each rebuild generates a new CoC event with the new hash.

## Filtering Options

| Filter       | Parameter     | SQL                          |
|--------------|---------------|------------------------------|
| Actor        | `actor`       | `actor = ?`                  |
| Source type   | `source_type` | `source_type = ?`           |
| Severity     | `severity`    | `severity = ?`               |
| Anchors only | `anchors_only`| `is_anchor = TRUE`          |
| Time range   | `time_start/end` | `normalised_ts >= ? / <= ?` |
| Keyword      | `keyword`     | `LIKE %keyword%` on action, target, detail |

## Pagination
Default: 500 events, max: 5000. Use `limit` + `offset` query params.
