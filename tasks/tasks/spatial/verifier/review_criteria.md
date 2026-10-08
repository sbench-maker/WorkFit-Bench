# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested file is a readable, non-empty WGS84 GeoJSON FeatureCollection of point features with identifiable records. |
| `completion__source_scope_metadata` | Rule test | The layer contains exactly the active, coordinate-valid source venues once each, with correct point coordinates and source display metadata. |
| `completion__zone_assignment` | Rule test | Each venue has the correct covered zone, including boundary, overlap-priority, and null out-of-zone outcomes. |
| `completion__nearest_hub_distance` | Rule test | Every output venue identifies its nearest pickup hub and reports a WGS84 spheroid distance in meters within a small numerical tolerance. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
