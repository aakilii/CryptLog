# Anchor Event Detection

## Purpose
Automatically flag the first occurrence of key forensic events per actor to help investigators quickly identify the start of suspicious activity.

## Auto-Detection Rules

| Source | Trigger Actions                         | Label                          |
|--------|-----------------------------------------|--------------------------------|
| AUTH   | LOGIN_SUCCESS, LOGIN_FAILED             | First authentication event     |
| VPN    | VPN_CONNECT                             | First VPN session              |
| DB     | SELECT, INSERT, UPDATE, DELETE, EXPORT  | First database access          |
| FW     | DENY, DROP                              | First firewall block           |
| FILE   | FILE_READ, FILE_WRITE, FILE_DELETE      | First file-system access       |
| EPP    | MALWARE_DETECTED, QUARANTINE            | First endpoint security alert  |
| *      | Any HIGH-severity action                | High-severity: {action}        |

## Manual Anchors
Investigators can click the pin icon (○ → 📌) on any timeline event to toggle anchor status. Manual anchors are stored with `auto_detected = FALSE`.

## Storage
Anchors are stored in two locations:
- `anchor_events` table (dedicated lookup table)
- `unified_timeline.is_anchor` flag (for efficient querying)
