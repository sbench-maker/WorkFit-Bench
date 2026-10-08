# Offline BigQuery / BigFrames fixture

This directory is a fictional, deterministic warehouse snapshot plus a small BigFrames-compatible emulator. Run a pipeline with:

```bash
PYTHONPATH=/root/data/emulator python3 /root/results/churn_pipeline.py
```

The emulator maps these BigQuery table IDs to frozen CSV-backed remote frames:

- `skillbench.customers`
- `skillbench.monthly_usage`
- `skillbench.support_cases`

It supports ordinary pandas-style BigFrames operations used by this task, including filtering, joins, `groupby().agg()`, string/date accessors, `drop_duplicates`, `peek`, and small-result materialization. `bigframes.bigquery.ml.create_model`, `evaluate`, and `predict` implement a deterministic offline stand-in for BigQuery ML logistic regression. Use `BIGFRAMES_FIXTURE_ROOT` and `BIGFRAMES_RESULTS_ROOT` instead of hard-coded fixture/result roots if they are set; the default values are `/root/data` and `/root/results`.

## Business contract

Build one row per account-month. Keep the newest `monthly_usage` row by `ingested_at` when a correction exists. Aggregate support cases by the month of `opened_at`, with `case_count`, `urgent_case_count` (`high` or `critical`), and `avg_first_response_hours`; accounts with no cases receive zero counts and zero average response time.

Use these model features, with exactly these meanings:

- `utilization_rate = active_users / licensed_seats`
- `sessions_per_active_user = sessions / active_users`, using `0` when active users is zero
- `api_calls`, `invoice_amount`, `case_count`, `urgent_case_count`, `avg_first_response_hours`
- `days_since_activity`, measured from the calendar month end to `last_activity_date`
- `tenure_days`, measured from the calendar month end to `signup_date`

Training comprises June-August 2026 labeled rows for non-internal accounts with positive licensed seats. Use `churned_next_30d` as the boolean label, name it `label` for model creation, and persist the logistic model as `skillbench.churn_model` with replacement enabled. Evaluate that model on its training rows.

Score September 2026 rows only for active, non-internal accounts with positive licensed seats. `churn_scores.csv` must contain each eligible `account_id` once with its churn probability and be sorted from highest to lowest risk. `metrics.json` should expose the emulator's evaluation metrics and identify the model.

The emulator records calls in `bigframes_trace.json` under the result root. Full source-table downloads defeat the production shape of this workflow; materializing small evaluation or final scoring results is expected.

## Table schemas

`customers`: `account_id`, `region`, `plan_name`, `signup_date`, `account_status`, `is_internal`.

`monthly_usage`: `account_id`, `month`, `licensed_seats`, `active_users`, `sessions`, `api_calls`, `invoice_amount`, `last_activity_date`, nullable `churned_next_30d`, `ingested_at`.

`support_cases`: `case_id`, `account_id`, `opened_at`, `severity`, `first_response_hours`, nullable `resolution_hours`, `case_status`.

