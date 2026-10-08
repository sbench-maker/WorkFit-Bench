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

The EdgeServe team has frozen the Orion-mini checkpoint and calibration run under `/root/data/`. We need a retraining-free, activation-aware 2:4 sparse build for the Vega accelerator; groups are consecutive within each output row, and the deployment contract in the fixture governs eligibility and ties.

Save the complete pruned checkpoint, a concise layer summary, and validation notes to `/root/results/output.json`. Preserve excluded tensors unchanged so the artifact is ready for the serving handoff.
