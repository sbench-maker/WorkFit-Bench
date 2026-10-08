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

The generated Nimbus SDK v7 migration catalog is about to be published. Have two independent reviewers audit it against the frozen release evidence and publication rubric in `/root/data`, resolve every blocker across the full catalog, and repeat fresh reviews after changes until both pass (stop after three rounds and escalate if needed). Save the corrected catalog and auditable review history to `/root/results/release_packet.json`; do not publish unsupported behavior or guarantees.
