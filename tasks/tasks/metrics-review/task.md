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

Run the August 2026 monthly product metrics review from the frozen exports in `/root/data/`. Create `/root/results/output.json` with a concise executive summary, a metric-hierarchy scorecard comparing August with July and targets, trend and segment diagnosis, prioritized actions, a small set of actionable alert recommendations with owners and severity, and data caveats. Use weighted rollups where the definitions call for them, distinguish event timing from proven causation, and do not hide incomplete or estimated observations.
