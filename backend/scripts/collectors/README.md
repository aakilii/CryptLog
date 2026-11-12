# JIT Remote Collectors

These collectors pull logs from remote systems and upload them through the existing Phase-1 secure WebSocket ingestion pipeline.

## Files

- `scripts/collectors/linux_jit_collector.py`
- `scripts/collectors/windows_jit_collector.py`

## What they do

1. Request JIT session from `POST /api/ingestion/manual`
2. Collect local logs into a JSONL bundle
3. Stream bundle to `/ws/secure-stream/{session_id}` with:
   - per-chunk SHA-256
   - ordered chunk numbers
   - base64 chunk payload
4. Print final backend result (`audit_id`, `sha256`, `file_path`, `merkle_root`)

## Linux collector

### Example

```bash
python scripts/collectors/linux_jit_collector.py \
  --api-base http://127.0.0.1:8000 \
  --journal-since "2026-03-19 00:00:00" \
  --file /var/log/auth.log \
  --file /var/log/syslog
```

### Notes

- Requires `journalctl` for journald collection.
- Use `--no-journal` to skip journald.
- Chunk size must be `<= 5MB` (backend cap).

## Windows collector

### Example

```powershell
python scripts/collectors/windows_jit_collector.py `
  --api-base http://127.0.0.1:8000 `
  --log Security --log System --log Application `
  --since-iso 2026-03-19T00:00:00Z `
  --max-events-per-log 5000
```

### Notes

- Uses PowerShell `Get-WinEvent`.
- Security log access may require elevated privileges.
- Chunk size must be `<= 5MB` (backend cap).

## Backend compatibility

Collectors are compatible with current server protocol in:

- `app/ingestion/ws_router.py` (`/ws/secure-stream/{session_id}`)
- `app/ingestion/router.py` (`POST /api/ingestion/manual`)

