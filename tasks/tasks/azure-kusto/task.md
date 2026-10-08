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

Investigate the frozen Azure Data Explorer telemetry export in `/root/data/` for the primary customer-impacting deployment regression, following the local operations brief and table schemas. Write `/root/results/incident_report.json` with the incident and matching baseline window, affected service and region, deployment/version, request count, error rate, p95 latency, top endpoint, and concise evidence. Include reusable KQL that an on-call engineer can run against the named ADX tables to reproduce the hourly detection and deployment correlation; do not promote isolated background errors as the incident.
