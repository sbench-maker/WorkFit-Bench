from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("SUBMISSION_PATH", "/root/results/output.json"))
SCENARIOS = ("base", "high", "low")


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def as_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "").replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = norm_key(value)
        if token in {"true", "yes", "y", "eligible", "included", "pass"}:
            return True
        if token in {"false", "no", "n", "ineligible", "excluded", "fail"}:
            return False
    return None


def walk(value: object, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (str(index),))


def direct_value(row: dict, aliases: set[str]) -> object | None:
    normalized = {norm_key(key): value for key, value in row.items()}
    for alias in aliases:
        if norm_key(alias) in normalized:
            return normalized[norm_key(alias)]
    return None


def direct_number(row: dict, aliases: set[str]) -> float | None:
    return as_number(direct_value(row, aliases))


def discover_id(row: dict, path: tuple[str, ...], known: set[str], aliases: set[str]) -> str | None:
    value = direct_value(row, aliases)
    if value is not None and str(value).strip().upper() in known:
        return str(value).strip().upper()
    for part in reversed(path):
        if part.upper() in known:
            return part.upper()
    return None


def scenario_values(row: dict, nested_value_aliases: set[str] | None = None) -> dict[str, float] | None:
    result: dict[str, float] = {}
    scenario_aliases = {
        "base": {"base", "base_cost", "base_usd", "base_scenario", "base_total_cost", "base_total_delivered_cost_usd"},
        "high": {"high", "high_cost", "high_usd", "high_scenario", "stress_high", "upside", "high_total_delivered_cost_usd"},
        "low": {"low", "low_cost", "low_usd", "low_scenario", "stress_low", "downside", "low_total_delivered_cost_usd"},
    }
    for scenario, aliases in scenario_aliases.items():
        number = direct_number(row, aliases)
        if number is not None:
            result[scenario] = number
    if len(result) == 3:
        return result

    generic_cost_aliases = {
        "total_delivered_cost_usd",
        "scenario_total_delivered_cost_usd",
        "scenario_costs",
        "delivered_costs",
        "costs",
        "total_costs",
    }
    for key, value in row.items():
        if norm_key(key) in {norm_key(item) for item in generic_cost_aliases} and isinstance(value, dict):
            nested = scenario_values(value, nested_value_aliases)
            if nested is not None:
                return nested
    for scenario, aliases in scenario_aliases.items():
        for key, value in row.items():
            if norm_key(key) not in {norm_key(item) for item in aliases} or not isinstance(value, dict):
                continue
            number = direct_number(
                value,
                nested_value_aliases or {"total_delivered_cost_usd", "total_cost", "cost", "usd", "value"},
            )
            if number is not None:
                result[scenario] = number
    return result if len(result) == 3 else None


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="session")
def submission() -> object:
    assert OUTPUT_PATH.is_file(), f"requested artifact is missing: {OUTPUT_PATH}"
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")


@pytest.fixture(scope="session")
def truth() -> dict:
    facilities = read_csv("facilities.csv")
    intervals = read_csv("interval_load.csv")
    tariffs = read_csv("network_tariffs.csv")
    prices = read_csv("market_prices.csv")
    suppliers = read_csv("suppliers.csv")
    bids = read_csv("supplier_bids.csv")
    exceptions = read_csv("contract_exceptions.csv")
    policy = json.loads((DATA_DIR / "procurement_policy.json").read_text(encoding="utf-8"))
    facility_map = {row["facility_id"]: row for row in facilities}
    supplier_map = {row["supplier_id"]: row for row in suppliers}
    bid_map = {row["offer_id"]: row for row in bids}

    raw_profiles = defaultdict(lambda: {"annual_kwh": 0.0, "peak_kw": 0.0})
    period_mwh = defaultdict(float)
    for row in intervals:
        annualized_kwh = float(row["interval_kwh"]) * int(row["represented_days"])
        interval_kw = float(row["interval_kwh"]) * 4
        facility_id = row["facility_id"]
        raw_profiles[facility_id]["annual_kwh"] += annualized_kwh
        raw_profiles[facility_id]["peak_kw"] = max(raw_profiles[facility_id]["peak_kw"], interval_kw)
        market = facility_map[facility_id]["market"]
        period_mwh[(market, row["representative_month"], row["pricing_period"])] += annualized_kwh / 1000

    profiles = {}
    for facility_id, raw in raw_profiles.items():
        profiles[facility_id] = {
            "annual_mwh": raw["annual_kwh"] / 1000,
            "peak_kw": raw["peak_kw"],
            "load_factor": raw["annual_kwh"] / (raw["peak_kw"] * 8760),
        }

    network_by_market = defaultdict(float)
    for row in tariffs:
        facility_id = row["facility_id"]
        raw = raw_profiles[facility_id]
        cost = (
            raw["annual_kwh"] / 1000 * (float(row["distribution_usd_mwh"]) + float(row["riders_usd_mwh"]))
            + raw["peak_kw"] * float(row["demand_rate_usd_kw_month"]) * 12
            + float(row["capacity_tag_kw"]) * float(row["capacity_rate_usd_kw_year"])
            + float(row["transmission_tag_kw"]) * float(row["transmission_rate_usd_kw_year"])
        )
        network_by_market[facility_map[facility_id]["market"]] += cost

    price_map = {(row["market"], row["month"], row["pricing_period"]): row for row in prices}
    open_exceptions = defaultdict(list)
    for row in exceptions:
        if row["status"] == "open":
            open_exceptions[row["offer_id"]].append(row)

    rating_order = policy["eligibility"]["credit_rating_order_best_to_worst"]
    min_rating_index = rating_order.index(policy["eligibility"]["minimum_credit_rating"])
    prohibited = set(policy["eligibility"]["prohibited_open_clause_codes"])
    eligible_ids = set()
    offer_costs = {}
    for bid in bids:
        rules = policy["eligibility"]
        rating = supplier_map[bid["supplier_id"]]["credit_rating"]
        eligible = rating_order.index(rating) <= min_rating_index
        eligible = eligible and int(bid["term_months"]) in rules["allowed_term_months"]
        eligible = eligible and bid["contract_start"] == policy["delivery_start"] and bid["contract_end"] == policy["delivery_end"]
        eligible = eligible and bid["quote_valid_through"] >= rules["minimum_quote_valid_through"]
        eligible = eligible and float(bid["volume_tolerance_pct"]) >= rules["minimum_volume_tolerance_pct"]
        eligible = eligible and float(bid["early_termination_cap_usd"]) <= rules["maximum_early_termination_cap_usd"]
        required_fields = rules["required_price_fields_by_product"][bid["product"]]
        eligible = eligible and all(bid[field].strip() != "" for field in required_fields)
        eligible = eligible and not any(item["clause_code"] in prohibited for item in open_exceptions[bid["offer_id"]])
        if not eligible:
            continue
        eligible_ids.add(bid["offer_id"])
        scenario_costs = {}
        for scenario in SCENARIOS:
            supply = 0.0
            for (market, month, period), volume in period_mwh.items():
                if market != bid["market"]:
                    continue
                fixed_share = float(bid["fixed_share_pct"]) / 100
                ancillary_rec = float(bid["ancillary_usd_mwh"]) + float(bid["rec_usd_mwh"])
                if bid["product"] == "fixed_full_requirements":
                    unit = float(bid["fixed_energy_usd_mwh"]) + ancillary_rec
                else:
                    index_price = float(price_map[(market, month, period)][f"{scenario}_usd_mwh"])
                    floor = as_number(bid["index_floor_usd_mwh"])
                    cap = as_number(bid["index_cap_usd_mwh"])
                    if floor is not None:
                        index_price = max(index_price, floor)
                    if cap is not None:
                        index_price = min(index_price, cap)
                    indexed = index_price + float(bid["index_adder_usd_mwh"])
                    if bid["product"] == "index":
                        unit = indexed + ancillary_rec
                    else:
                        unit = fixed_share * float(bid["fixed_energy_usd_mwh"]) + (1 - fixed_share) * indexed + ancillary_rec
                supply += volume * unit
            scenario_costs[scenario] = supply + network_by_market[bid["market"]]
        offer_costs[bid["offer_id"]] = scenario_costs

    return {
        "facilities": facilities,
        "profiles": profiles,
        "policy": policy,
        "eligible_ids": eligible_ids,
        "offer_costs": offer_costs,
        "bid_map": bid_map,
        "supplier_map": supplier_map,
    }


def collect_facility_profiles(payload: object, known_ids: set[str]) -> dict[str, list[dict]]:
    aliases = {"facility_id", "site_id", "facility", "site", "id"}
    collected: dict[str, list[dict]] = defaultdict(list)
    for path, row in walk(payload):
        facility_id = discover_id(row, path, known_ids, aliases)
        if facility_id is None:
            continue
        annual = direct_number(row, {"annual_mwh", "annual_energy_mwh", "yearly_mwh", "volume_mwh"})
        peak = direct_number(row, {"peak_kw", "annual_peak_kw", "max_demand_kw", "maximum_kw"})
        load_factor = direct_number(row, {"load_factor", "annual_load_factor", "loadfactor"})
        if annual is not None and peak is not None and load_factor is not None:
            if load_factor > 1.5:
                load_factor /= 100
            collected[facility_id].append({"annual_mwh": annual, "peak_kw": peak, "load_factor": load_factor})
    return collected


def collect_offer_comparisons(payload: object, known_ids: set[str]) -> dict[str, list[dict]]:
    aliases = {"offer_id", "bid_id", "proposal_id", "offer", "bid", "id"}
    collected: dict[str, list[dict]] = defaultdict(list)
    for path, row in walk(payload):
        offer_id = discover_id(row, path, known_ids, aliases)
        if offer_id is None:
            continue
        eligibility = as_bool(direct_value(row, {"eligible", "is_eligible", "qualified", "included"}))
        costs = scenario_values(row)
        if eligibility is not False and costs is not None:
            collected[offer_id].append({"costs": costs, "row": row})
    return collected


def market_from(row: dict, path: tuple[str, ...]) -> str | None:
    direct = direct_value(row, {"market", "iso", "region"})
    if direct is not None and str(direct).strip().upper() in {"PJM", "ERCOT"}:
        return str(direct).strip().upper()
    for part in reversed(path):
        if part.upper() in {"PJM", "ERCOT"}:
            return part.upper()
    return None


def allocation_list(row: dict) -> list | None:
    value = direct_value(row, {"allocations", "awards", "award_mix", "award_allocations", "supplier_allocations"})
    return value if isinstance(value, list) else None


def normalize_awards(payload: object, known_offer_ids: set[str]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for path, row in walk(payload):
        items = allocation_list(row)
        market = market_from(row, path)
        if items is None or market is None:
            continue
        allocations = []
        for item in items:
            if not isinstance(item, dict):
                continue
            offer_id = discover_id(item, (), known_offer_ids, {"offer_id", "bid_id", "proposal_id", "offer", "bid", "id"})
            share = direct_number(item, {"award_share_pct", "allocation_share_pct", "volume_share_pct", "share_pct", "share", "allocation"})
            if offer_id is not None and share is not None:
                allocations.append({"offer_id": offer_id, "share": share})
        if allocations:
            groups[market] = {"allocations": allocations, "report": row}

    if len(groups) < 2:
        flat = defaultdict(list)
        reports = {}
        for path, row in walk(payload):
            market = market_from(row, path)
            offer_id = discover_id(row, path, known_offer_ids, {"offer_id", "bid_id", "proposal_id", "offer", "bid"})
            share = direct_number(row, {"award_share_pct", "allocation_share_pct", "volume_share_pct", "share_pct", "share", "allocation"})
            if market and offer_id and share is not None:
                flat[market].append({"offer_id": offer_id, "share": share})
                reports.setdefault(market, row)
        for market, allocations in flat.items():
            groups.setdefault(market, {"allocations": allocations, "report": reports[market]})

    for group in groups.values():
        total = sum(item["share"] for item in group["allocations"])
        if 0.99 <= total <= 1.01:
            for item in group["allocations"]:
                item["share"] *= 100
    return groups


def find_named_container(payload: object, aliases: set[str]) -> dict | None:
    normalized_aliases = {norm_key(alias) for alias in aliases}
    for _path, row in walk(payload):
        for key, value in row.items():
            if norm_key(key) in normalized_aliases and isinstance(value, dict):
                return value
    return None


def assert_close(actual: float, expected: float, *, label: str, tolerance: float) -> None:
    assert abs(actual - expected) <= tolerance, f"{label} is {actual}, expected {expected} within {tolerance}"


def test_facility_profile_coverage(submission, truth):
    known = set(truth["profiles"])
    records = collect_facility_profiles(submission, known)
    assert set(records) == known, f"facility profiles must cover all sites; missing={sorted(known - set(records))}"
    duplicates = sorted(facility_id for facility_id, rows in records.items() if len(rows) != 1)
    assert not duplicates, f"facility profiles are duplicated for {duplicates}, making the portfolio totals ambiguous"


def test_load_profile_metrics(submission, truth):
    records = collect_facility_profiles(submission, set(truth["profiles"]))
    errors = []
    for facility_id, expected in truth["profiles"].items():
        if len(records.get(facility_id, [])) != 1:
            continue
        actual = records[facility_id][0]
        if abs(actual["annual_mwh"] - expected["annual_mwh"]) > 0.02:
            errors.append(f"{facility_id} annual_mwh")
        if abs(actual["peak_kw"] - expected["peak_kw"]) > 0.02:
            errors.append(f"{facility_id} peak_kw")
        if abs(actual["load_factor"] - expected["load_factor"]) > 0.0002:
            errors.append(f"{facility_id} load_factor")
    assert not errors, f"incorrect interval-derived load metrics: {errors}"


def test_eligible_offer_coverage(submission, truth):
    known = set(truth["bid_map"])
    records = collect_offer_comparisons(submission, known)
    actual = set(records)
    expected = truth["eligible_ids"]
    assert actual == expected, (
        "eligible-offer comparison scope is wrong; "
        f"missing={sorted(expected - actual)}, ineligible_or_unknown={sorted(actual - expected)}"
    )
    duplicates = sorted(offer_id for offer_id, rows in records.items() if len(rows) != 1)
    assert not duplicates, f"eligible offers have multiple conflicting cost comparisons: {duplicates}"


def test_offer_total_delivered_costs(submission, truth):
    records = collect_offer_comparisons(submission, set(truth["bid_map"]))
    errors = []
    for offer_id, expected_costs in truth["offer_costs"].items():
        if len(records.get(offer_id, [])) != 1:
            continue
        actual_costs = records[offer_id][0]["costs"]
        for scenario in SCENARIOS:
            tolerance = max(15.0, abs(expected_costs[scenario]) * 0.000002)
            if abs(actual_costs[scenario] - expected_costs[scenario]) > tolerance:
                errors.append(f"{offer_id}/{scenario}")
    assert not errors, f"delivered-cost calculations are materially wrong for {errors}"


def test_award_constraints(submission, truth):
    groups = normalize_awards(submission, set(truth["bid_map"]))
    assert set(groups) == {"PJM", "ERCOT"}, "award mix must cover both PJM and ERCOT"
    ranges = truth["policy"]["award_constraints"]["fixed_hedge_pct_range_by_market"]
    errors = []
    for market, group in groups.items():
        allocations = group["allocations"]
        total_share = sum(item["share"] for item in allocations)
        if abs(total_share - 100) > 0.02:
            errors.append(f"{market} shares sum to {total_share}")
            continue
        if any(item["offer_id"] not in truth["eligible_ids"] for item in allocations):
            errors.append(f"{market} awards an ineligible offer")
            continue
        if any(truth["bid_map"][item["offer_id"]]["market"] != market for item in allocations):
            errors.append(f"{market} includes an offer from another market")
        supplier_shares = defaultdict(float)
        hedge = 0.0
        for item in allocations:
            bid = truth["bid_map"][item["offer_id"]]
            supplier_shares[bid["supplier_id"]] += item["share"]
            hedge += item["share"] * float(bid["fixed_share_pct"]) / 100
        if len(supplier_shares) < truth["policy"]["award_constraints"]["minimum_distinct_suppliers_per_market"]:
            errors.append(f"{market} lacks supplier diversification")
        if max(supplier_shares.values()) > truth["policy"]["award_constraints"]["maximum_supplier_share_per_market_pct"] + 0.02:
            errors.append(f"{market} exceeds the supplier concentration cap")
        if not ranges[market][0] - 0.02 <= hedge <= ranges[market][1] + 0.02:
            errors.append(f"{market} fixed hedge is {hedge:.2f}%")
        reported_hedge = direct_number(group["report"], {"fixed_hedge_pct", "hedge_pct", "fixed_pct", "fixed_coverage_pct"})
        if reported_hedge is not None and abs(reported_hedge - hedge) > 0.05:
            errors.append(f"{market} reported hedge does not match allocations")
    assert not errors, f"award mix violates the approved procurement policy: {errors}"


def test_award_cost_and_budget_consistency(submission, truth):
    groups = normalize_awards(submission, set(truth["bid_map"]))
    assert set(groups) == {"PJM", "ERCOT"}, "cannot reconcile costs without awards for both markets"
    calculated = {}
    for market, group in groups.items():
        calculated[market] = {
            scenario: sum(
                item["share"] / 100 * truth["offer_costs"][item["offer_id"]][scenario]
                for item in group["allocations"]
            )
            for scenario in SCENARIOS
        }

    market_cost_reports = 0
    market_budget_reports = 0
    errors = []
    for market, group in groups.items():
        reported_costs = scenario_values(group["report"])
        if reported_costs is not None:
            market_cost_reports += 1
            for scenario in SCENARIOS:
                if abs(reported_costs[scenario] - calculated[market][scenario]) > 25:
                    errors.append(f"{market}/{scenario} award cost")
        budget_container = direct_value(group["report"], {"budget_variance_usd", "budget_variances", "scenario_budget_variance", "variance_to_budget_usd"})
        budget_values = scenario_values(
            budget_container,
            {"variance", "variance_usd", "budget_variance", "budget_variance_usd", "value"},
        ) if isinstance(budget_container, dict) else None
        if budget_values is not None:
            market_budget_reports += 1
            budget = truth["policy"]["annual_budget_usd"][market]
            for scenario in SCENARIOS:
                if abs(budget_values[scenario] - (calculated[market][scenario] - budget)) > 25:
                    errors.append(f"{market}/{scenario} budget variance")

    portfolio_cost_container = find_named_container(
        submission,
        {"portfolio_scenario_total_delivered_cost_usd", "portfolio_total_delivered_cost_usd", "portfolio_costs", "total_portfolio_costs"},
    )
    portfolio_costs = scenario_values(portfolio_cost_container) if portfolio_cost_container else None
    portfolio_budget_container = find_named_container(
        submission,
        {"portfolio_budget_variance_usd", "portfolio_budget_variances", "total_budget_variance_usd", "budget_variance"},
    )
    portfolio_budget = scenario_values(
        portfolio_budget_container,
        {"variance", "variance_usd", "budget_variance", "budget_variance_usd", "value"},
    ) if portfolio_budget_container else None
    expected_portfolio = {scenario: sum(calculated[market][scenario] for market in calculated) for scenario in SCENARIOS}
    if portfolio_costs is not None:
        for scenario in SCENARIOS:
            if abs(portfolio_costs[scenario] - expected_portfolio[scenario]) > 35:
                errors.append(f"portfolio/{scenario} total cost")
    if portfolio_budget is not None:
        total_budget = sum(truth["policy"]["annual_budget_usd"].values())
        for scenario in SCENARIOS:
            if abs(portfolio_budget[scenario] - (expected_portfolio[scenario] - total_budget)) > 35:
                errors.append(f"portfolio/{scenario} budget variance")

    assert market_cost_reports == 2 or portfolio_costs is not None, "base/high/low award costs are not reported at market or portfolio level"
    assert market_budget_reports == 2 or portfolio_budget is not None, "base/high/low exposure versus approved budget is not reported"
    assert not errors, f"award totals or budget exposures do not reconcile: {errors}"
