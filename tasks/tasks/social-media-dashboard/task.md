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

Build a single-file creator social analytics dashboard from the frozen exports and `DESIGN.md` in `/root/data/`, and save it as `/root/results/index.html` for Monday's campaign review.

- I need X, LinkedIn, YouTube, and Instagram switching to keep KPIs, follower trend and campaign spikes, top post, topics, and comments in sync.
- I'm worried the incomplete day will make performance look worse; show the data cutoff clearly and base comparisons on complete days.
- I need it presentation-ready, responsive, and fully offline with no external assets.
- Use accessible platform controls and a semantic main landmark. Embed the final per-platform KPI, trend annotations, top post, topics, comments, and cutoff view model as valid JSON in a `<script type="application/json">` element so runtime-rendered values remain traceable to the selected platform during review.
