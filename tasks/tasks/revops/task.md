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

Our mid-market SaaS lead handoff has been missing owners and SLAs. Use the frozen CRM snapshot and operating policy in `/root/data` to score every contact, determine the current lifecycle outcome, route each MQL, and set the appropriate follow-up or escalation action.

Return an import-ready JSON handoff plan at `/root/results/handoff_plan.json`. Preserve account continuity, respect rep availability and capacity, calculate deadlines on the supplied business calendar, and flag ambiguous or overloaded cases for human review instead of guessing.

For each contact, make the account-resolution method, resulting lifecycle stage, assigned owner, routing category, handoff time, first-contact due time, SLA status, next action, and human-review reason explicit fields. Use an explicit `not_applicable` state when a policy field does not apply; reserve `null` for information that is genuinely unavailable or intentionally queued for human assignment.
