# Engineering conventions

- Tenant boundaries are authorization boundaries. Every cache or memoized value derived from a tenant request must include `tenant_id` in its key.
- Authorization comes only from the verified `claims.scopes` collection. Request metadata is caller-controlled and must never bypass a scope check.
- A request whose `token_count` exceeds the configured batch budget must be rejected, not emitted as an oversized batch.
- Only `TimeoutError` is retryable. Authentication, authorization, validation, and policy failures must be returned to the caller and must never be routed to a fallback model.
- Review comments should identify regressions introduced by the proposed branch, not unrelated legacy behavior.
