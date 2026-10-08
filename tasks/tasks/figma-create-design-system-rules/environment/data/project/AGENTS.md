# Emberline Console Contributor Notes

## API and data safety

- Route every HTTP request through `src/services/apiClient.ts`; feature components must not call `fetch` directly.
- Keep the session token in the server-set HTTP-only cookie. Never read or persist it from browser code.

## Generated files

- Do not edit `src/app/routes.generated.ts` by hand; it is rebuilt by `npm run routes:generate`.
