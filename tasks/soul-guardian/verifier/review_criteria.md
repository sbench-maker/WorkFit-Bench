# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The machine-readable incident handoff, recovered workspace, and updated guardian state all exist and can be opened. |
| `completion__policy_response` | Rule test | Restore-mode drift is recovered to its approved content, alert-only and missing-file cases remain for review, clean and ignored files are not changed, and current drift is not silently approved. |
| `completion__evidence_integrity` | Rule test | The updated state preserves the original audit history, appends valid chained incident events, retains reviewable patches for detected drift, and quarantines pre-restore content without inventing unrelated evidence. |
| `completion__incident_judgment` | LLM Judge | The handoff distinguishes the restored critical drift from retained alert-only changes and the missing file, prioritizes the suspicious control-bypass changes, and gives proportionate human-review guidance without treating actor metadata as proof of authorship. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
