# Offline customer-delivery workspace snapshot

This directory is a frozen, fictional export of a team's mail, chat, shared action tracker, calendar, account register, roster, and OKR sheet. The snapshot time is `2026-04-17T17:00:00Z`; the weekly reporting window is April 13–17 and the next planning window is April 20–24. No network service is available and no source file should be modified.

## Object model

- `email_messages.jsonl` contains ordered messages. Messages in one `thread_id` are one mail conversation; the latest authoritative message supersedes an earlier deadline or cancellation state.
- `chat_messages.jsonl` contains team standups and thread replies. `sensitivity=restricted` content is context for the lead only and must not appear in the shareable digest or chat draft.
- `action_tracker.csv` is the current shared task sheet. Its `source_refs` use `email:<thread_id>` or `chat:<message_id>` and may contain multiple references separated by `|`.
- `calendar_events.csv` is the accepted/tentative agenda for the next workweek. `private_detail` is never shareable; an `out_of_office` event may be described only as an availability conflict.
- `accounts.csv`, `roster.csv`, and `okrs.csv` provide account ownership, team identity, and the latest objective state. Account `private_note` is lead-only context.
- `snapshot_meta.json` records the frozen dates, joins, and input row counts.

## Coordination conventions

The deliverable is a reviewable proposal, not an executed mutation. An actionable item is an unresolved customer request or explicit team commitment that changes the current tracker. Routine FYIs, newsletters, thanks, and work already represented without a changed owner, date, priority, or status do not create changes.

Match an item to the tracker by a shared source reference first, then by the same account and deliverable. Consolidate duplicate mail/chat evidence into one change. Use `update` for a matched tracker item and `create` only for a genuinely new deliverable. A later explicit cancellation closes the matched item; a later explicit reopen may reopen it.

Use the latest explicit assignee. If no one is named, use the account owner. If current sources conflict about ownership, leave the owner unassigned and mark the change for review. Preserve an explicit customer date; phrases such as “early next week” are not a firm deadline and require review. Preserve an explicitly assigned owner who is unavailable through the deadline, but mark the availability conflict for review.

Priority is `critical` for an active incident deliverable due within two business days, `high` for an at-risk account renewing within 30 days or another committed customer deadline within three business days, and `normal` otherwise. Existing blocked, overdue, or unowned active tracker items belong in the attention section even when they do not otherwise require a tracker mutation. Treat Saturday and Sunday as non-business days.

A calendar conflict is material only when two accepted required events overlap for the same person. Tentative or optional internal events are not material conflicts. The OKR snapshot should include only key results whose current `status` is not `on_track`.

## Coordination packet contract

Write one JSON object containing:

- the snapshot time;
- a `task_changes` collection with the operation, matched task ID when updating, account, concise deliverable, owner (or null), deadline (or null), priority, resulting status, source references, and whether human review is required;
- an `attention` section covering active blocked/overdue/unowned tracker IDs, material calendar conflict event IDs, and assignment-versus-availability conflicts;
- a `weekly_digest` with concise wins, risks/decisions, and the non-on-track OKR snapshot with current and target values; and
- a ready-to-review `team_chat_draft` for Monday kickoff that makes owners, dates, blockers, and decisions easy to scan without exposing restricted or private text.

Equivalent key names, nesting, and ordering are acceptable if these semantics remain unambiguous. Use stable source IDs in the packet so a reviewer can trace each proposed change.
