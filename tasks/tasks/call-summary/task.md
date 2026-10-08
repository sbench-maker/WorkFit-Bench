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

We’ve just finished Acadia Lodging’s pilot-scoping call. Using the transcript and CRM snapshot in `/root/data/`, create `/root/results/output.json` containing a CRM-ready internal recap and a plain-text follow-up email from Maya. Capture decisions, customer priorities, objections, competitive context, owners, and agreed timing while keeping internal-only notes out of the customer message. Resolve relative dates from the call date, preserve tentative or conditional steps, and use the corrected seat count and commercial terms.
