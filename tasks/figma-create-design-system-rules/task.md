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

Set up Codex’s project-level Figma-to-code rules for the fictional Emberline Console snapshot in `/root/data/project`, using the captured offline Figma MCP response in `/root/data/figma_mcp`. Preserve the repository’s existing contributor instructions and make the guidance match the conventions actually present, including component reuse, tokens and styling, assets, architecture, accessibility, and validation. Save the complete, ready-to-use file as `/root/results/AGENTS.md`.
