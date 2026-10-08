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

Draft the Workplace Systems Reliability team's September 1-7 weekly 3P update for leadership from the exported incident, ticket, action-item, and discussion files in `/root/data/`. Focus on the SSO troubleshooting outcome, user impact, and next week's highest-priority follow-ups; distinguish unresolved risk from completed work and do not invent causes where evidence is inconclusive. Save the concise, Slack-ready update to `/root/results/weekly_3p.md`.

Use the standard 3P headings `Progress`, `Plans`, and `Problems`. Put completed recovery and verified outcomes under Progress, next-week owner actions under Plans, and only unresolved risks or blockers under Problems so leadership can scan the update without reclassifying items.
