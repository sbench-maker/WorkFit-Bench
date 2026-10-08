# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_integrity` | Rule test | The requested index.html is a readable, substantive single-file dashboard that does not depend on external assets or network requests. |
| `completion__metric_accuracy` | Rule test | Followers, weekly follower gain, weighted engagement rate, likes, and reposts agree with the frozen complete-day records for every platform, and the partial-day cutoff is clearly disclosed. |
| `completion__platform_sync_scope` | Rule test | X, LinkedIn, YouTube, and Instagram are all selectable, and the dashboard exposes synchronized KPI, growth, top-post, topic, and comment regions for the active platform. |
| `completion__trend_content_fidelity` | Rule test | Each platform's 30-day follower view carries its named growth events, and its highest-click complete-week post, leading ranked topics, and leading approved comments are represented accurately. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
