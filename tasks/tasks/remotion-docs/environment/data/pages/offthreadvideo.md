---
title: <OffthreadVideo>
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/offthreadvideo
---

# <OffthreadVideo>

Render video frames reliably and control interactive buffering behavior.

`<OffthreadVideo>` extracts exact frames while rendering. Set `pauseWhenBuffering` when an interactive Player or Studio preview should pause its timeline while the browser buffers the source.

`pauseWhenBuffering` has no effect during a render, because frames are extracted rather than played in real time. It is supported for interactive playback in Chrome and Edge; do not promise identical buffering behavior in every browser.
