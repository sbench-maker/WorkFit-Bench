# Current manual workflow

1. An operations lead opens one queue and rebuilds a filter from memory.
2. They scan ticket subject, customer tier, current owner, priority, and routing tags.
3. They open a ticket, change one routing field, save, and return to the list.
4. The list re-sorts after a save, so the lead must find their previous place.
5. They repeat the edit for every ticket, then sample the queue to look for mistakes.
6. If another agent changed a ticket in the meantime, the later save can hide the conflict.
7. Audit events exist for individual edits, but there is no session-level summary of intended, changed, skipped, or failed tickets.

The session data records this manual workflow. `completion_minutes` runs from opening the queue until the lead declares the set complete. `misroutes` counts tickets corrected within 24 hours because the routing choice was wrong. `permission_blocks` counts sessions in which the operator attempted at least one edit they were not allowed to make. `audit_gaps` counts sessions in which an expected individual audit event was missing.

The four workflow segments are jobs, not demographic groups:

- `volume_spike_response`: regain control of a sudden queue surge without losing place.
- `daily_backlog_control`: clear a bounded queue consistently at the start of a shift.
- `specialist_handoff`: prepare the right cases for a specialist team without firing unrelated automations.
- `audit_ready_triage`: make high-volume routing changes that remain reviewable ticket by ticket.
