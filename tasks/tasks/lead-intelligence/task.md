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

Our launch team is lining up design-partner conversations for TracePilot, an AI release-readiness assistant.

Use the frozen CRM, company/activity, and social-graph exports in `/root/data/` to produce a ranked top-12 outreach plan at `/root/results/output.json`. Merge duplicate profiles, follow the campaign brief for eligibility, fit scoring, and routing, and use only verified evidence for warm paths and personalization. For every lead, recommend one channel with rationale and draft a concise, review-ready first message; do not send anything.

Structure `output.json` as an object with a top-level `leads` array containing exactly 12 ranked records. After deduplication, each record must contain `person_id`, `rank`, `fit_score`, `channel`, `evidence_ids`, `channel_rationale`, and `message`. Rank records from 1 through 12 without ties, and keep the draft message inside the same record as the evidence and channel decision it relies on.
