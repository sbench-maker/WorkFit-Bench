# Completion-only Judge instructions

Judge only the `llm_judge` delivery conditions in `evaluation_rubric.json`. The rule conditions are decided by their mapped tests. Use the task request, supplied local data, input-completeness manifest, and submitted artifacts or state. Do not use the model identity, trajectory, source Skill, or hidden oracle.

For each assigned condition, return exactly 10 if every substantive delivery clause is met and 0 otherwise. There are no quality points, partial credit, or scores between 0 and 10. Do not grade style, polish, length, or extra scope unless the task explicitly makes them a delivery condition. Accept semantically equivalent headings, schemas, and file layouts that deliver the same requested outcome. For an all-record or exact-data requirement, inspect coverage and counterexamples; do not infer success from a few examples.

Cite concrete files, sections, records, values, or behavior for each decision. For a 0, identify the unmet clause and evidence. For a 10, include a `counterexample_check` describing a plausible missing or incorrect case that you checked. If relevant evidence cannot be inspected for infrastructure reasons, report it in `limitations`; do not call it a submission failure.

## Assigned LLM delivery conditions

- `completion__artifact_scope` — **Usable PDF and requested QBR scope**: The requested PDF opens as a concise multi-page review and covers revenue, margin, customers, pipeline, opportunities, and risks.
- `completion__priorities` — **Evidence-grounded opportunities, risks, and actions**: The PDF identifies next-quarter opportunities and risks, links them to supplied evidence, and states specific owner actions.

Return one JSON object with `scores`, `hard_fail`, `hard_fail_reason`, `limitations`, and `summary`. `scores` must contain exactly one item per assigned LLM condition and no rule conditions. Each item requires `criterion_id`, `score` (0 or 10), and non-empty `evidence`; include `counterexample_check` for a pass. Set `hard_fail` to false and `hard_fail_reason` to JSON null; record every delivery failure as a 0 on its named condition. Output JSON only.
