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

The overnight sweep in `/root/data/` did not produce usable experiment monitoring. Instrument the supplied training script so every run records its configuration and step metrics, fires deduplicated diagnostic alerts under the supplied policy, and leaves a queryable store at `/root/results/experiment_store.json`. Replay the traces and save the runnable script as `/root/results/train_monitored.py` plus `/root/results/experiment_report.json` with each run’s final and best validation metrics, alerts, and STOP/INVESTIGATE/CONTINUE decision tied to nearby evidence. Keep everything local; do not configure remote sync or webhooks.
