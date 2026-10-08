# Hook ownership

`policy_guard.py` is a synchronous pre-tool control. `check_filename.py` is a
standalone helper retained for manual reviews. Post-tool hooks summarize diffs
and send operational telemetry. Hook failures should remain visible to users.
