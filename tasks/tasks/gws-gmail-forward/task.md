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

Handle procurement handoff FH-2048 using the offline Gmail snapshot and directory in `/root/data/`: forward the correct final vendor pricing message to the approved internal recipients with the requested note, include only the pricing PDF, and leave it as a draft for review—do not send it. Save the resulting mailbox state to `/root/results/mailbox_state.json`.
