---
title: useVideoConfig()
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/use-video-config
---

# useVideoConfig()

Read the active composition's width, height, fps, and duration from a React component.

`useVideoConfig()` returns the configuration of the composition currently being rendered: `width`, `height`, `fps`, and `durationInFrames`. It may only be called from a React component that is rendered inside a Remotion composition. For values outside React, pass the configuration explicitly rather than calling the hook.

The returned duration reflects calculated composition metadata, including any value resolved from input props. Do not duplicate frame-rate constants in child components when the composition configuration is the source of truth.
