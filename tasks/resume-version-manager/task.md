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

Our migrated job-search archive needs a dependable source of truth before the next application round. Inspect `/root/data/` and create `/root/results/resume_register.json` that identifies the current master, inventories the tailored versions, reconciles every submitted application to the résumé actually sent, and builds a prioritized action queue for conflicts, refreshes, and archiving. Follow the snapshot’s documented reconciliation and lifecycle rules; when evidence conflicts, leave the link unresolved with its candidates rather than guessing, and preserve old files through archiving rather than deletion.

Structure `resume_register.json` with `canonical_master` as an object and `versions`, `applications`, and `actions` as top-level arrays. Preserve `master_id`, `version_id`, and `application_id` in their respective records. Each submitted application must identify the version actually sent; when that cannot be resolved, set the link status to unresolved and provide `candidate_version_ids` instead of choosing one.
