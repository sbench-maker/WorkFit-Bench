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

We’re handing the September support-ops snapshot to Analytics. The DuckDB file and the project’s existing shared session state are under `/root/data/project/`; attach and select the snapshot read-only for follow-up queries, using `support_ops_snapshot` if the filename alias is already taken, and preserve the shared setup.

Stage the reusable init file at `/root/results/state.sql` and a concise schema handoff at `/root/results/attach_report.json` with the resolved source, chosen alias, and every table’s column definitions and row count.
