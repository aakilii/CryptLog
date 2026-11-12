import duckdb
from app.features.generator import generate_features
from app.detection.service import load_cold_into_hot


def compute_features(audit_id=None):

    if not load_cold_into_hot():
        return {"status": "no_data"}

    conn = duckdb.connect("data/hot/analytics.duckdb")
    df = conn.execute("SELECT * FROM logs").fetchdf()

    if audit_id and "audit_id" in df.columns:
        df = df[df["audit_id"] == audit_id]

    if df.empty:
        conn.close()
        return {"status": "no_logs"}

    df["timestamp"] = df["timestamp"].astype("datetime64[ns]")

    feature_df = generate_features(df)

    conn.execute("DROP TABLE IF EXISTS features")
    conn.register("feature_df", feature_df)
    conn.execute("CREATE TABLE features AS SELECT * FROM feature_df")
    conn.close()

    return {"status": "features_generated", "rows": len(feature_df)}
