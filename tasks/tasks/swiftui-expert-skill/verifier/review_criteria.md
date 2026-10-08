# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The revised LoopLog project is readable at the requested path and retains its production source, localization catalog, and 500-record offline fixture. |
| `completion__observation_data_flow` | Rule test | The app owns the observable store, the feed receives rather than re-owns it, local view state is private, and rows do not freeze passed activities as state. |
| `completion__stable_identity` | Rule test | Dynamic rows use persistent activity identity, and a favorite action targets the visible activity UUID rather than a filtered or sorted position. |
| `completion__localization` | Rule test | All feed and detail interface concepts are backed by complete English/Japanese catalog entries, while dates and distances use locale-aware formatting and user titles remain data. |
| `completion__modern_swiftui` | Rule test | The edited screen uses current navigation and modifier forms, a semantic button for the row action, and an animation scoped to the favorite change. |
| `completion__interaction_quality` | LLM Judge | Search, favorites filtering, sorting, empty state, detail navigation, and favorite toggling remain a coherent user flow, with one state-aware VoiceOver action per row and no conflicting tap targets. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
