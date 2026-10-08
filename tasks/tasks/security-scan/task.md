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

We’re onboarding the Helio Console repository. Audit `/root/data/helio-console/.claude/` before it is approved, and save the assessment as `/root/results/security-report.json`.

- I need actionable vulnerabilities tied to file evidence, with severity and a practical remediation.
- I’m most concerned about launch blockers across settings, project instructions, MCP servers, hooks, and agent definitions.
- Please distinguish real risks from the existing safe controls, and never repeat credential-like values in the report.
