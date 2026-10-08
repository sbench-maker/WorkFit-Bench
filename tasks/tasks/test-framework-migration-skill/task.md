---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 1200.0
  os: linux
  cpus: 2
  memory_mb: 4096
  storage_mb: 10240
---

Our Cypress checkout regression project under `/root/data/cypress_project` is ready to move to Playwright Test with TypeScript. Deliver the migrated, runnable project in `/root/results/playwright_project`.

- I need every existing checkout behavior preserved, including failure handling and the receipt popup.
- Keep it deterministic and offline, with the app base URL overridable via `BASE_URL` for CI.
- Remove Cypress-only code and dependencies, and leave a brief migration note with the validation command.
- The image provides `@playwright/test` 1.55.0, TypeScript 5.9.2, Chromium, and its OS dependencies. Declare those exact package versions, use the preinstalled `playwright` command for validation, and do not run `npm install`, `npx playwright install`, or `playwright install`. Do not include `node_modules` in the delivered project.
