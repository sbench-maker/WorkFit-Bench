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

Build an offline monitoring agent for the fictional inference-model catalog snapshots in `/root/data/`. Put the runnable project in `/root/results/model_monitor/` and run it once, producing `/root/results/output.json`.

- I need normalized model records from every page, with unusable entries excluded and duplicates resolved against both the crawl and prior store.
- I need each newly stored or materially updated model enriched from the supplied configuration and feedback, with concise reasons for compatibility triage.
- I need deterministic local persistence plus a schedule-ready entry point; nothing may require network access or credentials.
