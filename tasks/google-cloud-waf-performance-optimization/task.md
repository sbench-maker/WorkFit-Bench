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

Northstar Retail needs a launch-readiness performance assessment of the Google Cloud workload captured in `/root/data/`. Create `/root/results/performance_assessment.json` that identifies breached requirements and evidence-backed bottlenecks, then gives a prioritized action plan covering resource allocation, component boundaries, elasticity, and monitoring. Respect the stated budget, downtime, caching, and inventory-consistency constraints, and include measurable validation and rollback guidance for the platform team.
