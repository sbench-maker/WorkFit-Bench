---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 1200.0
  os: linux
  cpus: 2
  memory_mb: 6144
  storage_mb: 10240
---

Stage the confirmed open-model tuning run described in `/root/data/`. Clean and format the support examples for chat tuning, preserve the approved holdout policy, and configure the supported model with a budget-aware cost estimate. Upload, submit, and monitor the run through the bundled offline control-plane mock. Put the complete run bundle plus a concise operator handoff in `/root/results/tuning_run/`; clearly distinguish the simulated result from a real cloud deployment and do not use network services or real credentials.
