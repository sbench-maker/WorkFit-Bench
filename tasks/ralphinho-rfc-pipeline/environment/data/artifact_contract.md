# Orchestration handoff contract

`output.json` is consumed by the release dashboard, so it must be valid JSON and expose these semantic sections. Common equivalent key names, nesting, and ordering are acceptable to reviewers, but every object must remain identifiable.

## Work units

Provide one active unit collection plus a retired/recovery record for the stalled `WU-WORKER` attempt.

Each active unit needs:

- a stable ID and short title;
- the requirement IDs it owns and the repository modules in its scope;
- dependency unit IDs;
- a status (`merged`, `merge_ready`, `planned`, or `blocked`);
- risk level (`tier1`, `tier2`, or `tier3`);
- acceptance test IDs from `ci_catalog.json`;
- the six gate names `research`, `implementation_plan`, `implementation`, `tests`, `review`, and `merge_ready_report`, each with a meaningful state;
- a concrete rollback plan.

Keep the existing IDs for unaffected units. New replacement IDs may vary, but the old worker ID may not remain active and R4, R5, and R6 must be owned by three separate successor units.

## Dependency graph and queue

Include a graph snapshot as directed producer-to-consumer edges, plus an acyclic topological order. Include an ordered merge queue whose entries identify a unit, the required rebase target or action, merge preconditions, and post-merge test IDs. A wave-based queue is fine, but units in one wave must not depend on each other.

Only `merge_ready` units belong in the immediate queue. Planned or blocked units may appear in later queue entries only if the entry explicitly lists the predecessor merges and unfinished gates that must complete first. Merged units do not re-enter the queue.

## Recovery and release verification

Record that `WU-WORKER` is evicted, preserve its useful findings, name all narrower successor units, and state retry constraints. Include final verification test IDs and the cohort-disable/job-history check. Summarize the integration risks that most affect merge order or rollback safety.

The handoff may include additional execution-log or scorecard fields when useful. Do not invent test IDs, repository modules, requirements, or completed work.
