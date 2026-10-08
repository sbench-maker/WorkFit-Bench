from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ground_truth import build_decisions


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "handoff_plan.json"
MISSING = object()
BATCHES = 6


def _read_submission() -> object:
    assert OUTPUT_PATH.is_file(), f"missing requested artifact: {OUTPUT_PATH}"
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"handoff_plan.json is not readable JSON: {exc}")


def _find_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = MISSING
        for path in (
            ("decisions",),
            ("records",),
            ("results",),
            ("leads",),
            ("contacts",),
            ("handoff_plan", "decisions"),
            ("handoff_plan", "records"),
        ):
            candidate = _lookup(payload, [path])
            if isinstance(candidate, list):
                rows = candidate
                break
        assert rows is not MISSING, "JSON must contain a list of contact handoff decisions"
    else:
        pytest.fail("handoff_plan.json must be a JSON object or list")
    assert all(isinstance(row, dict) for row in rows), "every handoff decision must be a JSON object"
    return rows


def _lookup(row: dict, paths: list[tuple[str, ...]]) -> object:
    for path in paths:
        value: object = row
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = MISSING
                break
            value = value[key]
        if value is not MISSING:
            return value
    return MISSING


def _field(row: dict, name: str) -> object:
    aliases = {
        "lead_id": [("lead_id",), ("contact_id",), ("id",), ("lead", "id"), ("contact", "id")],
        "resolved_account_id": [("resolved_account_id",), ("resolved_account",), ("account_id",), ("account", "id"), ("account", "account_id")],
        "account_resolution": [("account_resolution",), ("account_match",), ("account", "resolution"), ("account", "match_method")],
        "fit_score": [("fit_score",), ("scores", "fit"), ("scores", "fit_score"), ("scoring", "fit")],
        "engagement_score": [("engagement_score",), ("scores", "engagement"), ("scores", "engagement_score"), ("scoring", "engagement")],
        "negative_score": [("negative_score",), ("scores", "negative"), ("scores", "negative_score"), ("scoring", "negative")],
        "total_score": [("total_score",), ("score",), ("scores", "total"), ("scores", "total_score"), ("scoring", "total")],
        "disqualifiers": [("disqualifiers",), ("scores", "disqualifiers"), ("scoring", "disqualifiers")],
        "lifecycle_stage": [("lifecycle_stage",), ("resulting_lifecycle_stage",), ("final_stage",), ("stage",), ("lifecycle", "stage"), ("qualification", "stage")],
        "assigned_owner_id": [("assigned_owner_id",), ("assigned_owner",), ("owner_id",), ("assigned_to",), ("routing", "owner_id"), ("routing", "owner"), ("routing", "owner", "id")],
        "routing_reason": [("routing_reason",), ("route_reason",), ("routing", "reason"), ("routing", "category")],
        "handoff_at": [("handoff_at",), ("handoff_timestamp",), ("sla", "handoff_at"), ("handoff", "at")],
        "first_contact_due_at": [("first_contact_due_at",), ("first_contact_due_time",), ("follow_up_due_at",), ("due_at",), ("sla", "due_at"), ("sla", "first_contact_due_at")],
        "first_contact_at": [("first_contact_at",), ("sla", "first_contact_at"), ("contact", "first_sales_contact_at")],
        "sla_status": [("sla_status",), ("sla", "status"), ("handoff", "sla_status")],
        "next_action": [("next_action",), ("action",), ("sla", "next_action"), ("handoff", "action")],
        "human_review_required": [("human_review_required",), ("review_required",), ("review", "required")],
        "human_review_reasons": [("human_review_reasons",), ("human_review_reason",), ("review_reasons",), ("review_reason",), ("review", "reasons"), ("review", "reason")],
    }
    return _lookup(row, aliases[name])


def _text(value: object) -> str | None:
    if value is MISSING:
        return None
    if value is None:
        return None
    return str(value).strip()


def _enum(value: object) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    aliases = {
        "marketing_qualified_lead": "mql",
        "dq": "disqualified",
        "not_applicable": "not_applicable",
        "n_a": "not_applicable",
    }
    return aliases.get(normalized, normalized)


def _number(value: object) -> int | None:
    if value is MISSING or value is None or value == "":
        return None
    number = float(value)
    assert number.is_integer(), f"expected an integer score, got {value!r}"
    return int(number)


def _timestamp(value: object) -> str | None:
    raw = _text(value)
    if raw is None or raw.lower() in {"none", "null", "n/a", "not applicable"}:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _boolean(value: object) -> bool | None:
    if value is MISSING or value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise AssertionError(f"expected a boolean review flag, got {value!r}")


def _string_set(value: object) -> set[str] | None:
    if value is MISSING:
        return None
    if value is None or value == "":
        return set()
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"\s*[;,|]\s*", str(value))
    return {_enum(item) or "" for item in items if _text(item)}


def _account_resolution(value: object) -> str | None:
    normalized = _enum(value)
    aliases = {
        "id": "account_id",
        "direct_id": "account_id",
        "crm_account_id": "account_id",
        "email_domain": "unique_email_domain",
        "domain_match": "unique_email_domain",
        "unique_domain": "unique_email_domain",
        "ambiguous": "unresolved",
        "unmatched": "unresolved",
        "no_match": "unresolved",
    }
    return aliases.get(normalized, normalized)


def _route_matches(value: object, expected: str) -> bool:
    observed = _enum(value)
    accepted = {
        "not_applicable": {"not_applicable", "none", "no_route"},
        "current_owner": {"current_owner", "existing_owner", "retained_owner", "owner_continuity"},
        "named_account_owner": {"named_account_owner", "named_owner", "account_owner", "abm_owner"},
        "healthcare_specialist": {"healthcare_specialist", "healthcare", "vertical_specialist"},
        "general_pool": {"general_pool", "general", "fallback_pool", "fallback"},
        "capacity_queue": {"capacity_queue", "queue", "no_capacity_queue", "revops_queue"},
        "engaged_existing_owner": {"engaged_existing_owner", "contacted_existing_owner", "current_owner_engaged"},
        "missing_contact_owner": {"missing_contact_owner", "contact_without_owner", "owner_missing"},
    }
    if expected.startswith("enterprise_"):
        return observed in {expected, "enterprise", "enterprise_pool", "enterprise_team"}
    if expected.startswith("territory_"):
        return observed in {expected, "territory", "territory_pool", "territory_based", "geographic_territory"}
    return observed in accepted.get(expected, {expected})


def _action_matches(value: object, expected: str) -> bool:
    observed = _enum(value)
    accepted = {
        "none": {"none", "no_action"},
        "record_sla_breach": {"record_sla_breach", "log_sla_breach", "record_late_contact"},
        "manual_assignment_required": {"manual_assignment_required", "manual_assign", "manual_review", "assign_from_queue"},
        "create_followup_task": {"create_followup_task", "create_follow_up_task", "create_task", "follow_up"},
        "alert_manager_and_keep_task_open": {"alert_manager_and_keep_task_open", "alert_manager", "manager_alert_keep_open"},
        "reassign_and_alert_manager": {"reassign_and_alert_manager", "reassign_alert_manager", "reassign_and_escalate"},
        "reassign_and_create_followup_task": {"reassign_and_create_followup_task", "reassign_and_create_task", "reassign_follow_up"},
        "reassign_and_create_urgent_task": {"reassign_and_create_urgent_task", "urgent_reassignment", "reassign_urgent_task"},
    }
    return observed in accepted.get(expected, {expected})


def _sla_status(value: object) -> str | None:
    normalized = _enum(value)
    aliases = {
        "n_a": "not_applicable",
        "pending_within_sla": "within_sla",
        "open_within_sla": "within_sla",
        "on_time_contact": "contacted_on_time",
        "contacted_within_sla": "contacted_on_time",
        "late_contact": "contacted_late",
        "first_contact_overdue": "breached_4h",
        "overdue_4h": "breached_4h",
        "reassignment_overdue": "breached_48h",
        "overdue_48h": "breached_48h",
    }
    return aliases.get(normalized, normalized)


@pytest.fixture(scope="session")
def expected() -> dict[str, dict]:
    result = build_decisions(DATA_DIR)
    return {row["lead_id"]: row for row in result["decisions"]}


@pytest.fixture(scope="session")
def actual_rows() -> list[dict]:
    return _find_records(_read_submission())


@pytest.fixture(scope="session")
def actual(actual_rows: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in actual_rows:
        lead_id = _text(_field(row, "lead_id"))
        if lead_id and lead_id not in indexed:
            indexed[lead_id] = row
    return indexed


def _batch_ids(expected: dict[str, dict], batch_index: int) -> list[str]:
    ids = sorted(expected)
    return [lead_id for position, lead_id in enumerate(ids) if position % BATCHES == batch_index]


def _require_material_scope(actual: dict[str, dict], expected: dict[str, dict]) -> None:
    assert len(set(actual) & set(expected)) >= int(len(expected) * 0.8), (
        "fewer than 80% of source contacts are identifiable, so semantic outcomes cannot be meaningfully evaluated"
    )


@pytest.mark.parametrize("batch_index", range(BATCHES))
def test_artifact_and_contact_coverage(actual_rows: list[dict], expected: dict[str, dict], batch_index: int) -> None:
    expected_ids = set(_batch_ids(expected, batch_index))
    observed = [_text(_field(row, "lead_id")) for row in actual_rows]
    observed_ids = [lead_id for lead_id in observed if lead_id in expected_ids]
    assert len(observed_ids) == len(set(observed_ids)), f"batch {batch_index + 1} contains duplicate contact decisions"
    assert set(observed_ids) == expected_ids, f"batch {batch_index + 1} does not contain exactly one decision per source contact"


@pytest.mark.parametrize("batch_index", range(BATCHES))
def test_scoring_and_lifecycle_by_batch(actual: dict[str, dict], expected: dict[str, dict], batch_index: int) -> None:
    _require_material_scope(actual, expected)
    for lead_id in _batch_ids(expected, batch_index):
        if lead_id not in actual:
            continue
        row = actual[lead_id]
        truth = expected[lead_id]
        comparisons = {
            "resolved account": (_text(_field(row, "resolved_account_id")), truth["resolved_account_id"]),
            "account resolution": (_account_resolution(_field(row, "account_resolution")), _account_resolution(truth["account_resolution"])),
            "fit score": (_number(_field(row, "fit_score")), truth["fit_score"]),
            "engagement score": (_number(_field(row, "engagement_score")), truth["engagement_score"]),
            "negative score": (_number(_field(row, "negative_score")), truth["negative_score"]),
            "total score": (_number(_field(row, "total_score")), truth["total_score"]),
            "lifecycle stage": (_enum(_field(row, "lifecycle_stage")), _enum(truth["lifecycle_stage"])),
        }
        for label, (observed, wanted) in comparisons.items():
            assert observed == wanted, f"{lead_id} has incorrect {label}: {observed!r}, expected {wanted!r}"


@pytest.mark.parametrize("batch_index", range(BATCHES))
def test_routing_and_review_flags_by_batch(actual: dict[str, dict], expected: dict[str, dict], batch_index: int) -> None:
    _require_material_scope(actual, expected)
    for lead_id in _batch_ids(expected, batch_index):
        if lead_id not in actual:
            continue
        row = actual[lead_id]
        truth = expected[lead_id]
        observed_owner = _text(_field(row, "assigned_owner_id"))
        if observed_owner and observed_owner.lower() in {"none", "null", "unassigned", "n/a"}:
            observed_owner = None
        assert observed_owner == truth["assigned_owner_id"], (
            f"{lead_id} routes to {observed_owner!r}, expected {truth['assigned_owner_id']!r}; this changes owner workload or account continuity"
        )
        assert _route_matches(_field(row, "routing_reason"), _enum(truth["routing_reason"]) or ""), (
            f"{lead_id} has the wrong routing category for the selected owner"
        )
        assert _boolean(_field(row, "human_review_required")) == truth["human_review_required"], (
            f"{lead_id} has an incorrect human-review flag, which could hide an ambiguous or overloaded handoff"
        )


@pytest.mark.parametrize("batch_index", range(BATCHES))
def test_sla_and_actions_by_batch(actual: dict[str, dict], expected: dict[str, dict], batch_index: int) -> None:
    _require_material_scope(actual, expected)
    for lead_id in _batch_ids(expected, batch_index):
        if lead_id not in actual:
            continue
        row = actual[lead_id]
        truth = expected[lead_id]
        comparisons = {
            "handoff timestamp": (_timestamp(_field(row, "handoff_at")), truth["handoff_at"]),
            "first-contact due time": (_timestamp(_field(row, "first_contact_due_at")), truth["first_contact_due_at"]),
            "SLA status": (_sla_status(_field(row, "sla_status")), _sla_status(truth["sla_status"])),
        }
        for label, (observed, wanted) in comparisons.items():
            assert observed == wanted, f"{lead_id} has incorrect {label}: {observed!r}, expected {wanted!r}"
        assert _action_matches(_field(row, "next_action"), _enum(truth["next_action"]) or ""), (
            f"{lead_id} has a next action inconsistent with its SLA and routing state"
        )
