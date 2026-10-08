# Lumen Relay service

This fictional service accepts signed delivery events, offers an unauthenticated
template-preview route, and lets authenticated operators replay stored events.
It is a static review fixture: none of the functions contacts a real service or
contains credentials.

The application registers these HTTP handlers:

- `receive_event` for `POST /hooks/events`
- `preview_template` for `POST /templates/preview`
- `replay_event` for `POST /admin/replay`
- `health_check` for `GET /health`

`run_template` is the sensitive template execution boundary. The preview route
is intentionally unusual: unlike normal delivery processing, it accepts a
caller-supplied template instead of selecting an approved template from the
catalog.
