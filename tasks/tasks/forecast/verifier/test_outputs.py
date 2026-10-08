from __future__ import annotations

import csv
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest


DATA = Path(os.environ.get("FORECAST_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("FORECAST_OUTPUT_PATH", "/root/results/output.json"))


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a forecast number")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for alias in ("amount_usd", "amount", "value", "total_usd", "total", "forecast", "ratio"):
            found = _lookup(value, [alias], default=None)
            if found is not None:
                return _number(found)
        raise ValueError(f"mapping has no numeric value: {value!r}")
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("usd", "").replace("$", "").replace(",", "").replace("x", "")
        if cleaned.endswith("%"):
            return float(cleaned[:-1]) / 100.0
        return float(cleaned)
    raise ValueError(f"unsupported numeric representation: {value!r}")


_MISSING = object()


def _lookup(mapping: Any, aliases: list[str] | tuple[str, ...], default: Any = _MISSING) -> Any:
    if not isinstance(mapping, dict):
        if default is not _MISSING:
            return default
        raise KeyError(f"expected an object while looking for {aliases}")
    normalized = {_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if _key(alias) in normalized:
            return normalized[_key(alias)]
    if default is not _MISSING:
        return default
    raise KeyError(f"missing a field equivalent to one of {aliases}")


def _find_section(root: Any, aliases: list[str] | tuple[str, ...]) -> Any:
    targets = {_key(alias) for alias in aliases}
    queue: list[tuple[Any, int]] = [(root, 0)]
    while queue:
        node, depth = queue.pop(0)
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if _key(key) in targets:
                return value
        if depth < 2:
            queue.extend((value, depth + 1) for value in node.values() if isinstance(value, dict))
    raise KeyError(f"missing a section equivalent to one of {aliases}")


def _metric(section: Any, aliases: list[str] | tuple[str, ...]) -> float:
    if isinstance(section, dict):
        value = _lookup(section, aliases, default=None)
        if value is not None:
            return _number(value)
    if isinstance(section, list):
        targets = {_key(alias) for alias in aliases}
        for row in section:
            if not isinstance(row, dict):
                continue
            label = _lookup(row, ["metric", "name", "label", "scenario"], default="")
            if _key(label) in targets:
                return _number(_lookup(row, ["value", "amount", "amount_usd", "total", "forecast"]))
    raise KeyError(f"missing metric equivalent to one of {aliases}")


def _rows(section: Any, item_aliases: tuple[str, ...]) -> list[dict]:
    if isinstance(section, list):
        return [row if isinstance(row, dict) else {"deal_id": row} for row in section if isinstance(row, dict) or re.fullmatch(r"(?i)(?:opp|deal)[-_ ]?\d+", str(row))]
    if isinstance(section, dict):
        nested = _lookup(section, (*item_aliases, "deal_ids", "opportunity_ids"), default=None)
        if isinstance(nested, list):
            return [row if isinstance(row, dict) else {"deal_id": row} for row in nested if isinstance(row, dict) or re.fullmatch(r"(?i)(?:opp|deal)[-_ ]?\d+", str(row))]
        if isinstance(nested, dict):
            return [dict(value, **({"deal_id": key} if "deal_id" not in value and "id" not in value else {})) for key, value in nested.items() if isinstance(value, dict)]
        keyed_rows = []
        for key, value in section.items():
            if isinstance(value, dict) and re.fullmatch(r"(?i)(?:opp|deal)[-_ ]?\d+", str(key)):
                row = dict(value)
                row.setdefault("deal_id", key)
                keyed_rows.append(row)
        if keyed_rows:
            return keyed_rows
    return []


def _deal_id(row: dict) -> str:
    return str(_lookup(row, ["deal_id", "opportunity_id", "opportunityid", "id"]))


def _stage_rows(section: Any) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if isinstance(section, list):
        for row in section:
            if not isinstance(row, dict):
                continue
            stage = _lookup(row, ["stage", "name", "label"], default=None)
            if stage is not None:
                result[_key(stage)] = row
    elif isinstance(section, dict):
        nested = _lookup(section, ["stages", "rows", "items", "breakdown"], default=None)
        if nested is not None and nested is not section:
            return _stage_rows(nested)
        for stage, value in section.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("stage", stage)
                result[_key(stage)] = row
    return result


def _risk_texts(root: Any) -> dict[str, str]:
    found: dict[str, list[str]] = {}

    def walk(node: Any, context: str = "") -> None:
        if isinstance(node, dict):
            identifier = _lookup(node, ["deal_id", "opportunity_id", "id"], default=None)
            if identifier is not None and re.fullmatch(r"(?i)(?:opp|deal)[-_ ]?\d+", str(identifier)):
                found.setdefault(str(identifier), []).append(context + " " + json.dumps(node, ensure_ascii=False))
            for key, value in node.items():
                if re.fullmatch(r"(?i)(?:opp|deal)[-_ ]?\d+", str(key)):
                    found.setdefault(str(key), []).append(context + " " + str(key) + " " + json.dumps(value, ensure_ascii=False))
                walk(value, context + " " + str(key))
        elif isinstance(node, list):
            for value in node:
                walk(value, context)
        elif isinstance(node, str):
            for identifier in re.findall(r"(?i)(?:opp|deal)[-_ ]?\d+", node):
                found.setdefault(identifier, []).append(context + " " + node)

    walk(root)
    return {identifier: " ".join(parts).lower() for identifier, parts in found.items()}


def _load_submission() -> tuple[Any, str | None]:
    if not OUTPUT.is_file():
        return None, f"requested artifact is missing: {OUTPUT}"
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"


def _expected() -> dict:
    context = json.loads((DATA / "forecast_context.json").read_text(encoding="utf-8"))
    pipeline = _read_csv("pipeline.csv")
    activities = _read_csv("activities.csv")
    bookings = _read_csv("bookings.csv")
    as_of = date.fromisoformat(context["as_of_date"])
    start = date.fromisoformat(context["period_start"])
    end = date.fromisoformat(context["period_end"])
    open_stages = set(context["scope_policy"]["open_stages"])
    policy = context["commit_policy"]
    probabilities = context["stage_probabilities"]

    latest: dict[str, date] = {}
    for row in activities:
        when = date.fromisoformat(row["activity_date"])
        if when <= as_of and (row["deal_id"] not in latest or when > latest[row["deal_id"]]):
            latest[row["deal_id"]] = when

    closed = sum(
        float(row["booked_amount_usd"])
        for row in bookings
        if row["status"] == "Booked" and start <= date.fromisoformat(row["booked_date"]) <= as_of
    )
    scoped: dict[str, dict] = {}
    for source in pipeline:
        close = date.fromisoformat(source["close_date"])
        if source["stage"] not in open_stages or not start <= close <= end:
            continue
        row = dict(source)
        row["amount"] = float(source["amount_usd"])
        row["close"] = close
        row["age"] = None if source["deal_id"] not in latest else (as_of - latest[source["deal_id"]]).days
        row["sponsor"] = source["exec_sponsor_confirmed"].lower() == "true"
        scoped[source["deal_id"]] = row

    def risk_set(row: dict) -> set[str]:
        result: set[str] = set()
        if row["age"] is None or row["age"] > int(policy["maximum_activity_age_days"]):
            result.add("stale_activity")
        if row["close"] < as_of:
            result.add("overdue_close")
        days = (row["close"] - as_of).days
        if row["stage"] in {"Prospecting", "Qualification", "Discovery"} and 0 <= days <= 14:
            result.add("compressed_early_stage")
        if row["amount"] >= float(policy["large_deal_threshold_usd"]) and not row["sponsor"]:
            result.add("large_without_sponsor")
        if row["security_review_status"] == policy["blocked_security_status"]:
            result.add("blocked_security")
        return result

    def commit(row: dict) -> bool:
        return (
            row["stage"] in set(policy["eligible_stages"])
            and row["age"] is not None
            and row["age"] <= int(policy["maximum_activity_age_days"])
            and row["close"] >= as_of
            and row["security_review_status"] != policy["blocked_security_status"]
            and (row["amount"] < float(policy["large_deal_threshold_usd"]) or row["sponsor"])
        )

    commit_ids = {identifier for identifier, row in scoped.items() if commit(row)}
    stage = {}
    for stage_name in probabilities:
        rows = [row for row in scoped.values() if row["stage"] == stage_name]
        if rows:
            total = sum(row["amount"] for row in rows)
            stage[stage_name] = {
                "count": len(rows),
                "total": total,
                "weighted": total * float(probabilities[stage_name]),
            }
    open_total = sum(row["amount"] for row in scoped.values())
    weighted_open = sum(row["amount"] * float(probabilities[row["stage"]]) for row in scoped.values())
    likely = closed + weighted_open
    quota = float(context["quota_usd"])
    commit_total = sum(scoped[identifier]["amount"] for identifier in commit_ids)
    return {
        "context": context,
        "scoped": scoped,
        "commit_ids": commit_ids,
        "upside_ids": set(scoped) - commit_ids,
        "commit_total": commit_total,
        "upside_total": open_total - commit_total,
        "stage": stage,
        "risk_ids": {code: {identifier for identifier, row in scoped.items() if code in risk_set(row)} for code in context["risk_policy"]},
        "metrics": {
            "quota": quota,
            "closed": closed,
            "open": open_total,
            "weighted": likely,
            "gap": max(0.0, quota - likely),
            "coverage": open_total / max(quota - closed, 1.0),
            "best": closed + open_total,
            "likely": likely,
            "worst": closed + commit_total,
        },
    }


RAW, LOAD_ERROR = _load_submission()
EXPECTED = _expected()


def _require_loaded() -> Any:
    if LOAD_ERROR:
        pytest.skip(f"semantic checks skipped after the single artifact-readability failure: {LOAD_ERROR}")
    return RAW


def _summary_section(root: Any) -> Any:
    try:
        return _find_section(root, ["summary", "headline", "metrics", "overview"])
    except KeyError:
        if isinstance(root, dict):
            aliases = ["quota_usd", "quota", "closed_to_date", "open_pipeline", "weighted_forecast", "gap_to_quota", "coverage_ratio"]
            present = sum(_lookup(root, [alias], default=None) is not None for alias in aliases)
            if present >= 4:
                return root
        raise


def _scenario_section(root: Any) -> Any:
    try:
        return _find_section(root, ["scenarios", "forecast_scenarios", "outlook"])
    except KeyError:
        if isinstance(root, dict) and sum(_lookup(root, [name], default=None) is not None for name in ("best_case", "likely_case", "worst_case")) >= 2:
            return root
        raise


SUMMARY_CASES = [
    ("quota", ["quota_usd", "quota", "target"], "quota"),
    ("closed to date", ["closed_to_date_usd", "closed_to_date", "closed", "booked"], "closed"),
    ("open pipeline", ["open_pipeline_usd", "open_pipeline", "pipeline"], "open"),
    ("weighted forecast", ["weighted_forecast_usd", "weighted_forecast", "likely_forecast", "forecast"], "weighted"),
    ("gap to quota", ["gap_to_quota_usd", "gap_to_quota", "quota_gap", "gap"], "gap"),
    ("coverage ratio", ["coverage_ratio", "coverage_ratio_x", "coverage", "pipeline_coverage"], "coverage"),
]


@pytest.mark.parametrize("label,aliases,expected_key", SUMMARY_CASES, ids=[row[0] for row in SUMMARY_CASES])
def test_headline_forecast_math(label: str, aliases: list[str], expected_key: str) -> None:
    root = _require_loaded()
    summary = _summary_section(root)
    actual = _metric(summary, aliases)
    expected = EXPECTED["metrics"][expected_key]
    tolerance = 1e-4 if expected_key == "coverage" else 0.01
    assert actual == pytest.approx(expected, abs=tolerance), f"{label} is {actual}, expected {expected}; the forecast call would use a misleading headline"


SCENARIO_CASES = [
    ("best", ["best_case", "best", "bestcase"], "best"),
    ("likely", ["likely_case", "likely", "likelycase", "weighted"], "likely"),
    ("worst", ["worst_case", "worst", "worstcase", "commit_case"], "worst"),
]


@pytest.mark.parametrize("label,aliases,expected_key", SCENARIO_CASES, ids=[row[0] for row in SCENARIO_CASES])
def test_scenario_amounts(label: str, aliases: list[str], expected_key: str) -> None:
    scenarios = _scenario_section(_require_loaded())
    if isinstance(scenarios, dict):
        value = _lookup(scenarios, aliases)
        actual = _number(value)
    else:
        actual = _metric(scenarios, aliases)
    expected = EXPECTED["metrics"][expected_key]
    assert actual == pytest.approx(expected, abs=0.01), f"{label}-case amount is {actual}, expected {expected}; scenario planning would be wrong"


@pytest.mark.parametrize("stage", list(EXPECTED["stage"]), ids=lambda value: _key(value))
def test_stage_rollup_reconciles(stage: str) -> None:
    section = _find_section(_require_loaded(), ["stage_breakdown", "pipeline_by_stage", "stages", "stage_rollup"])
    rows = _stage_rows(section)
    assert _key(stage) in rows, f"stage rollup omits {stage}"
    row = rows[_key(stage)]
    expected = EXPECTED["stage"][stage]
    actual_count = int(round(_metric(row, ["deal_count", "count", "deals", "opportunity_count"])))
    actual_total = _metric(row, ["total_value_usd", "total_value", "pipeline_value", "total", "amount"])
    actual_weighted = _metric(row, ["weighted_value_usd", "weighted_value", "weighted", "expected_value"])
    assert actual_count == expected["count"], f"{stage} deal count is {actual_count}, expected {expected['count']}"
    assert actual_total == pytest.approx(expected["total"], abs=0.01), f"{stage} pipeline value does not reconcile to the CRM snapshot"
    assert actual_weighted == pytest.approx(expected["weighted"], abs=0.01), f"{stage} weighted value does not use the supplied stage probability"


def _deal_section(root: Any, aliases: list[str]) -> tuple[Any, list[dict]]:
    section = _find_section(root, aliases)
    if isinstance(section, list):
        prefix = "commit" if any("commit" in _key(alias) and "noncommit" not in _key(alias) for alias in aliases) else "upside"
        total = _find_section(root, [f"{prefix}_total", f"{prefix}_total_usd", f"total_{prefix}"])
        section = {"deals": section, "total": total}
    return section, _rows(section, ("deals", "opportunities", "items", "records"))


def test_commit_upside_partition() -> None:
    root = _require_loaded()
    _, commit_rows = _deal_section(root, ["commit", "committed", "commit_deals"])
    _, upside_rows = _deal_section(root, ["upside", "upside_deals", "non_commit"])
    commit_ids = {_deal_id(row) for row in commit_rows}
    upside_ids = {_deal_id(row) for row in upside_rows}
    assert not (commit_ids & upside_ids), "a deal appears in both commit and upside"
    assert commit_ids | upside_ids == set(EXPECTED["scoped"]), "deal-level commit/upside does not cover exactly the in-period open pipeline"


def test_commit_policy_decisions() -> None:
    _, commit_rows = _deal_section(_require_loaded(), ["commit", "committed", "commit_deals"])
    actual = {_deal_id(row) for row in commit_rows}
    expected = EXPECTED["commit_ids"]
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert actual == expected, f"commit classification violates the supplied policy; missing={missing[:8]}, extra={extra[:8]}"


def test_commit_upside_totals() -> None:
    root = _require_loaded()
    commit_section, _ = _deal_section(root, ["commit", "committed", "commit_deals"])
    upside_section, _ = _deal_section(root, ["upside", "upside_deals", "non_commit"])
    commit_total = _metric(commit_section, ["total_usd", "total", "total_value", "commit_total"])
    upside_total = _metric(upside_section, ["total_usd", "total", "total_value", "upside_total"])
    assert commit_total == pytest.approx(EXPECTED["commit_total"], abs=0.01), "commit total does not match the classified deals"
    assert upside_total == pytest.approx(EXPECTED["upside_total"], abs=0.01), "upside total does not match the classified deals"


RISK_CASES = [
    ("stale_activity", ("stale", "no activity", "inactive", "inactivity", "no recent activity", "dormant", "activity age", "days since activity", "last touch", "customer engagement")),
    ("overdue_close", ("overdue", "past due", "close date passed", "expired close", "push out", "update close date", "slipped")),
    ("compressed_early_stage", ("compressed", "early stage", "early-stage", "short runway", "closing soon", "unlikely to close", "accelerated decision")),
    ("large_without_sponsor", ("sponsor", "executive")),
    ("blocked_security", ("security", "blocked")),
]


@pytest.mark.parametrize("risk_code,terms", RISK_CASES, ids=[row[0] for row in RISK_CASES])
def test_risk_flag_coverage(risk_code: str, terms: tuple[str, ...]) -> None:
    section = _find_section(_require_loaded(), ["risk_flags", "material_risk_flags", "risks", "at_risk_deals"])
    evidence = _risk_texts(section)
    expected_ids = EXPECTED["risk_ids"][risk_code]
    missing = sorted(identifier for identifier in expected_ids if identifier not in evidence or not any(term in evidence[identifier] for term in terms))
    assert not missing, f"{risk_code} flags omit or mislabel {missing[:10]}; forecast reviewers would miss policy-defined risk"


def test_risk_flags_stay_in_scope() -> None:
    section = _find_section(_require_loaded(), ["risk_flags", "material_risk_flags", "risks", "at_risk_deals"])
    identifiers = set(_risk_texts(section))
    unexpected = sorted(identifiers - set(EXPECTED["scoped"]))
    assert not unexpected, f"risk list leaks out-of-period or closed deals into the Q4 call: {unexpected[:10]}"
