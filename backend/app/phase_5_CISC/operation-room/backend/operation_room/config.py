from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application configuration — loaded from environment or .env file."""

    # ── Paths ────────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    CASES_DIR: Path = DATA_DIR / "cases"
    AUDIT_LOG_PATH: Path = DATA_DIR / "audit_log.jsonl"

    # ── NLP Query Agent ──────────────────────────────────────────────────
    NLP_AGENT_URL: str = "http://localhost:9000"  # mock default

    # ── Phase 3 API (S3 cold storage query) ───────────────────────────
    PHASE3_API_BASE: str = "http://127.0.0.1:8000/api/phase3"

    # ── Hashing ──────────────────────────────────────────────────────────
    HASH_ALGORITHM: str = "sha256"  # sha256 | sha512 | blake2b

    # ── LLM Provider ────────────────────────────────────────────────────
    LLM_PROVIDER: str = "ollama"               # ollama | gemini
    LLM_MODEL: str = "gemini-2.5-flash"        # model name 
    OLLAMA_URL: str = "http://localhost:11434"
    GEMINI_API_KEY: str = ""                   # Single Google Gemini API key
    GEMINI_API_KEYS: str = ""                  # Comma-separated multiple keys
    KEY_ROTATION: str = "round_robin"          # round_robin | random | least_used

    # ── Embedding Configuration (Oracle 26AI Open-Source) ────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # all-MiniLM-L6-v2 | all-mpnet-base-v2
    EMBEDDING_DEVICE: str = "auto"             # auto | cpu | cuda
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DIMENSION: int = 384             # 384 for MiniLM, 768 for mpnet

    # ── Vector Store Configuration ───────────────────────────────────────
    VECTOR_STORE_PATH: str = "./data/vectordb"
    VECTOR_STORE_RESET_ON_STARTUP: bool = False
    GLOBAL_DB_PATH: str = "./data/global.duckdb"

    # ── Chain‑of‑Custody verbosity ───────────────────────────────────────
    COC_VERBOSITY: str = "STANDARD"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    model_config = {"env_prefix": "OPROOM_", "env_file": ".env", "extra": "ignore"}
    
    def get_gemini_keys(self) -> list[str]:
        """Get all Gemini API keys as a list."""
        keys = []
        # Check for comma-separated keys first
        if self.GEMINI_API_KEYS:
            keys.extend([k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()])
        # Check for single key
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY not in keys:
            keys.append(self.GEMINI_API_KEY)
        # Check for numbered keys (GEMINI_API_KEY_1 through GEMINI_API_KEY_10)
        for i in range(1, 11):
            key = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
            if key and key not in keys:
                keys.append(key)
        return keys


settings = Settings()

# Ensure data directories exist at import time
os.makedirs(settings.CASES_DIR, exist_ok=True)
os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)
