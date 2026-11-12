# Data Normalisation

## Purpose
Transform heterogeneous log records from the `raw_events` table into a uniform schema in `unified_timeline`.

## Field Mapping

| unified_timeline      | Raw Source                                      |
|-----------------------|-------------------------------------------------|
| `normalised_ts`       | `raw_events.timestamp` → parsed to UTC          |
| `utc_offset`          | Detected or `+00:00` (default)                  |
| `source_type`         | Copied from `raw_events.source_type`            |
| `source_system`       | Copied from `raw_events.source_system`          |
| `actor`               | `raw_events.actor`                              |
| `action`              | `raw_events.action` (uppercased)                |
| `target`              | `raw_events.target`                             |
| `severity`            | Classified from action (HIGH / MEDIUM / INFO)   |
| `detail`              | `raw_events.detail` (JSON string)               |

## Timestamp Handling

1. **ISO-8601** is the canonical format.
2. All timestamps are normalised to UTC with the original offset stored.
3. If a timestamp cannot be parsed, the current time is used and a warning is logged.

## Severity Classification

| Severity | Actions                                                              |
|----------|----------------------------------------------------------------------|
| HIGH     | LOGIN_FAILED, ACCOUNT_LOCKED, MALWARE_DETECTED, DENY, DROP, DELETE  |
| MEDIUM   | MFA_CHALLENGE, PASSWORD_CHANGE, VPN_FAILED, UPDATE, FILE_WRITE      |
| INFO     | All other actions                                                    |
