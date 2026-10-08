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

Our rollout plan at `/root/data/workspace/docs/merchant_assist_rollout.md` needs to become ready-to-paste `/orchestrate custom` commands. Use automatic project-language detection and include a full-plan overview, but emit runnable detail and batch commands only for steps 2–6. Keep each command self-contained, preserve step-specific out-of-scope boundaries, and add a compact chain rationale so reviewers can see why each hand-off is there. Save the result to `/root/results/orchestration.md`.
