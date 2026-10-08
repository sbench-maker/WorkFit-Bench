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

The Orion 4.8 production change packet is ready for release review. Using the draft Word document, corporate template, and release facts in `/root/data`, produce `/root/results/orion_4_8_release_packet.docx`.

- Keep every operational step, rollback warning, and approval row while replacing placeholders and correcting contradictions against the release facts.
- Match the template's page setup, styles, header/footer, and working heading hierarchy and table of contents.
- Make the packet easy for an engineer to navigate and an approver to sign without manual repair.
