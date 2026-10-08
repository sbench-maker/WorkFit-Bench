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

An editor sent a calendar change request. Use the offline Google Calendar account and request in `/root/data/` to reschedule the intended meeting, and save the completed update receipt to `/root/results/output.json`.

- I need the requested occurrence changed, not a similarly named meeting or the whole recurring series.
- Please keep its duration and other meeting details intact while using the requested timezone.
- Everyone currently invited must receive the update, with no extra recipients added.
