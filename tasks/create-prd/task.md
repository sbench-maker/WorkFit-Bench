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

The RelayDesk team has approval to scope Batch Triage after the August discovery review, but Sales, Security, and Operations disagree on what belongs in the first release. The research, workflow data, and stakeholder notes are in `/root/data/`.

Could you draft a concise, engineering-ready Markdown PRD at `/root/results/PRD-batch-triage.md`? Ground the priorities and SMART measures in the evidence, resolve the v1-versus-later trade-offs, flag assumptions that still need human review, and use relative release timeframes.
