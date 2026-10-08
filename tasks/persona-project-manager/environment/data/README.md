# Offline workspace export

This is a fictional, frozen snapshot. Times are ISO-8601 values in America/New_York unless a file says otherwise. `workspace.json` contains the reconciliation, scheduling, communication, deduplication, and audience rules.

Prepare a reviewable JSON dry-run plan, not evidence that anything was actually sent. Any clear JSON organization is acceptable. The plan should expose: the weekly project snapshot after proposed tracker changes; each tracker mutation and its effective source event; calendar creations with request IDs, occurrence times, duration, and attendees; email drafts with kind, recipients, subject/body, and related task/reporting period; and the upload-plus-channel announcement for any eligible document version.

`project_tasks.csv` is the current sheet state. `task_status_events.csv` contains imported updates. `availability.csv`, `calendar_events.csv`, and `meeting_requests.json` form the calendar snapshot. `stakeholders.csv`, `email_log.csv`, `documents.csv`, and `announcement_log.csv` determine pending communications. Pipe-delimited cells contain ID lists.

The optional `gws` command is a non-mutating local preview shim for common dry-run actions. Directly analyzing these files is equally valid.
