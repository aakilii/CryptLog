import pandas as pd


def generate_features(df: pd.DataFrame):

    df = df.sort_values(by=["user", "timestamp"])

    df["login_time_delta"] = (
        df.groupby("user")["timestamp"]
        .diff()
        .dt.total_seconds()
        .fillna(0)
    )
    df["failed_flag"] = df["status"].apply(
        lambda x: 1 if str(x).lower() == "failed" else 0
    )
    df["failed_attempt_ratio"] = (
        df.groupby("user")["failed_flag"]
        .transform(lambda x: x.rolling(5, min_periods=1).mean())
    )

    df["action_frequency"] = (
        df.groupby(["user", "action"])["action"]
        .transform("count")
    )

    df["ip_switch_flag"] = (
        df.groupby("user")["source_ip"]
        .apply(lambda x: x != x.shift())
        .astype(int)
        .reset_index(drop=True)
    )
    df["hour"] = df["timestamp"].dt.hour
    df["unusual_hour_flag"] = df["hour"].apply(
        lambda x: 1 if x < 8 or x > 20 else 0
    )

    return df
