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

The product-operations standup starts in fifteen minutes.

Using the fixed report date and offline Google Calendar and Tasks snapshot in `/root/data/`, create `/root/results/output.json` as a concise, date-stamped briefing that combines today’s attended agenda with all still-open work. Exclude cancelled or declined meetings and completed, deleted, or hidden tasks. Keep the agenda chronological, make time conflicts plus overdue or blocked work easy to spot, and include accurate headline meeting/open/risk counts and owner/priority rollups.
