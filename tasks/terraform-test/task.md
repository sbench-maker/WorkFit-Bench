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

Build a credential-free Terraform regression suite for the module in `/root/data/edge_delivery`. Cover default and customized topology, conditional private endpoints, protected tags, and invalid or unsafe inputs, including the production HA boundary. Keep every scenario plan-only so it is safe for pull requests, and make failures actionable for triage. Save the completed test file as `/root/results/edge_delivery_unit_test.tftest.hcl`; it must pass against the supplied module with `terraform test` without network access.
