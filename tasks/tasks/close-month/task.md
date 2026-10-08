---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 600.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
---

Finish Harbor & Pine Studio's April 2026 close from the exported books, processor settlements, owner triage, and close notes in `/root/data/`. Reconcile the available feeds, carry unresolved gaps and reviewed suspicious entries forward without altering the source exports, and explain the P&L movement from the underlying transactions. Save the accountant-ready workbook and one-page summary as `/root/results/close-packet-2026-04.xlsx` and `/root/results/close-packet-2026-04.pdf`, clearly disclosing any unavailable processor feed.

Use `close_instructions.md` as the authority for the close scope and required schedules, and preserve the approved/open status recorded in `owner_triage.csv`. The workbook should make the settlement reconciliation, flagged-item follow-up, March-versus-April P&L, and April 30 trial balance easy to locate. Sheet names and column wording need not match those phrases exactly as long as the schedules and their source identifiers are unambiguous.

Keep the PDF's headline figures and open-gap count as selectable text, not only as chart or screenshot content. In the workbook, place each schedule's field names in a real header row and keep source identifiers in cells so the close can be filtered, reconciled, and reviewed without relying on visual position alone.
