# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact` | Rule test | The snapshot has a readable manifest and resolvable Markdown files. |
| `completion__coverage` | Rule test | Every requested URL appears exactly once and maps to a distinct file. |
| `completion__content` | Rule test | Each file contains the page's real rendered documentation content without navigation or footer noise. |
| `completion__links_privacy` | Rule test | Per-page links are faithful and personal contact details are absent from outputs. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
