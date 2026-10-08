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

Quantize the fictional Orion decoder checkpoint in `/root/data` for the T4 deployment described there. Build the smallest calibration-free HQQ mixed-precision package that satisfies the supplied per-layer quality limits, preserves the excluded vocabulary endpoints, and uses a compatible optimized backend. Follow the bundled offline runtime and bundle contract; do not use network or calibration samples. Write the complete package and a concise deployment handoff to `/root/results`, with `/root/results/output.json` as its manifest.
