---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 900.0
  os: linux
  cpus: 2
  memory_mb: 4096
  storage_mb: 10240
---

Our fictional Acme gateway needs its staged query-budget policy applied before the next load test. The offline Apollo Router checkout and policy fixtures are in `/root/data/router_checkout`; it already includes the local test harness and plugin conventions.

Complete the native Rust `query_budget` plugin in a copied checkout at `/root/results/router_checkout`. Carry the client tier from the HTTP request into execution, enforce the configured per-tier and mutation cost ceilings with the policy's GraphQL error, leave disabled mode untouched, and wire, register, and configure the plugin. Keep the existing public interfaces and make `cargo test --offline` pass.
