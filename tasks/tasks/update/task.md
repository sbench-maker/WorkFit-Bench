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

Run a comprehensive workspace update using the offline project-tracker and recent-activity snapshot in `/root/data/`. Reconcile Maya Chen's current `TASKS.md`, capture missed follow-ups, and apply only the confirmations in `review_decisions.csv`; preserve source references and refresh the supplied memory with supported context. Write the finished workspace to `/root/results/updated_workspace/` and a concise change report to `/root/results/update_report.md`, leaving unresolved ambiguities flagged for Maya rather than guessing.
