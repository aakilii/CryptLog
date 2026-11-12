"""
Storage abstraction layer.

LocalStorageBackend stores artifacts on disk.
Future: swap to S3StorageBackend without touching any callers.
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from packages.shared.integrity import artifact_id, hash_bytes


class StorageBackend(ABC):
    """Abstract storage interface — all implementations must follow this contract."""

    @abstractmethod
    def put(self, case_id: str, data: bytes, ext: str = '') -> dict:
        """Store bytes, return {artifact_id, path, size}."""
        ...

    @abstractmethod
    def get(self, case_id: str, aid: str) -> Optional[bytes]:
        """Retrieve bytes by artifact_id."""
        ...

    @abstractmethod
    def exists(self, case_id: str, aid: str) -> bool:
        ...

    @abstractmethod
    def delete(self, case_id: str, aid: str) -> bool:
        ...


class LocalStorageBackend(StorageBackend):
    """Stores artifacts on disk at data/cases/{case_id}/artifacts/{artifact_id}."""

    def __init__(self, base_dir: str = "data/cases"):
        self.base = Path(base_dir)

    def _artifact_dir(self, case_id: str) -> Path:
        d = self.base / case_id / "artifacts"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def put(self, case_id: str, data: bytes, ext: str = '') -> dict:
        aid = artifact_id(data)
        filename = f"{aid}{ext}"
        path = self._artifact_dir(case_id) / filename
        path.write_bytes(data)
        return {
            "artifact_id": aid,
            "path": str(path),
            "size": len(data),
            "hash": hash_bytes(data),
        }

    def get(self, case_id: str, aid: str) -> Optional[bytes]:
        d = self._artifact_dir(case_id)
        # Find file with any extension matching the artifact id
        for f in d.iterdir():
            if f.stem == aid:
                return f.read_bytes()
        return None

    def exists(self, case_id: str, aid: str) -> bool:
        d = self._artifact_dir(case_id)
        return any(f.stem == aid for f in d.iterdir()) if d.exists() else False

    def delete(self, case_id: str, aid: str) -> bool:
        d = self._artifact_dir(case_id)
        for f in d.iterdir():
            if f.stem == aid:
                f.unlink()
                return True
        return False


# ── Singleton ──────────────────────────────────────────────
_backend: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = LocalStorageBackend()
    return _backend
