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

Our agent squad’s release board drifted during parallel work. Reconcile the frozen control-pane export and repository evidence in `/root/data/`, then save an actionable release orchestration plan to `/root/results/output.json`.

- I need every active work item to have one accountable owner, a safe branch/file boundary, and a justified current Kanban state.
- I need merge readiness based on actual gates and evidence, with a dependency-safe integration order.
- I need blockers tied to an owner and next action, plus concise handoff and reusable-workflow recommendations.
