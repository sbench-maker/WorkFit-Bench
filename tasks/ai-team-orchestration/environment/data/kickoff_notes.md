# EvalHarbor kickoff packet

EvalHarbor is a new internal web console for release owners to validate an AI agent build against a versioned JSONL evaluation set before promotion. The first usable slice must let an authenticated release owner upload a dataset, launch a deterministic mock run, and inspect run status plus a compact score summary. It is a workflow tool, not a model-training product.

## Users and core flow

- Release owner: signs in, uploads a JSONL set, launches a run, reviews status and summary.
- Reviewer: can view completed runs and audit history but cannot upload or launch.
- Platform operator: maintains local infrastructure and CI; no product-admin UI is needed in Sprint 1.
- Core flow: sign in -> validate/upload dataset -> create run with mock adapter -> poll status -> inspect score summary -> review audit event.

## Fixed delivery frame

- Sprint 1 runs 2027-01-11 through 2027-01-22 with 50 points of team capacity.
- Sprint 1 goal: a tested local vertical slice of the core flow above.
- The repository is brand new. There is no implemented feature code yet.
- A deterministic mock model adapter is mandatory for Sprint 1. Live model-provider connections are prohibited until the security review in Sprint 3.
- All data is fictional and local. Do not describe it as production telemetry.

## Product decisions

- Evaluation datasets use UTF-8 JSONL. Each row requires `case_id`, `input`, and `expected`; duplicate `case_id` values reject the whole upload.
- A run snapshots the dataset version and immutable adapter configuration.
- Sprint 1 score summary is pass count, fail count, pass rate, and p50 latency. Cost charts, prompt editing, and exports are later work.
- The mock identity provider exposes two test roles: `release_owner` and `reviewer`.

## Security and privacy

- Secrets are supplied only through environment variables. Documentation may name `DATABASE_URL`, `REDIS_URL`, and `OIDC_CLIENT_SECRET`, but must never include values.
- Uploaded JSONL is untrusted input: enforce 5 MiB maximum, `.jsonl` extension, UTF-8 decoding, row schema validation, and duplicate-ID rejection.
- Audit events record actor ID, action, target ID, timestamp, and outcome; they must not store dataset row content, bearer tokens, or secret values.
- Logs must redact authorization headers and environment-variable values.

## Local run and deployment

- Local full stack: `docker compose up --build`.
- Frontend-only development: `npm run dev --workspace apps/web`.
- Backend tests: `pytest services/api/tests`.
- E2E tests: `npm run test:e2e`.
- Sprint 1 deployment target is the local Docker Compose stack only. A managed cloud environment is deferred to Sprint 4.
