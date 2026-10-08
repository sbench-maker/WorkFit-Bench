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

Our pulmonary registry team needs the fictional notes under `/root/data` abstracted against the supplied schema. Write `/root/results/output.json` with one schema-complete result per source file and a compact reviewer summary.

- I need every populated value traceable to verbatim note evidence so reviewers can verify it quickly.
- Please preserve negated, possible, historical, hypothetical, and family-member context, using explicit nulls instead of clinical guesses.
- Surface malformed inputs and numeric, date, or terminology validation issues rather than silently treating them as valid.
