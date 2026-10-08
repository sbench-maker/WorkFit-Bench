from __future__ import annotations

import csv
import json
import math
import os
import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULT = Path(os.environ.get("TASK_RESULT_PATH", "/root/results/output.json"))


def _csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _norm(value: object) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _field(row: dict, aliases: set[str]):
    targets = {_norm(alias) for alias in aliases}
    for key, value in row.items():
        if _norm(key) in targets:
            return value
    return None


def _number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _boolean(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if _norm(value) in {"true", "yes", "y", "risk", "atrisk", "stockout", "1"}:
            return True
        if _norm(value) in {"false", "no", "n", "norisk", "safe", "0"}:
            return False
    return None


def _walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _sku_id(row: dict) -> str | None:
    value = _field(row, {"sku_id", "sku", "item_id", "item", "product_id", "product"})
    if isinstance(value, (str, int)):
        match = str(value).strip().upper()
        if match.startswith("SKU-"):
            return match
    return None


def _extract_plans(payload: object, source_ids: set[str]) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for node in _walk(payload):
        if not isinstance(node, list):
            continue
        found: dict[str, dict] = {}
        for item in node:
            if isinstance(item, dict):
                sku_id = _sku_id(item)
                if sku_id in source_ids:
                    found[sku_id] = item
        if len(found) > len(best):
            best = found
    if not best and isinstance(payload, dict):
        for key, value in payload.items():
            sku_id = str(key).strip().upper()
            if sku_id in source_ids and isinstance(value, dict):
                best[sku_id] = {"sku_id": sku_id, **value}
    return best


def _forecast_total(row: dict) -> float | None:
    direct = _field(row, {
        "forecast_4_week_units", "forecast_4_weeks", "four_week_forecast",
        "four_week_forecast_units", "forecast_4_week", "forecast_total", "total_forecast_units",
    })
    number = _number(direct)
    if number is not None:
        return number
    weekly = _field(row, {"forecast_weeks", "weekly_forecast", "weekly_forecasts", "forecast", "forecasts"})
    if isinstance(weekly, dict):
        values = [_number(value) for value in weekly.values()]
        if values and all(value is not None for value in values):
            return sum(values)
    if isinstance(weekly, list):
        values = []
        for item in weekly:
            if isinstance(item, dict):
                raw = _field(item, {"units", "forecast_units", "quantity", "demand", "value"})
            else:
                raw = item
            number = _number(raw)
            if number is not None:
                values.append(number)
        if len(values) >= 4:
            return sum(values[:4])
    return None


def _measure(row: dict, aliases: set[str]) -> float | None:
    value = _field(row, aliases)
    number = _number(value)
    if number is not None:
        return number
    if isinstance(value, dict):
        for nested in value.values():
            number = _number(nested)
            if number is not None:
                return number
    return None


def _ols(rows: list[dict], future: list[date]) -> list[float]:
    latest = rows[-13:]
    x = [(row["date"] - rows[0]["date"]).days / 7 for row in latest]
    y = [row["units"] for row in latest]
    xb, yb = statistics.mean(x), statistics.mean(y)
    slope = sum((a - xb) * (b - yb) for a, b in zip(x, y)) / sum((a - xb) ** 2 for a in x)
    intercept = yb - slope * xb
    return [max(0.0, intercept + slope * ((day - rows[0]["date"]).days / 7)) for day in future]


def _croston(rows: list[dict]) -> float:
    values = [row["units"] for row in rows[-26:]]
    positives = [(idx, value) for idx, value in enumerate(values) if value > 0]
    if not positives:
        return 0.0
    previous, size = positives[0]
    interval = float(previous + 1)
    for idx, value in positives[1:]:
        size = 0.2 * value + 0.8 * size
        interval = 0.2 * (idx - previous) + 0.8 * interval
        previous = idx
    return size / interval


def _expected() -> dict[str, dict]:
    policy = json.loads((DATA / "planning_policy.json").read_text(encoding="utf-8"))
    planning_date = date.fromisoformat(policy["planning_date"])
    vendors = {row["vendor_id"]: row for row in _csv("vendors.csv")}
    inventory = {row["sku_id"]: row for row in _csv("inventory_snapshot.csv")}
    pos: dict[str, list[dict[str, str]]] = {}
    for row in _csv("open_purchase_orders.csv"):
        pos.setdefault(row["sku_id"], []).append(row)
    histories: dict[str, list[dict]] = {}
    for row in _csv("weekly_demand.csv"):
        histories.setdefault(row["sku_id"], []).append({
            "date": date.fromisoformat(row["week_start"]),
            "units": int(row["units_sold"]),
            "eligible": row["promo_flag"] == "false" and row["stockout_flag"] == "false",
        })
    z_scores = {float(key): float(value) for key, value in policy["z_scores"].items()}
    result = {}
    for sku in _csv("sku_master.csv"):
        sku_id = sku["sku_id"]
        all_rows = sorted(histories[sku_id], key=lambda row: row["date"])
        clean = [row for row in all_rows if row["eligible"]]
        future = [all_rows[-1]["date"] + timedelta(weeks=offset) for offset in range(1, 5)]
        pattern = sku["demand_pattern"]
        if pattern == "stable":
            level = statistics.mean(row["units"] for row in clean[-8:])
            forecasts = [level] * 4
        elif pattern == "trending":
            forecasts = _ols(clean, future)
        elif pattern == "seasonal":
            by_date = {row["date"]: row for row in clean}
            pairs = [row for row in clean if row["date"] - timedelta(weeks=52) in by_date][-8:]
            factor = statistics.mean(row["units"] for row in pairs) / statistics.mean(
                by_date[row["date"] - timedelta(weeks=52)]["units"] for row in pairs
            )
            forecasts = [by_date[day - timedelta(weeks=52)]["units"] * factor for day in future]
        else:
            forecasts = [_croston(clean)] * 4
        mean_forecast = statistics.mean(forecasts)
        sigma = statistics.stdev(row["units"] for row in clean[-26:])
        vendor = vendors[sku["vendor_id"]]
        lt = float(vendor["new_lead_time_avg_days"]) / 7
        lt_std = float(vendor["new_lead_time_std_days"]) / 7
        z = z_scores[float(sku["target_service_level"])]
        ss = math.ceil(z * math.sqrt((lt + 1) * sigma**2 + mean_forecast**2 * lt_std**2))
        valid_pos = [row for row in pos.get(sku_id, []) if row["status"] in {"open", "confirmed"}]
        inv = inventory[sku_id]
        on_hand, backorders, committed = int(inv["on_hand"]), int(inv["backorders"]), int(inv["committed"])
        on_order = sum(int(row["quantity"]) for row in valid_pos)
        inventory_position = on_hand + on_order - backorders - committed
        raw = max(0.0, mean_forecast * (lt + 1) + ss - inventory_position)
        pack, moq = int(sku["case_pack"]), int(sku["moq"])
        order = 0 if raw <= 0 else max(moq, math.ceil(math.ceil(raw) / pack) * pack)
        arrival = planning_date + timedelta(days=int(vendor["new_lead_time_avg_days"]))
        due = sum(int(row["quantity"]) for row in valid_pos if date.fromisoformat(row["expected_arrival_date"]) <= arrival)
        risk = on_hand - backorders - committed + due + 1e-9 < mean_forecast * lt
        result[sku_id] = {
            "pattern": pattern,
            "forecast": sum(forecasts),
            "safety_stock": ss,
            "inventory_position": inventory_position,
            "net_requirement": math.ceil(raw),
            "recommended_order": order,
            "risk": risk,
        }
    return result


@pytest.fixture(scope="session")
def source_ids() -> set[str]:
    return {row["sku_id"] for row in _csv("sku_master.csv")}


@pytest.fixture(scope="session")
def submission(source_ids):
    assert RESULT.is_file(), f"requested output is missing: {RESULT}"
    try:
        payload = json.loads(RESULT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    return payload, _extract_plans(payload, source_ids)


@pytest.fixture(scope="session")
def expected():
    return _expected()


def test_artifact_usability(submission):
    """artifact_usability: output opens and contains recognizable per-SKU planning records."""
    payload, plans = submission
    assert isinstance(payload, (dict, list)), "output must be a JSON object or list usable by downstream planning"
    assert plans, "no per-SKU planning records with recognizable SKU identifiers were found"
    populated = 0
    for row in plans.values():
        if _forecast_total(row) is not None and _measure(row, {"safety_stock_units", "safety_stock", "new_safety_stock", "ss_units"}) is not None:
            populated += 1
    assert populated >= 30, f"only {populated} SKU records expose both forecast and safety stock values"


def test_sku_coverage(submission, source_ids):
    """artifact_usability: every source SKU is represented exactly once after normalization."""
    _, plans = submission
    assert set(plans) == source_ids, f"SKU coverage differs: missing={sorted(source_ids - set(plans))}, extra={sorted(set(plans) - source_ids)}"


@pytest.mark.parametrize("pattern", ["stable", "trending", "seasonal", "intermittent"])
def test_forecast_calculations(submission, expected, pattern):
    """forecast_correctness: forecasts follow the frozen planning policy for every demand pattern."""
    _, plans = submission
    if not plans:
        pytest.skip("per-SKU records are unavailable; the artifact criterion reports this root failure")
    errors = []
    for sku_id, target in expected.items():
        if target["pattern"] != pattern or sku_id not in plans:
            continue
        actual = _forecast_total(plans.get(sku_id, {}))
        if actual is None or not math.isclose(actual, target["forecast"], rel_tol=0.005, abs_tol=0.55):
            errors.append(f"{sku_id}: got {actual}, expected {target['forecast']:.2f}")
    assert not errors, "four-week forecasts are materially wrong: " + "; ".join(errors[:6])


@pytest.mark.parametrize("vendor_id", ["V-ASTER", "V-BRIM", "V-COVE", "V-DUSK"])
def test_safety_stock_calculations(submission, expected, vendor_id):
    """safety_stock_correctness: recalculated safety stock reflects demand and lead-time variability."""
    _, plans = submission
    if not plans:
        pytest.skip("per-SKU records are unavailable; the artifact criterion reports this root failure")
    sku_vendor = {row["sku_id"]: row["vendor_id"] for row in _csv("sku_master.csv")}
    errors = []
    for sku_id, target in expected.items():
        if sku_vendor[sku_id] != vendor_id or sku_id not in plans:
            continue
        actual = _measure(plans.get(sku_id, {}), {"safety_stock_units", "safety_stock", "new_safety_stock", "ss_units"})
        if actual is None or abs(actual - target["safety_stock"]) > 1:
            errors.append(f"{sku_id}: got {actual}, expected {target['safety_stock']}")
    assert not errors, "safety stock is materially wrong: " + "; ".join(errors[:6])


@pytest.mark.parametrize("segment", ["order", "no_order", "moq_limited"])
def test_replenishment_math(submission, expected, segment):
    """replenishment_correctness: inventory position, net need, case packs, and MOQ yield executable orders."""
    _, plans = submission
    if not plans:
        pytest.skip("per-SKU records are unavailable; the artifact criterion reports this root failure")
    master = {row["sku_id"]: row for row in _csv("sku_master.csv")}
    errors = []
    for sku_id, target in expected.items():
        if sku_id not in plans:
            continue
        moq_limited = 0 < target["net_requirement"] < int(master[sku_id]["moq"])
        if segment == "order" and target["recommended_order"] <= 0:
            continue
        if segment == "no_order" and target["recommended_order"] != 0:
            continue
        if segment == "moq_limited" and not moq_limited:
            continue
        row = plans.get(sku_id, {})
        position = _measure(row, {"inventory_position_units", "inventory_position", "ip_units", "stock_position"})
        order = _measure(row, {"recommended_order_units", "recommended_order", "order_qty", "order_quantity", "suggested_po_qty", "replenishment_qty"})
        if position is None or abs(position - target["inventory_position"]) > 0.01:
            errors.append(f"{sku_id} inventory position got {position}, expected {target['inventory_position']}")
        if order is None or abs(order - target["recommended_order"]) > 0.01:
            errors.append(f"{sku_id} order got {order}, expected {target['recommended_order']}")
    assert not errors, f"{segment} replenishment decisions are not executable: " + "; ".join(errors[:8])


def test_pre_arrival_risk_flags(submission, expected, source_ids):
    """risk_flag_correctness: the complete set of pre-arrival stockout risks is flagged."""
    payload, plans = submission
    if not plans:
        pytest.skip("per-SKU records are unavailable; the artifact criterion reports this root failure")
    declared: set[str] = set()
    explicit_false: set[str] = set()
    for sku_id, row in plans.items():
        value = _field(row, {"pre_arrival_stockout_risk", "stockout_before_arrival", "pre_arrival_risk", "at_risk", "stockout_risk"})
        parsed = _boolean(value)
        if parsed is True:
            declared.add(sku_id)
        elif parsed is False:
            explicit_false.add(sku_id)
    for node in _walk(payload):
        if isinstance(node, dict):
            for key, value in node.items():
                if _norm(key) in {"prearrivalstockoutrisks", "prearrivalrisks", "stockoutrisks", "riskskus"} and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.upper() in source_ids:
                            declared.add(item.upper())
                        elif isinstance(item, dict) and _sku_id(item) in source_ids:
                            declared.add(_sku_id(item))
    represented = set(plans)
    expected_risks = {sku_id for sku_id, target in expected.items() if target["risk"] and sku_id in represented}
    declared &= represented
    assert declared or explicit_false, "no recognizable pre-arrival risk flags or risk list was found"
    assert declared == expected_risks, f"risk set differs: missing={sorted(expected_risks - declared)}, false_positive={sorted(declared - expected_risks)}"
