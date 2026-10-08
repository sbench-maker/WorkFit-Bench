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

The `feature/batched-routing` changes in `/root/data/inference-gateway` need a security-and-auth second opinion before the PR. Run both local Codex and Gemini reviewers against the branch diff from `main`, including the repository’s `AGENTS.md` conventions; compare where they agree and differ, and don’t report pre-existing behavior as a patch finding.

Save a consolidated JSON review to `/root/results/review.json` with each reviewer’s findings, the comparison, and an overall merge recommendation.
