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

Prioritize the Northstar Care roadmap assumptions using the evidence and planning rules in `/root/data/`. Create `/root/results/assumption_priority.md` with a decision-ready Impact × Risk matrix, a clear test-first order, and a recommended action for every assumption. For assumptions needing validation, propose the leanest feasible experiment from the available resources, measuring actual behavior with a numeric success threshold; respect the two-week, no-production, and privacy constraints, and flag material evidence limitations.
