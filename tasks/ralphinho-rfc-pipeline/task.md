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

The Workspace Export v2 RFC has stalled. Rebuild its execution plan from the approved RFC, repository/CI catalog, and pipeline snapshot in `/root/data/`; save the updated multi-agent DAG and merge plan to `/root/results/output.json`.

- I need independently reviewable work units with scope, acceptance checks, risk, rollback, and explicit dependencies.
- I’m worried the security and migration path—or the merge queue—could run ahead of prerequisites.
- I need the stalled unit recovered with narrower scope and a credible final verification path.
