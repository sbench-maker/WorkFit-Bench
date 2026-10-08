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

Run a hygiene pass on the frozen HubSpot export in `/root/data/`. Identify open deals with no recorded activity in the last 14 days as of the snapshot date, likely duplicate contacts, and required-field gaps on open deals and their contacts. Put a review-ready cleanup plan in `/root/results/output.json`, with current evidence and proposed changes shown side by side. Do not modify source records or treat any merge, stage change, or close-lost action as approved.

Use `snapshot.json` for the as-of time and `cleanup_policy.json` for the authoritative definitions of open deals, qualifying activity, required fields, and duplicate candidates. Make the three finding groups—stale deals, duplicate contacts, and required-field gaps—separately identifiable in the JSON. The exact nesting and key names are up to you, but each finding should retain the relevant deal/contact IDs so it can be reconciled to the export.

Structure `output.json` with exactly three top-level finding arrays: `stale_deals`, `duplicate_contacts`, and `missing_required_fields`. Every stale-deal and field-gap record must carry the relevant deal or contact ID. Every duplicate group must list its contact IDs and keep the current evidence, proposed keeper/transfers, and unresolved conflicts separate. Proposed changes must remain visibly pending rather than appearing as completed CRM updates.
