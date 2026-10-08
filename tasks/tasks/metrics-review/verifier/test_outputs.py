from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"
CURRENT = "2026-08"
PREVIOUS = "2026-07"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


FIELD_ALIASES = {
    "current": {"current", "currentvalue", "actual", "august", "aug", "reviewperiodvalue"},
    "previous": {"previous", "previousvalue", "prior", "july", "jul", "comparison", "comparisonvalue"},
    "target": {"target", "goal", "objective", "targetvalue"},
    "status": {"status", "health", "targetstatus", "assessment", "trafficlight"},
    "change": {"change", "changepct", "changepercent", "mom", "momchange", "monthovermonth", "percentchange", "relativechange", "delta"},
    "hierarchy": {"hierarchy", "hierarchylevel", "level", "metriclevel", "tier"},
}

SECTION_ALIASES = {
    "summary": {"summary", "executivesummary", "overview", "healthsummary"},
    "scorecard": {"scorecard", "metricscorecard", "metrics", "metricreview"},
    "actions": {"actions", "recommendedactions", "prioritizedactions", "recommendations", "nextsteps"},
    "alerts": {"alerts", "alertrecommendations", "monitoringalerts", "monitoringrecommendations"},
    "caveats": {"caveats", "datacaveats", "contextandcaveats", "limitations", "dataquality", "datanotes"},
}

STATUS_ALIASES = {
    "ontrack": "on_track", "green": "on_track", "healthy": "on_track", "met": "on_track",
    "hit": "on_track", "ontarget": "on_track", "achieved": "on_track",
    "atrisk": "at_risk", "amber": "at_risk", "yellow": "at_risk", "needsattention": "at_risk",
    "near": "at_risk", "watch": "at_risk",
    "miss": "miss", "missed": "miss", "offtrack": "miss", "red": "miss", "unhealthy": "miss",
}


def load_output() -> object:
    assert OUTPUT_PATH.is_file(), "output.json is missing, so the monthly review cannot be used"
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")


def load_output_optional() -> object | None:
    """Avoid cascading one missing/parse defect into every semantic criterion."""
    if not OUTPUT_PATH.is_file():
        return None
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def find_sections(doc: object, section: str) -> list[object]:
    aliases = SECTION_ALIASES[section]
    found: list[object] = []
    for node in walk(doc):
        if isinstance(node, dict):
            for key, value in node.items():
                if norm(key) in aliases:
                    found.append(value)
    return found


def nonempty_size(value: object) -> int:
    if isinstance(value, (list, dict, str)):
        return len(value)
    return 1 if value is not None else 0


def metric_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for row in read_csv("metric_definitions.csv"):
        metric_id = row["metric_id"]
        for label in (metric_id, row["display_name"]):
            aliases[norm(label)] = metric_id
        aliases[norm(metric_id.replace("rate", ""))] = metric_id
    aliases.update({
        "nsm": "weekly_value_teams",
        "valueteams": "weekly_value_teams",
        "weeklyactiveteams": "weekly_value_teams",
        "retention": "d30_retention_rate",
        "d30retention": "d30_retention_rate",
        "activation": "activation_rate",
        "paidconversion": "paid_conversion_rate",
        "sessionerrorrate": "error_rate",
        "automationadoption": "automation_adoption_rate",
        "supportticketrate": "support_tickets_per_100_active_teams",
        "coreactions": "core_actions_per_active_team",
    })
    return aliases


def identify_metric(value: object, aliases: dict[str, str]) -> str | None:
    candidate = norm(value)
    if candidate in aliases:
        return aliases[candidate]
    for alias, metric_id in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if len(alias) >= 8 and alias in candidate:
            return metric_id
    return None


def extract_metric_records(doc: object) -> dict[str, list[dict]]:
    aliases = metric_aliases()
    records: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, int]] = set()

    def add(metric_id: str, record: dict) -> None:
        marker = (metric_id, id(record))
        if marker not in seen:
            records[metric_id].append(record)
            seen.add(marker)

    for node in walk(doc):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            key_metric = identify_metric(key, aliases)
            if key_metric and isinstance(value, dict):
                merged = dict(value)
                merged.setdefault("metric", key)
                add(key_metric, merged)
        metric_id = None
        for key, value in node.items():
            if norm(key) in {"metric", "metricid", "metricname", "name", "kpi", "indicator"}:
                metric_id = identify_metric(value, aliases)
                if metric_id:
                    break
        if metric_id:
            add(metric_id, node)
    return records


def get_field(record: dict, field: str) -> tuple[object | None, str | None]:
    aliases = FIELD_ALIASES[field]
    for key, value in record.items():
        if norm(key) in aliases:
            return value, norm(key)
    return None, None


def parse_number(value: object) -> tuple[float | None, bool]:
    if isinstance(value, bool):
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False
    if isinstance(value, str):
        percent = "%" in value
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
        if match:
            return float(match.group(0).replace(",", "")), percent
    return None, False


def normalize_metric_number(value: object, unit: str) -> float | None:
    number, explicit_percent = parse_number(value)
    if number is None:
        return None
    if unit == "rate" and (explicit_percent or abs(number) > 1.5):
        return number / 100.0
    return number


def choose_scorecard_record(records: list[dict]) -> dict | None:
    best = None
    best_score = -1
    for record in records:
        score = sum(get_field(record, field)[0] is not None for field in ("current", "previous", "target", "status", "change"))
        if score > best_score:
            best, best_score = record, score
    # Alert or narrative objects may mention a metric by name. Treat an object as
    # a scorecard row only when it carries at least three scorecard dimensions.
    return best if best_score >= 3 else None


def expected_values() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = read_csv("weekly_metric_observations.csv")
    definitions = {row["metric_id"]: row for row in read_csv("metric_definitions.csv")}
    targets = {row["metric_id"]: row for row in read_csv("monthly_targets.csv")}

    def aggregate(metric_id: str, period: str) -> float:
        selected = [row for row in rows if row["metric_id"] == metric_id and row["week_start"].startswith(period)]
        method = definitions[metric_id]["monthly_aggregation"]
        if method == "average_weekly_sum":
            weekly: dict[str, float] = defaultdict(float)
            for row in selected:
                weekly[row["week_start"]] += float(row["numerator"])
            return sum(weekly.values()) / len(weekly)
        numerator = sum(float(row["numerator"]) for row in selected)
        denominator = sum(float(row["denominator"]) for row in selected)
        return numerator / denominator * (100.0 if method == "weighted_ratio_scaled" else 1.0)

    expected: dict[str, dict] = {}
    for metric_id, definition in definitions.items():
        current = aggregate(metric_id, CURRENT)
        previous = aggregate(metric_id, PREVIOUS)
        target = float(targets[metric_id]["target"])
        band = float(targets[metric_id]["at_risk_relative_band"])
        if definition["direction"] == "higher":
            status = "on_track" if current >= target else ("at_risk" if current >= target * (1 - band) else "miss")
        else:
            status = "on_track" if current <= target else ("at_risk" if current <= target * (1 + band) else "miss")
        expected[metric_id] = {
            "current": current,
            "previous": previous,
            "target": target,
            "relative_change_pct": (current / previous - 1) * 100,
            "absolute_change": current - previous,
            "status": status,
            "unit": definition["unit"],
            "hierarchy": definition["hierarchy_level"],
        }
    return expected, definitions


def normalize_status(value: object) -> str | None:
    candidate = norm(value)
    if candidate in STATUS_ALIASES:
        return STATUS_ALIASES[candidate]
    for alias, status in STATUS_ALIASES.items():
        if alias in candidate:
            return status
    return None


def close_enough(actual: float, expected: float, unit: str) -> bool:
    if unit == "teams":
        return math.isclose(actual, expected, abs_tol=1.0)
    if unit == "rate":
        return math.isclose(actual, expected, abs_tol=0.005)
    return math.isclose(actual, expected, rel_tol=0.0075, abs_tol=0.05)


def selected_records(doc: object) -> tuple[dict[str, dict], dict[str, dict]]:
    extracted = extract_metric_records(doc)
    selected = {metric_id: choose_scorecard_record(rows) for metric_id, rows in extracted.items()}
    return {metric_id: row for metric_id, row in selected.items() if row is not None}, extracted


def test_current_previous_and_targets():
    """Criterion: scorecard_correctness."""
    doc = load_output_optional()
    if doc is None:
        return
    records, _ = selected_records(doc)
    expected, _ = expected_values()
    assert set(expected).issubset(records), "not all source-defined metrics have a usable scorecard record"
    problems = []
    for metric_id, exp in expected.items():
        record = records[metric_id]
        for field in ("current", "previous", "target"):
            raw, _ = get_field(record, field)
            actual = normalize_metric_number(raw, exp["unit"])
            if actual is None or not close_enough(actual, exp[field], exp["unit"]):
                problems.append(f"{metric_id}.{field}={raw!r}, expected about {exp[field]:.6g}")
    assert not problems, "weighted monthly values are misleading: " + "; ".join(problems)


def test_changes_and_statuses():
    """Criterion: scorecard_correctness."""
    doc = load_output_optional()
    if doc is None:
        return
    records, _ = selected_records(doc)
    expected, _ = expected_values()
    assert set(expected).issubset(records), "status and change cannot be checked because scorecard coverage is incomplete"
    problems = []
    for metric_id, exp in expected.items():
        record = records[metric_id]
        status_raw, _ = get_field(record, "status")
        if normalize_status(status_raw) != exp["status"]:
            problems.append(f"{metric_id}.status={status_raw!r}, expected {exp['status']}")
        change_raw, change_key = get_field(record, "change")
        change, explicit_percent = parse_number(change_raw)
        valid_change = False
        if change is not None:
            candidates = [exp["relative_change_pct"]]
            if exp["unit"] == "rate":
                candidates.append(exp["absolute_change"] * 100)
                candidates.append(exp["absolute_change"])
            elif exp["unit"] in {"teams", "ratio", "per_100"}:
                candidates.append(exp["absolute_change"])
            values_to_try = [change]
            if not explicit_percent and change_key in {"relativechange", "delta"} and abs(change) <= 1:
                values_to_try.append(change * 100)
            valid_change = any(
                math.isclose(value, candidate, rel_tol=.035, abs_tol=.12)
                for value in values_to_try for candidate in candidates
            )
        if not valid_change:
            problems.append(f"{metric_id}.change={change_raw!r} is inconsistent with current versus previous")
    assert not problems, "scorecard trends or target states are inconsistent: " + "; ".join(problems)


def test_scope_and_hierarchy_consistency():
    """Criterion: scope_consistency."""
    doc = load_output_optional()
    if doc is None:
        return
    records, extracted = selected_records(doc)
    expected, definitions = expected_values()
    assert set(records) == set(expected), (
        "the scorecard must cover each source-defined metric exactly once at the semantic level"
    )
    duplicate_scorecards = []
    for metric_id, candidates in extracted.items():
        rich = [row for row in candidates if sum(get_field(row, field)[0] is not None for field in ("current", "previous", "target")) >= 2]
        unique_payloads = {json.dumps(row, sort_keys=True, default=str) for row in rich}
        if len(unique_payloads) > 1:
            duplicate_scorecards.append(metric_id)
    assert not duplicate_scorecards, f"conflicting duplicate scorecard records found for {duplicate_scorecards}"

    nsm_record = records["weekly_value_teams"]
    hierarchy_raw, _ = get_field(nsm_record, "hierarchy")
    hierarchy_text = norm(hierarchy_raw) if hierarchy_raw is not None else ""
    document_text = norm(json.dumps(doc, ensure_ascii=False))
    assert "northstar" in hierarchy_text or (
        "northstar" in document_text and "weeklyvalueteams" in document_text
    ), "weekly value teams is not identifiable as the North Star in the metric hierarchy"
    assert all(definitions[metric_id]["unit"] for metric_id in records), "source metric units are incomplete"
