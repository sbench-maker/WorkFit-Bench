# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | LLM Judge | The requested index.html exists, opens as a self-contained HTML document, identifies the company and period, and exposes the requested report sections. |
| `completion__financial_summary_accuracy` | Rule test | Executive KPIs and the Q3-versus-Q2 P&L agree with reportable ledger and customer data, use the defined period basis, and reconcile across line items. |
| `completion__analysis_view_fidelity` | LLM Judge | The trailing-12-month revenue view covers the correct month range and data, while the Q3 operating-cost breakdown reports the correct cost-center totals and units. |
| `completion__top_account_accuracy` | Rule test | The report presents the five highest reportable Q3 ARR accounts with their correct ARR, plan, and status, excluding non-reportable or lower-ranked accounts. |
| `completion__executive_interpretation` | LLM Judge | The report includes an opening executive summary and Q4 outlook that state guidance, material performance drivers, and account or cost risks using the supplied figures. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
