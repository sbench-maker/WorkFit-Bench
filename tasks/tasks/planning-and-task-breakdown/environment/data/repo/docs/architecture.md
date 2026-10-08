# OrbitDesk architecture notes

- API routes validate input with Zod and call services; routes do not publish messages or send mail.
- PostgreSQL access is exposed through `@orbitdesk/db`. Schema changes are timestamped SQL migrations and mirrored in `packages/db/src/schema.ts`.
- A transactional outbox is the only boundary from API/worker database transactions to asynchronous consumers.
- Workers use `FOR UPDATE SKIP LOCKED`, short transactions, and unique job keys when claiming repeatable work.
- React settings pages use TanStack Query, shared permission hooks, and versioned writes. Keep server authorization authoritative.
- Feature flags must be enforced server-side as well as hidden client-side.
- Audit payloads use identifiers and changed-field names. They must not contain email addresses, message bodies, or access tokens.

The CI merge gate runs `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`.
