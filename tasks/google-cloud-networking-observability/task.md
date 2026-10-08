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

Investigate the `checkout-api` outbound timeout spike during the incident window in `/root/data/incident_context.json` using the exported Google Cloud networking snapshot under `/root/data/`. Produce `/root/results/incident_report.json` with the primary cause, affected path, hourly traffic/drop trend, top three impacted internal sources, and a practical immediate action and alert recommendation. Distinguish Cloud NAT exhaustion from firewall or latency causes, account for duplicate VPC reporters and missing VM metadata, and include reusable BigQuery SQL plus the Flow Analyzer link.
