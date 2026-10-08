# Offline knowledge sync policy

These exports are a frozen snapshot. They model GitHub, Linear, repository documents,
conversation/session exports, large-document imports, and the current target stores.
No live service calls are needed.

## Identity and normalization

- Use `project_aliases.json` to resolve every project spelling to its canonical slug.
- A topic identity is `project-slug/kind/topic-slug`.
- Create a topic slug by trimming, lowercasing, and replacing each run of non-alphanumeric
  characters with one hyphen.
- Records with the same topic identity describe one fact set. Preserve every contributing
  source record ID on that canonical topic.

## Canonical storage layer

| kind | canonical home |
| --- | --- |
| roadmap | linear |
| release | github |
| implementation | github |
| runbook | repo |
| api_contract | repo |
| decision | memory |
| reference | memory |
| session_summary | kb_repo |
| large_document | external_store |

The canonical home is the single authoritative location for a fact set. The sync result is
an offline plan; it must not claim that any remote write has already happened.

## Selecting retained fields

Choose `body` and `status` independently. Ignore empty values for the field being selected.
First use the highest-authority source for that kind, then the latest `updated_at` within
that source. A newer low-authority session note must not replace active project truth.

| kind | source authority, highest first |
| --- | --- |
| roadmap | linear, github, session |
| release | github, linear, session |
| implementation | github, repo_doc, session |
| runbook | repo_doc, github, session |
| api_contract | repo_doc, github, session |
| decision | linear, session, github |
| reference | repo_doc, session, github |
| session_summary | session, linear, repo_doc |
| large_document | document_import, repo_doc, session |

If equally authoritative, equally recent records disagree on a retained field, do not pick
one silently: mark the topic for review and retain the conflicting source IDs and values.
Likewise, two target-store rows for one canonical key require review because an automatic
update would have an ambiguous target.

Whitespace-only differences are equivalent. Compare status values case-insensitively.
Before retaining text, replace any bracketed `[credential: ...]` removal marker with
`<REDACTED>`. The markers in this fixture are synthetic and contain no usable secrets.

## Sync actions and relationships

- `create`: the canonical topic has no current target-store row.
- `noop`: one target row already has the selected body, status, and canonical storage layer.
- `update`: one target row exists but at least one of those values differs.
- `review`: an unresolved source conflict or duplicate target row makes automatic application unsafe.

Merge relationships from all contributing source records. Resolve each related topic through
the same project-alias and topic normalization rules, deduplicate it, and retain only canonical
topic keys present in the exports.

The JSON handoff should contain one consolidated record per canonical topic, including its
identity, retained values, canonical home, action, provenance IDs, relationships, and any
conflict evidence. It should also contain a topic index grouped by project and kind, plus a
review queue that lets a human see why each review action is blocked and which source records
or target entries must be compared.
