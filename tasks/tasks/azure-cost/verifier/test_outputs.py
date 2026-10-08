from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data")).resolve()
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/output.json")).resolve()

SUBSCRIPTIONS = {
    "00000000-0000-4000-8000-000000000101": "Atlas Commerce",
    "00000000-0000-4000-8000-000000000202": "Borealis Analytics",
    "00000000-0000-4000-8000-000000000303": "Cascade Core",
    "00000000-0000-4000-8000-000000000404": "Delta Labs",
    "00000000-0000-4000-8000-000000000505": "Ember Sandbox",
}


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _lookup(mapping: dict, aliases: tuple[str, ...], default=None):
    normalized = {_norm(key): value for key, value in mapping.items()}
    for alias in aliases:
        if _norm(alias) in normalized:
            return normalized[_norm(alias)]
    return default


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _load_output() -> dict:
    if not OUTPUT.is_file():
        return {}
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _find_section(root: dict, aliases: tuple[str, ...]):
    value = _lookup(root, aliases)
    if value is not None:
        return value
    targets = {_norm(alias) for alias in aliases}
    for node in _walk(root):
        if not isinstance(node, dict):
            continue
        for key, candidate in node.items():
            normalized = _norm(key)
            if normalized in targets or any(target in normalized for target in targets):
                return candidate
    return None


def _response_records(payload: dict) -> list[dict]:
    properties = payload.get("properties", {})
    columns = [column["name"] for column in properties.get("columns", [])]
    return [dict(zip(columns, row)) for row in properties.get("rows", [])]


def _expected_historical() -> tuple[float, dict[str, float]]:
    manifest = json.loads((DATA / "export_manifest.json").read_text(encoding="utf-8"))
    target = manifest["latest_complete_month"].replace("-", "") + "01"
    services: defaultdict[str, float] = defaultdict(float)
    for filename in manifest["historical_query_pages"]:
        payload = json.loads((DATA / filename).read_text(encoding="utf-8"))
        for row in _response_records(payload):
            if str(row["UsageDate"]) == target:
                services[str(row["ServiceName"])] += float(row["Cost"])
    return sum(services.values()), dict(services)


def _historical_section(root: dict) -> dict:
    section = _find_section(
        root,
        ("latest_complete_month", "historical", "historical_costs", "actual_cost_summary", "cost_breakdown"),
    )
    return section if isinstance(section, dict) else {}


def _service_values(section: dict) -> dict[str, float]:
    raw = _find_section(section, ("service_breakdown", "by_service", "services", "service_costs"))
    result: dict[str, float] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            amount = _number(value)
            if amount is None and isinstance(value, dict):
                amount = _number(_lookup(value, ("cost_usd", "total_cost_usd", "cost", "amount", "value")))
            if amount is not None:
                result[str(key)] = amount
    elif isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = _lookup(row, ("service_name", "service", "name"))
            amount = _number(_lookup(row, ("cost_usd", "total_cost_usd", "actual_cost_usd", "cost", "amount", "value")))
            if name is not None and amount is not None:
                result[str(name)] = result.get(str(name), 0.0) + amount
    return result


def _outlook_entities(root: dict) -> list[dict]:
    raw = _find_section(
        root,
        ("subscription_outlook", "subscription_forecasts", "forecasts", "outlook", "monthly_outlook"),
    )
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        inner = _lookup(raw, ("subscriptions", "records", "items"))
        if isinstance(inner, list):
            return [item for item in inner if isinstance(item, dict)]
        entities = []
        for key, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("subscription_name", key)
                entities.append(item)
        return entities
    return []


def _subscription_id(entity: dict) -> str | None:
    raw_id = _lookup(entity, ("subscription_id", "subscriptionid", "id"))
    if raw_id in SUBSCRIPTIONS:
        return str(raw_id)
    raw_name = _lookup(entity, ("subscription_name", "subscription", "name"))
    for subscription_id, name in SUBSCRIPTIONS.items():
        if _norm(raw_name) == _norm(name):
            return subscription_id
    return None


def _month_rows(entity: dict) -> list[dict]:
    raw = _lookup(entity, ("months", "monthly", "monthly_breakdown", "monthly_outlook", "periods", "records", "forecast"))
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("month", key)
                rows.append(item)
        return rows
    return []


def _normalize_months(entity: dict) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, dict[str, float | None]] = {}
    for row in _month_rows(entity):
        month = _lookup(row, ("month", "billing_month", "period", "date"))
        if month is None:
            continue
        month = str(month)[:7]
        target = grouped.setdefault(
            month,
            {"actual": None, "forecast": None, "projected": None, "budget": None},
        )
        explicit_actual = _number(_lookup(row, ("actual_cost_usd", "actual_cost", "actual")))
        explicit_forecast = _number(_lookup(row, ("forecast_cost_usd", "forecast_cost", "forecast")))
        explicit_projected = _number(
            _lookup(row, ("projected_total_usd", "projected_total", "outlook_cost_usd", "estimated_total_usd", "total"))
        )
        explicit_budget = _number(_lookup(row, ("budget_usd", "monthly_budget_usd", "budget")))
        if explicit_actual is not None:
            target["actual"] = explicit_actual
        if explicit_forecast is not None:
            target["forecast"] = explicit_forecast
        if explicit_projected is not None:
            target["projected"] = explicit_projected
        if explicit_budget is not None:
            target["budget"] = explicit_budget

        status = _lookup(row, ("cost_status", "status", "type"))
        generic_cost = _number(_lookup(row, ("cost_usd", "cost", "amount", "value")))
        if status is not None and generic_cost is not None:
            if _norm(status) == "actual":
                target["actual"] = (target["actual"] or 0.0) + generic_cost
            elif _norm(status) == "forecast":
                target["forecast"] = (target["forecast"] or 0.0) + generic_cost

        components = _lookup(row, ("components", "cost_components"))
        if isinstance(components, list):
            for component in components:
                if not isinstance(component, dict):
                    continue
                component_status = _lookup(component, ("cost_status", "status", "type"))
                amount = _number(_lookup(component, ("cost_usd", "cost", "amount", "value")))
                if component_status is not None and amount is not None:
                    if _norm(component_status) == "actual":
                        target["actual"] = (target["actual"] or 0.0) + amount
                    elif _norm(component_status) == "forecast":
                        target["forecast"] = (target["forecast"] or 0.0) + amount
    return grouped


def _expected_forecasts() -> tuple[dict, dict]:
    manifest = json.loads((DATA / "export_manifest.json").read_text(encoding="utf-8"))
    budgets = {}
    with (DATA / manifest["budget_file"]).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            budgets[(row["subscription_id"], row["month"])] = float(row["budget_usd"])
    expected = {}
    unavailable = {}
    for filename in manifest["forecast_responses"]:
        payload = json.loads((DATA / filename).read_text(encoding="utf-8"))
        subscription_id = payload["scope"].split("/subscriptions/", 1)[1].split("/", 1)[0]
        records = _response_records(payload)
        if not records:
            unavailable[subscription_id] = payload.get("message", "")
            continue
        grouped = defaultdict(lambda: {"actual": 0.0, "forecast": 0.0})
        for row in records:
            grouped[str(row["BillingMonth"])][_norm(row["CostStatus"])] += float(row["Cost"])
        expected[subscription_id] = {
            month: {
                "actual": values["actual"],
                "forecast": values["forecast"],
                "projected": values["actual"] + values["forecast"],
                "budget": budgets[(subscription_id, month)],
            }
            for month, values in grouped.items()
        }
    return expected, unavailable


def test_historical_cost_breakdown():
    """July portfolio and service totals reconcile across both query pages."""
    output = _load_output()
    section = _historical_section(output)
    assert section, "cannot locate the historical cost section"
    month = _lookup(section, ("month", "billing_month", "period"))
    assert month is not None and str(month)[:7] == "2026-07", "latest complete month must be July 2026"
    total = _number(
        _lookup(section, ("portfolio_total_cost_usd", "portfolio_total_usd", "total_cost_usd", "portfolio_total", "total"))
    )
    expected_total, expected_services = _expected_historical()
    assert total is not None and abs(total - expected_total) <= 0.02, (
        f"July portfolio total is {total}, expected {expected_total:.2f}; omitting a query page would understate spend"
    )
    actual_services = _service_values(section)
    assert {_norm(name) for name in actual_services} == {_norm(name) for name in expected_services}, (
        "the July service breakdown must cover every service present in the Cost Query export"
    )
    normalized_actual = {_norm(name): value for name, value in actual_services.items()}
    for service, expected in expected_services.items():
        actual = normalized_actual[_norm(service)]
        assert abs(actual - expected) <= 0.02, (
            f"July {service} cost is {actual}, expected {expected:.2f}; service-level planning would be misleading"
        )


def test_subscription_forecast_and_budget_outlook():
    """Every subscription's August-November status and available monthly amounts are correct."""
    output = _load_output()
    entities = _outlook_entities(output)
    by_id = {_subscription_id(entity): entity for entity in entities if _subscription_id(entity)}
    assert set(by_id) == set(SUBSCRIPTIONS), "the outlook must cover each subscription in subscriptions.csv exactly once"
    expected, unavailable = _expected_forecasts()
    for subscription_id, expected_months in expected.items():
        actual_months = _normalize_months(by_id[subscription_id])
        assert set(actual_months) >= set(expected_months), (
            f"{SUBSCRIPTIONS[subscription_id]} is missing one or more August-November outlook months"
        )
        for month, values in expected_months.items():
            actual = actual_months[month]
            for field in ("forecast", "projected", "budget"):
                assert actual[field] is not None and abs(float(actual[field]) - values[field]) <= 0.02, (
                    f"{SUBSCRIPTIONS[subscription_id]} {month} {field} is {actual[field]}, expected {values[field]:.2f}"
                )
            if month == "2026-08":
                assert actual["actual"] is not None and abs(float(actual["actual"]) - values["actual"]) <= 0.02, (
                    f"{SUBSCRIPTIONS[subscription_id]} August Actual component must remain separate from Forecast"
                )
            elif actual["actual"] is not None:
                assert abs(float(actual["actual"])) <= 0.02, (
                    f"{SUBSCRIPTIONS[subscription_id]} {month} should not invent an Actual amount"
                )
            assert abs(float(actual["projected"]) - (values["actual"] + values["forecast"])) <= 0.02, (
                f"{SUBSCRIPTIONS[subscription_id]} {month} projected total double-counts or omits a cost-status component"
            )

    for subscription_id in unavailable:
        entity = by_id[subscription_id]
        text = json.dumps(entity, ensure_ascii=False).lower()
        assert "unavailable" in text or "insufficient" in text or "no forecast" in text, (
            f"{SUBSCRIPTIONS[subscription_id]} must be marked as forecast unavailable"
        )
        actual_months = _normalize_months(entity)
        assert set(actual_months) >= {"2026-08", "2026-09", "2026-10", "2026-11"}, (
            f"{SUBSCRIPTIONS[subscription_id]} must retain all four budget months even without a forecast"
        )
        for month_name in ("2026-08", "2026-09", "2026-10", "2026-11"):
            month = actual_months[month_name]
            assert month["budget"] is not None and abs(float(month["budget"]) - 2500.0) <= 0.02, (
                f"{SUBSCRIPTIONS[subscription_id]} {month_name} budget is missing or incorrect"
            )
            assert month["forecast"] is None and month["projected"] is None, (
                f"{SUBSCRIPTIONS[subscription_id]} has an invented forecast or projected total"
            )


def test_priority_risk_coverage():
    """The risk shortlist contains the two largest over-budget exposures and the forecast gap."""
    output = _load_output()
    section = _find_section(output, ("priority_budget_risks", "budget_risks", "risks", "priorities"))
    text = json.dumps(section, ensure_ascii=False).lower()
    for subscription_id in (
        "00000000-0000-4000-8000-000000000101",
        "00000000-0000-4000-8000-000000000303",
        "00000000-0000-4000-8000-000000000505",
    ):
        name = SUBSCRIPTIONS[subscription_id]
        assert subscription_id.lower() in text or name.lower() in text, (
            f"priority risks omit {name}, a material budget exposure or forecast-availability gap"
        )
