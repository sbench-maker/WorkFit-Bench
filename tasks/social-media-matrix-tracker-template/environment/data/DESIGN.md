# Moonwake Studio dashboard direction

Build a cinematic, data-dense review surface for the fictional **Night Bloom** campaign. The default dark theme should feel like a night trail rather than a generic neon admin panel; the light theme should remain calm and editorial.

## Color

- Dark background: `#07131A`; elevated background: `#0B1D25`; glass panel: `rgba(15, 35, 44, .76)`.
- Primary text: `#F2F7F6`; muted text: `#9EB4B7`; hairline: `rgba(174, 220, 215, .16)`.
- Coral accent: `#FF6B5E`; mint signal: `#53E2C2`; moon-gold: `#F3C969`; danger: `#FF7187`.
- Light background: `#F3F0E8`; light panel: `rgba(255, 255, 255, .9)`; light text: `#172428`.

## Typography

Use a system sans-serif stack for controls and numbers, with Georgia as the display face. Do not import web fonts. Keep labels compact but never smaller than 11px; large KPI figures should be easy to scan.

## Layout

Use a 1540px maximum canvas with a concise hero, a four-platform matrix, a four-KPI strip, and dense chart sections below. At widths below roughly 1260px, multi-column regions must collapse cleanly rather than clip.

## Components and motion

Panels use restrained glass blur, 14–18px radii, thin borders, and soft depth. Reserve coral for the selected state and focal series; use mint for positive movement and gold for warnings. Motion should be subtle, respect `prefers-reduced-motion`, and never interfere with reading or chart interaction.
