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

Break down the oversized supplier-returns epic in `/root/data/` into vertical, sprint-sized user stories for backlog refinement. Use the supplied workflow, policies, discovery signals, and sizing constraints to explain the split pattern(s), write testable acceptance criteria and estimates, and identify what should ship first, be deferred, or still needs validation. Preserve an end-to-end usable increment rather than front-end/back-end tasks. Save the plan to `/root/results/epic_breakdown.md`.
