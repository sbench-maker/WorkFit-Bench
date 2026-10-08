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

Create a cinematic, data-dense social media matrix dashboard for the Night Bloom campaign from the exports and `DESIGN.md` in `/root/data/`, saving one self-contained file at `/root/results/index.html`. Keep platform cards, 30-day KPIs, alerts, and chart insights synchronized, and handle the flagged data gaps without turning missing observations into zeroes. The chart sections need live hover details, point pinning, drag and Shift+drag range comparison, plus dark/light switching, all usable offline.
