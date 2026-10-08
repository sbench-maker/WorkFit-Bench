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

The bug-triage export is ready in `/root/data/`. Inspect the offline Airtable-compatible base and reconcile `incoming_issues.csv` into its Issues table by External ID, following the local sync policy and applying the changes idempotently through REST.

Keep populated optional values when the import leaves them blank. Save a concise receipt with created, updated, unchanged, and rejected items plus post-sync totals to `/root/results/output.json`.
