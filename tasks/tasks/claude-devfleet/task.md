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

The release team approved the offline coding-fleet rehearsal in `/root/data/release_request.md`; go ahead against the bundled simulator and supporting project files. Plan the work into isolated-agent missions, launch the approved root mission, respect dependencies and the three-agent limit, then monitor every mission to a terminal state.

Save `/root/results/output.json` as the handoff, including the project and mission plan, dispatch record, final statuses, each structured mission report, and a concise release summary that calls out failures and manual follow-up.
