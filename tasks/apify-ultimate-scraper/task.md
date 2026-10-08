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

Sales needs a vetted Portland-metro event-vendor list for a new outreach campaign.

Use the offline Actor service and campaign brief in `/root/data/brief.json` to scrape the requested Google Maps businesses, enrich the scrape with contacts, and save a deduplicated CRM-ready file to `/root/results/output.json`. Keep separate branches even when they share a website, include the source place ID and requested business/contact fields, and add a compact run summary with scrape counts, dataset references, and any material enrichment gaps.
