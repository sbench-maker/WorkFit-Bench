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

Finish the offline incident-response agent in `/root/data/incident_agent/` so it coordinates the planner, investigator, and remediator across the frozen scenarios and mock tool registry. Keep execution bounded and auditable, escalate unsafe or uncertain cases instead of claiming success, and retain only reusable resolution memory. Put the complete runnable project in `/root/results/incident_agent/` and include its full-suite `evaluation.json` for the on-call team to review and extend.
