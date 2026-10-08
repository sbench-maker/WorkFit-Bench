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

The portfolio committee needs a first-pass gate packet for the Phase II AURORA-2 study. Use the frozen planning inputs under `/root/data/` to select and classify endpoints, estimate the dropout-adjusted two-arm sample size, and pressure-test enrollment, operations, and budget. Write `/root/results/gate_packet.json`. Treat all figures as planning estimates, surface surrogate and multiplicity risks plus assumptions, and route unresolved items to the named clinician, biostatistician, or regulatory owner rather than presenting a submission-ready protocol.

Use `study_brief.json` for the decision horizon, planning assumptions, ownership, and gate thresholds; supporting files provide evidence but do not silently override those stated constraints. Separate the current gate recommendation from the conditions that would change it, and show the calculation inputs used for the sample-size and feasibility conclusions.
