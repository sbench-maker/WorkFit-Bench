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

The HelioLedger 4.6 autonomous patch campaign is churning and its merge queue has stalled. Use the frozen run snapshot and operating policy in `/root/data/` to decide the loop mode, freeze/recovery actions, and a dependency-safe restart plan; preserve completed work and stay within the remaining budget.

Write `/root/results/recovery_plan.json`. Make it actionable for the runner, with concise evidence and explicit human-review flags wherever the release lead must decide.

Use `operating_policy.json` for retry, budget, concurrency, freeze, and escalation limits. Keep completed, recoverable, blocked, and human-decision units distinguishable, and retain their unit/dependency identifiers so the restart order can be applied without redoing accepted work.
