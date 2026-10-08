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

We need the one-time order service in `/root/data/checkout_service` ready for rollout. Replace legacy payment creation with Checkout Sessions on the current API version supported by the bundled mock, preserve the documented Python interface, keep payment methods dynamic, and make each Checkout flow distinguishable under the configured tracking prefix.

Make paid-order updates depend only on verified, retry-safe webhooks; don’t put credentials in code or logs. Save the runnable repository to `/root/results/checkout_service`, including a short `HANDOFF.md` covering configuration, event behavior, and operational caveats.
