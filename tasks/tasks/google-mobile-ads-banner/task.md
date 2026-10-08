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

Add a Google Mobile Ads banner to the Android Browse screen in `/root/data/mobile_app`, then deliver the updated project at `/root/results/mobile_app`. The repository includes its own offline SDK mock and integration brief.

- I need the banner to sit naturally inside the scrolling product feed without covering content.
- I want useful loaded and failed states, even though ad callbacks arrive off the UI thread.
- I need existing browse interactions preserved, an offline build, and a clear production ad-unit handoff note.
