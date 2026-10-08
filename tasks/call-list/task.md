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

The sales director needs the September 10 call sheet before stand-up.

Use the frozen CRM, mailbox, and calendar snapshots in `/root/data/` to rank the five leads most worth calling, honoring contact restrictions. Save `/root/results/call_plan.json` with decision-ready call cards, email-grounded talking points and call goals, conflict-free 20-minute proposed slots, and follow-up drafts where they are due. Keep every event and message in proposal/draft state; do not send, create, or update anything.

Apply the eligibility, restriction, ranking, and follow-up timing rules in `call_policy.json`; when a CRM field conflicts with a more recent dated email or calendar record, preserve the conflict and base the proposed action on the newer evidence rather than silently rewriting history. Keep each call card tied to the lead and source message/event IDs.
