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

We’ve had repeat pages for RelayForge’s production webhook queue-age alert, and the response still lives across tickets and shift notes. The frozen on-call evidence is in `/root/data/`.

Consolidate it into `/root/results/webhook_backlog_runbook.md` for the on-call rotation. Make it safe to execute under pressure: use the approved commands and limits, distinguish the observed failure modes, state expected results and verification, and include rollback and escalation paths. Flag source conflicts instead of silently guessing.

Use `response_policy.md` as the authority for command limits, approval gates, stop conditions, and escalation. Organize the diagnostic branches around observable symptoms and command results so an operator can choose one safe next action; do not combine mutually exclusive mitigations into a single default sequence.
