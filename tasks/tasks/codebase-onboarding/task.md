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

A platform engineer joins Rosterly tomorrow. Inspect the unfamiliar repository at `/root/data/repository/` and create `/root/results/onboarding-guide.md` with the current architecture, one end-to-end approval request path, and trustworthy day-one commands.

Also create `/root/results/CLAUDE.md` by refreshing the repository’s existing instructions. Keep both files quick to scan, preserve its project-specific rules, prefer current code and configuration over stale notes, and flag conventions that the available repository history cannot support.
