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

Our PilotDesk team needs an import-ready first-response agent for the ticket queue captured in `/root/data/`; use the included deployment contract, support policies, tool catalog, and representative threads. Configure it to draft routine customer replies, carry out only clearly authorized small refunds, and route risky or unresolved cases to the right human queue without overstating what was sent or completed. Keep replies on-brand and make each disposition easy for staff to audit, then save the configuration as `/root/results/support_agent.json`.

The deployment contract controls the import shape and available tools; `refund_policy.json` and `support_policy.json` control authorization and routing. A draft, an executed refund, and an escalation must remain distinct outcomes, with the ticket evidence and any missing prerequisite visible to the reviewing agent.
