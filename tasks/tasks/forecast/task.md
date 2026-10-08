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

Finance is locking the Q4 forecast, and I need a defensible call from the frozen CRM snapshot in `/root/data/`. Use its reporting date, stage probabilities, and commit/risk policy; out-of-period deals must not leak into the quarter.

Save `/root/results/output.json` with the stage-weighted forecast, best/likely/worst outlook, quota gap and coverage, stage rollup, deal-level commit versus upside, material risk flags, and a short prioritized action list. Keep assumptions and totals reviewable for our offline CI handoff.
