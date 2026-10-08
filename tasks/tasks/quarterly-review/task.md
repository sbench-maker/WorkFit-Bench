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

Build the 2026-Q2 quarterly business review from the frozen finance, settlement, and CRM exports in `/root/data/`. Deliver a presentation-ready PDF at `/root/results/qbr-2026-Q2.pdf` covering revenue and margin trends, customer health, next-quarter pipeline, and the most important opportunities and risks. Reconcile PayPal activity against booked revenue, make any material data gaps or concentration risks visible, and keep the executive narrative concise enough for owner review; do not publish or email it.

Keep the headline figures, chart labels, comparison periods, and material caveats as selectable PDF text rather than embedding them only inside raster images. The PDF may use as many pages as the review needs, but each page should advance the owner decision and avoid appendix-style raw-data dumps.
