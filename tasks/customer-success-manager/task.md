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

Build this week’s CSM portfolio triage from the frozen CRM export in `/root/data/` and save it as `/root/results/output.json`.

- I’m worried high-value accounts with worsening health or near-term renewal will get missed; give us a prioritized intervention queue with the evidence and next action.
- I’m worried expansion outreach will hit unhealthy accounts; include portfolio health, churn, and expansion rollups, but only recommend sales motions when the account context supports them.
- I’m worried bad CRM fields will distort decisions; isolate incomplete or contradictory records for human review and don’t invent replacements.
