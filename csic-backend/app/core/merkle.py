"""
app/core/merkle.py
------------------
Cryptographic Merkle Tree Implementation for chunk-level integrity sealing.
Used by the secure WebSocket ingestion pipeline to produce a tamper-evident
root hash from ordered chunk hashes.
"""

import hashlib
from typing import List
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_pair_bytes(left: bytes, right: bytes) -> bytes:
    """Hash two 32-byte sibling nodes into a 32-byte parent node."""
    h = hashlib.sha256()
    h.update(left)
    h.update(right)
    return h.digest()


def _normalize_layer_bytes(layer: List[bytes]) -> List[bytes]:
    """
    Ensure an even number of nodes per layer by duplicating the last node
    when the layer length is odd (standard Bitcoin-style Merkle padding).
    """
    if len(layer) % 2 != 0:
        layer = layer + [layer[-1]]
    return layer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_merkle_root(chunk_hashes: List[str]) -> str:
    """
    Build a Merkle root from an ordered list of SHA-256 chunk hashes.

    Args:
        chunk_hashes: Ordered list of hex-encoded SHA-256 digests, one per
                      received chunk. Must not be empty.

    Returns:
        Hex-encoded Merkle root hash.

    Raises:
        ValueError: If chunk_hashes is empty.
    """
    if not chunk_hashes:
        raise ValueError("Cannot build Merkle root from an empty chunk list.")

    # Leaf nodes — convert hex digests to raw bytes ONCE.
    # This avoids repeated bytes.fromhex() calls per tree level.
    try:
        current_layer: List[bytes] = [bytes.fromhex(h) for h in chunk_hashes]
    except ValueError as exc:
        raise ValueError(f"Invalid hex digest in chunk_hashes: {exc}") from exc

    logger.debug(
        f"[Merkle] Building tree from {len(current_layer)} leaf nodes."
    )

    while len(current_layer) > 1:
        current_layer = _normalize_layer_bytes(current_layer)
        next_layer: List[bytes] = []
        for i in range(0, len(current_layer), 2):
            next_layer.append(_sha256_pair_bytes(current_layer[i], current_layer[i + 1]))
        current_layer = next_layer

    root_hex = current_layer[0].hex()
    logger.debug(f"[Merkle] Root hash computed: {root_hex}")
    return root_hex


def build_merkle_proof(chunk_hashes: List[str], index: int) -> List[dict]:
    """
    Generate a Merkle proof (audit path) for a single leaf at *index*.

    Returns a list of {"sibling": <hash>, "direction": "left"|"right"}
    entries that can be used by an external verifier to reconstruct the root
    without possessing all chunks.

    Args:
        chunk_hashes: Full ordered list of chunk hashes.
        index: Zero-based index of the leaf to prove.

    Returns:
        List of proof steps.
    """
    if not chunk_hashes:
        raise ValueError("Chunk hash list is empty.")
    if index < 0 or index >= len(chunk_hashes):
        raise ValueError(f"Index {index} out of range [0, {len(chunk_hashes)}).")

    # Work on raw bytes internally; return hex siblings for external use.
    current_layer = [bytes.fromhex(h) for h in chunk_hashes]
    proof: List[dict] = []
    current_index = index

    while len(current_layer) > 1:
        current_layer = _normalize_layer_bytes(current_layer)
        if current_index % 2 == 0:
            sibling_index = current_index + 1
            direction = "right"
        else:
            sibling_index = current_index - 1
            direction = "left"

        proof.append({
            "sibling": current_layer[sibling_index].hex(),
            "direction": direction,
        })

        # Build next layer
        next_layer: List[bytes] = []
        for i in range(0, len(current_layer), 2):
            next_layer.append(_sha256_pair_bytes(current_layer[i], current_layer[i + 1]))

        current_layer = next_layer
        current_index //= 2

    return proof


def verify_merkle_proof(
    leaf_hash: str,
    proof: List[dict],
    expected_root: str,
) -> bool:
    """
    Verify a Merkle proof for a single leaf.

    Args:
        leaf_hash: Hex-encoded SHA-256 hash of the leaf.
        proof: List of proof steps returned by build_merkle_proof().
        expected_root: Hex-encoded Merkle root to verify against.

    Returns:
        True if the proof is valid, False otherwise.
    """
    current = bytes.fromhex(leaf_hash)
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        direction = step["direction"]
        if direction == "right":
            current = _sha256_pair_bytes(current, sibling)
        else:
            current = _sha256_pair_bytes(sibling, current)

    valid = current.hex() == expected_root
    if not valid:
        logger.warning(
            f"[Merkle] Proof verification failed. "
            f"Computed root={current.hex()}, expected={expected_root}"
        )
    return valid


def verify_merkle_integrity(chunk_hashes: List[str], expected_root: str) -> bool:
    """
    Full re-computation integrity check: rebuild the Merkle root from all
    chunk hashes and compare against a stored expected root.

    Args:
        chunk_hashes: Ordered chunk hash list.
        expected_root: Previously stored Merkle root.

    Returns:
        True if roots match, False otherwise.
    """
    try:
        computed_root = build_merkle_root(chunk_hashes)
        match = computed_root == expected_root
        if not match:
            logger.error(
                f"[Merkle] Integrity mismatch! "
                f"Computed={computed_root}, Stored={expected_root}"
            )
        else:
            logger.info("[Merkle] Integrity check passed.")
        return match
    except Exception as exc:
        logger.error(f"[Merkle] Integrity check exception: {exc}")
        return False
