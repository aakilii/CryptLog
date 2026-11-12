from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class VerificationResult:
    valid: bool
    reason: str
    merkle_root: str | None = None


class PDFIntegrityService:
    """Utility service for PDF integrity primitives."""

    @staticmethod
    def hash_element(element: dict[str, Any]) -> str:
        canonical = json.dumps(element, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def build_merkle_tree(leaf_hashes: list[str]) -> str:
        if not leaf_hashes:
            return hashlib.sha256(b"empty").hexdigest()

        nodes = list(leaf_hashes)
        while len(nodes) > 1:
            if len(nodes) % 2 == 1:
                nodes.append(nodes[-1])
            next_layer: list[str] = []
            for index in range(0, len(nodes), 2):
                combined = f"{nodes[index]}{nodes[index + 1]}"
                next_layer.append(hashlib.sha256(combined.encode("utf-8")).hexdigest())
            nodes = next_layer
        return nodes[0]

    @staticmethod
    def hash_pdf(pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()

    @staticmethod
    def build_export_manifest(
        *,
        case_id: str,
        doc_id: str,
        actor: str,
        focus_mode: str,
        generation_manifest: dict[str, Any],
        pdf_hash: str,
        signature: str,
        signature_algorithm: str,
        public_key_pem: str,
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "doc_id": doc_id,
            "actor": actor,
            "focus_mode": focus_mode,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "engine": "reportlab",
            "generation": generation_manifest,
            "pdf_sha256": pdf_hash,
            "signature": signature,
            "signature_algorithm": signature_algorithm,
            "public_key_pem": public_key_pem,
        }
