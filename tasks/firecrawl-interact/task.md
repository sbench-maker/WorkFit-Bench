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

Triage the offline support console described in `/root/data`: scrape the mock endpoint, filter to open urgent tickets, paginate through the results, and open each detail drawer to identify tickets already beyond their SLA. Write `/root/results/output.json` with the breached tickets and their available operational details, preserving blank owners as unassigned, plus counts by region and a short handoff note that highlights the most urgent follow-up.
