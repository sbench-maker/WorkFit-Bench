# Offline fixture guide

All entities and observations in this folder are fictional and were constructed locally. `campaign_config.json` is the source of truth for reporting windows, metric definitions, alert rules, platform order, and data-quality handling. `daily_platform_metrics.csv` contains platform-day activity and follower snapshots; blank values are meaningful and must not be coerced to zero.

`content_posts.csv` supplies approved content, formats, conversions, clicks, and comment sentiment. `hourly_engagement.csv`, `weekly_operations.csv`, and `geo_conversions.csv` supply the deep-chart series. Display units should remain honest: percentages for engagement/retention/sentiment, minutes for SLA, a one-decimal multiplier for ROI, and counts for funnel or geography.
