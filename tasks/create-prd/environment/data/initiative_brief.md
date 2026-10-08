# RelayDesk Batch Triage initiative brief

Snapshot date: 2026-08-31. RelayDesk, the company and every account in this bundle are fictional.

## Product and strategy

RelayDesk is a B2B support operations workspace. Agents receive customer tickets in shared queues, then set an owner, priority, and routing tags before specialist work begins. Today those routing fields are edited one ticket at a time.

The 2026 product strategy is to make high-volume support work faster without weakening customer controls. Batch Triage is the proposed initiative. It should help an operations lead act on a filtered set of tickets, see the impact before confirming, and understand the outcome afterward.

## Business objective and pilot contract

The baseline dataset is `triage_sessions.csv`. An eligible baseline session is a manual session with 10–50 open tickets and no permission exception (`permission_blocks = 0`). Metrics use all eligible sessions through the snapshot date, not only pilot-candidate accounts.

Leadership approved these pilot targets:

- Within six weeks of pilot start, reduce median completion time for eligible sessions by at least 35% from the supplied baseline.
- By pilot week six, keep misrouted tickets at or below 2.0% of tickets handled with Batch Triage.
- By pilot week six, at least 75% of eligible pilot agents should use Batch Triage on three or more days per week.
- Every applied bulk change must have a per-ticket audit event; no unauthorized change may be applied.

Instrumentation must distinguish selected, eligible, changed, skipped, failed, and retried tickets. Product Analytics owns the metric definitions before pilot enrollment.

## People and decisions

The named contacts are in `stakeholders.csv`. The decision forum is the weekly Product, Engineering, Design, Security, Accessibility, Support Operations, and Analytics review.

Committed decisions:

- v1 is for human-confirmed routing edits inside one queue.
- Existing RelayDesk permissions remain authoritative. Batch Triage must not broaden access.
- The pilot will include Team and Scale accounts already marked as pilot candidates. It is not a plan-wide launch.
- A launch decision needs target movement plus qualitative feedback from agents and operations leads.

Open assumptions for human review:

- Saved views will make the feature discoverable enough without a new home-page entry.
- A 50-ticket batch is large enough for most useful sessions even though surge queues can be larger.
- Users will accept partial success when skipped and failed items are explained clearly.
- Setting priority in bulk will not create harmful alert volume for specialist teams.

## Conflicting asks

Sales asked for 500-ticket batches, automatic routing rules, cross-queue selection, and bulk status changes in the first release. Those asks are not commitments. Security will not approve cross-queue actions until permission behavior has been separately tested. Support Operations wants preview and partial success before any automation. Engineering says the current write path can safely support only 50 tickets per job without a new job service. Changing status can trigger customer automations and must not be bundled with routing-field work.

## Non-goals

This initiative does not write customer replies, summarize ticket text, change SLAs, replace specialist review, or create a new permissions model.
