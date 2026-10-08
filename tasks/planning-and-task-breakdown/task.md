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

Break the scheduled project-digest feature in `/root/data/feature_spec.md` into an implementation plan for the codebase snapshot at `/root/data/repo/`. Write `/root/results/plan.md` and `/root/results/todo.md`; plan only, without implementing the feature. Keep tasks dependency-ordered, small, and independently verifiable, using vertical slices where practical. Surface unresolved product, security, and operations decisions, and place human review checkpoints before irreversible schema, rollout, or delivery changes.
