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

Support keeps seeing the same saved contact-import failure after a workspace member leaves.

Use the resolved ticket export and related product, bug, account, and KB snapshots in `/root/data/` to draft a customer-facing troubleshooting article at `/root/results/kb_article.md`. Cover the supported workaround, affected accounts, exact error, verification, and escalation, with publishing metadata and handoff notes. Reconcile stale attempts and internal-only details; do not expose customer identities or an unconfirmed fix date.
