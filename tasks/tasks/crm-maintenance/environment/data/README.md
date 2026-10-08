# Frozen CRM cleanup export

This directory is a deterministic, fictional snapshot captured at the time in `snapshot_policy.json`. It is not connected to a live service.

- `crm_deals.json`: deal fields from the CRM export.
- `crm_contacts.json`: contacts available for case-insensitive email resolution.
- `deal_contact_associations.json`: current deal/contact links.
- `crm_activities.json`: activities already present on deal timelines; `source_ref` links back to exported communications when available.
- `crm_notes.json`: immutable historical notes.
- `email_threads.json`: email threads with ordered messages; a thread's activity timestamp is its latest message time.
- `calendar_events.json`: calendar events; call duration is derived from `start` and `end`.
- `snapshot_policy.json`: audit cutoff, target deal, matching scope, and write/approval boundaries.

Use source record IDs when referring to evidence so a sales owner can inspect the snapshot. Blank or null `source_ref` values do not match a communication.
