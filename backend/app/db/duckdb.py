import os
from pathlib import Path

import duckdb

_IS_VERCEL = bool(os.environ.get("VERCEL"))
BASE_DIR = Path(__file__).resolve().parent.parent.parent

if _IS_VERCEL:
    DUCKDB_PATH = "/tmp/csic-data/analytics.duckdb"
else:
    DUCKDB_PATH = str(BASE_DIR / "data" / "analytics.duckdb")


def get_duckdb_connection():
    Path(DUCKDB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(DUCKDB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
             audit_id VARCHAR,
            timestamp TIMESTAMP,
            user VARCHAR,
            source_ip VARCHAR,
            action VARCHAR,
            status VARCHAR,
            raw_hash VARCHAR
        )
    """)

    return conn
