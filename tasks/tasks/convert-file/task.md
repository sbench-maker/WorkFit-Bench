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

Our growth team needs the campaign-event export in `/root/data/campaign_events.jsonl` converted to a Parquet dataset at `/root/results/campaign_events.parquet` for the attribution pipeline.

Partition it by `campaign_month`, use Zstandard compression, and preserve every record, column, value, null, and detected field type so downstream joins remain reliable.
