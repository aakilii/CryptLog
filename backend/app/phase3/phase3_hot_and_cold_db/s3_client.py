"""
AWS S3 client for Phase 3 cold storage.

Supports real AWS S3 and S3-compatible services (MinIO, LocalStack) via
S3_ENDPOINT_URL. When S3_BUCKET_NAME is unset, all operations gracefully
degrade to no-ops so the rest of Phase 3 can fall back to local Parquet.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional


def is_s3_enabled() -> bool:
    return bool(os.getenv("S3_BUCKET_NAME", "").strip())


def _bucket() -> str:
    return os.getenv("S3_BUCKET_NAME", "").strip()


@lru_cache(maxsize=1)
def get_s3_client():
    """Return a boto3 S3 client configured from env vars."""
    import boto3

    kwargs: dict = {
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
    }
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def upload_parquet(key: str, local_path: Path) -> None:
    """Upload a local Parquet file to S3."""
    client = get_s3_client()
    client.upload_file(str(local_path), _bucket(), key)


def download_parquet(key: str) -> bytes:
    """Download a Parquet object from S3 and return its bytes."""
    client = get_s3_client()
    buf = io.BytesIO()
    client.download_fileobj(_bucket(), key, buf)
    return buf.getvalue()


def list_parquets(prefix: str) -> List[str]:
    """List all .parquet keys under the given S3 prefix."""
    client = get_s3_client()
    keys: List[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=_bucket(), Prefix=prefix):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(".parquet"):
                keys.append(k)
    return keys


def delete_parquet(key: str) -> None:
    """Delete a single Parquet object from S3."""
    client = get_s3_client()
    client.delete_object(Bucket=_bucket(), Key=key)


def s3_parquet_uri(key: str) -> str:
    """Return the s3:// URI for a key."""
    return f"s3://{_bucket()}/{key}"


def cold_s3_key(date_str: str, lineage: str, staging: bool = False) -> str:
    """Build the canonical S3 key for a cold Parquet file."""
    folder = "_staging" if staging else "events"
    return f"phase3/{folder}/{date_str}/{lineage}.parquet"


def configure_duckdb_s3(con) -> None:
    """
    Install and configure the httpfs extension on a DuckDB connection
    so it can read s3:// URIs directly.
    """
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{os.getenv('AWS_REGION', 'us-east-1')}';")
    con.execute(f"SET s3_access_key_id='{os.getenv('AWS_ACCESS_KEY_ID', '')}';")
    con.execute(f"SET s3_secret_access_key='{os.getenv('AWS_SECRET_ACCESS_KEY', '')}';")
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    if endpoint:
        clean = endpoint.replace("https://", "").replace("http://", "")
        con.execute(f"SET s3_endpoint='{clean}';")
        if endpoint.startswith("http://"):
            con.execute("SET s3_use_ssl=false;")
            con.execute("SET s3_url_style='path';")
