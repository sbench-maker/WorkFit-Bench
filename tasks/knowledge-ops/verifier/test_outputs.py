from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/knowledge_sync.json"))
SOURCE_FILES = {
    "github": "github_items.jsonl",
    "linear": "linear_items.jsonl",
    "repo_doc": "repo_documents.jsonl",
    "session": "session_exports.jsonl",
    "document_import": "document_imports.jsonl",
}
AUTHORITY = {
    "roadmap": ["linear", "github", "session"],
    "release": ["github", "linear", "session"],
    "implementation": ["github", "repo_doc", "session"],
    "runbook": ["repo_doc", "github", "session"],
    "api_contract": ["repo_doc", "github", "session"],
    "decision": ["linear", "session", "github"],
    "reference": ["repo_doc", "session", "github"],
    "session_summary": ["session", "linear", "repo_doc"],
    "large_document": ["document_import", "repo_doc", "session"],
}
HOMES = {
    "roadmap": "linear",
    "release": "github",
    "implementation": "github",
    "runbook": "repo",
    "api_contract": "repo",
    "decision": "memory",
    "reference": "memory",
    "session_summary": "kb_repo",
    "large_document": "external_store",
}
ACTION_ALIASES = {
    "create": "create",
    "new": "create",
    "insert": "create",
    "update": "update",
    "change": "update",
    "modify": "update",
    "noop": "noop",
    "no-op": "noop",
    "no_op": "noop",
    "unchanged": "noop",
    "skip": "noop",
    "review": "review",
    "manual-review": "review",
    "manual_review": "review",
    "conflict": "review",
}
HOME_ALIASES = {
    "linear": "linear",
    "github": "github",
    "repo": "repo",
    "repository": "repo",
    "memory": "memory",
    "mcp-memory": "memory",
    "kb-repo": "kb_repo",
    "knowledge-base-repo": "kb_repo",
    "knowledge-repo": "kb_repo",
    "external-store": "external_store",
    "external-data-store": "external_store",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def _collapse(value: Any) -> str:
    return " ".join(str(value).split())


def _sanitize(value: Any) -> str:
    return re.sub(r"\[credential:[^\]]+\]", "<REDACTED>", str(value), flags=re.IGNORECASE)


def _pick(mapping: dict, names: tuple[str, ...], default: Any = None) -> Any:
    lowered = {_slug(key).replace("-", "_"): value for key, value in mapping.items()}
    for name in names:
        key = _slug(name).replace("-", "_")
        if key in lowered:
            return lowered[key]
    return default


def _aliases() -> dict[str, str]:
    payload = json.loads((DATA_DIR / "project_aliases.json").read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for row in payload["projects"]:
        for value in [row["slug"], row["display_name"], *row["aliases"]]:
            result[_slug(value)] = row["slug"]
    return result


def _normalize_key(value: Any, aliases: dict[str, str], context: dict | None = None) -> str | None:
    if isinstance(value, dict):
        direct = _pick(value, ("canonical_key", "key", "topic_id", "knowledge_id"))
        if direct is not None:
            return _normalize_key(direct, aliases)
        project = _pick(value, ("project", "project_slug", "workspace"))
        kind = _pick(value, ("kind", "type", "category"))
        topic = _pick(value, ("topic", "topic_slug", "name"))
        if project is not None and kind is not None and topic is not None:
            project_slug = aliases.get(_slug(project), _slug(project))
            return f"{project_slug}/{_slug(kind).replace('-', '_')}/{_slug(topic)}"
        return None
    if value is None:
        return None
    raw = str(value).strip()
    if raw.count("/") >= 2:
        project, kind, topic = raw.split("/", 2)
        project_slug = aliases.get(_slug(project), _slug(project))
        return f"{project_slug}/{_slug(kind).replace('-', '_')}/{_slug(topic)}"
    if context:
        return _normalize_key({**context, "topic": raw}, aliases)
    return None


def _extract_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, str):
        if re.fullmatch(r"(?:GH|LIN|DOC|SES|IMP)-\d{4}", value.strip(), flags=re.IGNORECASE):
            ids.add(value.strip().upper())
    elif isinstance(value, list):
        for item in value:
            ids.update(_extract_ids(item))
    elif isinstance(value, dict):
        direct = _pick(value, ("id", "source_id", "record_id"))
        if direct is not None:
            ids.update(_extract_ids(direct))
        else:
            for item in value.values():
                ids.update(_extract_ids(item))
    return ids


def _all_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, list):
        for item in value:
            found.update(_all_strings(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key))
            found.update(_all_strings(item))
    return found


def _entry_rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    container = _pick(payload, ("entries", "catalog", "records", "knowledge_items", "topics"))
    if isinstance(container, list):
        return [row for row in container if isinstance(row, dict)]
    if isinstance(container, dict):
        rows = []
        for key, value in container.items():
            if isinstance(value, dict):
                rows.append({"canonical_key": key, **value})
        return rows
    return []


def _action_rows(payload: dict) -> dict[str, dict]:
    aliases = _aliases()
    container = _pick(payload, ("actions", "sync_actions", "operations"), [])
    if isinstance(container, dict):
        rows = list(container.values())
    elif isinstance(container, list):
        rows = container
    else:
        rows = []
    result: dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict):
            key = _normalize_key(row, aliases)
            if key:
                result[key] = row
    return result


def _review_rows(payload: dict, aliases: dict[str, str]) -> tuple[set[str], dict[str, list[dict]]]:
    container = _pick(payload, ("review_queue", "reviews", "manual_review"), [])
    rows: list[dict] = []
    if isinstance(container, list):
        rows = [row for row in container if isinstance(row, dict)]
    elif isinstance(container, dict):
        for key, value in container.items():
            if isinstance(value, dict):
                rows.append({"canonical_key": key, **value})
    keys: set[str] = set()
    by_key: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _normalize_key(row, aliases)
        if key:
            keys.add(key)
            by_key[key].append(row)
    return keys, by_key


def _index_groups(raw: Any, aliases: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    if isinstance(raw, dict):
        for project_value, kinds in raw.items():
            project = aliases.get(_slug(project_value), _slug(project_value))
            if isinstance(kinds, dict):
                for kind_value, topics in kinds.items():
                    kind = _slug(kind_value).replace("-", "_")
                    if isinstance(topics, dict):
                        topics = list(topics)
                    if isinstance(topics, list):
                        for topic in topics:
                            key = _normalize_key(topic, aliases, {"project": project, "kind": kind})
                            if key:
                                groups[(project, kind)].add(key)
            elif "/" in str(project_value):
                parts = str(project_value).split("/", 1)
                project = aliases.get(_slug(parts[0]), _slug(parts[0]))
                kind = _slug(parts[1]).replace("-", "_")
                topics = kinds if isinstance(kinds, list) else list(kinds) if isinstance(kinds, dict) else []
                for topic in topics:
                    key = _normalize_key(topic, aliases, {"project": project, "kind": kind})
                    if key:
                        groups[(project, kind)].add(key)
    elif isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            project_value = _pick(row, ("project", "project_slug"))
            kind_value = _pick(row, ("kind", "type", "category"))
            topics = _pick(row, ("topics", "keys", "entries", "items"), [])
            if project_value is None or kind_value is None or not isinstance(topics, list):
                continue
            project = aliases.get(_slug(project_value), _slug(project_value))
            kind = _slug(kind_value).replace("-", "_")
            for topic in topics:
                key = _normalize_key(topic, aliases, {"project": project, "kind": kind})
                if key:
                    groups[(project, kind)].add(key)
    return groups


def _load_submission() -> tuple[dict[str, dict], set[str], dict[tuple[str, str], set[str]], str, str | None]:
    try:
        raw_text = OUTPUT_PATH.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, set(), {}, "", f"knowledge_sync.json is missing or unreadable: {exc}"
    if not isinstance(payload, (dict, list)):
        return {}, set(), {}, raw_text, "knowledge_sync.json must contain a JSON object or list"
    aliases = _aliases()
    top = payload if isinstance(payload, dict) else {}
    actions = _action_rows(top) if top else {}
    review_keys, reviews = _review_rows(top, aliases) if top else (set(), {})
    normalized: dict[str, dict] = {}
    duplicate_keys: set[str] = set()
    for row in _entry_rows(payload):
        key = _normalize_key(row, aliases)
        if not key:
            continue
        if key in normalized:
            duplicate_keys.add(key)
            continue
        action_row = actions.get(key, {})
        action_raw = _pick(row, ("action", "operation", "change", "decision"), _pick(action_row, ("action", "operation", "change", "decision"), ""))
        action_key = _slug(action_raw)
        home_raw = _pick(row, ("canonical_home", "storage_layer", "destination", "home"), "")
        home_key = _slug(home_raw)
        provenance = _pick(row, ("source_ids", "provenance", "source_records", "sources"), [])
        relationship_raw = _pick(row, ("relationships", "cross_references", "relations", "related_topics"), [])
        relations: set[str] = set()
        if isinstance(relationship_raw, (list, dict)):
            items = relationship_raw.values() if isinstance(relationship_raw, dict) else relationship_raw
            for item in items:
                relation = _normalize_key(item, aliases)
                if relation:
                    relations.add(relation)
        normalized[key] = {
            "body": _pick(row, ("body", "content", "text", "summary")),
            "status": _pick(row, ("status", "state")),
            "home": HOME_ALIASES.get(home_key, home_key.replace("-", "_")),
            "action": ACTION_ALIASES.get(action_key, action_key),
            "source_ids": _extract_ids(provenance),
            "relationships": relations,
            "raw_evidence_strings": _all_strings(row) | _all_strings(action_row) | _all_strings(reviews.get(key, [])),
        }
    if duplicate_keys:
        return normalized, review_keys, {}, raw_text, f"multiple output records normalize to the same canonical key: {sorted(duplicate_keys)[:3]}"
    index_raw = _pick(top, ("topic_index", "index", "catalog_index"), {}) if top else {}
    return normalized, review_keys, _index_groups(index_raw, aliases), raw_text, None


def _select(records: list[dict], kind: str, field: str) -> tuple[str | None, set[str]]:
    for source in AUTHORITY[kind]:
        candidates = [row for row in records if row["source"] == source and _collapse(row.get(field, ""))]
        if not candidates:
            continue
        latest = max(datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) for row in candidates)
        finalists = [row for row in candidates if datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) == latest]
        buckets: dict[str, list[dict]] = defaultdict(list)
        for row in finalists:
            raw = _sanitize(row[field]) if field == "body" else row[field]
            value = _collapse(raw)
            if field == "status":
                value = value.lower()
            buckets[value].append(row)
        if len(buckets) > 1:
            return None, {row["id"] for row in finalists}
        value = next(iter(buckets))
        return value, set()
    return None, set()


def _expected() -> dict[str, dict]:
    aliases = _aliases()
    groups: dict[str, list[dict]] = defaultdict(list)
    for source, filename in SOURCE_FILES.items():
        for row in _jsonl(DATA_DIR / filename):
            project = aliases[_slug(row["project"])]
            key = f"{project}/{row['kind']}/{_slug(row['topic'])}"
            groups[key].append({**row, "source": source})
    stores: dict[str, list[dict]] = defaultdict(list)
    for row in _jsonl(DATA_DIR / "store_snapshot.jsonl"):
        stores[row["canonical_key"]].append(row)
    all_keys = set(groups)
    result: dict[str, dict] = {}
    for key, rows in groups.items():
        project, kind, _ = key.split("/", 2)
        body, body_conflicts = _select(rows, kind, "body")
        status, status_conflicts = _select(rows, kind, "status")
        target_rows = stores.get(key, [])
        conflict_ids = body_conflicts | status_conflicts
        target_ids = {row["entry_id"] for row in target_rows} if len(target_rows) > 1 else set()
        if conflict_ids or target_ids:
            action = "review"
        elif not target_rows:
            action = "create"
        else:
            target = target_rows[0]
            same = (
                _collapse(_sanitize(target["body"])) == _collapse(body or "")
                and _collapse(target["status"]).lower() == _collapse(status or "").lower()
                and target["storage_layer"] == HOMES[kind]
            )
            action = "noop" if same else "update"
        relations: set[str] = set()
        for row in rows:
            for relation in row.get("related_topics", []):
                try:
                    related = f"{aliases[_slug(relation['project'])]}/{relation['kind']}/{_slug(relation['topic'])}"
                except (KeyError, TypeError):
                    continue
                if related in all_keys and related != key:
                    relations.add(related)
        result[key] = {
            "body": body,
            "status": status,
            "home": HOMES[kind],
            "action": action,
            "source_ids": {row["id"] for row in rows},
            "relationships": relations,
            "source_conflict_ids": conflict_ids,
            "target_conflict_ids": target_ids,
            "group": (project, kind),
        }
    return result


def test_catalog_scope_and_provenance():
    actual, _, _, _, error = _load_submission()
    assert error is None, error
    expected = _expected()
    assert set(actual) == set(expected), (
        f"canonical topic coverage differs: missing={sorted(set(expected) - set(actual))[:5]}, "
        f"unexpected={sorted(set(actual) - set(expected))[:5]}"
    )
    mismatches = {
        key: sorted(expected[key]["source_ids"] ^ actual[key]["source_ids"])
        for key in expected
        if actual[key]["source_ids"] != expected[key]["source_ids"]
    }
    assert not mismatches, f"provenance is incomplete or misassigned for {list(mismatches.items())[:4]}"


def test_authoritative_values_and_storage():
    actual, _, _, _, error = _load_submission()
    if error is not None:
        return
    expected = _expected()
    if set(actual) != set(expected):
        return
    wrong_home = {key: (actual[key]["home"], row["home"]) for key, row in expected.items() if actual.get(key, {}).get("home") != row["home"]}
    assert not wrong_home, f"canonical storage layer is wrong for {list(wrong_home.items())[:5]}"
    wrong_values = {}
    for key, row in expected.items():
        if row["source_conflict_ids"]:
            continue
        actual_row = actual.get(key, {})
        actual_body = _collapse(_sanitize(actual_row.get("body", "")))
        actual_status = _collapse(actual_row.get("status", "")).lower()
        if actual_body != _collapse(row["body"] or "") or actual_status != _collapse(row["status"] or "").lower():
            wrong_values[key] = {
                "actual_body": actual_body,
                "expected_body": row["body"],
                "actual_status": actual_status,
                "expected_status": row["status"],
            }
    assert not wrong_values, f"authority/recency field selection is wrong for {list(wrong_values.items())[:3]}"


def test_sync_actions_and_conflict_evidence():
    actual, review_keys, _, _, error = _load_submission()
    if error is not None:
        return
    expected = _expected()
    if set(actual) != set(expected):
        return
    wrong_actions = {key: (actual.get(key, {}).get("action"), row["action"]) for key, row in expected.items() if actual.get(key, {}).get("action") != row["action"]}
    assert not wrong_actions, f"sync actions are wrong for {list(wrong_actions.items())[:6]}"
    expected_review = {key for key, row in expected.items() if row["action"] == "review"}
    assert review_keys == expected_review, (
        f"review queue membership differs: missing={sorted(expected_review - review_keys)}, "
        f"unexpected={sorted(review_keys - expected_review)}"
    )
    missing_evidence = {}
    for key in expected_review:
        required = expected[key]["source_conflict_ids"] | expected[key]["target_conflict_ids"]
        strings = actual[key]["raw_evidence_strings"]
        absent = {identifier for identifier in required if identifier not in strings}
        if absent:
            missing_evidence[key] = sorted(absent)
    assert not missing_evidence, f"review conflict evidence omits relevant IDs: {list(missing_evidence.items())[:4]}"


def test_redaction_relationships_and_index():
    actual, _, index, raw_text, error = _load_submission()
    if error is not None:
        return
    expected = _expected()
    if set(actual) != set(expected):
        return
    assert re.search(r"\[credential:[^\]]+\]", raw_text, flags=re.IGNORECASE) is None, "credential removal markers remain in the output"
    redacted_expected = {key for key, row in expected.items() if row["body"] and "<REDACTED>" in row["body"]}
    missing_redactions = {key for key in redacted_expected if "<REDACTED>" not in _collapse(actual.get(key, {}).get("body", ""))}
    assert not missing_redactions, f"retained sensitive text was not visibly redacted for {sorted(missing_redactions)}"
    wrong_relations = {key: (actual.get(key, {}).get("relationships", set()), row["relationships"]) for key, row in expected.items() if actual.get(key, {}).get("relationships") != row["relationships"]}
    assert not wrong_relations, f"merged cross-references are wrong for {list(wrong_relations.items())[:4]}"
    expected_index: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, row in expected.items():
        expected_index[row["group"]].add(key)
    assert dict(index) == dict(expected_index), "topic index is not complete and correctly grouped by project and kind"
