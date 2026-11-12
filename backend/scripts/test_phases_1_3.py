from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
UPLOAD_SOURCE = os.getenv("UPLOAD_SOURCE", "manual")
UPLOADER = os.getenv("UPLOADER", "phase1_test")


SAMPLE_LOG = """Mar 19 10:01:02 host sshd[123]: Failed password for admin from 192.168.1.22 port 55234 ssh2 password=SuperSecret123!
Mar 19 10:01:05 host nginx[222]: Authorization: Bearer abcdefghijklmnopqrstuvwxyz.12345 token used by user=test@example.com
Mar 19 10:01:07 host app[333]: Aadhaar 1234-5678-9012 submitted during onboarding
"""


def _ok(resp: httpx.Response) -> httpx.Response:
    try:
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"HTTP {resp.status_code} {resp.url}\n{resp.text}") from e
    return resp


def phase1_upload(client: httpx.Client) -> Dict[str, Any]:
    files = {
        "file": ("phase1_sample.log", SAMPLE_LOG.encode("utf-8"), "text/plain"),
    }
    data = {"source": UPLOAD_SOURCE, "uploader": UPLOADER}
    r = _ok(client.post(f"{BASE_URL}/api/ingestion/upload-log", files=files, data=data, timeout=60))
    return r.json()


def phase2_process(client: httpx.Client, audit_id: str) -> Dict[str, Any]:
    payload = {"audit_id": audit_id, "file_path": "", "source_ip": "127.0.0.1"}
    r = _ok(client.post(f"{BASE_URL}/api/phase2/process", json=payload, timeout=180))
    return r.json()


def phase2_commit(client: httpx.Client, staging_id: str) -> Dict[str, Any]:
    payload = {"confirm": True, "human_overrides": None}
    r = _ok(client.post(f"{BASE_URL}/api/phase2/commit/{staging_id}", json=payload, timeout=180))
    return r.json()


def phase3_ingest_from_phase2(client: httpx.Client, *, lineage: str, target_user: str) -> Dict[str, Any]:
    payload = {
        "Target_User": target_user,
        "Notes": SAMPLE_LOG,
        "Lineage": lineage,
    }
    r = _ok(client.post(f"{BASE_URL}/api/phase3/phase2_webhook", json=payload, timeout=60))
    return r.json()


def phase3_query(client: httpx.Client, *, target_user: str) -> Dict[str, Any]:
    payload = {"depth": 2, "Target_User": target_user, "limit": 25, "offset": 0}
    r = _ok(client.post(f"{BASE_URL}/api/phase3/graphql_query", json=payload, timeout=60))
    return r.json()


def main() -> None:
    with httpx.Client() as client:
        # Phase 1
        p1 = phase1_upload(client)
        audit_id = p1["id"]
        filename = p1["filename"]
        print("PHASE1_OK", {"audit_id": audit_id, "filename": filename, "sha256": p1.get("sha256_hash")})

        # Phase 2
        p2 = phase2_process(client, audit_id)
        staging_id = p2.get("staging_id") or p2.get("staging_ids", [None])[0]
        if not staging_id:
            raise RuntimeError(f"Phase2 did not return staging_id: {p2}")
        print("PHASE2_STAGED", {"staging_id": staging_id, "rows_processed": p2.get("rows_processed")})

        c2 = phase2_commit(client, staging_id)
        print("PHASE2_COMMITTED", {"staging_id": c2.get("staging_id"), "final_row_hash": c2.get("final_row_hash")})

        # Phase 3 (Phase2 -> Phase3 signal is not wired in Phase2 yet; inject manually for now)
        p3_accept = phase3_ingest_from_phase2(client, lineage=staging_id, target_user="admin")
        print("PHASE3_ACCEPTED", p3_accept)

        # background task executes; give it a moment
        time.sleep(1.5)

        p3q = phase3_query(client, target_user="admin")
        print("PHASE3_QUERY", {"count": p3q.get("count"), "sample": (p3q.get("data") or [])[:2]})


if __name__ == "__main__":
    main()

