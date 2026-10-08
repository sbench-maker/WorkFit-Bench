# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__project_integrity` | Rule test | The delivered SDK 55 project is readable at the requested path, retains its configuration, local validation workflow, and all 24 source notes unchanged. |
| `completion__native_tabs` | Rule test | The root navigator uses static NativeTabs for Home, Saved, and Search, with Search last and configured with its native search role, and the legacy JavaScript tab navigator is removed. |
| `completion__shared_stacks` | Rule test | Home, Saved, and Search each anchor a native stack that includes one shared dynamic note-detail implementation while preserving /, /saved, /search, and /notes/:id. |
| `completion__header_search` | Rule test | Search input is provided through the native stack header and drives the preserved case-insensitive, trimmed, multi-field filtering and empty-result state without a legacy in-page text field. |
| `completion__screen_continuity` | LLM Judge | The refactor keeps Home useful as a newest-first note list, Saved limited to favorites, cards navigating to the correct note, and detail/not-found screens informative across the new navigation structure. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
