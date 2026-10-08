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

FulfilFlow's order service has outgrown its tenant-keyed JSON tables, and the backend team needs a safe PostgreSQL 16 redesign before the next volume step. The current model, workload sample, domain rules, and capacity targets are under `/root/data`.

Produce `/root/results/schema.sql` and `/root/results/architecture.md` with the target relational model, constraints and workload-driven indexes, plus the partitioning/replication and staged migration/rollback plan. Preserve tenant isolation, financial history, and idempotent ingestion; keep the transactional source of truth in PostgreSQL 16.
