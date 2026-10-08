---
title: <Sequence>
snapshot_id: remotion-mirror-2026-08-15
canonical_url: https://www.remotion.dev/docs/sequence
---

# <Sequence>

Offset, trim, and locally time children on the composition timeline.

A `<Sequence from={90}>` hides its children before global frame 90 and shifts their local timeline. Inside that sequence, `useCurrentFrame()` returns `0` when the composition is at frame 90. With `durationInFrames={60}`, the children are mounted for local frames 0 through 59.

Nested sequences add their offsets. A negative `from` trims the beginning of a child. `premountFor` can mount children before their visible start for warm-up and is available from Remotion 4.0.140.
