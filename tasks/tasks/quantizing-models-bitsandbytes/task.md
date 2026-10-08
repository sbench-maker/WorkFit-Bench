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

Turn the frozen model catalog, GPU inventory, deployment queue, and operating policy in `/root/data` into `/root/results/quantization_plan.json` for Hugging Face causal-LM inference. For every request, choose the least-memory feasible option among 4-bit NF4, 8-bit INT8, FP16, and rejection while respecting accuracy, compatibility, reserved VRAM, non-weight load, latency, and permitted CPU offload. Include BitsAndBytesConfig-compatible kwargs and load settings for accepted jobs, traceable memory figures, reconciled totals, and concise operator notes that identify the actual blocker or offload trade-off.

Use `planning_policy.json` for calculation rules and decision priority when it differs from general background guidance. Provide one identifiable decision per deployment request, retaining the request, model, and GPU IDs. For accepted requests, keep quantization kwargs separate from model-loading settings; for rejected requests, report the binding constraint instead of fabricating a configuration.
