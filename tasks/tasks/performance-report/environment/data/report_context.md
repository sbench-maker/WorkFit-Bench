# August 2026 marketing review context

LumaForge is a fictional B2B workflow-software company. Leadership will use this report to set September demand-generation priorities and decide where to hold, reduce, or shift effort. The reporting window is August 1–31, 2026; July 1–31 is the comparison period. Amounts are USD.

## Data semantics

- `impressions` is platform impressions for paid and organic search, and delivered messages for Email.
- `leads`, `mqls`, and `new_customers` are channel-attributed outcomes and may be summed across the supplied rows for this report.
- `attributed_revenue_usd` is reported attributed revenue, not total company revenue.
- `revenue_tracking_coverage` estimates the captured share of attributed revenue for that row. A value below 1 means revenue is incomplete; lead and customer counts remain valid. Coverage-adjusted revenue may be shown as an estimate, clearly labeled, by dividing reported revenue by coverage.
- CPA is paid spend divided by new customers. ROAS is attributed revenue divided by paid spend. Do not calculate CPA or ROAS for channels with zero spend.
- Target direction is explicit in `august_targets.csv`: `at_least` means higher is better and `at_most` means lower is better.

Daily rows join to campaign metadata and dated events through `campaign_id`. Event notes provide operational context, not proof of causation; causal explanations should be framed as hypotheses unless the arithmetic itself is definitive.
