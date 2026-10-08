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

Review the exported primary calendar and planning preferences in `/root/data/` for October 5–9, 2026. Identify the usable gaps, then add six 75-minute “Atlas Focus Block” events without moving existing commitments. Respect the recorded timezone, working hours, protected time, buffers, and event availability; spread the work across the week and favor morning time when the calendar allows.

Save `/root/results/output.json` with the usable gaps, proposed additions, updated workweek agenda, and a concise rationale for the choices.
