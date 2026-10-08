# Harborlight partner console snapshot

This is a deterministic, fictional pre-launch static-site snapshot. It is deployed by the
Nginx fragment in `deploy/headers.conf`; Vite creates the production bundle. No network
service is needed to inspect or harden it.

## User-visible contract

- `/index.html` is the console home and greets the partner named by the optional `name`
  query parameter as plain text.
- `/activity.html` shows all 240 local activity records and filters them with the optional
  `q` query parameter. Every field in `data/activity.json` is untrusted plain text, never HTML.
- `/settings.html` offers location-aware timezone detection only after the user presses
  **Use my location** and confirms the explanation. If permission or loading fails, the page
  must show a useful message rather than fail silently.
- Navigation labels, the three routes, and the local dataset must remain available after
  hardening. The bundled `js/vendor/chartlite-1.4.2.js` is the approved offline copy of the
  tiny chart helper used on the home page.

## Deployment boundary

The session cookie is issued by the separately managed EdgeGate service. Its frozen policy
snapshot is in `deploy/edge_snapshot.json`; this repository cannot change that policy.
Application-owned response headers belong in `deploy/headers.conf`.
