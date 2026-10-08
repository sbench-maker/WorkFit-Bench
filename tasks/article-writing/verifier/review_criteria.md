# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested Markdown newsletter exists at the requested path, is readable text, and stays within the requested 900–1,200-word range. |
| `completion__approved_fact_coverage` | Rule test | The issue includes the campaign brief's material pilot scale, measured changes, adoption signal, and launch details, while presenting the two launch thresholds as targets rather than observed Harborline outcomes. |
| `completion__source_integrity` | Rule test | The newsletter excludes specifically superseded, internal, off-record, or unapproved claims in the packet, and any direct customer quotation is faithful to an approved quotation. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
