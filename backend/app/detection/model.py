from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import numpy as np


FEATURE_COLUMNS = [
    "login_time_delta",
    "failed_attempt_ratio",
    "action_frequency",
    "ip_switch_flag",
    "unusual_hour_flag"
]


def train_isolation_forest(df):

    missing = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    X_raw = df[FEATURE_COLUMNS].fillna(0)

    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    model = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=42,
        n_jobs=-1
    )

    model.fit(X)

    scores = model.decision_function(X)
    predictions = model.predict(X)

    return model, scaler, scores, predictions
