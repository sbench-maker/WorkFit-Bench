# Daily call-plan snapshot

All entities are fictional and the files are a frozen offline export. `run_context.json` fixes the owner, target date, snapshot time, timezone, and requested count. `call_policy.json` is the sales team's current eligibility, ranking, follow-up, and scheduling policy.

Join `contacts.csv`, `deals.csv`, `activities.csv`, and `emails.csv` with `contact_id`; calendar rows join on `owner_id`. Timestamps without an explicit offset use the owner's timezone. For eligibility, the 30-calendar-day window includes the target date and the preceding 29 dates. A proposed call may use any free 20-minute interval inside a working window and must not overlap a busy event or another proposed call. All calendar entries and email messages in the deliverable are proposals or drafts for Morgan's approval, never executed actions.
