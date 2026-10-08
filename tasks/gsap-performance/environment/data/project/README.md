# Northstar incident wall fixture

This fictional, offline checkout isolates the motion controller for a wall that can render 240 incident cards. The host application supplies `gsap` and `ScrollTrigger`; there is no package install or network step. `profile_samples.jsonl` is a deterministic synthetic trace of the current implementation, included only to make the hot paths and low-end-device symptoms concrete.

## Integration contract

`app.js` must keep exporting `mountIncidentWall({ root, win, gsap, ScrollTrigger })` and must return a cleanup function. The supplied DOM has these behaviors:

- On mount and scroll, only previously unrevealed `.incident-card` elements intersecting the viewport are revealed. Their visual entrance ends at opacity 1 and the authored position, from a 24px lower offset. A card is revealed at most once.
- `.cursor-halo` follows the latest `pointermove` coordinates within `.incident-board` with the existing 0.18-second `power3.out` response.
- `[data-action="open-drawer"]` and `[data-action="close-drawer"]` switch `.detail-drawer` between its documented open and closed state, including `data-state` and `aria-hidden`. Its fixed 360px width and endpoint positions are product behavior.
- A resize burst must eventually refresh `ScrollTrigger`, but doing that for every raw event is the current defect.
- The returned cleanup function must detach handlers, cancel pending work, and stop controller-owned animation activity. Nothing should react after cleanup.
- With `prefers-reduced-motion: reduce`, content remains at the same usable endpoints and nonessential transitions resolve immediately.

The visual endpoints are also summarized in `interaction-contract.json`. Preserve the public selectors and export; internal organization and animation composition may change.
