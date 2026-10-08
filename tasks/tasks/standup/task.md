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

Draft my September 9 standup from the offline activity export in `/root/data/`. Pull together my September 8 commits and PR work, ticket moves, relevant chat decisions, and CI/deploy status, then save the shareable update to `/root/results/standup.md`.

Keep it concise in Yesterday/Today/Blockers form, retaining useful ticket and PR references. Don’t turn other teammates’ activity or resolved/transient failures into my blockers; for a real blocker, include what is needed and who can help.
