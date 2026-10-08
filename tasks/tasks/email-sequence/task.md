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

Build an implementation-ready six-email onboarding sequence for HarborLoop's 14-day team trial using the brief and CRM, product-event, asset, and campaign-history files in `/root/data/`. Save it as `/root/results/onboarding_sequence.md`. Include copy-ready drafts, subject variants, preview text, cadence, a text flow diagram with behavior-based branches, exit/suppression/re-entry logic, and a practical A/B and measurement plan grounded in the history. Keep one primary CTA per email, use only approved product claims and links, and tailor the path to each account's remaining activation steps.
