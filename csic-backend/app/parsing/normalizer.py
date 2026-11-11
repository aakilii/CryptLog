import pandas as pd
from datetime import datetime


def normalize_logs(df: pd.DataFrame, raw_hash: str, audit_id: str):
    df = df.copy()

    df.columns = [col.lower() for col in df.columns]

    if "timestamp" not in df.columns:
        df["timestamp"] = datetime.utcnow()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")


    df["user"] = df.get("user", None)
    df["source_ip"] = df.get("ip", df.get("source_ip", None))
    df["action"] = df.get("action", None)
    df["status"] = df.get("status", None)


    df["audit_id"] = audit_id
    df["raw_hash"] = raw_hash

    return df[
        [
            "audit_id",
            "timestamp",
            "user",
            "source_ip",
            "action",
            "status",
            "raw_hash",
        ]
    ]
