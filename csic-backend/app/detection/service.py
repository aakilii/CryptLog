from pathlib import Path
import duckdb

from app.detection.model import train_isolation_forest
from app.features.generator import generate_features


HOT_DB = "data/hot/analytics.duckdb"


def load_cold_into_hot():
    try:
        files = list(Path("data/parquet").glob("audit_id=*/**/*.parquet"))
        if not files:
            print("No Parquet files found")
            return False

        file_paths = [str(f).replace("\\", "/") for f in files]

        conn = duckdb.connect(HOT_DB)
        conn.execute("""
            CREATE OR REPLACE TABLE logs AS
            SELECT * FROM read_parquet('data/parquet/**/part_*.parquet', union_by_name=true)
        """)
        row_count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        conn.close()

        print(f"Loaded {row_count} rows from {len(file_paths)} Parquet files")
        return row_count > 0

    except Exception as e:
        print(f"Error loading cold into hot: {e}")
        return False


def run_detection():
    try:
        if not load_cold_into_hot():
            return {"status": "no_data", "message": "No parquet files found"}

        conn = duckdb.connect(HOT_DB)

        df = conn.execute("SELECT * FROM logs").fetchdf()
        if df.empty:
            conn.close()
            return {"status": "no_logs"}

        if len(df) < 5:
            conn.close()
            return {
                "status": "insufficient_data",
                "message": "Need at least 5 rows for stable anomaly detection"
            }

        if "timestamp" in df.columns:
            df["timestamp"] = df["timestamp"].astype("datetime64[ns]")

        feature_df = generate_features(df)

        model, scaler, scores, predictions = train_isolation_forest(feature_df)

        feature_df["anomaly_score"] = scores
        feature_df["is_anomaly"] = (predictions == -1).astype(int)

        min_score = feature_df["anomaly_score"].min()
        max_score = feature_df["anomaly_score"].max()

        if max_score - min_score == 0:
            feature_df["risk_score"] = 0
        else:
            feature_df["risk_score"] = (
                100 * (max_score - feature_df["anomaly_score"]) / (max_score - min_score)
            )

        conn.execute("DROP TABLE IF EXISTS detection_results")
        conn.register("result_df", feature_df)
        conn.execute("CREATE TABLE detection_results AS SELECT * FROM result_df")
        conn.close()

        return {
            "status": "detection_complete",
            "total_rows": len(feature_df),
            "anomalies_detected": int(feature_df["is_anomaly"].sum())
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
