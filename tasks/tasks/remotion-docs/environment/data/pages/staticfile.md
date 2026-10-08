---
title: staticFile()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/staticfile
---

# staticFile()

Reference files from the public directory using a deployment-safe URL.

Place local static assets in the project's `public` directory and call `staticFile()` with the path relative to that directory, for example `staticFile('team intro.mp4')`. The helper URL-encodes filenames and respects a configured Remotion base path.

Do not include `public/` in the argument and do not import a public file as a module. `staticFile()` is for local public assets; pass remote HTTP URLs directly to media components.
