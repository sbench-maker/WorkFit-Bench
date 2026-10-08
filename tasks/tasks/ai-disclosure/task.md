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

The retry-budget feature branch is ready for PR, and its opted-in AI contribution record needs closing out.

Inspect the repository snapshot at `/root/data/repo`, including the existing branch disclosure, commit history, and session notes. Verify recorded work against the current files and human follow-up changes, then write the finalized disclosure to `/root/results/.claude/disclosures/retry-budget-v2.md` and a categorized, copy-paste PR block to `/root/results/pr-disclosure.md`. Preserve the internal audit trail, reflect meaningful human co-creation, and exclude anything before opt-in.

In the PR block, use the three contribution headings `Autonomous`, `Assisted`, and `Advised`, placing each contribution under exactly one heading. Keep the internal branch disclosure's existing audit comments and machine-readable metadata intact rather than flattening it into the public summary.
