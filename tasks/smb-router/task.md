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

These owner messages are waiting in our small-business concierge queue.

Use the frozen profiles, connector snapshot, and pending messages under `/root/data/` to select the single best next step for every case, then draft a concise, context-aware owner reply. Flag missing connectors or unavailable portions, offer a fallback only when genuinely useful, and ask before anything runs; handle ambiguity, onboarding, overviews, and out-of-scope requests without inventing capabilities. Save a mergeable JSON response set to `/root/results/routing_responses.json`, preserving every `case_id`.

Structure `routing_responses.json` as an object with a top-level `responses` array. Each response must contain `case_id`, `route`, `connectors`, `reply`, `requires_confirmation`, and `fallback`. Use one response per pending case and one selected route per response. Set `fallback` to `null` when no fallback is warranted, and keep the reply in proposal form because no action has been authorized.
