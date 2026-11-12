# CRUD Heuristics — Anomalous Pattern Detection

## Detection Rules

### Rule 1: Off-Hours Bulk Reads
```
IF crud_type = READ AND (hour < 7 OR hour > 20)
THEN flag: "Bulk read outside business hours"
```
**Rationale:** Data exfiltration often occurs after hours when monitoring is reduced.

### Rule 2: High-Sensitivity Deletes
```
IF crud_type = DELETE AND sensitivity IN (CRITICAL, HIGH)
THEN flag: "Delete on {sensitivity}-sensitivity data"
```
**Rationale:** Deleting critical data may indicate evidence destruction or sabotage.

### Rule 3: Audit Trail Tampering
```
IF target CONTAINS "audit" AND crud_type IN (DELETE, UPDATE)
THEN flag: "Modification of audit trail data"
```
**Rationale:** Attackers often attempt to cover tracks by modifying audit logs.

### Rule 4: High-Anomaly Writes
```
IF anomaly_score > 0.7 AND crud_type IN (CREATE, UPDATE, DELETE)
THEN flag: "High anomaly ({score}) + write operation"
```
**Rationale:** ML-confirmed anomaly performing destructive operations.

### Rule 5: High-Severity Data Reads
```
IF severity = HIGH AND crud_type = READ
THEN flag: "High-severity data read/export"
```
**Rationale:** Flagged event accessing sensitive data.

### Rule 6: Large Data Reads
```
IF volume_bytes > 100,000 AND crud_type = READ
THEN flag: "Large data read ({bytes} bytes)"
```
**Rationale:** Bulk data downloads suggest exfiltration.

### Rule 7: Burst Activity (Sequential Pattern)
```
IF COUNT(events by same actor in 5 minutes) > 10
THEN flag all events: "Burst activity (10+ events in 5min)"
```
**Rationale:** Automated/scripted activity, potential bot or tool-based attack.

## Chain-of-Custody Entry Example

```json
{
  "coc_event_id": "coc-a1b2c3d4",
  "case_id": "CASE-FORENSIC-001",
  "actor": "crud_agent",
  "event_type": "CRUD_ANALYSIS_COMPLETED",
  "target_artefact": "crud_run:run-e5f6g7h8",
  "timestamp_utc": "2026-03-27T03:15:00Z",
  "justification": "Classified CRUD operations with sensitivity and risk analysis",
  "hash_after": "sha256:a4f8c2e1...",
  "details": {
    "run_id": "run-e5f6g7h8",
    "total_events": 385,
    "high_risk": 42,
    "crud_counts": {"CREATE": 45, "READ": 210, "UPDATE": 78, "DELETE": 52},
    "summaries": 127
  }
}
```
