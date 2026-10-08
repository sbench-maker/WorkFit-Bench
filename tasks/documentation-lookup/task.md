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

We’re moving an async invoice worker to FluxCache Python 4.2 and need an answer grounded in the current docs, not remembered v3 behavior. Use the offline Context7 snapshot in `/root/data` to identify the official versioned library and confirm installation, client setup, transaction retries, and shutdown.

Write `/root/results/migration_note.md` with a minimal production-safe example and supporting snapshot section IDs. Flag the old v3 names we must remove, and don’t include credentials.
