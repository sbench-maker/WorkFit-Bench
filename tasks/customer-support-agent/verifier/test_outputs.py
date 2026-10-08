from __future__ import annotations

import json
import os
import re
from pathlib import Path


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_FILE = Path(
    os.environ.get("TASK_OUTPUT_FILE", "/root/results/support_agent.json")
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _submission() -> dict:
    assert OUTPUT_FILE.is_file(), (
        f"missing {OUTPUT_FILE}; the PilotDesk configuration cannot be imported"
    )
    try:
        payload = _load_json(OUTPUT_FILE)
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"support_agent.json is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "support_agent.json must contain one JSON object"
    return payload


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _tool_ids(raw: object) -> set[str]:
    if not isinstance(raw, list):
        return set()
    found = set()
    for item in raw:
        if isinstance(item, str):
            found.add(item.strip())
        elif isinstance(item, dict):
            value = item.get("id") or item.get("tool_id") or item.get("name")
            if isinstance(value, str):
                found.add(value.strip())
    return found


def _rows(raw: object, identity: str) -> list[dict]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                rows.append({identity: key, **value})
        return rows
    return []


def _mapping(rows: list[dict], identity: str) -> tuple[dict[str, dict], list[str]]:
    mapped: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in rows:
        key = _norm(row.get(identity, ""))
        if not key:
            continue
        if key in mapped:
            duplicates.append(key)
        mapped[key] = row
    return mapped, duplicates


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if _norm(value) in {"true", "yes", "required", "1"}:
        return True
    if _norm(value) in {"false", "no", "not_required", "0"}:
        return False
    return None


def _assert_no_issues(issues: list[str], context: str) -> None:
    assert not issues, context + ":\n- " + "\n- ".join(issues)


def test_artifact_contract() -> None:
    output = _submission()
    contract = _load_json(DATA_DIR / "deployment_contract.json")
    issues: list[str] = []
    for field in contract["required_top_level_fields"]:
        if field not in output:
            issues.append(f"missing required top-level field {field!r}")
    for field, expected in contract["fixed_values"].items():
        if output.get(field) != expected:
            issues.append(f"{field!r} must be {expected!r}, got {output.get(field)!r}")
    for field in ("name", "description"):
        if not isinstance(output.get(field), str) or len(output[field].strip()) < 12:
            issues.append(f"{field!r} is not a substantive string")
    prompt = output.get("system_prompt")
    if not isinstance(prompt, str) or len(prompt.strip()) < 700:
        issues.append("system_prompt is missing or too thin to operate the support workflow")
    if not isinstance(output.get("attached_tools"), list):
        issues.append("attached_tools must be a JSON array for import")
    completion = output.get("completion_contract")
    if not isinstance(completion, dict):
        issues.append("completion_contract must be an object")
    else:
        allowed = completion.get("allowed_primary_outputs")
        actual_allowed = {_norm(item) for item in allowed} if isinstance(allowed, list) else set()
        expected_allowed = {
            _norm(item) for item in contract["completion_contract"]["allowed_primary_outputs"]
        }
        if actual_allowed != expected_allowed:
            issues.append("completion_contract does not expose the contract-defined primary outputs")
        note = completion.get("internal_note_template")
        if not isinstance(note, str) or len(note.strip()) < 20:
            issues.append("completion_contract lacks a usable internal note template")
    _assert_no_issues(issues, "deployment contract violations")


def test_tool_and_action_boundaries() -> None:
    output = _submission()
    catalog = _load_json(DATA_DIR / "tool_catalog.json")
    expected = {row["id"] for row in catalog["tools"]}
    actual = _tool_ids(output.get("attached_tools"))
    unavailable = {_norm(item) for item in catalog["unavailable_capabilities"]}
    boundaries = output.get("action_boundaries")
    issues: list[str] = []
    if actual != expected:
        issues.append(
            f"attached tool IDs differ from the catalog: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    if {_norm(item) for item in actual} & unavailable:
        issues.append("an explicitly unavailable capability was attached")
    if not isinstance(boundaries, dict):
        issues.append("action_boundaries must be an object")
        boundaries = {}
    expected_boundaries = {
        "customer_reply_mode": "draft_only",
        "draft_tool": "helpdesk.create_draft",
        "refund_completion_status": "succeeded",
        "refund_non_success_action": "escalate",
    }
    for field, expected_value in expected_boundaries.items():
        if _norm(boundaries.get(field, "")) != _norm(expected_value):
            issues.append(f"{field}={boundaries.get(field)!r}, expected {expected_value!r}")
    if boundaries.get("customer_send_tool") not in (None, "", False):
        issues.append("customer_send_tool must be null because the catalog has no send capability")
    non_success = boundaries.get("refund_non_success_statuses")
    actual_non_success = {_norm(item) for item in non_success} if isinstance(non_success, list) else set()
    if actual_non_success != {"pending", "failed"}:
        issues.append("refund_non_success_statuses must contain pending and failed")
    _assert_no_issues(issues, "unsafe or incomplete tool boundary")


def test_routing_and_escalation_policy() -> None:
    output = _submission()
    contract = _load_json(DATA_DIR / "deployment_contract.json")
    support = _load_json(DATA_DIR / "support_policy.json")
    routing_rows = _rows(output.get("routing_policy"), "category")
    routing, routing_dupes = _mapping(routing_rows, "category")
    escalation_rows = _rows(output.get("escalation_policy"), "trigger_id")
    escalations, escalation_dupes = _mapping(escalation_rows, "trigger_id")
    expected_actions = {
        "question": "answer_from_knowledge_base",
        "bug_report": "collect_missing_bug_details",
        "refund_request": "evaluate_refund_policy",
        "feature_request": "log_feature_request",
        "account_issue": "escalate",
        "abuse_spam": "escalate",
        "security_privacy": "escalate",
        "legal_escalation": "escalate",
    }
    expected_categories = {
        _norm(value) for value in contract["routing_policy"]["one_row_per_category"]
    }
    allowed_outcomes = {
        _norm(value) for value in contract["routing_policy"]["customer_outcome_values"]
    }
    expected_queues = {
        _norm(row["trigger_id"]): _norm(row["queue"])
        for row in support["escalation_triggers"]
    }
    issues: list[str] = []
    if routing_dupes:
        issues.append(f"duplicate routing categories: {sorted(routing_dupes)}")
    if set(routing) != expected_categories:
        issues.append(
            f"routing coverage differs: missing={sorted(expected_categories - set(routing))}, extra={sorted(set(routing) - expected_categories)}"
        )
    for category, expected_action in expected_actions.items():
        row = routing.get(category)
        if row is None:
            continue
        if _norm(row.get("internal_action", "")) != expected_action:
            issues.append(
                f"{category} uses {row.get('internal_action')!r}, expected {expected_action!r}"
            )
        if _norm(row.get("customer_outcome", "")) not in allowed_outcomes:
            issues.append(f"{category} has an unsupported customer outcome")
    if escalation_dupes:
        issues.append(f"duplicate escalation triggers: {sorted(escalation_dupes)}")
    if set(escalations) != set(expected_queues):
        issues.append(
            f"escalation coverage differs: missing={sorted(set(expected_queues) - set(escalations))}, extra={sorted(set(escalations) - set(expected_queues))}"
        )
    for trigger_id, expected_queue in expected_queues.items():
        row = escalations.get(trigger_id)
        if row is None:
            continue
        if _norm(row.get("queue", "")) != expected_queue:
            issues.append(
                f"{trigger_id} routes to {row.get('queue')!r}, expected {expected_queue!r}"
            )
        if not isinstance(row.get("reason"), str) or len(row["reason"].strip()) < 12:
            issues.append(f"{trigger_id} lacks a usable human escalation reason")
    _assert_no_issues(issues, "triage or escalation mapping errors")


def test_refund_policy_alignment() -> None:
    output = _submission()
    source = _load_json(DATA_DIR / "refund_policy.json")
    rules = source["automatic_refund"]["all_conditions_required"]
    actual = output.get("refund_policy")
    assert isinstance(actual, dict), "refund_policy must be an object"
    expected = {
        "lookup_tool": "billing.lookup_charge",
        "action_tool": "billing.issue_refund",
        "max_purchase_age_days": rules["purchase_age_days_lte"],
        "max_amount_usd": rules["amount_usd_lte"],
        "currency": rules["currency"],
        "allowed_reasons": set(rules["allowed_reasons"]),
        "required_charge_status": rules["charge_status"],
        "required_payment_method": rules["payment_method"],
        "require_identity_verified": rules["identity_verified"],
        "require_no_prior_refund": not rules["prior_refund"],
        "success_status": "succeeded",
        "non_success_route": "billing-review",
    }
    issues: list[str] = []
    for field in ("lookup_tool", "action_tool", "currency", "required_charge_status", "required_payment_method", "success_status"):
        if _norm(actual.get(field, "")) != _norm(expected[field]):
            issues.append(f"{field}={actual.get(field)!r}, expected {expected[field]!r}")
    route = _norm(actual.get("non_success_route", "")).replace("_", "")
    expected_route = _norm(expected["non_success_route"]).replace("_", "")
    for prefix in ("escalateto", "routeto", "sendto"):
        if route.startswith(prefix):
            route = route[len(prefix):]
            break
    if route != expected_route:
        issues.append(
            f"non_success_route={actual.get('non_success_route')!r}, expected a route to {expected['non_success_route']!r}"
        )
    for field in ("max_purchase_age_days", "max_amount_usd"):
        try:
            value = float(actual.get(field))
        except (TypeError, ValueError):
            value = None
        if value != float(expected[field]):
            issues.append(f"{field}={actual.get(field)!r}, expected {expected[field]!r}")
    reasons = actual.get("allowed_reasons")
    normalized_reasons = {_norm(item) for item in reasons} if isinstance(reasons, list) else set()
    if normalized_reasons != {_norm(item) for item in expected["allowed_reasons"]}:
        issues.append("allowed_reasons does not match the automatic-refund policy")
    for field in ("require_identity_verified", "require_no_prior_refund"):
        if _as_bool(actual.get(field)) is not expected[field]:
            issues.append(f"{field}={actual.get(field)!r}, expected {expected[field]!r}")
    _assert_no_issues(issues, "refund policy mismatch")
