import os
from app.parsing.detector import detect_format
from app.parsing.parser import parse_json, parse_csv, parse_text
from app.parsing.normalizer import normalize_logs
import os
from datetime import datetime

COLD_PATH = "data/parquet/logs.parquet"

def save_to_cold_storage(df, audit_id: str):

    base_path = "data/parquet"
    partition_path = os.path.join(base_path, f"audit_id={audit_id}")

    os.makedirs(partition_path, exist_ok=True)

    file_path = os.path.join(
        partition_path,
        f"part_{int(datetime.utcnow().timestamp())}.parquet"
    )

    try:
        df.to_parquet(
            file_path,
            engine="pyarrow",
            compression="snappy"
        )
    except ImportError:
        # Fallback if pyarrow not available
        df.to_parquet(
            file_path,
            engine="fastparquet",
            compression="snappy"
        )



def process_log_file(filename: str, content: bytes, raw_hash: str, audit_id: str):

    format_type = detect_format(content, filename)

    if format_type == "json":
        df = parse_json(content)
    elif format_type == "csv":
        df = parse_csv(content)
    else:
        df = parse_text(content)

    normalized_df = normalize_logs(df, raw_hash, audit_id)

    save_to_cold_storage(normalized_df, audit_id)



    return {
        "rows_saved_to_cold": len(normalized_df),
        "format": format_type
    }
