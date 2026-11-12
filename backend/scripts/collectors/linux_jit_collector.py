#!/usr/bin/env python3
"""
Linux JIT collector for Phase-1 secure ingestion.

Flow:
1) Request JIT session from /api/ingestion/manual
2) Collect logs from journalctl and/or files into a local bundle
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
from typing import Iterable

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


def _iter_journal_lines(since: str | None, until: str | None) -> Iterable[str]:
    cmd = ["journalctl", "--no-pager", "-o", "short-iso"]
    if since:
        cmd.extend(["--since", since])
    if until:
        cmd.extend(["--until", until])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"journalctl failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    for line in proc.stdout.splitlines():
        yield line


def _iter_file_lines(paths: list[str]) -> Iterable[tuple[str, str]]:
    for p in paths:
        path = Path(p).expanduser().resolve()
        if not path.exists() or not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                yield str(path), line.rstrip("\n")


def build_bundle(
    out_dir: Path,
    include_journal: bool,
    journal_since: str | None,
    journal_until: str | None,
    file_paths: list[str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    bundle = out_dir / f"linux_logs_{host}_{_iso_now()}.jsonl"

    with bundle.open("w", encoding="utf-8") as out:
        if include_journal:
            for line in _iter_journal_lines(journal_since, journal_until):
                rec = {"source": "journalctl", "host": host, "raw": line}
                out.write(json.dumps(rec, ensure_ascii=True) + "\n")

        for src, line in _iter_file_lines(file_paths):
            rec = {"source": src, "host": host, "raw": line}
            out.write(json.dumps(rec, ensure_ascii=True) + "\n")

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
        tempfile.mkdtemp(prefix="jit_linux_collector_")
    )
    bundle = build_bundle(
        out_dir=bundle_dir,
        include_journal=not args.no_journal,
        journal_since=args.journal_since,
        journal_until=args.journal_until,
        file_paths=args.file or [],
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
        description="Linux JIT log collector for Phase-1 WS ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/collectors/linux_jit_collector.py --api-base http://127.0.0.1:8000\n"
            "  python scripts/collectors/linux_jit_collector.py --file /var/log/auth.log --file /var/log/syslog\n"
            "  python scripts/collectors/linux_jit_collector.py --journal-since '2026-03-19 00:00:00'\n"
        ),
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--no-journal", action="store_true", help="Do not collect from journalctl")
    parser.add_argument("--journal-since", default=None, help="journalctl --since value")
    parser.add_argument("--journal-until", default=None, help="journalctl --until value")
    parser.add_argument("--file", action="append", help="Additional log file path (repeatable)")
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

