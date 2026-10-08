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

Checkout operations has three React screens with inconsistent one-off styles; the next release needs a small shared foundation.

Use the brand brief, UI inventory, and accessibility notes in `/root/data/` to create `/root/results/orbit-ds/` as an implementation-ready React/TypeScript starter: W3C-style design tokens, light/dark CSS-variable themes, and documented Button, TextInput, FormField, Alert, and Modal primitives/compositions. Preserve the approved palette and observed variants, make native props/ref behavior usable, and meet WCAG 2.1 AA keyboard, focus, labeling, error-announcement, and dialog expectations. Include a concise README with component hierarchy, usage examples, and theme setup.
