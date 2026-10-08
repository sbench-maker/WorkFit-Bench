# Scheduled project digests — approved brief

## Outcome

OrbitDesk project owners want one weekly email that summarizes recent project activity. The first release lets a project administrator configure one schedule per project and lets any active project member view that schedule. Delivery must use the existing outbox and mail worker; API requests must never send email directly.

## Release scope

### Schedule settings

- Store at most one digest schedule per project.
- A schedule contains an IANA time zone, weekday `1`–`7` (Monday–Sunday), local send time in `HH:MM`, recipient mode (`all_active_members` or `admins_only`), and enabled state.
- `GET /api/projects/:projectId/digest-schedule` is available to active project members and returns `404` when no schedule exists.
- `PUT /api/projects/:projectId/digest-schedule` creates or updates the schedule. Only project `admin` and `owner` roles may write.
- Updates use the repository's versioned-write convention: the current version is required and a stale write returns `409`. A successful write recalculates `nextRunAt`.
- `POST /api/projects/:projectId/digest-preview` is available to admins and owners. It returns a preview from the prior seven complete days without persisting a schedule, creating a run, writing an outbox event, or writing an audit event.
- Validate the IANA time zone, weekday range, strict 24-hour time, and recipient-mode enum at the API boundary. Do not accept a fixed UTC offset as a time zone.

### Digest content and recipients

- Summarize task creations, task completions, comments, and membership changes from the existing activity feed. Include totals and up to 20 most recent items, with stable newest-first ordering by `(occurred_at, activity_id)`.
- `all_active_members` includes users whose membership status is `active`; `admins_only` further restricts roles to `admin` and `owner`.
- Exclude users with `email_opt_out = true`, even if their membership is active.
- If recipient resolution yields zero users, record a `skipped` run with `ZERO_RECIPIENTS` and do not create an outbox event.

### Scheduling and delivery

- The scheduler polls every five minutes and considers rows whose `enabled = true` and `next_run_at <= now`.
- Claim a due occurrence exactly once. A database uniqueness constraint on `(schedule_id, scheduled_for)` is required so overlapping worker processes cannot duplicate a run.
- After a claim, advance `next_run_at` and append one `project.digest.requested` event to the existing transactional outbox. Use a stable dedupe key derived from the schedule and occurrence.
- The existing mail worker consumes that event, renders the digest template, fans out to the resolved recipients, and records the run as `sent` or `failed`. Do not add a second queue or send path.
- Failed delivery remains visible on the run and follows the outbox consumer's existing retry policy. Retrying must reuse the original occurrence and dedupe key.

### Product safety and rollout

- Gate the API, scheduler, mail consumer, and settings UI behind `scheduled_project_digest`; default the flag to off.
- Append `project_digest.schedule_updated` to the existing audit log after a successful create, update, enable, or disable. Record changed field names, actor, and project, but never recipient email addresses.
- Disabling a schedule retains its history and prevents new claims. Re-enabling recalculates the next future occurrence; missed weeks are not replayed.
- The migration must be backward-compatible, create no schedules for existing projects, and support rollback before the feature flag is enabled.

## UI

Add a "Project digest" panel to project notification settings. It shows loading, no-schedule, editable, saving, stale-version, and generic-error states. The form exposes weekday, local time, time zone, recipient mode, and enabled state; preserve unsaved values after a failed save. Reuse the existing `SettingsPanel`, `TimezoneSelect`, query client, and permission hooks. Associate labels and error text accessibly with their inputs.

## Quality and release checks

- Add migration/schema checks, API authorization and validation coverage, stale-write coverage, digest ordering/limit tests, recipient filtering tests, worker overlap/idempotency tests, zero-recipient behavior, audit redaction checks, UI state tests, and a flag-off end-to-end check.
- Existing `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` must stay green.
- The first production enablement is one internal project, followed by mail/outbox/run-status monitoring before broader rollout.

## Decisions that remain open

1. **DST gaps and overlaps:** Product must choose whether a nonexistent local time is skipped or shifted, and which occurrence is used when a local time repeats. Do not silently choose a policy in implementation.
2. **Activity visibility:** Security must decide whether digest content is filtered to what each recipient can currently view or whether the project-wide feed is acceptable. This changes fan-out and caching design.
3. **Failure threshold:** Operations has not chosen the alert threshold for repeated digest delivery failures.

## Explicit non-goals

Daily or monthly cadence, multiple schedules per project, arbitrary external recipient addresses, custom templates, attachments, per-user delivery times, replaying missed weeks, and a new queue system are not part of this release.
