from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import pytest


OUTPUT = Path("/root/results/output.json")
DATA = Path("/root/data")


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        cleaned = cleaned.strip("() ")
        try:
            number = float(cleaned)
        except ValueError:
            return None
        return -number if value.strip().startswith("(") else number
    return None


def _load() -> tuple[object | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"
    if not isinstance(payload, (dict, list)):
        return None, "output.json must contain a JSON object or array"
    return payload, None


def _walk(node: object):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


YEAR_KEYS = {"year", "budgetyear", "period", "projectyear"}
DIRECT_KEYS = {"totaldirectcosts", "directcosts", "directtotal", "totaldirect", "correcteddirectcosts"}
FA_KEYS = {
    "indirectcosts",
    "indirect",
    "fa",
    "fanda",
    "facosts",
    "fandacosts",
    "totalfandacosts",
    "facilitiesandadministrative",
    "facilitiesandadministration",
}
TOTAL_KEYS = {
    "total",
    "totalcost",
    "totalcosts",
    "grandtotal",
    "totalrequest",
    "totalrequested",
    "requestedtotal",
    "correctedtotal",
    "projectcost",
    "projecttotal",
    "projecttotals",
    "annualtotal",
}


def _field(row: dict, aliases: set[str]) -> object | None:
    for key, value in row.items():
        if _norm(key) in aliases:
            return value
    return None


def _year_token(value: object) -> int | str | None:
    token = _norm(value)
    if token in {"1", "y1", "year1", "budgetyear1"}:
        return 1
    if token in {"2", "y2", "year2", "budgetyear2"}:
        return 2
    if token in {"3", "y3", "year3", "budgetyear3"}:
        return 3
    if token in {"total", "all", "allyears", "project", "projecttotal", "projecttotals", "cumulative", "threeyeartotal", "grandtotal"}:
        return "project_total"
    return None


def _budget_rows(payload: object) -> dict[int | str, dict[str, float]]:
    candidates: list[dict] = []
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        candidates.append(node)
        for key, value in node.items():
            inherited = _year_token(key)
            if inherited is not None and isinstance(value, dict):
                expanded = dict(value)
                expanded.setdefault("year", inherited)
                candidates.append(expanded)
    rows: dict[int | str, dict[str, float]] = {}
    for row in candidates:
        year = _year_token(_field(row, YEAR_KEYS))
        direct = _number(_field(row, DIRECT_KEYS))
        indirect = _number(_field(row, FA_KEYS))
        total = _number(_field(row, TOTAL_KEYS))
        if year is not None and direct is not None and indirect is not None and total is not None:
            rows[year] = {"direct": direct, "indirect": indirect, "total": total}
    return rows


def _text_under_alias(payload: object, aliases: set[str]) -> str:
    found: list[str] = []

    def collect_text(node: object) -> list[str]:
        return [part.strip() for part in _walk(node) if isinstance(part, str) and part.strip()]

    for node in _walk(payload):
        if isinstance(node, dict):
            for key, value in node.items():
                nk = _norm(key)
                if nk in aliases or any(alias in nk for alias in aliases):
                    found.extend(collect_text(value))
    return max(found, key=len, default="") if found else ""


STATUS_GROUPS = {
    "blockers": "blocker", "submissionblockers": "blocker", "routingblockers": "blocker",
    "confirmlater": "confirm_later", "followup": "confirm_later", "nonblocking": "confirm_later",
    "resolved": "resolved", "corrections": "resolved", "corrected": "resolved",
}


def _compliance_records(payload: object) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    roots: list[object] = []
    for node in _walk(payload):
        if isinstance(node, dict):
            for key, value in node.items():
                nk = _norm(key)
                if any(term in nk for term in ("compliance", "routinglog", "reviewlog", "findings")):
                    roots.append(value)
    if not roots:
        return []

    def visit(node: object, inherited_status: str | None = None) -> None:
        if isinstance(node, dict):
            flat = " ".join(str(value) for value in node.values() if not isinstance(value, (dict, list)))
            normalized_keys = {_norm(key) for key in node}
            has_issue_shape = bool(normalized_keys & {
                "issue", "issueid", "finding", "description", "title", "action", "evidence", "rule"
            })
            own_status = next((str(value) for key, value in node.items()
                               if _norm(key) in {"status", "disposition", "severity", "category"}), None)
            if has_issue_shape and (own_status or inherited_status):
                records.append({"text": flat, "status": own_status or inherited_status or ""})
            for key, value in node.items():
                status = STATUS_GROUPS.get(_norm(key), inherited_status)
                if isinstance(value, (dict, list)):
                    visit(value, status)
                elif status and isinstance(value, str):
                    records.append({"text": value, "status": status})
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, str) and inherited_status:
                    records.append({"text": value, "status": inherited_status})
                else:
                    visit(value, inherited_status)

    for root in roots:
        visit(root)
    # Stable de-duplication prevents nested aliases from overweighting a record.
    unique = []
    seen = set()
    for record in records:
        key = (_norm(record["text"]), _norm(record["status"]))
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


def _status(record: dict[str, str]) -> str:
    token = _norm(record.get("status", ""))
    text = _norm(record.get("text", ""))
    joined = token + text
    if any(term in joined for term in ("confirmlater", "nonblocking", "followup", "doesnotdelay", "notablocker")):
        return "confirm_later"
    # Future-tense remediation is still a blocker. Check it before completed
    # words such as "removed", which also occur in "must be removed".
    if any(term in joined for term in ("mustberemoved", "mustfix", "routinghold", "requiredbeforerouting", "blocker")):
        return "blocker"
    if any(term in joined for term in ("resolved", "corrected", "removed", "reclassified", "fixed", "movedtoyear")):
        return "resolved"
    return token


ISSUE_MATCHERS = {
    "data_management_plan": lambda t: "datamanagementplan" in t,
    "postdoc_mentoring_plan": lambda t: "postdoc" in t and "mentor" in t,
    "subaward_letter": lambda t: ("cygnus" in t or "subaward" in t) and "letter" in t,
    "consultant_documents": lambda t: "consultant" in t and any(x in t for x in ("cv", "rate", "commitment", "document")),
    "voluntary_cost_share": lambda t: "costshar" in t or ("outreachcoordinator" in t and "nocharge" in t),
    "current_pending_refresh": lambda t: "currentandpending" in t or ("seniorpersonnel" in t and "reconfirm" in t),
}


def _matches(records: list[dict[str, str]], issue: str) -> list[dict[str, str]]:
    matcher = ISSUE_MATCHERS[issue]
    return [record for record in records if matcher(_norm(record["text"]))]


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _expected_budget() -> dict[int | str, dict[str, int]]:
    annual = {year: defaultdict(int) for year in (1, 2, 3)}
    for row in _read_csv("personnel_plan.csv"):
        year = int(row["budget_year"])
        requested = float(row["requested_calendar_months"])
        if row["role"] in {"Principal Investigator", "Co-Principal Investigator"}:
            requested = min(requested, 2.0 - float(row["other_nsf_calendar_months"]))
        escalated = float(row["year_1_base_salary"]) * 1.03 ** (year - 1)
        salary = round(escalated * requested / float(row["appointment_months"]))
        fringe = round(salary * float(row["fringe_rate"]))
        annual[year]["personnel"] += salary
        annual[year]["fringe"] += fringe
    for row in _read_csv("cost_items.csv"):
        amount = round(float(row["quantity"]) * float(row["unit_cost"]))
        year = int(row["budget_year"])
        category = row["draft_category"]
        description = row["description"].lower()
        if "alcohol" in description:
            continue
        if row["task_id"] == "D1":
            year = 3
        if "sensor array" in description and float(row["unit_cost"]) >= 5000:
            category = "equipment"
        annual[year][category] += amount
    expected: dict[int | str, dict[str, int]] = {}
    for year in (1, 2, 3):
        direct = sum(annual[year].values())
        mtdc = direct - annual[year]["equipment"] - annual[year]["participant_support"] - annual[year]["subaward"]
        if year == 1:
            mtdc += 25000
        indirect = round(mtdc * 0.54)
        expected[year] = {"direct": direct, "indirect": indirect, "total": direct + indirect}
    expected["project_total"] = {
        key: sum(expected[year][key] for year in (1, 2, 3))
        for key in ("direct", "indirect", "total")
    }
    return expected


def _skip_if_unreadable(payload: object | None, error: str | None) -> None:
    if error or payload is None:
        pytest.skip("artifact readability is scored once under artifact_usability")


@pytest.mark.parametrize("period", [1, 2, 3, "project_total"], ids=["year_1", "year_2", "year_3", "project_total"])
def test_financial_totals(period):
    payload, error = _load()
    _skip_if_unreadable(payload, error)
    rows = _budget_rows(payload)
    if not rows:
        pytest.skip("financial-section discoverability is scored once under artifact_usability")
    assert period in rows, f"missing corrected financial totals for {period}"
    expected = _expected_budget()[period]
    actual = rows[period]
    for field in ("direct", "indirect", "total"):
        assert math.isclose(actual[field], expected[field], abs_tol=1.0), (
            f"{period} {field} is {actual[field]:.2f}, expected {expected[field]:.2f}; "
            "the routed request would contain a material reconciliation error"
        )


@pytest.mark.parametrize(
    ("issue", "expected_status"),
    [
        ("data_management_plan", "blocker"),
        ("postdoc_mentoring_plan", "blocker"),
        ("subaward_letter", "blocker"),
        ("consultant_documents", "blocker"),
        ("voluntary_cost_share", "blocker"),
        ("current_pending_refresh", "confirm_later"),
    ],
)
def test_required_compliance_dispositions(issue, expected_status):
    payload, error = _load()
    _skip_if_unreadable(payload, error)
    records = _compliance_records(payload)
    if not records:
        pytest.skip("compliance-log presence is scored once under artifact_usability")
    matches = _matches(records, issue)
    assert matches, f"compliance log omits the material {issue.replace('_', ' ')} issue"
    assert any(_status(record) == expected_status for record in matches), (
        f"{issue.replace('_', ' ')} is not classified as {expected_status}; "
        "the routing team could hold the wrong item or miss a required correction"
    )


def test_no_material_false_blockers():
    payload, error = _load()
    _skip_if_unreadable(payload, error)
    records = _compliance_records(payload)
    if not records:
        pytest.skip("compliance-log presence is scored once under artifact_usability")
    false_blockers = []
    for record in records:
        text = _norm(record["text"])
        if _status(record) != "blocker":
            continue
        if "currentandpending" in text or "optional" in text or "safecomputingfacility" in text:
            false_blockers.append(record["text"])
        if any(term in text for term in ("alcohol", "sensorarray", "disseminationtiming", "pieffort")) and any(
            term in text for term in ("removed", "reclassified", "moved", "reduced", "corrected")
        ):
            false_blockers.append(record["text"])
    assert not false_blockers, (
        "resolved or expressly nonblocking items were labeled as submission blockers: "
        + " | ".join(false_blockers)
    )
