# RFC-042: Workspace Export v2

Status: approved  
Target integration branch: `integration/export-v2` at `int-48`  
Owners: Platform API, Data Runtime, Trust, Admin Web, SRE

## Goal

Allow an authorized workspace owner or admin to request a revision-consistent export, follow its progress, and download a short-lived encrypted archive. Version 1 stays available until the rollout cohort is proven safe.

## Approved requirements

| ID | Requirement | Primary module | Minimum risk |
|---|---|---|---|
| R1 | Publish canonical export states, formats, and error codes without changing v1 contracts. | `libs/export-contract` | tier1 |
| R2 | Add `export_jobs` and `export_artifacts` with a reversible populated-database migration. | `db/export-schema` | tier3 |
| R3 | Permit workspace owners and admins; deny members and every service account for create and download. | `services/policy` | tier3 |
| R4 | Produce a snapshot pinned to one workspace revision, including a stable manifest during concurrent writes. | `workers/export-snapshot` | tier2 |
| R5 | Redact secrets, recovery codes, internal moderation notes, and deleted-user email addresses deterministically on retry. | `workers/export-redaction` | tier3 |
| R6 | Stream a ZIP archive under the memory budget, encrypt it with an envelope key, and expose only the artifact reference. | `workers/export-package` | tier3 |
| R7 | Implement idempotent create-export behavior and persist the initial job. | `services/export-api` | tier2 |
| R8 | Implement status plus a five-minute signed download; preserve v1 response compatibility. | `services/export-api` | tier2 |
| R9 | Record append-only audit events for create, completion, failure, download, and denied download. | `services/audit` | tier2 |
| R10 | Add the admin start/progress/download flow, including useful terminal failure messaging. | `web/admin-exports` | tier2 |
| R11 | Expire artifacts after seven days, clean orphans, and add latency/failure metrics and an operator runbook. | `ops/export-lifecycle` | tier2 |
| R12 | Gate v2 by cohort, prove v1 coexistence, and support disabling the cohort without losing job history. | `config/feature-flags` and `tests/export-system` | tier2 |

Each requirement must have exactly one accountable active work unit. A unit may own multiple requirements only when its code surface, validation, and rollback are genuinely inseparable. The failed worker attempt demonstrates that R4, R5, and R6 are not inseparable.

## Interface and ordering constraints

- R2 consumes the states from R1.
- R4 consumes R1 and persists through R2.
- R5 consumes the pinned `SnapshotManifest` from R4; redaction must finish before packaging begins.
- R6 consumes only the redacted snapshot from R5 and persists its artifact reference through R2.
- R7 requires R1, R2, and R3.
- R8 requires R1, R2, R3, and R6.
- R9 integrates after R7 and R8 and after worker terminal states from R6 are stable.
- R10 requires both API behaviors in R7 and R8.
- R11 requires R2 and R6.
- R12 is the release unit. It follows R9, R10, and R11 and owns final cross-system verification.

Independent units with satisfied dependencies may progress in parallel. A dependency means the producer must be merged before the consumer may enter the merge queue, not merely that both appear in the same wave.

## Operational constraints

- Keep already merged work; do not reopen R1.
- `WU-SCHEMA` and `WU-POLICY` have completed their unit gates. Before either merges, its branch must be rebased on the latest integration commit. Schema is already rebased; policy is not.
- Retire `WU-WORKER`. Preserve its findings, then replace it with separately reviewable snapshot, redaction, and packaging units.
- Never schedule a stalled or blocked unit for merge.
- After every queued unit merge, rerun that unit's blocking tests plus every cataloged system test whose covered requirements are all present at that point. The release unit must run all four system tests.
- Rollback must protect persisted job history. Disabling the feature flag alone is not an adequate rollback for schema, redaction, or encrypted artifacts.

## Final verification decision

The release is ready only after `SYS-01`, `SYS-02`, `SYS-03`, and `SYS-04` pass from the latest integration branch and a cohort-disable rehearsal confirms existing jobs remain inspectable.
