from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"
SCHEMA_FIELDS = set(
    json.loads((DATA_DIR / "extraction_schema.json").read_text(encoding="utf-8"))
)


def _load_oracle_module():
    candidates = [Path("/verifier/reference_parser.py"), Path(__file__).resolve().parent / "reference_parser.py"]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("reference parser is unavailable")
    spec = importlib.util.spec_from_file_location("clinical_note_reference", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


EXPECTED = _load_oracle_module().build_output(DATA_DIR)
EXPECTED_BY_ID = {row["note_id"]: row for row in EXPECTED["records"]}


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _pick(mapping: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    wanted = {_norm_key(alias) for alias in aliases}
    for key, value in mapping.items():
        if _norm_key(key) in wanted:
            return value
    return None


def _load_submission() -> tuple[Any | None, str | None]:
    if not OUTPUT_PATH.is_file():
        return None, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"


PAYLOAD, PAYLOAD_ERROR = _load_submission()


def _record_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    raw = _pick(payload, ("records", "results", "extractions", "notes"))
    if raw is None:
        # A top-level map keyed by the supplied note IDs is also usable.
        if any(str(key).upper().startswith("PN-") for key in payload):
            raw = payload
        else:
            return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                if _pick(row, ("note_id", "noteId", "id", "source_id", "filename")) is None:
                    row["note_id"] = key
                rows.append(row)
        return rows
    return []


def _canonical_note_id(raw: Any) -> str | None:
    if raw is None:
        return None
    match = re.search(r"PN[-_ ]?(\d{1,3})", str(raw), flags=re.I)
    return f"PN-{int(match.group(1)):03d}" if match else None


def _is_refusal(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    for container in (row, _pick(row, ("record", "fields", "extraction", "data"))):
        if not isinstance(container, dict):
            continue
        refusal = _pick(container, ("refusal", "_refusal", "refused"))
        if refusal is True:
            return True
        status = _pick(container, ("status", "outcome"))
        if isinstance(status, str) and _norm_key(status) in {"refused", "rejected", "multinote"}:
            return True
    return False


def _fields(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or _is_refusal(row):
        return {}
    raw = _pick(row, ("fields", "record", "extraction", "data", "values"))
    if isinstance(raw, dict) and not _is_refusal(raw):
        return raw
    # Accept schema fields directly on the record.
    direct = {key: value for key, value in row.items() if key in SCHEMA_FIELDS}
    return direct


def _normalize_field(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"value": raw}
    result = dict(raw)
    value = _pick(raw, ("value", "val", "answer", "extracted_value", "extractedValue"))
    if value is not None or any(_norm_key(key) in {"value", "val", "answer", "extractedvalue"} for key in raw):
        result["value"] = value
    span = _pick(raw, ("span", "evidence", "source_span", "sourceSpan", "quote", "source_text"))
    if span is not None:
        result["span"] = span
    location = _pick(raw, ("location", "section", "source_location", "sourceLocation"))
    if location is not None:
        result["location"] = location
    null_reason = _pick(raw, ("null_reason", "nullReason", "missing_reason", "missingReason"))
    if null_reason is not None:
        result["null_reason"] = null_reason
    unit = _pick(raw, ("unit", "units"))
    if unit is not None:
        result["unit"] = unit

    for nested_name in ("assertion", "context", "assertions", "validation", "checks", "check"):
        nested = _pick(raw, (nested_name,))
        if isinstance(nested, dict):
            for key, value in nested.items():
                result.setdefault(key, value)
    for axis in ("presence", "temporality", "experiencer"):
        axis_value = _pick(result, (axis,))
        if axis_value is not None:
            result[axis] = axis_value
    return result


def _submission_by_id() -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows = _record_list(PAYLOAD)
    found: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_id = _pick(row, ("note_id", "noteId", "id", "source_id", "sourceId", "filename", "file"))
        note_id = _canonical_note_id(raw_id)
        if note_id is None:
            continue
        if note_id in found:
            duplicates.append(note_id)
        else:
            found[note_id] = row
    return found, duplicates


def _axis(value: Any, axis: str) -> str:
    defaults = {"presence": "present", "temporality": "current", "experiencer": "patient"}
    if value is None:
        return defaults[axis]
    token = _norm_key(value)
    aliases = {
        "presence": {
            "present": "present",
            "positive": "present",
            "affirmed": "present",
            "absent": "absent",
            "negative": "absent",
            "negated": "absent",
            "possible": "possible",
            "uncertain": "possible",
            "suspected": "possible",
        },
        "temporality": {
            "current": "current",
            "present": "current",
            "historical": "historical",
            "history": "historical",
            "past": "historical",
            "hypothetical": "hypothetical",
            "conditional": "hypothetical",
            "future": "hypothetical",
            "planned": "hypothetical",
        },
        "experiencer": {
            "patient": "patient",
            "self": "patient",
            "familymember": "family_member",
            "family": "family_member",
            "relative": "family_member",
            "other": "other",
        },
    }
    return aliases[axis].get(token, token)


def _normalize_null_reason(value: Any) -> str:
    token = _norm_key(value)
    aliases = {
        "notmentioned": "not_mentioned",
        "missing": "not_mentioned",
        "absentfromnote": "not_mentioned",
        "mentionedunclear": "mentioned_unclear",
        "unclear": "mentioned_unclear",
        "unreadable": "mentioned_unclear",
        "redacted": "redacted",
        "outofscope": "out_of_scope",
    }
    return aliases.get(token, token)


def _normalize_date_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"June\s+(\d{4})", value.strip(), flags=re.I)
    return f"{match.group(1)}-06" if match else value.strip()


def _same_value(field_name: str, actual: Any, expected: Any, expected_field: dict[str, Any]) -> bool:
    actual = _normalize_date_value(actual)
    expected = _normalize_date_value(expected)
    if expected is None:
        return actual is None
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-7, abs_tol=1e-7)
        except (TypeError, ValueError):
            return False
    if field_name in {"bronchodilator_response", "home_oxygen", "current_chest_pain", "family_emphysema"} and isinstance(actual, bool):
        expected_presence = _axis(expected_field.get("presence"), "presence")
        if expected_presence == "possible":
            return False
        return actual is (expected_presence == "present")
    return re.sub(r"\s+", " ", str(actual).strip().lower()) == re.sub(
        r"\s+", " ", str(expected).strip().lower()
    )


def _summary() -> Any:
    if not isinstance(PAYLOAD, dict):
        return None
    return _pick(PAYLOAD, ("reviewer_summary", "reviewerSummary", "completion_summary", "completionSummary", "summary", "report"))


def _walk_pairs(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_pairs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_pairs(child)


def _metric(summary: Any, aliases: tuple[str, ...]) -> int | None:
    wanted = {_norm_key(alias) for alias in aliases}
    if isinstance(summary, (dict, list)):
        for key, value in _walk_pairs(summary):
            if _norm_key(key) in wanted and isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    if isinstance(summary, str):
        for alias in aliases:
            alias_pattern = re.escape(alias).replace(r"\ ", r"\s*")
            pattern = rf"(?:{alias_pattern})\D{{0,20}}(\d+)"
            match = re.search(pattern, summary, flags=re.I)
            if match:
                return int(match.group(1))
    return None


def _fatal_message() -> str:
    return PAYLOAD_ERROR or "output.json does not expose one result per source note"


def test_artifact_and_note_scope():
    """artifact_scope: the requested JSON and all source-note results are usable."""
    assert PAYLOAD_ERROR is None, PAYLOAD_ERROR
    assert isinstance(PAYLOAD, (dict, list)), "output.json must contain a JSON object or array"
    by_id, duplicates = _submission_by_id()
    assert not duplicates, f"duplicate note results would make registry rows ambiguous: {duplicates}"
    assert set(by_id) == set(EXPECTED_BY_ID), (
        f"note coverage differs from the 24-file inventory; missing={sorted(set(EXPECTED_BY_ID)-set(by_id))}, "
        f"extra={sorted(set(by_id)-set(EXPECTED_BY_ID))}"
    )
    for note_id in sorted(set(EXPECTED_BY_ID) - {"PN-024"}):
        actual_fields = _fields(by_id[note_id])
        assert set(actual_fields) == SCHEMA_FIELDS, (
            f"{note_id} is not schema-complete; missing={sorted(SCHEMA_FIELDS-set(actual_fields))}, "
            f"extra={sorted(set(actual_fields)-SCHEMA_FIELDS)}"
        )
    assert _summary() is not None, "the requested compact reviewer summary is missing"


VALUE_GROUPS = [
    [f"PN-{i:03d}" for i in range(1, 6)],
    [f"PN-{i:03d}" for i in range(6, 11)],
    [f"PN-{i:03d}" for i in range(11, 16)],
    [f"PN-{i:03d}" for i in range(16, 21)],
    [f"PN-{i:03d}" for i in range(21, 24)],
]


@pytest.mark.parametrize("note_ids", VALUE_GROUPS, ids=["01-05", "06-10", "11-15", "16-20", "21-23"])
def test_extracted_values_and_nulls(note_ids):
    """extraction_correctness: source-stated values and null reasons are correct."""
    by_id, _ = _submission_by_id()
    assert all(note_id in by_id for note_id in note_ids), _fatal_message()
    errors = []
    for note_id in note_ids:
        actual_fields = _fields(by_id[note_id])
        expected_fields = EXPECTED_BY_ID[note_id]["fields"]
        if set(actual_fields) != SCHEMA_FIELDS:
            errors.append(f"{note_id}: fields unavailable for semantic comparison")
            continue
        for field_name in sorted(SCHEMA_FIELDS):
            actual = _normalize_field(actual_fields[field_name])
            expected = expected_fields[field_name]
            if not _same_value(field_name, actual.get("value"), expected.get("value"), expected):
                errors.append(
                    f"{note_id}.{field_name}: got value {actual.get('value')!r}, expected source-stated {expected.get('value')!r}"
                )
                continue
            if expected.get("value") is None:
                if _normalize_null_reason(actual.get("null_reason")) != expected["null_reason"]:
                    errors.append(
                        f"{note_id}.{field_name}: null reason {actual.get('null_reason')!r} does not explain the source absence"
                    )
            elif field_name in {
                "fev1_liters",
                "fev1_percent_predicted",
                "fvc_liters",
                "fvc_percent_predicted",
                "dlco_percent_predicted",
            }:
                if str(actual.get("unit", "")).strip() != expected.get("unit"):
                    errors.append(
                        f"{note_id}.{field_name}: unit {actual.get('unit')!r} does not preserve the note's unit {expected.get('unit')!r}"
                    )
    assert not errors, "\n".join(errors[:20])


ASSERTION_CASES = [
    ("PN-001", "current_chest_pain", "absent", "current", "patient"),
    ("PN-001", "family_emphysema", "present", "current", "family_member"),
    ("PN-002", "family_emphysema", "absent", "current", "family_member"),
    ("PN-003", "current_chest_pain", "possible", "current", "patient"),
    ("PN-004", "current_chest_pain", "present", "hypothetical", "patient"),
    ("PN-018", "family_emphysema", "possible", "historical", "family_member"),
    ("PN-019", "family_emphysema", "absent", "historical", "family_member"),
    ("PN-020", "home_oxygen", "present", "hypothetical", "patient"),
    ("PN-021", "home_oxygen", "absent", "current", "patient"),
    ("PN-022", "bronchodilator_response", "possible", "current", "patient"),
]


@pytest.mark.parametrize(
    "note_id,field_name,presence,temporality,experiencer",
    ASSERTION_CASES,
    ids=[f"{row[0]}-{row[1]}" for row in ASSERTION_CASES],
)
def test_assertion_context_and_malformed_note(note_id, field_name, presence, temporality, experiencer):
    """assertion_and_refusal_safety: clinically distinct assertion axes are preserved."""
    by_id, _ = _submission_by_id()
    assert note_id in by_id, _fatal_message()
    actual_fields = _fields(by_id[note_id])
    assert field_name in actual_fields, f"{note_id}.{field_name} is unavailable"
    actual = _normalize_field(actual_fields[field_name])
    observed = (
        _axis(actual.get("presence"), "presence"),
        _axis(actual.get("temporality"), "temporality"),
        _axis(actual.get("experiencer"), "experiencer"),
    )
    assert observed == (presence, temporality, experiencer), (
        f"{note_id}.{field_name} assertion is {observed}, expected {(presence, temporality, experiencer)}; "
        "flattening these axes can turn denials, plans, or family history into patient findings"
    )


def test_multi_note_source_is_refused():
    """assertion_and_refusal_safety: a concatenated two-note source is not merged."""
    by_id, _ = _submission_by_id()
    assert "PN-024" in by_id, _fatal_message()
    assert _is_refusal(by_id["PN-024"]), (
        "PN-024 contains two encounter notes and must be surfaced as a refusal, not merged into one patient record"
    )


PROVENANCE_GROUPS = [
    [f"PN-{i:03d}" for i in range(1, 6)],
    [f"PN-{i:03d}" for i in range(6, 11)],
    [f"PN-{i:03d}" for i in range(11, 16)],
    [f"PN-{i:03d}" for i in range(16, 21)],
    [f"PN-{i:03d}" for i in range(21, 24)],
]


@pytest.mark.parametrize("note_ids", PROVENANCE_GROUPS, ids=["01-05", "06-10", "11-15", "16-20", "21-23"])
def test_provenance_and_field_validation(note_ids):
    """provenance_validation: populated fields are citable and material check failures are surfaced."""
    by_id, _ = _submission_by_id()
    assert all(note_id in by_id for note_id in note_ids), _fatal_message()
    summary_text = json.dumps(_summary(), ensure_ascii=False).lower()
    errors = []
    expected_flags = {
        ("PN-009", "test_date"): ("date", "invalid"),
        ("PN-010", "fev1_percent_predicted"): ("range", "above"),
        ("PN-011", "fev1_liters"): ("unit", "mismatch"),
        ("PN-012", "fev1_fvc_ratio"): ("range", "above"),
        ("PN-013", "dlco_percent_predicted"): ("range", "below"),
    }
    for note_id in note_ids:
        text = (DATA_DIR / "notes" / f"{note_id}.txt").read_text(encoding="utf-8")
        for field_name, raw in _fields(by_id[note_id]).items():
            actual = _normalize_field(raw)
            if actual.get("value") is not None:
                span = actual.get("span")
                location = actual.get("location")
                if not isinstance(span, str) or not span or span not in text:
                    errors.append(f"{note_id}.{field_name}: evidence is missing or not verbatim in the source note")
                if not isinstance(location, str) or not location.strip():
                    errors.append(f"{note_id}.{field_name}: evidence location is missing")
            flag_words = expected_flags.get((note_id, field_name))
            if flag_words:
                field_text = json.dumps(actual, ensure_ascii=False).lower()
                surfaced = all(word in field_text for word in flag_words) or (
                    note_id.lower() in summary_text
                    and field_name.lower() in summary_text
                    and any(word in summary_text for word in flag_words)
                )
                if not surfaced:
                    errors.append(f"{note_id}.{field_name}: material validation issue {flag_words} is not surfaced")
    if "PN-014" in note_ids or "PN-023" in note_ids:
        if not ("unvalidated" in summary_text and ("icd10cm" in _norm_key(summary_text) or "icd-10" in summary_text)):
            errors.append("the unavailable ICD-10-CM terminology validation is not named in the reviewer summary")
    assert not errors, "\n".join(errors[:25])


def test_summary_reconciles_with_records():
    """summary_consistency: completion, null, and validation counts reconcile to the batch."""
    assert PAYLOAD_ERROR is None, PAYLOAD_ERROR
    summary = _summary()
    assert summary is not None, "reviewer summary is missing"
    expected = EXPECTED["reviewer_summary"]
    checks = [
        (("notes_requested", "notes requested", "total notes"), expected["notes_requested"]),
        (("notes_completed", "notes completed", "processed notes"), expected["notes_completed"]),
        (("notes_refused", "notes refused", "refused notes"), expected["notes_refused"]),
        (("field_slots_processed", "field slots processed", "fields processed"), expected["field_slots_processed"]),
        (("populated", "fields populated", "populated fields"), expected["populated"]),
        (("null", "null fields", "fields null"), expected["null"]),
        (("not_mentioned", "not mentioned"), expected["null_reasons"]["not_mentioned"]),
        (("mentioned_unclear", "mentioned unclear", "unclear"), expected["null_reasons"]["mentioned_unclear"]),
        (("redacted",), expected["null_reasons"]["redacted"]),
        (("range_flagged", "range flagged", "range flags"), expected["validation"]["range_flagged"]),
        (("date_flagged", "date flagged", "date flags"), expected["validation"]["date_flagged"]),
        (("terminology_unvalidated", "terminology unvalidated", "unvalidated terminology"), expected["validation"]["terminology_unvalidated"]),
    ]
    errors = []
    for aliases, expected_value in checks:
        actual = _metric(summary, aliases)
        if actual != expected_value:
            errors.append(f"summary metric {aliases[0]!r} is {actual!r}, expected {expected_value}")
    assert not errors, "\n".join(errors)
