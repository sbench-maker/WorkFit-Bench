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

Friday’s Northstar renewal call needs one internal prep brief. The frozen calendar, email, chat, contract, and document exports are in `/root/data`; reconcile them as of the snapshot, including earlier follow-ups and anything unavailable or outdated.

Create `/root/results/meeting_brief.md` with the meeting context, participants, agenda, key terms and open issues, decisions/questions, and actionable next steps. Clearly separate privileged or internal-only negotiation authority from vendor-safe talking points so the team does not disclose it during the call.
