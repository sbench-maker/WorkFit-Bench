from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from reference_solution import solve  # noqa: E402


SECTION_ALIASES = {
    "portfolio": {"portfoliosummary", "portfolio", "rollups", "portfoliorollups", "portfoliometrics"},
    "intervention": {"interventionqueue", "interventions", "riskqueue", "retentionactions", "prioritizedinterventions", "savequeue"},
    "expansion": {"expansionqueue", "growthcandidates", "expansionrecommendations", "salesmotions", "growthqueue"},
    "review": {"humanreview", "dataqualityreview", "exceptions", "quarantine", "reviewqueue", "invalidrecords"},
}

ID_ALIASES = {"customerid", "accountid", "id", "customer", "account"}
RANK_ALIASES = {"rank", "priorityrank", "order", "position"}
REVENUE_ALIASES = {"totalestimatedrevenue", "estimatedrevenue", "expansionvalue", "potentialarr", "estimatedarr"}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def load_output() -> object:
    assert OUTPUT_PATH.is_file(), "output.json is missing, so the portfolio triage cannot be used"
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    assert isinstance(value, (dict, list)), "output.json must contain a JSON object or list"
    return value


def load_output_optional() -> object | None:
    if not OUTPUT_PATH.is_file():
        return None
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def load_inputs() -> tuple[dict, dict]:
    portfolio = json.loads((DATA_DIR / "customer_portfolio.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA_DIR / "scoring_policy.json").read_text(encoding="utf-8"))
    return portfolio, policy


def expected_output() -> dict:
    portfolio, policy = load_inputs()
    return solve(portfolio, policy)


def find_section(doc: object, section: str) -> object | None:
    aliases = SECTION_ALIASES[section]
    for node in walk(doc):
        if isinstance(node, dict):
            for key, value in node.items():
                if norm(key) in aliases:
                    return value
    return None


def section_records(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        records: list[dict] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                if not any(norm(field) in ID_ALIASES for field in row):
                    row["customer_id"] = key
                records.append(row)
        return records
    return []


def direct_value(record: dict, aliases: set[str]) -> object | None:
    for key, value in record.items():
        if norm(key) in aliases:
            return value
    return None


def record_id(record: dict) -> str | None:
    value = direct_value(record, ID_ALIASES)
    if value is None:
        for node in walk(record):
            if isinstance(node, dict):
                value = direct_value(node, ID_ALIASES)
                if value is not None:
                    break
    if not isinstance(value, (str, int)):
        return None
    match = re.search(r"(?:CUST[-_ ]?)?0*(\d{1,4})$", str(value).strip(), re.I)
    return f"CUST-{int(match.group(1)):04d}" if match else str(value).strip().upper()


def parse_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
        if match:
            return float(match.group(0).replace(",", ""))
    return None


def recursive_number(node: object, aliases: set[str]) -> float | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if norm(key) in aliases:
                number = parse_number(value)
                if number is not None:
                    return number
        for value in node.values():
            number = recursive_number(value, aliases)
            if number is not None:
                return number
    elif isinstance(node, list):
        for value in node:
            number = recursive_number(value, aliases)
            if number is not None:
                return number
    return None


def nested_section(node: object, aliases: set[str]) -> object | None:
    if not isinstance(node, dict):
        return None
    for key, value in node.items():
        if norm(key) in aliases:
            return value
    return None


def summary_number(summary: object, group: str | None, aliases: set[str]) -> float | None:
    search_node = summary
    if group:
        group_aliases = {
            "health": {"health", "customerhealth", "healthrollup"},
            "churn": {"churn", "retention", "risk", "churnrisk"},
            "expansion": {"expansion", "growth", "expansionopportunities"},
        }[group]
        selected = nested_section(summary, group_aliases)
        if selected is not None:
            search_node = selected
        aliases = aliases | {norm(group + alias) for alias in aliases}
    return recursive_number(search_node, aliases)


def queue_map(doc: object, section: str) -> tuple[list[str], dict[str, dict]]:
    rows = section_records(find_section(doc, section))
    order: list[tuple[float, int, str]] = []
    mapped: dict[str, dict] = {}
    for position, row in enumerate(rows, 1):
        customer_id = record_id(row)
        if customer_id is None or customer_id in mapped:
            continue
        mapped[customer_id] = row
        rank = parse_number(direct_value(row, RANK_ALIASES))
        order.append((rank if rank is not None else float(position), position, customer_id))
    order.sort()
    return [item[2] for item in order], mapped


def text_blob(value: object) -> str:
    return norm(json.dumps(value, ensure_ascii=False, default=str))


def test_portfolio_scoring_rollups():
    """Criterion: scoring_rollups."""
    doc = load_output_optional()
    if doc is None:
        return
    summary = find_section(doc, "portfolio")
    assert summary is not None, "portfolio rollups are unavailable"
    expected = expected_output()["portfolio_summary"]
    checks = [
        (None, {"inputcustomers", "totalcustomers", "sourcecustomers", "accountsreceived"}, expected["input_customers"], 0),
        (None, {"scoredcustomers", "analyzedcustomers", "validcustomers", "accountsreviewed"}, expected["scored_customers"], 0),
        (None, {"reviewrequired", "excludedcustomers", "quarantinecount", "dataqualityreviewcount"}, expected["review_required"], 0),
        ("health", {"averagescore", "averagehealthscore", "meanhealthscore"}, expected["health"]["average_score"], .11),
        ("health", {"greencount", "healthycount", "green"}, expected["health"]["green_count"], 0),
        ("health", {"yellowcount", "attentioncount", "yellow"}, expected["health"]["yellow_count"], 0),
        ("health", {"redcount", "atriskcount", "red"}, expected["health"]["red_count"], 0),
        ("churn", {"criticalcount", "critical"}, expected["churn"]["critical_count"], 0),
        ("churn", {"highcount", "high"}, expected["churn"]["high_count"], 0),
        ("churn", {"mediumcount", "medium"}, expected["churn"]["medium_count"], 0),
        ("churn", {"lowcount", "low"}, expected["churn"]["low_count"], 0),
        ("churn", {"arratrisk", "revenueatrisk", "highriskarr"}, expected["churn"]["arr_at_risk"], .5),
        ("expansion", {"modeledopportunities", "totalopportunities", "opportunitycount"}, expected["expansion"]["modeled_opportunities"], 0),
        ("expansion", {"modeledestimatedrevenue", "totalmodeledrevenue", "modeledpotentialarr"}, expected["expansion"]["modeled_estimated_revenue"], .5),
        ("expansion", {"eligiblecustomers", "qualifiedcustomers", "growthcandidates"}, expected["expansion"]["eligible_customers"], 0),
        ("expansion", {"eligibleestimatedrevenue", "qualifiedrevenue", "eligiblepotentialarr"}, expected["expansion"]["eligible_estimated_revenue"], .5),
    ]
    problems = []
    for group, aliases, expected_value, tolerance in checks:
        actual = summary_number(summary, group, aliases)
        if actual is None or not math.isclose(actual, float(expected_value), abs_tol=tolerance):
            problems.append(f"{group or 'portfolio'}.{sorted(aliases)[0]}={actual!r}, expected {expected_value}")
    assert not problems, "portfolio health/churn/expansion rollups are misleading: " + "; ".join(problems)


def test_action_queues_and_priorities():
    """Criterion: queue_decisions."""
    doc = load_output_optional()
    if doc is None:
        return
    expected = expected_output()
    expected_intervention = [row["customer_id"] for row in expected["intervention_queue"]]
    expected_expansion = [row["customer_id"] for row in expected["expansion_queue"]]
    actual_intervention, intervention_map = queue_map(doc, "intervention")
    actual_expansion, expansion_map = queue_map(doc, "expansion")
    assert set(actual_intervention) == set(expected_intervention), (
        f"intervention eligibility is wrong; missing {sorted(set(expected_intervention)-set(actual_intervention))[:8]}, "
        f"unexpected {sorted(set(actual_intervention)-set(expected_intervention))[:8]}"
    )
    assert actual_intervention == expected_intervention, "intervention priorities do not follow effective severity, renewal, trend, ARR, and ID tie-breaks"
    assert set(actual_expansion) == set(expected_expansion), (
        f"expansion guardrails are wrong; missing {sorted(set(expected_expansion)-set(actual_expansion))[:8]}, "
        f"unexpected {sorted(set(actual_expansion)-set(expected_expansion))[:8]}"
    )
    assert actual_expansion == expected_expansion, "expansion candidates are not ranked by modeled revenue and the declared tie-break"
    assert not set(actual_intervention) & set(actual_expansion), "an account appears in both save and sales queues"

    expected_revenue = {row["customer_id"]: row["total_estimated_revenue"] for row in expected["expansion_queue"]}
    revenue_problems = []
    for customer_id, expected_value in expected_revenue.items():
        actual = recursive_number(expansion_map[customer_id], REVENUE_ALIASES)
        if actual is None or not math.isclose(actual, expected_value, abs_tol=.5):
            revenue_problems.append(f"{customer_id}={actual!r}, expected {expected_value}")
    assert not revenue_problems, "candidate expansion values are incorrect: " + "; ".join(revenue_problems[:12])


def test_data_quality_quarantine():
    """Criterion: data_quality_quarantine."""
    doc = load_output_optional()
    if doc is None:
        return
    _, review_map = queue_map(doc, "review")
    expected_ids = {"CUST-0235", "CUST-0236", "CUST-0237", "CUST-0238", "CUST-0239", "CUST-0240"}
    assert set(review_map) == expected_ids, f"human review must contain exactly the six invalid CRM records; found {sorted(review_map)}"
    intervention_ids = set(queue_map(doc, "intervention")[1])
    expansion_ids = set(queue_map(doc, "expansion")[1])
    assert not expected_ids & (intervention_ids | expansion_ids), "quarantined records leaked into an action queue"
    issue_tokens = {
        "CUST-0235": ({"contract", "renewal", "date"}, {"missing", "invalid", "null", "required"}),
        "CUST-0236": ({"active", "seat", "license"}, {"exceed", "range", "capacity", "more"}),
        "CUST-0237": ({"segment"}, {"unsupported", "unknown", "invalid", "strategic"}),
        "CUST-0238": ({"module", "security", "adopted"}, {"usage", "contradict", "inconsistent"}),
        "CUST-0239": ({"previous", "prior", "overall"}, {"missing", "incomplete", "required"}),
        "CUST-0240": ({"arr", "revenue"}, {"negative", "nonpositive", "invalid", "zero"}),
    }
    problems = []
    for customer_id, (subject, defect) in issue_tokens.items():
        blob = text_blob(review_map[customer_id])
        if not any(token in blob for token in subject) or not any(token in blob for token in defect):
            problems.append(customer_id)
    assert not problems, f"human-review reasons do not identify the actual CRM defect for {problems}"
