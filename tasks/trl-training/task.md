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
  cpus: 2
  memory_mb: 4096
  storage_mb: 10240
---

Build a review-ready DPO launch bundle from the frozen model, preference pairs, hardware profile, and handoff notes in `/root/data`. Save the completed bundle under `/root/results/dpo_run/` with the prepared train/eval data, configuration, launch script, and preflight report described in the notes.

- I need unsafe, ambiguous, or unusable pairs excluded without losing record-level traceability.
- I need the two-GPU memory limit and required effective batch size honored.
- I need the handoff to stay fully local: no downloads, Hub pushes, or remote experiment tracking.
