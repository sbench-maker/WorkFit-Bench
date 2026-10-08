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

Our release job needs a regression snapshot from the baseline and current SARIF exports under `/root/data/`. Aggregate the runs, normalize repository paths, and deduplicate alerts according to `scan_manifest.json`; write `/root/results/output.json` with new, fixed, and unchanged findings, per-status severity totals, and a pass/fail gate. Keep each finding traceable to its rule, severity, message, file, and line so engineers can act on it.
