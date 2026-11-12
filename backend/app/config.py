import os
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_IS_VERCEL = bool(os.environ.get("VERCEL"))
_VERCEL_DATA_ROOT = Path("/tmp/csic-data")


class Settings(BaseSettings):
    """Backend-only settings. Unknown keys in `.env` (e.g. NEXT_PUBLIC_* for the Next.js app) are ignored."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    APP_NAME: str = "Forensic AI Engine"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///data/ledger.db"
    SQLITE_DB_PATH: str = "data/ledger.db"
    RAW_STORAGE_PATH: str = "data/raw"
    PARQUET_STORAGE_PATH: str = "data/parquet"

    # Phase-1 secure ingestion paths
    WORM_STORAGE_PATH: str = "data/worm"
    QUARANTINE_PATH: str = "data/quarantine"
    TEMP_CHUNKS_PATH: str = "data/temp"

    # JIT session TTL (minutes)
    SESSION_TTL_MINUTES: int = 30

    # Authentication
    SECRET_KEY: str = "change-this-secret-key-in-production-use-openssl-rand-hex-32"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def coerce_debug(cls, v: object) -> bool:
        """
        Accept string env-var values for DEBUG.
        Non-boolean strings like 'release'/'production'/'prod'/'false'/'0'
        are treated as False; everything else as True.
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() not in {"false", "0", "no", "off", "release", "production", "prod"}
        return bool(v)

    @model_validator(mode="after")
    def apply_vercel_paths(self) -> "Settings":
        """Vercel Lambda has a read-only project dir; use /tmp for ephemeral storage."""
        if not _IS_VERCEL:
            return self

        root = _VERCEL_DATA_ROOT
        self.SQLITE_DB_PATH = str(root / "ledger.db")
        self.DATABASE_URL = f"sqlite:///{self.SQLITE_DB_PATH}"
        self.RAW_STORAGE_PATH = str(root / "raw")
        self.PARQUET_STORAGE_PATH = str(root / "parquet")
        self.WORM_STORAGE_PATH = str(root / "worm")
        self.QUARANTINE_PATH = str(root / "quarantine")
        self.TEMP_CHUNKS_PATH = str(root / "temp")
        return self


settings = Settings()

# Ensure required directories exist at startup (writable on Vercel only under /tmp).
for _path in (
    settings.RAW_STORAGE_PATH,
    settings.PARQUET_STORAGE_PATH,
    settings.WORM_STORAGE_PATH,
    settings.QUARANTINE_PATH,
    settings.TEMP_CHUNKS_PATH,
    Path(settings.SQLITE_DB_PATH).parent,
):
    try:
        Path(_path).mkdir(parents=True, exist_ok=True)
    except OSError:
        # Never crash import on read-only filesystems; local dev may still warn elsewhere.
        pass
