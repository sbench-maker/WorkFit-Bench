# Alder Peak Systems finance package

All entities and records in this directory are fictional and were constructed for this reporting exercise.

## Reporting basis

- Report Q3 FY2025 (2025-07-01 through 2025-09-30) against Q2 FY2025.
- Use `recognition_date`, not `posting_date`, to assign a ledger entry to a period.
- `amount_usd` is signed: revenue is positive; cost of revenue and operating expenses are negative.
- Include only rows where `include_in_report` is `yes`. Excluded rows represent financing or duplicate sandbox entries and are outside management P&L.
- Gross profit = revenue + cost of revenue. Operating income = gross profit + operating expenses. A negative operating income is the operating loss.
- Gross margin = gross profit / revenue.
- Net new MRR = the sum of `q3_end_mrr_usd` minus the sum of `q2_end_mrr_usd` for reportable accounts.
- Cash runway = 2025-09-30 cash divided by the absolute average monthly Q3 operating loss. Show one decimal month; if the company is not burning cash, describe runway as not meaningful rather than dividing by a loss.
- Top accounts are the five reportable customers with the highest Q3 ending ARR (`q3_end_mrr_usd * 12`). Preserve their supplied plan and Q3 status.

## Files

- `ledger.csv`: journal-level P&L activity, including negative refunds and excluded rows.
- `customer_accounts.csv`: Q2/Q3 ending MRR, plan, region, and account status.
- `company_context.json`: report metadata, ending cash, preparer, and dated outlook assumptions.
- `DESIGN.md`: approved presentation tokens and layout guidance.

Dollar amounts are whole USD. Round displayed percentages to one decimal and percentage-point changes to one decimal where space permits. Charts should label their periods and units; narrative claims should be supported by these files.
