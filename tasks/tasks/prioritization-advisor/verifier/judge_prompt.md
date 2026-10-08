# Completion-only Judge instructions

Judge only the `llm_judge` delivery conditions in `evaluation_rubric.json`. The rule conditions are decided by their mapped tests. Use the task request, supplied local data, input-completeness manifest, and submitted artifacts or state. Do not use the model identity, trajectory, source Skill, or hidden oracle.

For each assigned condition, return exactly 10 if every substantive delivery clause is met and 0 otherwise. There are no quality points, partial credit, or scores between 0 and 10. Do not grade style, polish, length, or extra scope unless the task explicitly makes them a delivery condition. Accept semantically equivalent headings, schemas, and file layouts that deliver the same requested outcome. For an all-record or exact-data requirement, inspect coverage and counterexamples; do not infer success from a few examples.

Cite concrete files, sections, records, values, or behavior for each decision. For a 0, identify the unmet clause and evidence. For a 10, include a `counterexample_check` describing a plausible missing or incorrect case that you checked. If relevant evidence cannot be inspected for infrastructure reasons, report it in `limitations`; do not call it a submission failure.

## Assigned LLM delivery conditions

- `completion__framework_fit` — **Framework choice fits AsterLane's context**: The primary recommendation is a defensible recurring prioritization framework for AsterLane's early-PMF stage, small team, uneven data, stakeholder misalignment, and mixed backlog, and its rationale distinguishes framework fit from a universal ranking claim.
- `completion__evidence_and_tradeoffs` — **Evidence-grounded diagnosis and trade-offs**: The recommendation accurately uses the packet to diagnose the RICE pilot and stakeholder conflict, treats unknown reach responsibly, and protects mandatory obligations and strategic judgment without fabricating capacity or certainty.
- `completion__implementation_design` — **Practical implementation and team governance**: The rollout is usable for recurring monthly and quarterly decisions: it defines how items enter comparison, supplies a concrete scoring or classification template, assigns collaborative roles, handles evidence and disagreements, and records gates or overrides within the team's time constraints.
- `completion__alternative_and_lifecycle` — **Alternative, safeguards, and reassessment**: The runner-up is contextually plausible with clear gains and losses, and the recommendation gives specific failure safeguards and stable reassessment triggers that avoid both framework whiplash and set-it-and-forget-it use.

Return one JSON object with `scores`, `hard_fail`, `hard_fail_reason`, `limitations`, and `summary`. `scores` must contain exactly one item per assigned LLM condition and no rule conditions. Each item requires `criterion_id`, `score` (0 or 10), and non-empty `evidence`; include `counterexample_check` for a pass. Set `hard_fail` to false and `hard_fail_reason` to JSON null; record every delivery failure as a 0 on its named condition. Output JSON only.
