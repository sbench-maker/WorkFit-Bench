---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 600.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
---

Build a runnable BigFrames churn-scoring pipeline against the offline BigQuery fixture in `/root/data`, following the cohort and feature definitions documented there. Use partial ordering and cloud-side dataframe operations to join and clean the tables, train and evaluate a logistic model named `skillbench.churn_model` on June–August rows, and score eligible September accounts without pulling full source tables into memory. Put the implementation at `/root/results/churn_pipeline.py`; it should write `/root/results/churn_scores.csv` and `/root/results/metrics.json`.
