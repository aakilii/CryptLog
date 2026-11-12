# CRUD Metrics — Calculations & Aggregation Logic

## Per-Event Metrics

| Metric | Calculation | Range |
|--------|-------------|-------|
| `hour` | UTC hour from `normalised_ts` | 0–23 |
| `day_of_week` | 0=Mon to 6=Sun | 0–6 |
| `is_business_hours` | `7 ≤ hour ≤ 20` | bool |
| `is_weekend` | `day_of_week ≥ 5` | bool |
| `sensitivity_weight` | LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4 | 1–4 |
| `risk_score` | Weighted formula (see below) | 0.0–1.0 |

## Risk Score Formula

```
risk_score = 0.40 × anomaly_score
           + 0.30 × (sensitivity_weight / 4)
           + 0.15 × min(1.0, volume_bytes / 500000)
           + 0.15 × (1.0 if off_hours else 0.0)
```

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Anomaly score (IF+LOF) | 40% | ML-based anomaly detection gives strongest signal |
| Sensitivity weight | 30% | Higher sensitivity data deserves more scrutiny |
| Volume factor | 15% | Large data transfers suggest exfiltration |
| Off-hours factor | 15% | After-hours activity common in insider threats |

## Aggregation (Matrix)

Events are grouped by `(actor, target_object, crud_type)`:

| Aggregate | Formula |
|-----------|---------|
| `event_count` | `COUNT(*)` per group |
| `total_bytes` | `SUM(volume_bytes)` |
| `total_rows` | `SUM(row_count)` |
| `avg_anomaly` | `MEAN(anomaly_score)` |
| `max_sensitivity` | `MAX(sensitivity)` by weight |
| `high_risk_count` | `COUNT(*) WHERE is_high_risk = TRUE` |
| `first_seen` / `last_seen` | `MIN(ts)` / `MAX(ts)` |
