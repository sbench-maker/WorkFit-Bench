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

Our incident wall checkout in `/root/data/project` drops frames during pointer tracking, card reveals, drawer motion, and resize bursts. Optimize its GSAP code for smooth low-end use while preserving the documented interaction/export contract, reduced-motion behavior, and visual endpoints; use the bundled profile only as diagnostic context and add no dependencies. Deliver an applicable unified patch at `/root/results/gsap-fix.patch` and a concise engineering handoff at `/root/results/performance-review.md`.
