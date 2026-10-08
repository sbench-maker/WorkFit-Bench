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

Add the web-research feature to the existing Python service in `/root/data/research_app` and return the completed project at `/root/results/research_app`.

- Queries must discover candidates before fetching full page content; only the top three usable results should be hydrated.
- Keep the current CLI JSON contract and preserve result ranking while tolerating individual page failures.
- Configuration must work with hosted or self-hosted deployments without committing secrets, and the offline mock must exercise the real integration path.
