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

Our responsive operations dashboard in `/root/data/project` has janky drawer, dialog, toast, progress, and status-badge motion. Audit the supplied styles and interaction-state notes, then produce `/root/results/animation-fix.patch` with layout-triggering animation work moved to compositor-friendly motion while preserving the desktop/mobile endpoints and the effects that are already safe.

Add `/root/results/animation-review.md` as a concise handoff explaining the affected selectors, why each change improves rendering, and how the reduced-motion state behaves.
