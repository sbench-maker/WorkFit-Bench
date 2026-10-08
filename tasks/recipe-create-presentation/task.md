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

Set up a new Google Slides deck in the offline Workspace from `/root/data/launch_brief.json`, including the three initial slides described there, and share it with the pilot operations address as an editor. There is an older presentation with the same title, so create a new one rather than reusing it, and keep the slides concise enough to present. Save a JSON confirmation with the new presentation ID and sharing result at `/root/results/creation_receipt.json`.
