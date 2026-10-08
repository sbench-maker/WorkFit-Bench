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

The ParcelPilot WordPress plugin snapshot in `/root/data/parcelpilot/` has a noisy, failing static-analysis setup after a REST and fulfillment update. Produce a corrected copy at `/root/results/parcelpilot/` so its existing `composer run phpstan` command passes, keeping the current Composer dependencies and baseline unchanged and avoiding broad suppressions that could hide first-party errors. Add a short handoff note at `/root/results/phpstan-review.md` summarizing the fixes and any remaining assumptions.
