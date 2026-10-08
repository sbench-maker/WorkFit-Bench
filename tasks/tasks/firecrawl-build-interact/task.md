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

Finish the local catalog integration in `/root/data/starter/` and deliver the completed `collector.py` plus the primary-case `output.json` in `/root/results/`.

- I need it to recognize when the initial scrape cannot expose the records and continue through the mock’s interactive flow.
- I’m concerned about preserving browser state while filtering and paginating, without missing or duplicating eligible controls.
- Please keep the existing CLI contract and make the implementation reusable for the other bundled case; this is a handoff, so keep failures understandable.
