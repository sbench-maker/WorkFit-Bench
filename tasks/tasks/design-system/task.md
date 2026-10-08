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

Before we freeze Aurora UI 3.4, audit the complete repository snapshot in `/root/data/aurora-ui/` and write `/root/results/design_system_audit.md`. Cover every catalogued component and focus on public variant/size naming drift, hardcoded visual values, and implementation or documentation gaps in required states and accessibility. Treat the supplied tokens, policies, and literal-exception registry as authoritative. Include an inventory-level summary, file evidence, approved replacements where available, and a risk-ranked, migration-safe action plan the frontend team can execute.
