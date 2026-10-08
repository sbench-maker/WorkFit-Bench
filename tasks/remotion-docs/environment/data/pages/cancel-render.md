---
title: cancelRender()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/cancel-render
---

# cancelRender()

Fail a render intentionally when required asynchronous work cannot complete.

`cancelRender(error)` aborts the render and surfaces the supplied error. Use it in the rejection path of work protected by `delayRender()` so a render cannot silently complete with a missing resource. Pass an `Error` object when possible.

Do not call `continueRender()` after cancelling the same operation. `cancelRender()` is available in Remotion 3.3.14 and later.
