# Mira Studio Analytics — Design System

## Color

- `--surface`: `#0f1720`
- `--surface-raised`: `#172431`
- `--surface-elevated`: `#203142`
- `--on-surface`: `#f4f7fa`
- `--on-surface-variant`: `#aab8c5`
- `--outline`: `#334b5f`
- `--accent`: `#59e0c1`
- `--accent-soft`: `rgba(89, 224, 193, 0.14)`
- `--warning`: `#f3c969`
- `--danger`: `#ff8d8d`

Use only these color tokens. Platform identity is communicated by name or monogram, not by platform brand colors. The accent is reserved for the active platform, the primary chart line, and one high-value callout.

## Typography

- Display and UI: `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Data: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
- Display headline: 38px / 1.1 / 700
- Section title: 18px / 1.25 / 650
- KPI value: 32px / 1.0 / 720
- Body: 14px / 1.55 / 400
- Label: 11px / 1.2 / 700 with 0.1em tracking and uppercase text

## Layout

- Desktop canvas: fluid, max width 1440px; outer margin 32px; 12-column grid.
- Spacing scale: 4, 8, 12, 16, 24, 32px.
- Primary dashboard grid: chart 2/3, top-post panel 1/3.
- Lower grid: equal-width topics and comments panels.
- At widths below 860px, KPI and main grids collapse without horizontal scrolling.

## Components

- Cards use the raised surface, 1px outline, 16px radius, and no heavy drop shadow.
- Active controls use the accent-soft surface plus an accent outline.
- Buttons are 40px tall with 10px radius; focus states need a visible 2px outline.
- Header and summary strip stay sticky; content below them scrolls.
- Charts use inline SVG with subtle grid lines and direct labels on important points.
- Motion is limited to 160ms color, border, and opacity transitions; honor `prefers-reduced-motion`.
