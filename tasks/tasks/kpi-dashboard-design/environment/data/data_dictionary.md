# Dashboard data dictionary

All entities and observations in this fixture are fictional. The fixed reporting month is **2025-08** and all amounts are USD.

## Metric rules

- A snapshot row represents one active paid customer at that month-end. Distinct customers, not rows in `cancellations.csv`, define the opening and closing logo counts.
- Normalize MRR from `contract_amount_usd`: monthly contracts use the amount as-is, quarterly contracts divide by 3, and annual contracts divide by 12.
- Current MRR is normalized MRR in the reporting-month snapshot. MRR growth is `(current MRR - prior-month MRR) / prior-month MRR`.
- New MRR belongs to customers present in the current snapshot but absent in the prior snapshot. Churned MRR belongs to customers present in the prior snapshot but absent in the current snapshot. Expansion and contraction compare normalized MRR for customers present in both snapshots.
- Gross logo churn is prior-month customers absent this month divided by prior-month customers. Gross revenue churn is churned MRR divided by prior-month MRR. A scheduled future cancellation and a rescinded request remain active and must not count as current churn.
- ARPA is current MRR divided by current active customers. CAC is reporting-month acquisition spend divided by customers whose `signup_date` falls in the reporting month.
- LTV is current ARPA divided by gross logo churn expressed as a decimal. LTV/CAC is LTV divided by CAC. Do not manufacture a finite LTV if churn is zero.
- A target is breached when a `min` metric falls below its threshold or a `max` metric rises above it. Only breached targets with `alert_enabled: true` belong in the actionable alert panel.

## Intended drilldowns

Use the MRR bridge to explain month-over-month movement. For churn analysis, completed cancellations effective in the reporting month may be grouped by reason, segment, or lost MRR. Owners and prescribed actions in `targets.json` make breaches operational rather than decorative.
