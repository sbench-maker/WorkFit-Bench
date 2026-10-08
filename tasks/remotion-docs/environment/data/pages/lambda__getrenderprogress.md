---
title: getRenderProgress()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/lambda/getrenderprogress
---

# getRenderProgress()

Poll the status and result of a Remotion Lambda render.

Pass the `renderId`, `bucketName`, function name, and region to `getRenderProgress()`. Poll until `done` is true. When complete, use `outputFile` from the response; do not guess an object URL from the render ID.

Inspect `fatalErrorEncountered` and `errors` before treating a job as successful. Progress responses and rendered artifacts can be removed by the deployment's lifecycle rules, so persist business records separately.
