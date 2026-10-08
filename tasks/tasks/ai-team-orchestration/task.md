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

EvalHarbor is moving from kickoff into parallel product, development, QA, and DevOps chats, and we need repository-based context before those conversations diverge. The frozen kickoff packet and backlog are in `/root/data`.

Create `/root/results/launch_pack` with a durable project brief, a role-specific launch brainstorm prompt, and Sprint 1 plan/progress/done working docs. Preserve fixed decisions, committed dependencies, and team boundaries; keep secret values out; make a fresh chat able to resume from the files alone.

Treat `operating_policy.md` as authoritative for role boundaries and handoff behavior, and use `fixture_manifest.json` to determine which frozen inputs are in scope. The working documents should distinguish approved scope, current status, blockers, and next ownership so that a new role chat does not have to infer them from narrative history.
