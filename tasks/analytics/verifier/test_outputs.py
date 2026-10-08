from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest


OUTPUT_PATH = Path(os.environ.get("SUBMISSION_PATH", "/root/results/tracking_plan.json"))
DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


SECTION_ALIASES = {
    "qa_summary": ["qa_summary", "qa_metrics", "quality_summary", "qa_results"],
    "audit_findings": ["audit_findings", "findings", "issues", "audit"],
    "events": ["events", "event_plan", "tracking_events", "tracking_plan"],
    "conversions": ["conversions", "key_events", "conversion_events"],
    "custom_dimensions": ["custom_dimensions", "custom_definitions", "dimensions"],
    "implementation_changes": ["implementation_changes", "implementation", "gtm_changes", "changes"],
    "validation_plan": ["validation_plan", "qa_plan", "test_plan", "validation"],
}

EVENT_ALIASES = {
    "cta_clicked": {"cta_clicked", "trial_cta_clicked"},
    "signup_started": {"signup_started", "account_signup_started", "sign_up_started"},
    "signup_completed": {"signup_completed", "account_signup_completed", "sign_up"},
    "onboarding_step_completed": {"onboarding_step_completed", "onboarding_stage_completed"},
    "workspace_created": {"workspace_created", "team_created"},
    "team_member_invited": {"team_member_invited", "invite_sent"},
    "report_exported": {"report_exported", "report_export_completed"},
    "activation_completed": {"activation_completed", "first_key_action_completed"},
    "checkout_started": {"checkout_started", "begin_checkout"},
    "purchase": {"purchase", "purchase_completed"},
}

EXPECTED_PROPERTIES = {
    "cta_clicked": {"cta_location", "button_text", "page_path", "source", "medium", "campaign"},
    "signup_started": {"method", "source", "medium", "campaign"},
    "signup_completed": {"method", "plan", "source", "medium", "campaign"},
    "onboarding_step_completed": {"step_number", "step_name"},
    "workspace_created": {"workspace_type", "plan"},
    "team_member_invited": {"role", "invite_method"},
    "report_exported": {"report_type", "export_format", "template_id", "is_first_export"},
    "activation_completed": {"days_since_signup", "report_type", "template_id"},
    "checkout_started": {"plan", "billing_cycle", "value", "currency"},
    "purchase": {"transaction_id", "plan", "billing_cycle", "value", "currency"},
}


def nk(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def direct_value(mapping: Any, aliases: list[str]) -> Any:
    if not isinstance(mapping, dict):
        return None
    keyed = {nk(key): value for key, value in mapping.items()}
    for alias in aliases:
        if nk(alias) in keyed:
            return keyed[nk(alias)]
    return None


def find_section(payload: Any, aliases: list[str]) -> Any:
    if not isinstance(payload, dict):
        return None
    found = direct_value(payload, aliases)
    if found is not None:
        return found
    for wrapper in ("plan", "tracking_plan", "handoff", "analytics", "result"):
        child = direct_value(payload, [wrapper])
        found = direct_value(child, aliases)
        if found is not None:
            return found
    return None


def as_entries(section: Any, name_key: str) -> list[dict[str, Any]]:
    if isinstance(section, list):
        rows: list[dict[str, Any]] = []
        for item in section:
            rows.extend(as_entries(item, name_key))
        return rows
    if isinstance(section, dict):
        if direct_value(section, [name_key, "name", "event_name", "parameter"]) is not None:
            return [section]
        rows: list[dict[str, Any]] = []
        for key, value in section.items():
            if isinstance(value, dict):
                has_row_shape = any(
                    direct_value(value, aliases) is not None
                    for aliases in (["properties", "parameters", "trigger", "counting_method", "scope"],)
                )
                if has_row_shape:
                    row = dict(value)
                    if direct_value(row, [name_key, "name", "event_name", "parameter"]) is None:
                        row[name_key] = key
                    rows.append(row)
                else:
                    rows.extend(as_entries(value, name_key))
            elif isinstance(value, list):
                rows.extend(as_entries(value, name_key))
        return rows
    return []


def load_submission() -> tuple[dict[str, Any] | None, str | None]:
    if not OUTPUT_PATH.is_file():
        return None, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"artifact is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "artifact root must be a JSON object"
    return payload, None


@pytest.fixture(scope="session")
def submission() -> dict[str, Any]:
    payload, error = load_submission()
    if error:
        pytest.skip(f"artifact parse failure is reported by test_artifact_usability: {error}")
    assert payload is not None
    return payload


def contains_forbidden_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(nk(key) in forbidden or contains_forbidden_key(child, forbidden) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_key(child, forbidden) for child in value)
    return False


def compute_qa_summary() -> dict[str, int]:
    rules = json.loads((DATA_DIR / "qa_rules.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (DATA_DIR / "qa_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    scoped = [row for row in rows if row.get("traffic_type") == "external"]
    aliases = rules["event_aliases"]
    required = rules["required_properties"]
    forbidden = {nk(item) for item in rules["forbidden_property_keys"]}
    duplicate_extra = 0
    missing = 0
    seen: set[tuple[Any, ...]] = set()
    for row in scoped:
        properties = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        signature = (
            row.get("session_id"),
            row.get("timestamp"),
            row.get("event_name"),
            row.get("analytics_storage"),
            json.dumps(properties, sort_keys=True, separators=(",", ":")),
        )
        if signature in seen:
            duplicate_extra += 1
        else:
            seen.add(signature)
        canonical = aliases.get(row.get("event_name"), row.get("event_name"))
        if canonical in required and any(properties.get(name) in (None, "") for name in required[canonical]):
            missing += 1
    return {
        "total_event_rows": len(scoped),
        "duplicate_extra_rows": duplicate_extra,
        "pre_consent_rows": sum(row.get("analytics_storage") != "granted" for row in scoped),
        "pii_property_rows": sum(contains_forbidden_key(row.get("properties", {}), forbidden) for row in scoped),
        "invalid_event_name_rows": sum(
            re.fullmatch(r"[a-z][a-z0-9_]*", str(row.get("event_name", ""))) is None for row in scoped
        ),
        "missing_required_property_rows": missing,
    }


def qa_value(payload: dict[str, Any], metric: str) -> int | None:
    section = find_section(payload, SECTION_ALIASES["qa_summary"])
    value = direct_value(section, [metric])
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*\d+\s*", value):
        return int(value)
    return None


def canonical_event_name(name: object) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    for canonical, aliases in EVENT_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def event_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    section = find_section(payload, SECTION_ALIASES["events"])
    rows = as_entries(section, "event_name")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_name = direct_value(row, ["event_name", "event", "name"])
        canonical = canonical_event_name(raw_name)
        if canonical and canonical not in result:
            result[canonical] = row
    return result


def property_names(event_row: dict[str, Any]) -> tuple[set[str], set[str]]:
    properties = direct_value(event_row, ["properties", "parameters", "event_properties"])
    all_names: set[str] = set()
    required_names: set[str] = set()
    if isinstance(properties, dict):
        for key, value in properties.items():
            name = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            all_names.add(name)
            if not isinstance(value, dict) or direct_value(value, ["required", "is_required"]) is not False:
                required_names.add(name)
    elif isinstance(properties, list):
        for item in properties:
            if isinstance(item, str):
                name = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
                all_names.add(name)
                required_names.add(name)
            elif isinstance(item, dict):
                raw_name = direct_value(item, ["name", "property", "parameter", "key"])
                if raw_name is None:
                    continue
                name = re.sub(r"[^a-z0-9]+", "_", str(raw_name).lower()).strip("_")
                all_names.add(name)
                if direct_value(item, ["required", "is_required"]) is not False:
                    required_names.add(name)
    extra_required = direct_value(event_row, ["required_properties", "required_parameters"])
    if isinstance(extra_required, list):
        required_names.update(re.sub(r"[^a-z0-9]+", "_", str(item).lower()).strip("_") for item in extra_required)
        all_names.update(required_names)
    return all_names, required_names


def event_consent_required(row: dict[str, Any]) -> bool:
    value = direct_value(row, ["analytics_consent_required", "consent_required", "requires_consent"])
    if value is True:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "yes", "required", "analytics_storage=granted", "granted only"} or (
            "analytics_storage" in normalized and "granted" in normalized
        )
    consent = direct_value(row, ["consent", "consent_state", "consent_requirement"])
    return isinstance(consent, str) and "granted" in consent.lower()


def meaningful(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return value is not None


def conversion_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_entries(find_section(payload, SECTION_ALIASES["conversions"]), "event_name")
    result = {}
    for row in rows:
        canonical = canonical_event_name(direct_value(row, ["event_name", "event", "name"]))
        if canonical:
            result[canonical] = row
    return result


def normalized_counting_method(value: object) -> str:
    compact = nk(value)
    if compact in {"oncepersession", "onepersession", "sessiononce"}:
        return "once_per_session"
    if compact in {"everyevent", "perevent", "alltransactions", "everytransaction"}:
        return "every_event"
    return compact


def dimension_parameters(payload: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    rows = as_entries(find_section(payload, SECTION_ALIASES["custom_dimensions"]), "parameter")
    params: set[str] = set()
    scopes: dict[str, str] = {}
    for row in rows:
        raw = direct_value(row, ["parameter", "parameter_name", "key", "name"])
        if raw is None:
            continue
        parameter = re.sub(r"[^a-z0-9]+", "_", str(raw).lower()).strip("_")
        params.add(parameter)
        scopes[parameter] = nk(direct_value(row, ["scope"]) or "")
    return params, scopes


@pytest.mark.parametrize("metric", sorted(compute_qa_summary()))
def test_qa_summary_accuracy(submission: dict[str, Any], metric: str) -> None:
    expected = compute_qa_summary()[metric]
    actual = qa_value(submission, metric)
    assert actual == expected, (
        f"QA metric {metric} is {actual!r}, expected {expected}; the launch audit would quantify the defect incorrectly"
    )


@pytest.mark.parametrize("canonical", sorted(EVENT_ALIASES))
def test_event_plan_coverage_and_naming(submission: dict[str, Any], canonical: str) -> None:
    index = event_index(submission)
    assert canonical in index, f"required product action {canonical} has no usable event design"
    raw_name = direct_value(index[canonical], ["event_name", "event", "name"])
    assert re.fullmatch(r"[a-z][a-z0-9_]*", str(raw_name or "")), (
        f"planned event {raw_name!r} is not lowercase underscore naming and would fragment the revised taxonomy"
    )
    trigger = direct_value(index[canonical], ["trigger", "success_trigger", "fires_when", "when"])
    source = direct_value(
        index[canonical],
        ["source", "producer", "implementation_source", "collection_source", "event_source", "emitter"],
    )
    assert meaningful(trigger), f"{canonical} lacks an unambiguous success trigger"
    assert meaningful(source), f"{canonical} lacks an implementation source/producer"


@pytest.mark.parametrize("canonical", sorted(EVENT_ALIASES))
def test_event_property_consent_and_privacy_design(submission: dict[str, Any], canonical: str) -> None:
    index = event_index(submission)
    if canonical not in index:
        pytest.skip(f"coverage failure for {canonical} is reported separately")
    all_names, required_names = property_names(index[canonical])
    expected = EXPECTED_PROPERTIES[canonical]
    missing = expected - all_names
    assert not missing, f"{canonical} omits decision-critical properties {sorted(missing)}"
    not_required = expected - required_names
    assert not not_required, f"{canonical} does not identify required properties {sorted(not_required)} as required"
    forbidden = {"email", "emailaddress", "fullname", "phone", "phonenumber", "freetext"}
    assert not any(nk(name) in forbidden for name in all_names), f"{canonical} proposes a forbidden personal-data property"
    assert event_consent_required(index[canonical]), f"{canonical} is not gated on granted analytics consent"


@pytest.mark.parametrize(
    ("canonical", "expected_method"),
    [("signup_completed", "once_per_session"), ("activation_completed", "once_per_session"), ("purchase", "every_event")],
)
def test_conversion_configuration(submission: dict[str, Any], canonical: str, expected_method: str) -> None:
    conversions = conversion_index(submission)
    assert canonical in conversions, f"{canonical} is missing from the conversion plan"
    method = direct_value(conversions[canonical], ["counting_method", "counting", "method"])
    assert normalized_counting_method(method) == expected_method, (
        f"{canonical} uses {method!r}; expected {expected_method} for the stated KPI and deduplication semantics"
    )


def test_custom_dimension_configuration(submission: dict[str, Any]) -> None:
    parameters, scopes = dimension_parameters(submission)
    required = {"cta_location", "plan", "report_type", "template_id", "billing_cycle"}
    missing = required - parameters
    assert not missing, f"custom definitions omit decision-critical segmentation parameters {sorted(missing)}"
    assert {"step_name", "step_number"} & parameters, (
        "custom definitions omit an onboarding-step parameter needed to locate onboarding drop-off"
    )
    checked = required | ({"step_name"} if "step_name" in parameters else {"step_number"})
    wrong_scope = sorted(name for name in checked if scopes.get(name) not in {"event", "eventscope"})
    assert not wrong_scope, f"custom dimensions have the wrong scope for event-varying parameters {wrong_scope}"


def test_automatic_fields_not_redefined_as_custom_dimensions(submission: dict[str, Any]) -> None:
    parameters, _ = dimension_parameters(submission)
    unnecessary = parameters & {"source", "medium", "campaign", "utm_source", "utm_medium", "utm_campaign", "transaction_id", "value", "currency"}
    assert not unnecessary, (
        f"standard acquisition/ecommerce fields were unnecessarily registered as custom dimensions {sorted(unnecessary)}; "
        "this wastes definition slots and can fragment standard GA4 reporting"
    )
