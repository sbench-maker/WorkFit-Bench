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

We need a discovery brief before the CRM roadmap review.

Summarize the full customer interview in `/root/data/interview_transcript.txt` as a structured Markdown brief at `/root/results/interview_summary.md`. Capture the participants and context, current solution, what works and fails, each underlying job with its desired outcome plus importance and satisfaction, notable evidence, and dated owner/action follow-ups. Keep the language plain, treat corrected statements as authoritative, separate tentative ideas from commitments, and use “-” where the transcript does not support an answer.
