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

Add Capybara/RSpec feature coverage for the ticket checkout in `/root/data/ticket_app/`. Exercise a successful purchase from event search through confirmation, plus the sold-out and invalid-promo paths described in `acceptance_notes.md`. Keep actions and assertions at the user-visible level, and make the spec runnable offline against the bundled Rack app. Save it as `/root/results/checkout_spec.rb`.
