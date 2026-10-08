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

We need Friday's handoff for the customer delivery squad. Use the offline Workspace/CRM snapshot under `/root/data/` to reconcile standups, customer mail, the action tracker, calendar, and OKRs into a reviewable weekly coordination packet at `/root/results/output.json`; follow the packet contract in the snapshot README.

Include a deduplicated create/update plan, the weekly digest, and a Monday team-chat draft. Do not send or alter anything, invent commitments, or expose private customer or staff notes; flag ownership, deadline, and availability conflicts for human review.
