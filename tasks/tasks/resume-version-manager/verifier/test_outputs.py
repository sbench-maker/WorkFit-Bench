from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_FILE", "/root/results/resume_register.json"))
MISSING = object()


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(row: dict, aliases: tuple[str, ...], default=MISSING):
    wanted = {_token(alias) for alias in aliases}
    for key, value in row.items():
        if _token(key) in wanted:
            return value
    if default is MISSING:
        raise KeyError(f"none of {aliases!r} is present")
    return default


def _section(root: object, aliases: tuple[str, ...]):
    wanted = {_token(alias) for alias in aliases}
    queue = [root]
    seen = set()
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        for key, value in current.items():
            if _token(key) in wanted:
                return value
        for value in current.values():
            if isinstance(value, dict):
                queue.append(value)
    return None


def _records(section: object, id_aliases: tuple[str, ...], id_pattern: str) -> list[dict]:
    records: list[dict] = []
    id_tokens = {_token(alias) for alias in id_aliases}

    def visit(node: object, keyed_id: str | None = None) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        has_id = any(_token(key) in id_tokens for key in node)
        if has_id or keyed_id is not None:
            row = dict(node)
            if not has_id and keyed_id is not None:
                row[id_aliases[0]] = keyed_id
            records.append(row)
            return
        for key, value in node.items():
            inferred = key if isinstance(value, dict) and re.fullmatch(id_pattern, str(key), re.I) else None
            visit(value, inferred)

    visit(section)
    return records


def _id_list(value: object, aliases: tuple[str, ...]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, dict):
        values = []
        for key, item in value.items():
            if isinstance(item, bool) and item:
                values.append(str(key))
            elif isinstance(item, dict):
                identifier = _field(item, aliases, None)
                if identifier is not None:
                    values.append(str(identifier))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                identifier = _field(item, aliases, None)
                if identifier is not None:
                    values.append(str(identifier))
        return values
    return []


def _bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if _token(value) in {"true", "yes", "valid", "1"}:
            return True
        if _token(value) in {"false", "no", "invalid", "0"}:
            return False
    return None


def _normalized_submission() -> dict:
    if not OUTPUT.is_file():
        return {"error": f"missing {OUTPUT}"}
    try:
        root = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable JSON: {exc}"}
    if not isinstance(root, dict):
        return {"error": "top-level JSON value is not an object"}
    master_section = _section(root, ("canonical_master", "current_master", "master_resume", "master"))
    version_section = _section(
        root,
        (
            "versions",
            "resume_versions",
            "version_register",
            "tailored_versions",
            "version_inventory",
            "tailored_version_inventory",
        ),
    )
    application_section = _section(
        root,
        ("applications", "application_links", "application_reconciliation", "application_audit", "submissions"),
    )
    masters = _records(master_section, ("master_id", "id", "master_version_id"), r"M\d{3}")
    versions = _records(version_section, ("version_id", "resume_version_id", "id"), r"V\d{3}")
    applications = _records(application_section, ("application_id", "app_id", "id"), r"A\d{4}")
    return {
        "root": root,
        "master_section": master_section,
        "version_section": version_section,
        "application_section": application_section,
        "masters": masters,
        "versions": versions,
        "applications": applications,
    }


def _require_usable(normalized: dict) -> None:
    if normalized.get("error"):
        pytest.skip("artifact-level parser failure is scored only by test_artifact_usability")
    if not normalized["masters"] or not normalized["versions"] or not normalized["applications"]:
        pytest.skip("missing root record groups are scored only by test_artifact_usability")


def _expected() -> dict:
    snapshot = _load("snapshot.json")
    masters = _load("master_revisions.json")
    versions = _load("resume_versions.json")
    updates = _load("content_updates.json")
    applications = _load("applications.json")
    master_by_id = {row["master_id"]: row for row in masters}
    version_by_id = {row["version_id"]: row for row in versions}
    by_hash: dict[str, list[str]] = defaultdict(list)
    by_name: dict[str, list[str]] = defaultdict(list)
    for row in versions:
        by_hash[row["content_sha256"]].append(row["version_id"])
        by_name[row["file_name"].casefold()].append(row["version_id"])

    reconciled = {}
    app_by_id = {row["application_id"]: row for row in applications}
    for app in applications:
        if app["submitted_at"] is None:
            continue
        reference = app.get("resume_ref")
        if reference in version_by_id:
            ref_matches = [reference]
        elif isinstance(reference, str) and reference:
            ref_matches = by_name.get(reference.casefold(), [])
        else:
            ref_matches = []
        hash_matches = by_hash.get(app.get("attachment_sha256"), [])
        resolved = None
        candidates: list[str] = []
        if len(hash_matches) == 1:
            hash_id = hash_matches[0]
            if ref_matches and hash_id not in ref_matches:
                status = "conflict"
                candidates = sorted(set(ref_matches + hash_matches))
            else:
                status = "resolved"
                resolved = hash_id
        elif len(ref_matches) == 1:
            status = "resolved"
            resolved = ref_matches[0]
        elif len(ref_matches) > 1:
            status = "ambiguous"
            candidates = sorted(ref_matches)
        else:
            status = "missing"
        if resolved is not None and version_by_id[resolved]["created_at"] > app["submitted_at"]:
            candidates = [resolved]
            resolved = None
            status = "conflict"
        reconciled[app["application_id"]] = {
            "status": status,
            "resolved": resolved,
            "candidates": candidates,
        }

    linked: dict[str, list[str]] = defaultdict(list)
    open_linked: dict[str, list[str]] = defaultdict(list)
    for application_id, result in reconciled.items():
        if result["resolved"] is None:
            continue
        linked[result["resolved"]].append(application_id)
        if app_by_id[application_id]["status"] in snapshot["open_application_statuses"]:
            open_linked[result["resolved"]].append(application_id)

    revision_for_update = {
        row["update_id"]: master_by_id[row["introduced_in_master_id"]]["revision_number"]
        for row in updates
    }
    update_by_id = {row["update_id"]: row for row in updates}
    expected_versions = {}
    for version in versions:
        base = master_by_id.get(version["base_master_id"])
        valid = base is not None and version["created_at"] >= base["published_at"]
        missing = []
        if base is not None:
            for update in updates:
                relevant = "all" in update["applies_to"] or version["role_family"] in update["applies_to"]
                later = revision_for_update[update["update_id"]] > base["revision_number"]
                if relevant and later and update["update_id"] not in version["included_update_ids"]:
                    missing.append(update["update_id"])
        linked_ids = sorted(linked[version["version_id"]])
        open_ids = sorted(open_linked[version["version_id"]])
        latest = max((app_by_id[item]["submitted_at"] for item in linked_ids), default=None)
        critical = [item for item in missing if update_by_id[item]["importance"] == "critical"]
        if version["stored_state"] == "archived":
            action = "retain_archived"
        elif not valid:
            action = "investigate"
        elif open_ids and critical:
            action = "rebuild"
        elif open_ids and missing:
            action = "refresh"
        elif (
            not open_ids
            and version["created_at"] < snapshot["archive_cutoff"]
            and (latest is None or latest < snapshot["archive_cutoff"])
        ):
            action = "archive"
        else:
            action = "keep"
        expected_versions[version["version_id"]] = {
            "base": version["base_master_id"],
            "valid": valid,
            "linked": linked_ids,
            "open": open_ids,
            "missing": sorted(missing),
            "action": action,
        }
    return {
        "master": next(row for row in masters if row["state"] == "current"),
        "versions": expected_versions,
        "applications": reconciled,
    }


def _index(records: list[dict], aliases: tuple[str, ...]) -> tuple[dict[str, dict], list[str]]:
    indexed: dict[str, dict] = {}
    duplicates = []
    for row in records:
        identifier = _field(row, aliases, None)
        if identifier is None:
            continue
        identifier = str(identifier)
        if identifier in indexed:
            duplicates.append(identifier)
        indexed[identifier] = row
    return indexed, duplicates


def test_master_source_of_truth():
    normalized = _normalized_submission()
    _require_usable(normalized)
    expected = _expected()["master"]
    candidates = normalized["masters"]
    matching = [
        row
        for row in candidates
        if str(_field(row, ("master_id", "master_version_id", "id"), "")) == expected["master_id"]
    ]
    assert matching, f"canonical master should be {expected['master_id']}"
    row = matching[0]
    assert str(_field(row, ("file_name", "filename", "file"), "")) == expected["file_name"]
    assert int(_field(row, ("revision_number", "revision", "version_number"), -1)) == expected["revision_number"]


def test_version_inventory_and_lineage():
    normalized = _normalized_submission()
    _require_usable(normalized)
    actual, duplicates = _index(normalized["versions"], ("version_id", "resume_version_id", "id"))
    expected = _expected()["versions"]
    assert not duplicates, f"duplicate version records: {duplicates[:8]}"
    assert set(actual) == set(expected), (
        f"version inventory mismatch; missing={sorted(set(expected)-set(actual))[:8]}, "
        f"extra={sorted(set(actual)-set(expected))[:8]}"
    )
    errors = []
    for version_id, wanted in expected.items():
        row = actual[version_id]
        base = str(_field(row, ("base_master_id", "master_id", "based_on_master_id", "base"), ""))
        valid = _bool(_field(row, ("lineage_valid", "valid_lineage", "base_valid"), None))
        if base != wanted["base"] or valid != wanted["valid"]:
            errors.append(f"{version_id}: base={base}, valid={valid}")
    assert not errors, "incorrect version lineage: " + "; ".join(errors[:8])


def test_submitted_application_coverage():
    normalized = _normalized_submission()
    _require_usable(normalized)
    actual, duplicates = _index(normalized["applications"], ("application_id", "app_id", "id"))
    expected = _expected()["applications"]
    assert not duplicates, f"duplicate application records: {duplicates[:8]}"
    assert set(expected) <= set(actual), f"submitted applications missing: {sorted(set(expected)-set(actual))[:10]}"


def test_application_reconciliation_values():
    normalized = _normalized_submission()
    _require_usable(normalized)
    actual, _ = _index(normalized["applications"], ("application_id", "app_id", "id"))
    expected = _expected()["applications"]
    if not set(expected) <= set(actual):
        pytest.skip("coverage failure is scored by test_submitted_application_coverage")
    errors = []
    for application_id, wanted in expected.items():
        row = actual[application_id]
        status = _token(_field(row, ("resolution_status", "link_status", "status", "result"), ""))
        resolved = _field(
            row,
            ("resolved_version_id", "matched_version_id", "sent_version_id", "resume_version_id", "version_id"),
            None,
        )
        resolved = None if resolved in (None, "", "null") else str(resolved)
        candidates = sorted(
            set(
                _id_list(
                    _field(row, ("candidate_version_ids", "candidates", "possible_version_ids"), []),
                    ("version_id", "resume_version_id", "id"),
                )
            )
        )
        if status != _token(wanted["status"]) or resolved != wanted["resolved"] or candidates != wanted["candidates"]:
            errors.append(
                f"{application_id}: status={status}, resolved={resolved}, candidates={candidates}"
            )
    assert not errors, "incorrect reconciliation outcomes: " + "; ".join(errors[:10])


def test_update_propagation_and_linkage():
    normalized = _normalized_submission()
    _require_usable(normalized)
    actual, _ = _index(normalized["versions"], ("version_id", "resume_version_id", "id"))
    expected = _expected()["versions"]
    if set(actual) != set(expected):
        pytest.skip("inventory mismatch is scored by test_version_inventory_and_lineage")
    errors = []
    for version_id, wanted in expected.items():
        row = actual[version_id]
        linked = sorted(
            set(
                _id_list(
                    _field(row, ("linked_application_ids", "application_ids", "linked_applications"), []),
                    ("application_id", "app_id", "id"),
                )
            )
        )
        opened = sorted(
            set(
                _id_list(
                    _field(row, ("open_application_ids", "active_application_ids", "open_applications"), []),
                    ("application_id", "app_id", "id"),
                )
            )
        )
        missing = sorted(
            set(
                _id_list(
                    _field(row, ("missing_update_ids", "pending_update_ids", "missing_updates"), []),
                    ("update_id", "id"),
                )
            )
        )
        if linked != wanted["linked"] or opened != wanted["open"] or missing != wanted["missing"]:
            errors.append(f"{version_id}: linked/open/missing updates disagree")
    assert not errors, "incorrect update propagation or application linkage: " + "; ".join(errors[:10])


def test_lifecycle_actions():
    normalized = _normalized_submission()
    _require_usable(normalized)
    actual, _ = _index(normalized["versions"], ("version_id", "resume_version_id", "id"))
    expected = _expected()["versions"]
    if set(actual) != set(expected):
        pytest.skip("inventory mismatch is scored by test_version_inventory_and_lineage")
    errors = []
    for version_id, wanted in expected.items():
        action = _token(
            _field(actual[version_id], ("lifecycle_action", "action", "disposition", "recommended_action"), "")
        )
        if action != _token(wanted["action"]):
            errors.append(f"{version_id}: {action or '<missing>'} != {wanted['action']}")
    assert not errors, "incorrect lifecycle actions: " + "; ".join(errors[:10])
    destructive = [
        version_id
        for version_id, row in actual.items()
        if "delete" in str(_field(row, ("lifecycle_action", "action", "disposition"), "")).casefold()
    ]
    assert not destructive, f"historical versions were marked for deletion: {destructive[:8]}"
