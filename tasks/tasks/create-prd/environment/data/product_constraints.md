# Product and technical constraints

## Required v1 behavior

- Start from a saved or temporary filter inside one queue. The filter definition and queue ID are frozen when preview begins.
- Select all visible eligible tickets or choose individual tickets, up to 50 tickets in one batch.
- Support only these routing edits: assign an owner or team, set priority, and add or remove an administrator-approved routing tag.
- Before confirmation, show selected count, eligible count, proposed field changes, and any ticket that will be skipped because of permissions, stale data, or an invalid value.
- Recheck authorization and ticket version at execution time. A stale or blocked ticket is skipped; it must not cancel valid edits for other tickets.
- After execution, show changed, skipped, and failed counts plus a per-ticket reason. Retrying applies only to failed tickets and creates a new attempt record.
- Write an immutable per-ticket audit event with actor, queue, batch ID, timestamp, old value, new value, and outcome. A session-level record links all attempts.
- Preserve the current role-based permissions and field-level visibility. A preview must not reveal message text or restricted fields.
- The full select-preview-confirm-result flow must work by keyboard, expose programmatic names, manage focus after updates, and announce counts and errors to screen readers.

## Service boundaries

The existing synchronous write path supports at most 50 selected tickets. For that size, the preview service target is p95 under 2 seconds and the initial execution acknowledgement target is p95 under 5 seconds. Finishing the changes may continue in the background. Idempotency keys must prevent a confirmation retry from applying a change twice.

One queue maps to one permission context. Cross-queue selection needs a separate authorization design and is not safe to infer from v1. The current audit store retains events for 18 months.

## Deferred candidates

- More than 50 tickets per batch, which depends on a durable job service and load testing.
- Cross-queue selection, which depends on a reviewed multi-context authorization design.
- Automatic or suggested routing rules, which need their own trust, override, and measurement work.
- Bulk status changes, because they can trigger customer automations.
- One-click undo, which requires compensating actions without erasing the original audit trail.
- Bulk customer replies and any text generation.

## Design evidence available

There is no approved mockup. Design has only the current list view and the workflow notes. The PRD may describe a low-fidelity flow, but must label any interface details as proposed rather than approved.
