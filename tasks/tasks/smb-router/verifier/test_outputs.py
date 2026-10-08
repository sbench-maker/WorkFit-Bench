from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


DATA = Path("/root/data")
OUTPUT = Path("/root/results/routing_responses.json")

COMMANDS = {
    "/plan-payroll": ({"quickbooks"}, set(), {"paypal", "stripe", "square"}),
    "/month-heads-up": ({"quickbooks"}, set(), {"paypal"}),
    "/close-month": ({"quickbooks"}, set(), {"paypal", "stripe", "square"}),
    "/price-check": ({"quickbooks"}, set(), {"paypal"}),
    "/tax-prep": ({"quickbooks"}, set(), {"paypal", "stripe"}),
    "/call-list": ({"hubspot"}, set(), {"mail", "google calendar"}),
    "/run-campaign": ({"hubspot", "canva"}, set(), {"quickbooks", "paypal"}),
    "/sales-brief": (set(), {"quickbooks", "paypal"}, {"hubspot"}),
    "/customer-pulse-check": (set(), {"paypal", "hubspot"}, set()),
    "/handle-complaint": (set(), set(), {"gmail", "hubspot", "paypal"}),
    "/crm-cleanup": ({"hubspot"}, set(), set()),
    "/review-contract": (set(), set(), {"docusign"}),
    "/monday-brief": (set(), set(), {"quickbooks", "paypal", "hubspot", "google calendar", "gmail"}),
    "/friday-brief": (set(), {"paypal", "hubspot"}, set()),
    "/quarterly-review": ({"quickbooks"}, set(), {"paypal", "hubspot"}),
}

BASE_ROUTES = [
    "/plan-payroll", "/month-heads-up", "/close-month", "/price-check", "/tax-prep",
    "/call-list", "/run-campaign", "/sales-brief", "/customer-pulse-check", "/handle-complaint",
    "/crm-cleanup", "/review-contract", "/monday-brief", "/friday-brief", "/quarterly-review",
    "overview", None, "smb-onboard", "outside_scope", None,
]
FOCUS_ROUTES = [
    "/plan-payroll", "/run-campaign", "/customer-pulse-check", "/price-check", "/crm-cleanup", "/review-contract"
]
TIEBREAK_ROUTES = ["/plan-payroll", "/handle-complaint", "clarify", "/close-month"]

ROUTE_ALIASES = {
    "onboard": "smb-onboard",
    "onboarding": "smb-onboard",
    "smb-onboarding": "smb-onboard",
    "smb-onboard": "smb-onboard",
    "general-overview": "overview",
    "capability-overview": "overview",
    "menu": "overview",
    "overview": "overview",
    "outside": "outside_scope",
    "out-of-scope": "outside_scope",
    "outside-scope": "outside_scope",
    "unsupported": "outside_scope",
    "clarification": "clarify",
    "ask-clarifying-question": "clarify",
    "clarify": "clarify",
}

CONNECTOR_PATTERNS = {
    "quickbooks": [r"quick\s*books", r"accounting (?:tool|system|connection)"],
    "paypal": [r"pay\s*pal"],
    "stripe": [r"stripe"],
    "square": [r"square"],
    "hubspot": [r"hub\s*spot", r"\bcrm\b"],
    "canva": [r"canva", r"design (?:tool|connection)"],
    "mail": [r"\bmail\b"],
    "google calendar": [r"google\s+calendar", r"\bcalendar\b"],
    "gmail": [r"gmail"],
    "docusign": [r"docu\s*sign", r"e-?signature"],
}

ID_KEYS = {"case_id", "caseid", "request_id", "requestid", "id"}
ROUTE_KEYS = {"route", "command", "recommended_command", "recommendedcommand", "next_step", "nextstep", "action"}
REPLY_KEYS = {"owner_reply", "ownerreply", "reply", "response", "message", "response_text", "responsetext"}
STATUS_KEYS = {"state", "status", "availability", "routing_status", "routingstatus"}
MISSING_KEYS = {"missing_connectors", "missingconnectors", "missing", "blocked_by", "blockedby", "required_connectors"}
OPTIONAL_KEYS = {
    "unavailable_optional_connectors", "unavailableoptionalconnectors", "optional_missing", "optionalmissing",
    "omitted_connectors", "omittedconnectors", "skipped_inputs", "skippedinputs",
}


@dataclass
class Normalized:
    case_id: str | None
    route: str | None
    reply: str
    status: str | None
    record: dict[str, Any]
    missing_explicit: set[str]
    optional_explicit: set[str]


@dataclass
class Submission:
    rows: list[Normalized]
    by_id: dict[str, Normalized]
    duplicate_ids: set[str]
    error: str | None


def norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def direct_value(record: dict[str, Any], aliases: set[str]) -> Any:
    for key, value in record.items():
        if norm_key(key).replace("_", "") in {item.replace("_", "") for item in aliases}:
            return value
    for container_name in ("recommendation", "decision", "routing", "next_step", "result"):
        for key, value in record.items():
            if norm_key(key) == container_name and isinstance(value, dict):
                found = direct_value(value, aliases)
                if found is not None:
                    return found
    return None


def all_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(all_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(all_text(item) for item in value)
    return ""


def connector_mentions(value: Any) -> set[str]:
    text = all_text(value).lower()
    found = set()
    for connector, patterns in CONNECTOR_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            found.add(connector)
    return found


def normalize_route(value: Any, fallback_text: str = "") -> str | None:
    candidates = []
    if isinstance(value, str):
        candidates.append(value)
    candidates.append(fallback_text)
    commands = sorted(COMMANDS, key=len, reverse=True)
    for raw in candidates:
        text = raw.strip().lower().replace("_", "-").replace("–", "-")
        text = re.sub(r"[`'\"]", "", text)
        compact = re.sub(r"\s+", "-", text).strip(" /.-")
        if compact in ROUTE_ALIASES:
            return ROUTE_ALIASES[compact]
        if re.search(r"out(?:side| of)[ -]?scope|not (?:something|a task) i can help|unsupported", text):
            return "outside_scope"
        if re.search(r"need(?:s)? clarif|ask .*clarif|two ways|which (?:one|direction)", text):
            return "clarify"
        if re.search(r"smb-?onboard|\bonboarding\b|setup .{0,35}business tools|connect .{0,35}business tools|start (?:the )?(?:short )?setup", text):
            return "smb-onboard"
        if all(word in text for word in ("money", "customers", "contracts")) and "week" in text:
            return "overview"
        if compact in {command.lstrip("/") for command in commands}:
            return "/" + compact
        for command in commands:
            token = command.lstrip("/")
            pattern = rf"(?<![a-z])/?{re.escape(token)}(?![a-z])"
            if re.search(pattern, text):
                return command
    return None


def normalize_status(value: Any, route: str | None, record: dict[str, Any], reply: str) -> str | None:
    if route in {"smb-onboard", "overview", "outside_scope", "clarify"}:
        return {
            "smb-onboard": "onboarding", "overview": "overview", "outside_scope": "outside_scope", "clarify": "clarify"
        }[route]
    blocked_flag = direct_value(record, {"blocked"})
    if blocked_flag is True:
        return "blocked"
    if blocked_flag is False:
        return "ready"
    ready_flag = direct_value(record, {"ready", "can_run", "canrun"})
    if ready_flag is True:
        return "ready"
    if ready_flag is False:
        return "blocked"
    if isinstance(value, str):
        token = norm_key(value)
        if token in {"blocked", "needs_setup", "missing_connector", "unavailable", "cannot_run", "not_ready"}:
            return "blocked"
        if token in {"ready", "available", "runnable", "can_run", "confirmed_pending"}:
            return "ready"
    text = reply.lower()
    if re.search(r"\bblocked\b|cannot run|can't run|needs? .{0,45}connect|until .{0,45}connect|required .{0,45}connect", text):
        return "blocked"
    if route in COMMANDS:
        return "ready"
    return None


def explicit_connector_set(record: dict[str, Any], aliases: set[str]) -> set[str]:
    value = direct_value(record, aliases)
    if value is None:
        return set()
    return connector_mentions(value)


def normalize_record(record: dict[str, Any]) -> Normalized:
    raw_id = direct_value(record, ID_KEYS)
    case_id = str(raw_id).strip().upper().replace("_", "-") if raw_id is not None else None
    route_value = direct_value(record, ROUTE_KEYS)
    reply_value = direct_value(record, REPLY_KEYS)
    reply = all_text(reply_value).strip() if reply_value is not None else ""
    record_text = all_text(record)
    route = normalize_route(route_value, reply or record_text)
    status_value = direct_value(record, STATUS_KEYS)
    status = normalize_status(status_value, route, record, reply or record_text)
    return Normalized(
        case_id=case_id,
        route=route,
        reply=reply,
        status=status,
        record=record,
        missing_explicit=explicit_connector_set(record, MISSING_KEYS),
        optional_explicit=explicit_connector_set(record, OPTIONAL_KEYS),
    )


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key, value in payload.items():
        if norm_key(key) in {"responses", "routes", "results", "items", "records", "cases", "decisions"} and isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if payload and all(re.fullmatch(r"CASE[-_]\d+", str(key), re.I) for key in payload):
        rows = []
        for key, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("case_id", key)
            else:
                row = {"case_id": key, "owner_reply": str(value)}
            rows.append(row)
        return rows
    return []


@pytest.fixture(scope="session")
def source() -> dict[str, Any]:
    requests = [json.loads(line) for line in (DATA / "pending_requests.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    profiles = {row["business_id"]: row for row in json.loads((DATA / "business_profiles.json").read_text(encoding="utf-8"))}
    connectors = {
        row["business_id"]: {name.lower() for name in row["connected"]}
        for row in json.loads((DATA / "connector_snapshot.json").read_text(encoding="utf-8"))
    }
    return {"requests": requests, "profiles": profiles, "connectors": connectors}


@pytest.fixture(scope="session")
def submission() -> Submission:
    if not OUTPUT.is_file():
        return Submission([], {}, set(), f"missing requested artifact: {OUTPUT}")
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Submission([], {}, set(), f"requested artifact is not readable JSON: {exc}")
    raw_records = extract_records(payload)
    if not raw_records:
        return Submission([], {}, set(), "JSON does not expose a response record collection")
    rows = [normalize_record(row) for row in raw_records]
    by_id: dict[str, Normalized] = {}
    duplicates = set()
    for row in rows:
        if row.case_id is None:
            continue
        if row.case_id in by_id:
            duplicates.add(row.case_id)
        else:
            by_id[row.case_id] = row
    return Submission(rows, by_id, duplicates, None)


def base_route_for(case_id: str) -> tuple[str, str]:
    number = int(case_id.split("-")[-1])
    blueprint = (number - 1) // 12
    repetition = (number - 1) % 12
    if blueprint == 16:
        return FOCUS_ROUTES[repetition % len(FOCUS_ROUTES)], "focus"
    if blueprint == 19:
        return TIEBREAK_ROUTES[repetition % len(TIEBREAK_ROUTES)], "tiebreaker"
    kinds = ["command"] * 15 + ["overview", "focus", "onboarding", "outside", "tiebreaker"]
    return BASE_ROUTES[blueprint], kinds[blueprint]


def missing_required(route: str, connected: set[str]) -> set[str]:
    mandatory, alternatives, _ = COMMANDS[route]
    missing = mandatory - connected
    if alternatives and not alternatives.intersection(connected):
        missing |= alternatives
    return missing


def expected_for(request: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    base_route, kind = base_route_for(request["case_id"])
    connected = source["connectors"][request["business_id"]]
    if kind == "onboarding" or (not connected and (base_route in COMMANDS or base_route == "overview")):
        required = missing_required(base_route, connected) if base_route in COMMANDS else set()
        return {"route": "smb-onboard", "state": "onboarding", "missing": required, "optional": set()}
    if base_route in {"overview", "outside_scope", "clarify"}:
        return {"route": base_route, "state": base_route, "missing": set(), "optional": set()}
    missing = missing_required(base_route, connected)
    optional = set()
    state = "blocked" if missing else "ready"
    if not missing:
        optional = COMMANDS[base_route][2] - connected
    return {"route": base_route, "state": state, "missing": missing, "optional": optional}


def connector_disclosed(row: Normalized, connector: str, *, optional: bool) -> bool:
    explicit = row.optional_explicit if optional else row.missing_explicit
    if connector in explicit:
        return True
    text = all_text(row.record).lower()
    patterns = CONNECTOR_PATTERNS[connector]
    named = any(re.search(pattern, text) for pattern in patterns)
    if not named:
        return False
    if optional:
        return bool(re.search(r"not connected|without|unavailable|left out|omit|skip|partial|limited|missing|exclude|won't be included|will not be included", text))
    return True


def test_artifact_coverage_and_usability(submission: Submission, source: dict[str, Any]) -> None:
    assert submission.error is None, submission.error
    expected_ids = {row["case_id"] for row in source["requests"]}
    actual_ids = {row.case_id for row in submission.rows if row.case_id is not None}
    assert not submission.duplicate_ids, f"duplicate case IDs make the response set unsafe to merge: {sorted(submission.duplicate_ids)[:8]}"
    assert actual_ids == expected_ids, (
        f"response scope differs from pending queue; missing={sorted(expected_ids - actual_ids)[:8]}, "
        f"unexpected={sorted(actual_ids - expected_ids)[:8]}"
    )
    unusable = [row.case_id for row in submission.rows if row.case_id in expected_ids and (row.route is None or not row.reply)]
    assert not unusable, f"cases lack an extractable next step or owner-facing reply: {unusable[:8]}"


@pytest.mark.parametrize("cohort", range(12), ids=lambda value: f"cohort-{value + 1:02d}")
def test_route_selection(cohort: int, submission: Submission, source: dict[str, Any]) -> None:
    if submission.error is not None:
        pytest.skip("artifact normalization failed; reported once by artifact_coverage")
    requests = [row for index, row in enumerate(source["requests"]) if index % 12 == cohort]
    present = [row for row in requests if row["case_id"] in submission.by_id]
    if not present:
        pytest.skip("scope omission is scored only by artifact_coverage")
    mismatches = []
    for request in present:
        expected = expected_for(request, source)["route"]
        actual = submission.by_id[request["case_id"]].route
        if actual != expected:
            mismatches.append((request["case_id"], expected, actual))
    assert not mismatches, f"wrong single best next step in this cohort: {mismatches[:8]}"


@pytest.mark.parametrize("cohort", range(12), ids=lambda value: f"cohort-{value + 1:02d}")
def test_connector_readiness_and_disclosure(cohort: int, submission: Submission, source: dict[str, Any]) -> None:
    if submission.error is not None:
        pytest.skip("artifact normalization failed; reported once by artifact_coverage")
    requests = [row for index, row in enumerate(source["requests"]) if index % 12 == cohort]
    present = [row for row in requests if row["case_id"] in submission.by_id]
    if not present:
        pytest.skip("scope omission is scored only by artifact_coverage")
    defects = []
    for request in present:
        expected = expected_for(request, source)
        row = submission.by_id[request["case_id"]]
        if expected["state"] not in {"ready", "blocked", "onboarding"}:
            continue
        if row.status != expected["state"]:
            defects.append((request["case_id"], f"state {expected['state']}", row.status))
            continue
        for connector in sorted(expected["missing"]):
            if not connector_disclosed(row, connector, optional=False):
                defects.append((request["case_id"], f"missing prerequisite {connector} not disclosed", None))
        for connector in sorted(expected["optional"]):
            if not connector_disclosed(row, connector, optional=True):
                defects.append((request["case_id"], f"omitted optional input {connector} not disclosed", None))
        if expected["state"] == "onboarding":
            text = all_text(row.record).lower()
            if not re.search(r"onboard|set(?:up| up)|connect", text):
                defects.append((request["case_id"], "onboarding next step not explained", None))
    assert not defects, f"connector readiness or limitation defects in this cohort: {defects[:8]}"
