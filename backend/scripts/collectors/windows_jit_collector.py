#!/usr/bin/env python3
"""
Windows JIT collector for Phase-1 secure ingestion.

Flow:
1) Request JIT session from /api/ingestion/manual
2) Pull events from Windows Event Logs via PowerShell
3) Stream bundle over WebSocket secure-stream protocol in hashed chunks
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import shlex
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_api_base(url: str) -> str:
    url = url.strip().rstrip("/")
    return url.replace("://0.0.0.0", "://127.0.0.1")


def _to_ws_url(api_base: str, session_id: str) -> str:
    if api_base.startswith("https://"):
        ws_base = "wss://" + api_base[len("https://") :]
    elif api_base.startswith("http://"):
        ws_base = "ws://" + api_base[len("http://") :]
    else:
        raise ValueError(f"Unsupported API base URL: {api_base}")
    return f"{ws_base}/ws/secure-stream/{session_id}"


def build_bundle(
    out_dir: Path,
    logs: list[str],
    max_events_per_log: int,
    since_iso: str | None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    bundle = out_dir / f"windows_logs_{host}_{_iso_now()}.jsonl"

    log_list = ",".join(f"'{l}'" for l in logs)
    since_clause = (
        f"$startTime = [datetime]::Parse('{since_iso}').ToUniversalTime();"
        if since_iso
        else "$startTime = (Get-Date).ToUniversalTime().AddHours(-24);"
    )

    # Emit NDJSON lines from PowerShell for predictable parsing.
    ps_script = rf"""
$ErrorActionPreference = 'Stop'
{since_clause}
$logs = @({log_list})
foreach ($logName in $logs) {{
  try {{
    Get-WinEvent -FilterHashtable @{{LogName=$logName; StartTime=$startTime}} -MaxEvents {max_events_per_log} |
      ForEach-Object {{
        $obj = [ordered]@{{
          source = "win_eventlog:" + $logName
          host = "{host}"
          time_created = $_.TimeCreated.ToUniversalTime().ToString("o")
          event_id = $_.Id
          level = $_.LevelDisplayName
          provider = $_.ProviderName
          machine = $_.MachineName
          message = $_.Message
        }}
        $obj | ConvertTo-Json -Compress -Depth 4
      }}
  }} catch {{
    [ordered]@{{
      source = "win_eventlog:" + $logName
      host = "{host}"
      error = $_.Exception.Message
    }} | ConvertTo-Json -Compress -Depth 3
  }}
}}
"""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"PowerShell collector failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )

    with bundle.open("w", encoding="utf-8") as out:
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            out.write(line + "\n")

    return bundle


async def stream_file_ws(ws_url: str, file_path: Path, chunk_size: int) -> dict:
    filename = file_path.name
    total_size = file_path.stat().st_size
    total_chunks = (total_size + chunk_size - 1) // chunk_size

    async with websockets.connect(ws_url, max_size=None, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"type": "meta", "filename": filename}))
        try:
            _ = await asyncio.wait_for(ws.recv(), timeout=3)
        except Exception:
            pass

        with file_path.open("rb") as fh:
            chunk_number = 0
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                chunk_hash = hashlib.sha256(chunk).hexdigest()
                payload = {
                    "chunk_number": chunk_number,
                    "chunk_hash": chunk_hash,
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "is_final": chunk_number == total_chunks - 1,
                }
                await ws.send(json.dumps(payload))

                raw = await ws.recv()
                msg = json.loads(raw)
                status = msg.get("status")
                if status == "error":
                    raise RuntimeError(msg.get("detail", "WebSocket upload failed"))
                if status != "ok":
                    raise RuntimeError(f"Unexpected WS response: {msg}")
                if msg.get("chunk_number") != chunk_number:
                    raise RuntimeError(
                        f"Ack mismatch: sent={chunk_number} got={msg.get('chunk_number')}"
                    )
                chunk_number += 1

        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("status") == "error":
                raise RuntimeError(msg.get("detail", "Upload failed at finalize"))
            if msg.get("status") == "done":
                return msg.get("result") or msg


async def main_async(args: argparse.Namespace) -> None:
    api_base = _normalize_api_base(args.api_base)
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{api_base}/api/ingestion/manual")
        res.raise_for_status()
        session = res.json()
    session_id = session["session_id"]
    ws_url = _to_ws_url(api_base, session_id)

    bundle_dir = Path(args.bundle_dir).expanduser().resolve() if args.bundle_dir else Path(
        tempfile.mkdtemp(prefix="jit_windows_collector_")
    )
    bundle = build_bundle(
        out_dir=bundle_dir,
        logs=args.log,
        max_events_per_log=args.max_events_per_log,
        since_iso=args.since_iso,
    )
    if bundle.stat().st_size == 0:
        raise RuntimeError("Collected bundle is empty. Nothing to upload.")

    print(f"[collector] session_id={session_id}")
    print(f"[collector] ws_url={ws_url}")
    print(f"[collector] bundle={bundle} size={bundle.stat().st_size} bytes")
    result = await stream_file_ws(ws_url, bundle, args.chunk_size)
    print("[collector] upload complete:")
    print(json.dumps(result, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Windows JIT eventlog collector for Phase-1 WS ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/collectors/windows_jit_collector.py --api-base http://10.0.0.20:8000\n"
            "  python scripts/collectors/windows_jit_collector.py --log Security --log System --max-events-per-log 5000\n"
            "  python scripts/collectors/windows_jit_collector.py --since-iso 2026-03-18T00:00:00Z\n"
        ),
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument(
        "--log",
        action="append",
        default=["Security", "System", "Application"],
        help="Windows Event Log name (repeatable)",
    )
    parser.add_argument("--max-events-per-log", type=int, default=3000, help="Max events per log source")
    parser.add_argument("--since-iso", default=None, help="Start time ISO-8601 UTC (default last 24h)")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Chunk size bytes (default 1MB, max backend allows 5MB)",
    )
    parser.add_argument("--bundle-dir", default=None, help="Directory for generated bundle file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.chunk_size <= 0 or args.chunk_size > 5 * 1024 * 1024:
        raise SystemExit("--chunk-size must be between 1 and 5242880 bytes")
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[collector] cancelled by user")
    except Exception as exc:
        cmd = " ".join(shlex.quote(p) for p in os.sys.argv)
        print(f"[collector] failed: {exc}")
        print(f"[collector] command: {cmd}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

