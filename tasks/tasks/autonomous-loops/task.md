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

Our billing-platform RFC needs a machine-readable autonomous implementation plan before we hand it to the agent pool. Use the frozen RFC, repository history, CI evidence, and operating policy in `/root/data/`; save the plan to `/root/results/output.json`.

- I’m concerned that dependencies and shared files could create unsafe parallel work or merge order.
- I’m concerned that quality depth and human gates may not match each unit’s risk, wasting effort or exposing the rollout.
- I’m concerned that failures will lose context or loop forever, so recovery and every stopping limit must be explicit.
