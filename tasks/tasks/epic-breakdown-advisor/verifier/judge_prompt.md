# Completion-only Judge instructions

Judge only the `llm_judge` delivery conditions in `evaluation_rubric.json`. The rule conditions are decided by their mapped tests. Use the task request, supplied local data, input-completeness manifest, and submitted artifacts or state. Do not use the model identity, trajectory, source Skill, or hidden oracle.

For each assigned condition, return exactly 10 if every substantive delivery clause is met and 0 otherwise. There are no quality points, partial credit, or scores between 0 and 10. Do not grade style, polish, length, or extra scope unless the task explicitly makes them a delivery condition. Accept semantically equivalent headings, schemas, and file layouts that deliver the same requested outcome. For an all-record or exact-data requirement, inspect coverage and counterexamples; do not infer success from a few examples.

Cite concrete files, sections, records, values, or behavior for each decision. For a 0, identify the unmet clause and evidence. For a 10, include a `counterexample_check` describing a plausible missing or incorrect case that you checked. If relevant evidence cannot be inspected for infrastructure reasons, report it in `limitations`; do not call it a submission failure.

## Assigned LLM delivery conditions

- `completion__usable_story_set` — **Usable, testable, sprint-sized story set**: The requested Markdown plan is readable and substantive, contains a meaningful set of user stories with persona/action/outcome and Given/When/Then acceptance criteria, and gives each story an estimate no higher than the frozen five-point ceiling.
- `completion__vertical_splitting_quality` — **Vertical slicing and pattern reasoning**: The selected split patterns fit the epic, the first slice traverses the complete requester-visible return journey in a genuinely simple case, later slices add coherent user-valued variations, and no story is merely a technical layer or isolated workflow stage.

Return one JSON object with `scores`, `hard_fail`, `hard_fail_reason`, `limitations`, and `summary`. `scores` must contain exactly one item per assigned LLM condition and no rule conditions. Each item requires `criterion_id`, `score` (0 or 10), and non-empty `evidence`; include `counterexample_check` for a pass. Set `hard_fail` to false and `hard_fail_reason` to JSON null; record every delivery failure as a 0 on its named condition. Output JSON only.
