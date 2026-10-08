from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
MANAGED = ["Title", "Status", "Priority", "Owner Email", "Labels", "Source Updated At", "Reopen Approved"]
CATEGORY_ALIASES = {
    "created": {"created", "create", "new", "inserted", "added"},
    "updated": {"updated", "update", "changed", "patched", "modified"},
    "unchanged": {"unchanged", "nochange", "alreadycurrent", "noop", "skippednochange"},
    "rejected": {"rejected", "reject", "invalid", "errors", "failed"},
}


def key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def truth(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def has_complete_listing(events: list[dict], expected_count: int) -> bool:
    """Accept any complete pagination pass, even when safe read-only scans repeat."""
    for start in range(len(events)):
        total = 0
        saw_offset = False
        for event in events[start:]:
            returned = event.get("returned")
            if not isinstance(returned, int) or returned < 0:
                break
            total += returned
            saw_offset = saw_offset or bool(event.get("offset"))
            if total == expected_count:
                return saw_offset
            if total > expected_count or returned < 100:
                break
    return False


def clean_row(row: dict[str, str]) -> dict:
    labels = []
    for raw in row.get("Labels", "").split("|"):
        label = raw.strip()
        if label and label not in labels:
            labels.append(label)
    return {
        "External ID": row.get("External ID", "").strip(),
        "Title": row.get("Title", "").strip(),
        "Status": row.get("Status", "").strip(),
        "Priority": row.get("Priority", "").strip(),
        "Owner Email": row.get("Owner Email", "").strip().lower(),
        "Labels": labels,
        "Source Updated At": row.get("Source Updated At", "").strip(),
        "Reopen Approved": truth(row.get("Reopen Approved", "")),
    }


def build_expected() -> dict:
    initial = json.loads((DATA / "initial_base.json").read_text(encoding="utf-8"))
    schema = json.loads((DATA / "schema.json").read_text(encoding="utf-8"))
    with (DATA / "incoming_issues.csv").open(encoding="utf-8", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    status_choices = {c["name"] for c in next(f for f in schema["tables"][0]["fields"] if f["name"] == "Status")["options"]["choices"]}
    priority_choices = {c["name"] for c in next(f for f in schema["tables"][0]["fields"] if f["name"] == "Priority")["options"]["choices"]}
    groups: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_rows:
        row = clean_row(raw)
        groups[row["External ID"]].append(row)

    final = {record["fields"]["External ID"]: dict(record["fields"]) for record in initial["records"]}
    outcomes = {name: set() for name in CATEGORY_ALIASES}
    mutated: set[str] = set()
    for external_id in sorted(groups):
        candidates = groups[external_id]
        try:
            parsed = [(parse_time(row["Source Updated At"]), row) for row in candidates]
        except ValueError:
            outcomes["rejected"].add(external_id)
            continue
        newest_time = max(value for value, _ in parsed)
        newest = [row for value, row in parsed if value == newest_time]
        signatures = {json.dumps({field: row[field] for field in MANAGED}, sort_keys=True) for row in newest}
        if len(signatures) > 1:
            outcomes["rejected"].add(external_id)
            continue
        row = newest[0]
        if (
            not re.fullmatch(r"BUG-\d{4}", external_id)
            or not row["Title"]
            or row["Status"] not in status_choices
            or row["Priority"] not in priority_choices
        ):
            outcomes["rejected"].add(external_id)
            continue
        old = final.get(external_id)
        if old is None:
            fields = {"External ID": external_id, **{name: row[name] for name in MANAGED}}
            if not row["Owner Email"]:
                fields.pop("Owner Email")
            if not row["Labels"]:
                fields.pop("Labels")
            final[external_id] = fields
            outcomes["created"].add(external_id)
            mutated.add(external_id)
            continue
        old_time = parse_time(old["Source Updated At"])
        if newest_time < old_time:
            outcomes["rejected"].add(external_id)
            continue
        if old.get("Status") == "Done" and row["Status"] != "Done" and not row["Reopen Approved"]:
            outcomes["rejected"].add(external_id)
            continue
        effective = dict(old)
        for name in MANAGED:
            if name in {"Owner Email", "Labels"} and not row[name]:
                continue
            effective[name] = row[name]
        if newest_time == old_time:
            old_values = {name: old.get(name, [] if name == "Labels" else "" if name == "Owner Email" else False) for name in MANAGED}
            new_values = {name: effective.get(name, [] if name == "Labels" else "" if name == "Owner Email" else False) for name in MANAGED}
            outcomes["unchanged" if old_values == new_values else "rejected"].add(external_id)
            continue
        final[external_id] = effective
        outcomes["updated"].add(external_id)
        mutated.add(external_id)
    statuses = Counter(fields["Status"] for fields in final.values())
    return {"final": final, "outcomes": outcomes, "mutated": mutated, "status_counts": dict(statuses)}


EXPECTED = build_expected()


def load_receipt() -> dict:
    path = RESULTS / "output.json"
    assert path.is_file(), "output.json is missing; the sync has no usable receipt"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    assert isinstance(payload, dict), "output.json must be a JSON object that a teammate can inspect"
    return payload


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def find_category(payload: dict, category: str) -> object | None:
    aliases = CATEGORY_ALIASES[category]
    for node in walk(payload):
        if isinstance(node, dict):
            for raw_key, value in node.items():
                if key(raw_key) in aliases and isinstance(value, (list, dict)):
                    return value
        if isinstance(node, list):
            for item in node:
                if not isinstance(item, dict):
                    continue
                label = next((value for raw_key, value in item.items() if key(raw_key) in {"category", "outcome", "result", "kind", "status"}), None)
                if label is not None and key(label) in aliases:
                    for raw_key, value in item.items():
                        if key(raw_key) in {"items", "issues", "records", "entries", "externalids", "ids"}:
                            return value
    return None


def external_id(item: object) -> str | None:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for raw_key, value in item.items():
            if key(raw_key) in {"externalid", "issueid", "key", "id"} and isinstance(value, (str, int)):
                return str(value).strip()
        fields = next((value for raw_key, value in item.items() if key(raw_key) == "fields"), None)
        if isinstance(fields, dict):
            return external_id(fields)
    return None


def category_ids(payload: dict, category: str) -> set[str] | None:
    value = find_category(payload, category)
    if value is None:
        return None
    if isinstance(value, dict):
        possible = {str(raw_key).strip() for raw_key in value if re.fullmatch(r"(?:BUG|BAD)-\d{4}", str(raw_key).strip())}
        if possible:
            return possible
        value = list(value.values())
    if not isinstance(value, list):
        return None
    ids = {found for item in value if (found := external_id(item))}
    return ids


def find_number(payload: dict, aliases: set[str]) -> int | None:
    for node in walk(payload):
        if isinstance(node, dict):
            for raw_key, value in node.items():
                if key(raw_key) in aliases and isinstance(value, (int, float)) and not isinstance(value, bool):
                    return int(value)
    return None


def find_status_counts(payload: dict) -> dict[str, int] | None:
    for node in walk(payload):
        if not isinstance(node, dict):
            continue
        for raw_key, value in node.items():
            if key(raw_key) in {"statuscounts", "bystatus", "statuses"} and isinstance(value, dict):
                try:
                    return {str(label): int(count) for label, count in value.items()}
                except (TypeError, ValueError):
                    return None
    return None


def canonical_fields(fields: dict) -> dict:
    result = dict(fields)
    result.setdefault("Owner Email", "")
    result.setdefault("Labels", [])
    result.setdefault("Reopen Approved", False)
    result["Labels"] = list(result["Labels"])
    result["Reopen Approved"] = bool(result["Reopen Approved"])
    return result


def test_synced_base_matches_policy() -> None:
    path = RESULTS / "base_state.json"
    assert path.is_file(), "the offline base has no persisted post-sync state"
    state = json.loads(path.read_text(encoding="utf-8"))
    records = state.get("records") if isinstance(state, dict) else None
    assert isinstance(records, list), "persisted base state does not contain a records list"
    actual: dict[str, dict] = {}
    duplicates: set[str] = set()
    for record in records:
        fields = record.get("fields", {}) if isinstance(record, dict) else {}
        issue_id = fields.get("External ID")
        if issue_id in actual:
            duplicates.add(issue_id)
        if isinstance(issue_id, str):
            actual[issue_id] = fields
    assert not duplicates, f"upsert created duplicate External IDs: {sorted(duplicates)}"
    assert set(actual) == set(EXPECTED["final"]), "post-sync base has missing or unexpected issue IDs"
    mismatched = [issue_id for issue_id in actual if canonical_fields(actual[issue_id]) != canonical_fields(EXPECTED["final"][issue_id])]
    assert not mismatched, f"post-sync fields violate the import policy for: {mismatched[:12]}"


def test_receipt_classifications_and_totals() -> None:
    payload = load_receipt()
    errors = []
    for category, wanted in EXPECTED["outcomes"].items():
        actual = category_ids(payload, category)
        if actual != wanted:
            errors.append(f"{category}: expected {sorted(wanted)}, got {sorted(actual or set())}")
        count_aliases = {
            form
            for alias in CATEGORY_ALIASES[category]
            for form in (alias, alias + "count", "number" + alias)
        }
        reported_count = find_number(payload, count_aliases)
        if reported_count != len(wanted):
            errors.append(f"{category} count: expected {len(wanted)}, got {reported_count}")
    total = find_number(payload, {"totalrecords", "recordcount", "totalissues", "total"})
    if total != len(EXPECTED["final"]):
        errors.append(f"post-sync total: expected {len(EXPECTED['final'])}, got {total}")
    status_counts = find_status_counts(payload)
    if status_counts != EXPECTED["status_counts"]:
        errors.append(f"status counts: expected {EXPECTED['status_counts']}, got {status_counts}")
    assert not errors, "receipt is inconsistent with the source data or final base:\n" + "\n".join(errors)


def test_rest_sync_was_safe_and_complete() -> None:
    path = RESULTS / "api_activity.jsonl"
    assert path.is_file(), "the REST base has no request audit, so its requested state transition is absent"
    try:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        pytest.fail(f"REST audit is invalid JSONL: {exc}")
    schema_positions = [i for i, event in enumerate(events) if event.get("operation") == "schema" and event.get("status") == 200]
    patches = [(i, event) for i, event in enumerate(events) if event.get("method") == "PATCH"]
    assert schema_positions, "the table schema was never successfully inspected before mutation"
    assert patches, "no REST upsert reached the Issues table"
    first_patch, last_patch = patches[0][0], patches[-1][0]
    assert min(schema_positions) < first_patch, "schema inspection occurred only after writes"
    successful = [event for _, event in patches if event.get("status") == 200]
    assert len(successful) == len(patches), "at least one mutation request failed"
    assert all(event.get("operation") == "upsert" and event.get("merge_fields") == ["External ID"] for event in successful), (
        "mutations were not idempotent External ID batch upserts"
    )
    assert all(isinstance(event.get("batch_size"), int) and 1 <= event["batch_size"] <= 10 for event in successful), (
        "an upsert batch was empty or exceeded the API limit"
    )
    written = [issue_id for event in successful for issue_id in event.get("external_ids", [])]
    assert len(written) == len(set(written)), "an issue was written more than once during this reconciliation"
    assert set(written) == EXPECTED["mutated"], "REST writes included rejected/unchanged IDs or omitted required mutations"

    pre_lists = [event for i, event in enumerate(events) if i < first_patch and event.get("operation") == "list" and not event.get("filtered") and event.get("status") == 200]
    post_lists = [event for i, event in enumerate(events) if i > last_patch and event.get("operation") == "list" and not event.get("filtered") and event.get("status") == 200]
    assert has_complete_listing(pre_lists, 235), (
        "the initial table was not listed through all paginated records"
    )
    assert has_complete_listing(post_lists, len(EXPECTED["final"])), (
        "the final totals were not based on a complete paginated listing"
    )
