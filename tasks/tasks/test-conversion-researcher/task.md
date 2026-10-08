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

The Side Panel team needs a migration handoff before its next ChromeOS bot rollout.

Research the checkout and migration note under `/root/data/bedrock_checkout`, then write an implementation-ready plan to `/root/results/conversion_plan.md` for moving the genuinely browser-coupled unit coverage to browser tests. Include a test-by-test disposition, code-backed behavior mapping, affected files and build targets, and bot-safe setup, validation, and teardown; keep pure unit coverage in place and do not modify the checkout.
