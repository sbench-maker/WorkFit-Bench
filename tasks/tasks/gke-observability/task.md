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

The platform team needs an offline rollout plan for the fictional Orion GKE fleet. Inspect the exported cluster state, metric inventory, and fleet policy in `/root/data/`, then write `/root/results/observability_rollout.json` with each cluster’s target settings and safe `gcloud container clusters update` commands, plus production Cloud Monitoring dashboards and alerts.

- I need every cluster accounted for, including explicit no-op decisions.
- Don’t leave production control-plane, node-health, or workload blind spots.
- Keep sandbox ingestion lean and make rollout order and blast radius clear.

Structure `observability_rollout.json` with the top-level arrays `clusters`, `dashboards`, `alerts`, and `rollout_order`. Put one record per cluster in `clusters`, with `cluster_name`, `target_logging_components`, `target_monitoring_components`, `managed_prometheus_enabled`, `dataplane_v2_metrics_enabled`, `command`, and `no_op`. Supply either an exact update command or `no_op: true` for every cluster. `rollout_order` must reference the same cluster names and make each rollout stage and blast radius clear.
