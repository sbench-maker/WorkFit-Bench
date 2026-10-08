# Frozen creator analytics export

This directory contains fictional, deterministic data for Mira Chen's four social channels. It is an offline export, not a live service snapshot.

## Files and joins

- `report_config.json` defines the reporting cutoff, windows, platform order, and metric/ranking definitions.
- `daily_metrics.csv` has one row per platform and date. Use `platform` to group the series.
- `posts.csv` contains post-level performance; join `platform` and use `post_id` for related comments.
- `trending_topics.csv` is already ranked within platform and includes ten 24-hour sparkline points.
- `comments.csv` includes moderation status; only approved comments are eligible for display.
- `DESIGN.md` is the visual contract for the dashboard.

All totals and comparisons must use complete rows through the configured cutoff. The newest partial-day rows are present so the dashboard can disclose freshness without treating them as a performance decline.
