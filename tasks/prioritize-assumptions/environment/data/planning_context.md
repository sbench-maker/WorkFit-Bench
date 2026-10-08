# Northstar Care roadmap planning context

The product council is freezing the next roadmap on 2026-09-30. The snapshot is fictional and complete: `assumptions.csv` contains the current assumption register, and each assumption has 12 linked rows in `research_observations.csv`. The confidence percentages are the council's current calibrated estimates; do not replace them with the observed completion rate.

## Scoring and decision rules

For each research row, calculate normalized opportunity as:

`(importance_1_5 / 5) × (1 - current_satisfaction_1_5 / 5)`

For each assumption:

- `Impact = mean(normalized opportunity across its research rows) × quarterly_customers_affected`
- `Risk = (1 - confidence_pct / 100) × validation_effort_days`

Round displayed scores to two decimal places only after calculating them. Impact is **high at 100 or above**; Risk is **high at 2.00 or above**. Values on either threshold belong to the high side.

Use the matrix consistently:

- high Impact / high Risk: test before committing
- high Impact / low Risk: proceed to implementation
- low Impact / high Risk: reject from this roadmap
- low Impact / low Risk: defer

Within the test-first group, larger combined exposure (`Impact × Risk`) is normally more urgent, but an earlier decision deadline or a binding privacy constraint may justify moving an item up if the rationale is stated.

## Experiment guardrails

Discovery has a two-week window. Each individual experiment must take no more than five setup days, stay out of production, and follow the assumption-specific constraint. Use only the capacities and measurement capabilities listed in `experiment_resources.csv`. The council wants observable behavior rather than survey intent. A proposal is actionable only if it names the behavior, success metric, numeric threshold, sample/capacity, and the roadmap decision that follows a pass or fail.
