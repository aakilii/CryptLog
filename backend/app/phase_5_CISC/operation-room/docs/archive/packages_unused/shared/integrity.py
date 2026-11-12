"""
Shared canonicalisation + hashing utilities for Report Studio.

Uses RFC 8785 (JCS) JSON canonicalisation for deterministic hashing.
All integrity operations MUST use these functions — no duplicated implementations.
"""

import json
import hashlib
from typing import Any


def canonicalise(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalisation Scheme.
    
    Produces a deterministic byte representation:
    - Keys sorted lexicographically
    - No whitespace
    - Unicode escapes normalised
    """
    return json.dumps(
        obj, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, default=str
    ).encode('utf-8')


def sha256_hash(data: bytes) -> str:
    """SHA-256 hash → hex string prefixed with 'sha256:'."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def hash_object(obj: Any) -> str:
    """Canonicalise a Python object, then SHA-256 hash it."""
    return sha256_hash(canonicalise(obj))


def hash_bytes(data: bytes) -> str:
    """SHA-256 hash raw bytes."""
    return sha256_hash(data)


def verify_hash(obj: Any, expected_hash: str) -> bool:
    """Verify that an object's canonical hash matches the expected value."""
    return hash_object(obj) == expected_hash


def artifact_id(content: bytes) -> str:
    """Generate an artifact ID from content bytes (content-addressable)."""
    return hashlib.sha256(content).hexdigest()
