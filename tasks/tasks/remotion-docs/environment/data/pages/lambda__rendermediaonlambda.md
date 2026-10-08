---
title: renderMediaOnLambda()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/lambda/rendermediaonlambda
---

# renderMediaOnLambda()

Start a Remotion Lambda render and receive identifiers used for progress polling.

`renderMediaOnLambda()` starts a render and returns a `renderId` and `bucketName`. Persist both values: together they identify the render for subsequent progress checks. The call returning does not mean the video has finished.

Supply the deployed function name, serve URL, composition name, input props, codec, and region used by the deployment. The caller and the Lambda function must use the same AWS region.
