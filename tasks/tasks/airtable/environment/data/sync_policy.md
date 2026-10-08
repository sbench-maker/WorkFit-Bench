# Issue import policy

The incoming CSV is a source-system snapshot. Reconcile it into the `Issues` table with these business rules:

1. Group input rows by trimmed `External ID`. A valid ID matches `BUG-` followed by four digits. `Title`, `Status`, `Priority`, and a valid ISO-8601 `Source Updated At` are required. Status and priority must match choices returned by the table schema.
2. Within an ID, use the row with the newest source timestamp. If multiple newest rows disagree on any managed value, reject that ID as an ambiguous duplicate and do not mutate it. Identical ties collapse harmlessly.
3. For an existing issue, reject an older source timestamp. At the same timestamp, classify an identical effective record as unchanged; otherwise reject it as a timestamp conflict. A `Done` issue may not move to another status unless the selected row says `Reopen Approved=true`.
4. Managed fields are `Title`, `Status`, `Priority`, `Owner Email`, `Labels`, `Source Updated At`, and `Reopen Approved`. Trim text; lowercase nonblank owner emails; split labels on `|`, trim them, and remove duplicates while preserving first occurrence. On an update, blank `Owner Email` or `Labels` means preserve the existing value. On a create, omit those blank optional fields.
5. Apply only created and updated issues using batch upserts merged on `External ID`; do not write unchanged or rejected issues. Keep batches within the API limit. A rerun of the same import must not create duplicates.
6. In the receipt, classify each distinct trimmed External ID once. Include a useful reason for every rejection and report post-sync total records and counts by Status after listing the final table through all pages.
