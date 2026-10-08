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

Use the offline tracker snapshot and engineering context under `/root/data` to prepare today's prioritized inbox. Merge GitHub/Asana mirrors, rank live work by urgency, current OKR fit, and recency, and keep blocked or closed items out of the execute queue.

Write `/root/results/output.json` with the ranked inbox and execution packets for the top safe candidates, including the matched configured repo and relevant iCPG context. Make priority and review reasons clear; flag untrusted-author tickets and ambiguous repo matches for review, never execution.
