---
title: delayRender() and continueRender()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/delay-render
---

# delayRender() and continueRender()

Block rendering while asynchronous resources are prepared.

Call `delayRender()` to obtain a handle before starting asynchronous work. Rendering remains blocked until the same handle is passed to `continueRender(handle)`. Create the handle once, not on every React render.

On success, call `continueRender(handle)`. If the operation fails, report that failure with `cancelRender(error)` instead of continuing with missing data. A delayed render times out unless the delay is resolved; the timeout can be configured when the handle is created.
