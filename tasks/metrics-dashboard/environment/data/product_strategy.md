# SignalNest product strategy and reporting notes

SignalNest is a fictional workflow-automation SaaS product. Customers receive core value when production workflows finish successfully, so the product team treats weekly successful production runs as the strongest North Star candidate. The current operating priority is reliable scale: grow completed automation volume without trading away run success or scheduler health.

Reporting uses UTC Monday-Sunday weeks. The snapshot was exported early on 2026-08-31, so every row marked `data_complete=false` is partial and must be excluded from totals, trends, and alert decisions. The latest complete week is 2026-08-24 through 2026-08-30; the comparison week is 2026-08-17 through 2026-08-23.

Definitions used by the operating team:

- Weekly successful production runs: sum `successful_runs` across complete rows in the week.
- Production run success rate: sum `successful_runs` divided by sum `production_runs`; do not average account-level percentages.
- Weekly active accounts: distinct accounts with at least 10 production runs in the week.
- Template adoption rate: sum `template_runs` divided by sum `production_runs`.
- Service error rate: sum `error_count` divided by sum `request_count` for that service and week.
- Worst daily p95 latency: maximum complete-day `p95_latency_ms` within the week; only daily aggregates are available, so do not average p95 values.
- MRR: sum account `mrr_usd` on the last complete day of the reporting period.
- Weekly gross logo churn rate: accounts whose `churn_effective_date` falls in the week divided by accounts with an active subscription on the day before the week starts.

The account roster joins to usage and MRR through `account_id`. Metric owners, targets, severity thresholds, channels, and response expectations are frozen in `metric_targets.csv`. Product analytics owns the usage export, Platform Observability owns service health, and Revenue Operations owns the MRR snapshot.
