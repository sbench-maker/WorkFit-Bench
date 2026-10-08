# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_integrity` | LLM Judge | The requested index.html is a readable, substantive single-file dashboard that works without network-loaded scripts, styles, fonts, images, or frames. |
| `completion__metric_accuracy` | Rule test | Each platform's current 30-day followers, growth, engagement rate and comparison, impressions, conversions, coverage, top converting post, active alerts, and data-gap treatment agree with the frozen exports and business rules. |
| `completion__chart_data_fidelity` | Rule test | Hourly engagement, approved-content mix, comment sentiment, funnel, weekly SLA/ROI/retention, and geo contribution are all represented with source-consistent values and honest units. |
| `completion__interactive_analysis` | Rule test | The standalone dashboard exposes working interaction logic for theme changes, hover tooltips, point pinning, drag interval analysis, Shift+drag saved-range comparison, and live insight updates. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
