"""Cryptographic hashing utilities for evidence integrity."""

import hashlib
import json
from typing import Any


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Hash a raw byte payload and return the hex digest."""
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def hash_json(obj: Any, algorithm: str = "sha256") -> str:
    """Deterministically hash a JSON‑serialisable object following RFC 8785.

    Objects are serialised strictly via canonicaljson.
    Dates/custom objects are stringified first.
    """
    import canonicaljson
    # Pre-process unsupported types (like datetime) using standard dumps/loads
    clean_obj = json.loads(json.dumps(obj, default=str))
    canonical_bytes = canonicaljson.encode_canonical_json(clean_obj)
    return hash_bytes(canonical_bytes, algorithm)


def hash_records(records: list[dict], algorithm: str = "sha256") -> str:
    """Hash a list of log records."""
    return hash_json(records, algorithm)
