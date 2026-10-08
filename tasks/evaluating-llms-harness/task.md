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

Turn the frozen `lm-evaluation-harness` exports in `/root/data` into a release-readiness report at `/root/results/benchmark_report.json` for the Aurora 7B checkpoint series. Compare checkpoints with the external baseline only on like-for-like benchmark configurations, summarize training progress across the required suite, and recommend whether a checkpoint is ready to promote. Keep the report auditable with per-benchmark scores, uncertainty, comparability exclusions, and concise evidence for the decision; do not average missing or incompatible runs.

For every checkpoint and required benchmark pair, include the compatible-run count, mean, sample standard deviation, 95% confidence-interval half-width, and delta versus the matching external-baseline result. Identify the promoted checkpoint and explicitly record the disposition of the latest checkpoint when it is not selected.
