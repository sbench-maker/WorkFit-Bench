# Resume archive snapshot notes

This is a deterministic, fictional export made for offline reconciliation. `snapshot.json` fixes the reporting date, archive cutoff, open application statuses, and source record counts. Identifiers are stable across the four JSON record files.

## Master and update semantics

- The canonical master is the sole `current` record in `master_revisions.json`. A tailored version's `base_master_id` establishes its lineage.
- A lineage is invalid when its base does not exist or the version predates that master's publication.
- Each content update first becomes part of the master named by `introduced_in_master_id`. It matters to a tailored version when `applies_to` contains `all` or that version's `role_family`.
- A relevant update is missing from a tailored version only when it was introduced after the version's base revision and is absent from `included_update_ids`. Included IDs represent deliberate cherry-picks.

## Application reconciliation

Only records with a non-null `submitted_at` are submitted applications. Resolve each submitted application using these evidence rules:

1. A hash matching exactly one version is strongest. A blank or stale text reference does not override that hash.
2. If a nonblank text reference identifies a different version from a unique hash, the result is `conflict`, remains unresolved, and keeps both candidate version IDs.
3. Without a unique hash match, a text reference may match a `version_id` exactly or a `file_name` case-insensitively. A unique match is `resolved`; multiple filename matches are `ambiguous`; no match is `missing`.
4. A version created after the submission could not have been sent. Such a match becomes `conflict`, remains unresolved, and keeps that version as a candidate.

Use the resolution labels `resolved`, `ambiguous`, `conflict`, and `missing`. Drafts need not appear in the application reconciliation.

## Version lifecycle

Keep every version in the register, including files already stored in the archive. For each version, report invalid lineage, resolved linked applications, open linked applications, and relevant missing update IDs, then assign exactly one lifecycle action in this precedence order:

1. `retain_archived` for a file whose `stored_state` is already `archived`.
2. `investigate` for invalid lineage.
3. For a version linked to an open application, `rebuild` if a critical relevant update is missing, otherwise `refresh` if any relevant update is missing, otherwise `keep`.
4. For a version with no open linked application, `archive` when it was created before the snapshot's archive cutoff and either has no resolved submission or its latest resolved submission predates the cutoff; otherwise `keep`.

Archiving means preserving history in the archive, never deleting the file. In the action queue, evidence conflicts and invalid lineage are high priority, active `rebuild` work is high priority, active `refresh` work and other unresolved application links are medium priority, and archive housekeeping is low priority.
