from __future__ import annotations

from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
from typing import Any

import pytest


DATA_DIR = Path(os.environ.get("DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "release_packet.json"


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


ALIASES = {
    "change_id": {"changeid", "id", "changeidentifier"},
    "component": {"component", "area", "module"},
    "change_type": {"changetype", "type", "migrationtype"},
    "legacy_symbol": {"legacysymbol", "oldsymbol", "fromsymbol"},
    "replacement_symbol": {"replacementsymbol", "newsymbol", "tosymbol"},
    "effective_version": {"effectiveversion", "version", "targetversion"},
    "command": {"command", "canonicalcommand", "migrationcommand", "cli"},
    "supported_regions": {"supportedregions", "regions", "availabilityregions"},
    "requires_restart": {"requiresrestart", "restartrequired", "needrestart"},
    "retry_limit": {"retrylimit", "retries", "maxretries"},
    "notice": {"notice", "requirednotice", "customernotice", "availabilitynote"},
}


def flatten_record(value: Any, output: dict[str, Any] | None = None) -> dict[str, Any]:
    output = {} if output is None else output
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = norm_key(str(key))
            if not isinstance(child, (dict, list)):
                output.setdefault(normalized, child)
            if isinstance(child, dict):
                flatten_record(child, output)
            elif isinstance(child, list):
                if all(not isinstance(item, (dict, list)) for item in child):
                    output.setdefault(normalized, child)
    return output


def field(record: dict[str, Any], semantic_name: str) -> Any:
    flat = flatten_record(record)
    for alias in ALIASES[semantic_name]:
        if alias in flat:
            return flat[alias]
    return None


def looks_like_catalog_record(value: Any) -> bool:
    if not isinstance(value, dict) or field(value, "change_id") is None:
        return False
    present = sum(
        field(value, name) is not None
        for name in (
            "component",
            "change_type",
            "legacy_symbol",
            "replacement_symbol",
            "command",
            "supported_regions",
            "requires_restart",
        )
    )
    return present >= 4


def collect_catalog_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if looks_like_catalog_record(node):
            records.append(node)
            return
        if isinstance(node, dict):
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return records


def load_submission() -> tuple[Any | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"release packet is not readable JSON: {exc}"
    if not isinstance(payload, (dict, list)):
        return None, "release packet JSON must contain an object or array"
    return payload, None


def load_expected() -> dict[str, dict[str, str]]:
    with (DATA_DIR / "authoritative_changes.csv").open(encoding="utf-8", newline="") as handle:
        return {row["change_id"]: row for row in csv.DictReader(handle)}


def text_leaves(value: Any) -> list[str]:
    leaves: list[str] = []
    if isinstance(value, str):
        leaves.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            leaves.extend(text_leaves(child))
    elif isinstance(value, list):
        for child in value:
            leaves.extend(text_leaves(child))
    return leaves


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "required"}:
            return True
        if lowered in {"false", "no", "n", "0", "not required"}:
            return False
    return None


def as_retry(value: Any) -> int | None | str:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "null", "none", "n/a"}):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return "invalid"


def as_regions(value: Any) -> set[str]:
    if isinstance(value, list):
        parts = [str(item) for item in value]
    elif isinstance(value, str):
        parts = re.split(r"[|,;]", value)
    else:
        return set()
    return {part.strip().lower() for part in parts if part.strip()}


def index_actual(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        identifier = field(record, "change_id")
        if identifier is not None:
            indexed[str(identifier).strip().upper()] = record
    return indexed


def limited_message(prefix: str, errors: list[str]) -> str:
    shown = errors[:12]
    suffix = f"; plus {len(errors) - len(shown)} more" if len(errors) > len(shown) else ""
    return prefix + ": " + "; ".join(shown) + suffix


def test_catalog_coverage() -> None:
    payload, error = load_submission()
    assert error is None, error
    records = collect_catalog_records(payload)
    expected_ids = set(load_expected())
    actual_ids = [str(field(record, "change_id")).strip().upper() for record in records]
    counts = Counter(actual_ids)
    missing = sorted(expected_ids - set(actual_ids))
    unknown = sorted(set(actual_ids) - expected_ids)
    duplicates = sorted(identifier for identifier, count in counts.items() if count != 1)
    assert len(records) == len(expected_ids) and not missing and not unknown and not duplicates, (
        f"catalog coverage is not one-to-one: records={len(records)}, missing={missing[:10]}, "
        f"unknown={unknown[:10]}, non_unique={duplicates[:10]}; customers could miss or receive "
        "duplicate migration actions"
    )


@pytest.mark.parametrize("group", ["identity", "command_regions", "operations", "notices"])
def test_factual_fidelity(group: str) -> None:
    payload, error = load_submission()
    if error is not None:
        if group == "identity":
            pytest.fail(error)
        pytest.skip("artifact parse failure is reported once in this criterion")
    records = collect_catalog_records(payload)
    if not records:
        if group == "identity":
            pytest.fail("no catalog records are available for factual verification")
        pytest.skip("missing catalog is reported once in this criterion")
    expected = load_expected()
    actual = index_actual(records)
    errors: list[str] = []
    for identifier, source in expected.items():
        record = actual.get(identifier)
        if record is None:
            continue  # Missing membership belongs only to catalog_coverage.
        if group == "identity":
            comparisons = {
                "component": source["component"],
                "change_type": source["change_type"],
                "legacy_symbol": source["legacy_symbol"],
                "replacement_symbol": source["replacement_symbol"],
                "effective_version": source["effective_version"],
            }
            for name, expected_value in comparisons.items():
                actual_value = field(record, name)
                if str(actual_value).strip() != expected_value:
                    errors.append(f"{identifier}.{name}={actual_value!r} expected {expected_value!r}")
        elif group == "command_regions":
            command = field(record, "command")
            if str(command).strip() != source["canonical_command"]:
                errors.append(f"{identifier}.command is not canonical")
            regions = as_regions(field(record, "supported_regions"))
            expected_regions = set(source["supported_regions"].lower().split("|"))
            if regions != expected_regions:
                errors.append(f"{identifier}.regions={sorted(regions)} expected {sorted(expected_regions)}")
        elif group == "operations":
            restart = as_bool(field(record, "requires_restart"))
            expected_restart = source["requires_restart"] == "true"
            if restart is not expected_restart:
                errors.append(f"{identifier}.requires_restart={restart!r} expected {expected_restart!r}")
            retry = as_retry(field(record, "retry_limit"))
            expected_retry = int(source["retry_limit"]) if source["retry_limit"] else None
            if retry != expected_retry:
                errors.append(f"{identifier}.retry_limit={retry!r} expected {expected_retry!r}")
        else:
            notice = field(record, "notice")
            notice_text = "" if notice is None else str(notice).lower()
            expected_regions = source["supported_regions"].lower().split("|")
            missing_regions = [region for region in expected_regions if region not in notice_text]
            expected_restart = source["requires_restart"] == "true"
            says_no_restart = bool(re.search(r"no[^.]{0,40}restart|restart[^.]{0,40}not required", notice_text))
            restart_ok = "restart" in notice_text and (not says_no_restart if expected_restart else says_no_restart)
            if missing_regions or not restart_ok:
                errors.append(
                    f"{identifier}.notice omits or contradicts restart/regions "
                    f"(missing_regions={missing_regions}, restart_ok={restart_ok})"
                )
    assert not errors, limited_message(
        f"{group} facts diverge from frozen release evidence", errors
    )


@pytest.mark.parametrize("aspect", ["claims", "release_state"])
def test_publication_safety(aspect: str) -> None:
    payload, error = load_submission()
    assert error is None, error
    records = collect_catalog_records(payload)
    if aspect == "claims":
        catalog_text = "\n".join(text_leaves(records)).lower()
        blocked = [
            phrase
            for phrase in (
                "guarantees zero downtime",
                "zero-risk migration",
                "works in every region",
            )
            if phrase in catalog_text
        ]
        broad_guarantees = re.findall(r"\bguarantee(?:d|s)?\b", catalog_text)
        assert not blocked and not broad_guarantees, (
            f"unsupported publication claims remain: blocked={blocked}, "
            f"guarantee_terms={len(broad_guarantees)}"
        )
    else:
        keyed_values: list[tuple[str, Any]] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    if not isinstance(child, (dict, list)):
                        keyed_values.append((norm_key(str(key)), child))
                    visit(child)
            elif isinstance(node, list):
                for child in node:
                    visit(child)

        visit(payload)
        version_values = {
            str(value).strip()
            for key, value in keyed_values
            if key in {"releaseversion", "targetversion"}
        }
        state_values = {
            str(value).strip().lower()
            for key, value in keyed_values
            if key in {"publicationstate", "releasestatus", "approvalstatus", "status", "approval"}
        }
        assert "7.0.0" in version_values, (
            f"the packet does not identify the approved release as 7.0.0; found {sorted(version_values)}"
        )
        assert any(
            any(marker in value for marker in ("approved", "pass", "publish", "ready"))
            for value in state_values
        ), (
            f"the corrected catalog is not clearly marked approved for publication; found {sorted(state_values)}"
        )
