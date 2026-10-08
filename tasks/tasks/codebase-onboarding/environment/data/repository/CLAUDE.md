# Existing project rules

Never provision access directly inside an HTTP request handler. The committed outbox is the audit boundary.

Do not log an employee's `private_note`, even in debug output.

Any change to approval policy needs tests for both manager and non-manager actors.
