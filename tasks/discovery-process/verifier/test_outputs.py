from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any

import pytest


DATA = Path(os.environ.get("DISCOVERY_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("DISCOVERY_OUTPUT_PATH", "/root/results/output.json"))
_MISSING = object()


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _yes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    normalized = _key(value)
    if normalized in {"true", "yes", "y", "1", "pass", "passed", "reached", "validated", "go"}:
        return True
    if normalized in {"false", "no", "n", "0", "fail", "failed", "notreached", "notvalidated"}:
        return False
    raise ValueError(f"cannot interpret as boolean/status: {value!r}")


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not numeric evidence")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for alias in ("value", "count", "rate", "percentage", "percentage_points", "score", "total"):
            found = _lookup(value, [alias], default=None)
            if found is not None:
                return _number(found)
        raise ValueError(f"mapping contains no numeric wrapper: {value!r}")
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "").replace("%", "")
        cleaned = cleaned.replace("percentage points", "").replace("points", "").replace("pp", "")
        return float(cleaned.strip())
    raise ValueError(f"unsupported numeric representation: {value!r}")


def _rate_pct(value: Any) -> float:
    number = _number(value)
    return number * 100.0 if 0 < abs(number) <= 1 else number


def _pp(value: Any) -> float:
    number = _number(value)
    return number * 100.0 if 0 < abs(number) <= 1 else number


def _lookup(mapping: Any, aliases: list[str] | tuple[str, ...], default: Any = _MISSING) -> Any:
    if isinstance(mapping, dict):
        normalized = {_key(key): value for key, value in mapping.items()}
        for alias in aliases:
            if _key(alias) in normalized:
                return normalized[_key(alias)]
    if default is not _MISSING:
        return default
    raise KeyError(f"missing a field equivalent to one of {aliases}")


def _find_value(root: Any, aliases: list[str] | tuple[str, ...], max_depth: int = 8) -> Any:
    targets = {_key(alias) for alias in aliases}
    queue: list[tuple[Any, int]] = [(root, 0)]
    while queue:
        node, depth = queue.pop(0)
        if isinstance(node, dict):
            for key, value in node.items():
                if _key(key) in targets:
                    return value
            if depth < max_depth:
                queue.extend((value, depth + 1) for value in node.values())
        elif isinstance(node, list) and depth < max_depth:
            queue.extend((value, depth + 1) for value in node)
    raise KeyError(f"missing content equivalent to one of {aliases}")


def _metric(root: Any, aliases: list[str] | tuple[str, ...]) -> float:
    return _number(_find_value(root, aliases))


def _collect_ids(value: Any, pattern: str) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if re.fullmatch(pattern, str(key), re.IGNORECASE):
                    found.append(str(key).upper())
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, str):
            found.extend(item.upper() for item in re.findall(pattern, node, re.IGNORECASE))

    walk(value)
    return list(dict.fromkeys(found))


def _entity_rows(root: Any, expected_ids: set[str], id_aliases: tuple[str, ...]) -> dict[str, dict]:
    expected_by_key = {_key(identifier): identifier for identifier in expected_ids}
    rows: dict[str, dict] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            identifier = _lookup(node, id_aliases, default=None)
            if identifier is not None and _key(identifier) in expected_by_key:
                rows.setdefault(expected_by_key[_key(identifier)], node)
            for key, child in node.items():
                if _key(key) in expected_by_key and isinstance(child, dict):
                    row = dict(child)
                    row.setdefault(id_aliases[0], key)
                    rows.setdefault(expected_by_key[_key(key)], row)
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(root)
    return rows


def _load_submission() -> tuple[Any, str | None]:
    if not OUTPUT.is_file():
        return None, f"requested artifact is missing: {OUTPUT}"
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"
    if not isinstance(value, dict):
        return None, "output.json must be a JSON object to function as a decision record"
    return value, None


@pytest.fixture(scope="module")
def submission() -> tuple[Any, str | None]:
    return _load_submission()


def _usable_or_skip(submission: tuple[Any, str | None]) -> Any:
    value, error = submission
    if error:
        pytest.skip(f"semantic criterion blocked by artifact readability failure: {error}")
    return value


def _expected() -> dict:
    context = json.loads((DATA / "discovery_context.json").read_text(encoding="utf-8"))
    participants = _read_csv("participants.csv")
    observations = _read_csv("interview_observations.csv")
    catalog = {row["theme_id"]: row for row in _read_csv("theme_catalog.csv")}
    tickets = _read_csv("support_tickets.csv")
    accounts = _read_csv("account_funnel.csv")
    experiment = _read_csv("experiment_results.csv")

    target = context["target_population"]
    included = [
        row
        for row in participants
        if row["status"] == target["include_interview_status"]
        and row["employee_band"] in target["participant_employee_bands"]
        and row["admin_experience"] == target["participant_admin_experience"]
    ]
    included_ids = {row["participant_id"] for row in included}
    excluded_ids = {row["participant_id"] for row in participants} - included_ids
    included_obs = [row for row in observations if row["participant_id"] in included_ids]
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for row in included_obs:
        by_theme[row["theme_id"]].append(row)
    included_tickets = [
        row
        for row in tickets
        if row["analysis_status"] == context["support_ticket_policy"]["include_analysis_status"]
    ]
    ticket_counts = Counter(row["theme_id"] for row in included_tickets)

    def frequency_score(count: int) -> int:
        for band in context["theme_prioritization"]["frequency_score_by_distinct_target_interviews"]:
            if int(band["min"]) <= count <= int(band["max"]):
                return int(band["score"])
        raise AssertionError(f"missing frequency band for {count}")

    themes = {}
    for theme_id, rows in by_theme.items():
        count = len({row["participant_id"] for row in rows})
        intensity = mean(float(row["intensity_1_to_5"]) for row in rows)
        score = frequency_score(count) * intensity * int(catalog[theme_id]["strategic_fit_1_to_5"])
        themes[theme_id] = {
            "interview_count": count,
            "mean_intensity": intensity,
            "priority_score": score,
            "support_ticket_count": ticket_counts.get(theme_id, 0),
            "observation_ids": {row["observation_id"] for row in rows},
        }
    ordered_theme_ids = sorted(themes, key=lambda item: (-themes[item]["priority_score"], item))
    for rank, theme_id in enumerate(ordered_theme_ids, start=1):
        themes[theme_id]["rank"] = rank

    ordered = sorted(included, key=lambda row: int(row["interview_order"]))
    first_seen: dict[str, int] = {}
    themes_by_participant: dict[str, set[str]] = defaultdict(set)
    for row in included_obs:
        themes_by_participant[row["participant_id"]].add(row["theme_id"])
    for participant in ordered:
        for theme_id in themes_by_participant[participant["participant_id"]]:
            first_seen.setdefault(theme_id, int(participant["interview_order"]))
    last_two = {int(row["interview_order"]) for row in ordered[-2:]}
    saturation = not any(order in last_two for order in first_seen.values()) and themes[ordered_theme_ids[0]][
        "interview_count"
    ] >= 3

    start = date.fromisoformat(target["analytics_created_from"])
    end = date.fromisoformat(target["analytics_created_through"])
    eligible = [
        row
        for row in accounts
        if start <= date.fromisoformat(row["created_date"]) <= end
        and row["employee_band"] in target["participant_employee_bands"]
        and row["admin_experience"] == target["participant_admin_experience"]
        and not _yes(row["is_internal"])
    ]
    funnel = {}
    for outcome in ("generic_validation_error", "clean_import", "no_import_attempt"):
        group = [row for row in eligible if row["import_outcome"] == outcome]
        activated = sum(_yes(row["launched_within_7d"]) for row in group)
        funnel[outcome] = {
            "account_count": len(group),
            "activated_count": activated,
            "activation_rate_pct": 100 * activated / len(group),
        }
    gap_pp = funnel["clean_import"]["activation_rate_pct"] - funnel["generic_validation_error"][
        "activation_rate_pct"
    ]

    experiment_groups = {}
    for variant in ("control", "guided_repair"):
        group = [row for row in experiment if row["variant"] == variant]
        successes = sum(
            _yes(row["valid_import_completed"])
            and int(row["help_requests"]) == 0
            and float(row["elapsed_minutes"]) <= 15
            for row in group
        )
        guardrail = sum(_yes(row["invalid_record_admitted"]) for row in group)
        experiment_groups[variant] = {
            "randomized_count": len(group),
            "primary_success_count": successes,
            "primary_success_rate_pct": 100 * successes / len(group),
            "guardrail_event_count": guardrail,
            "guardrail_rate_pct": 100 * guardrail / len(group),
        }
    uplift = (
        experiment_groups["guided_repair"]["primary_success_rate_pct"]
        - experiment_groups["control"]["primary_success_rate_pct"]
    )
    guardrail_delta = (
        experiment_groups["guided_repair"]["guardrail_rate_pct"]
        - experiment_groups["control"]["guardrail_rate_pct"]
    )
    problem_validated = (
        themes[ordered_theme_ids[0]]["interview_count"]
        >= context["problem_validation_policy"]["minimum_interviews_for_leading_theme"]
        and gap_pp
        >= context["problem_validation_policy"]["minimum_clean_vs_validation_activation_gap_percentage_points"]
    )
    primary_passed = uplift >= context["experiment_policy"]["minimum_absolute_uplift_percentage_points"]
    guardrail_passed = guardrail_delta <= context["experiment_policy"][
        "maximum_guardrail_increase_percentage_points"
    ]
    return {
        "included_ids": included_ids,
        "excluded_ids": excluded_ids,
        "saturation": saturation,
        "themes": themes,
        "top_theme_ids": ordered_theme_ids[:3],
        "eligible_count": len(eligible),
        "funnel": funnel,
        "gap_pp": gap_pp,
        "experiment": experiment_groups,
        "uplift_pp": uplift,
        "guardrail_delta_pp": guardrail_delta,
        "primary_passed": primary_passed,
        "guardrail_passed": guardrail_passed,
        "decision": "GO" if problem_validated and primary_passed and guardrail_passed else "PIVOT",
        "solution_id": "S1" if problem_validated and primary_passed and guardrail_passed else None,
    }


EXPECTED = _expected()


def test_artifact_usability(submission: tuple[Any, str | None]) -> None:
    root, error = submission
    assert error is None, error
    anchors = {
        "problem framing": ["refined_problem_statement", "refined_hypothesis", "problem_statement"],
        "research scope": ["included_participant_ids", "included_participants", "eligible_participant_ids"],
        "pain-point synthesis": ["themes", "pain_points", "top_pain_point_ids", "prioritized_themes"],
        "funnel evidence": ["funnel_analysis", "funnel", "activation_gap", "activation_rate"],
        "experiment": ["experiment", "experiment_results", "primary_uplift", "uplift_percentage_points"],
        "decision": ["call", "decision_call", "roadmap_decision"],
        "next steps": ["next_steps", "actions", "follow_up_plan"],
    }
    missing = []
    for label, aliases in anchors.items():
        try:
            _find_value(root, aliases)
        except KeyError:
            missing.append(label)
    assert not missing, f"decision record is readable but lacks requested content: {missing}"


def test_research_scope_and_saturation(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    included_value = _find_value(
        root, ["included_participant_ids", "included_interview_ids", "included_participants", "eligible_participant_ids"]
    )
    excluded_value = _find_value(root, ["excluded_participants", "excluded_participant_ids", "excluded_interviews"])
    included = set(_collect_ids(included_value, r"P\d{2}"))
    excluded = set(_collect_ids(excluded_value, r"P\d{2}"))
    saturation_value = _find_value(root, ["saturation", "research_saturation", "saturation_status"])
    actual_saturation = _yes(_lookup(saturation_value, ["status", "reached", "value"], default=saturation_value))
    errors = []
    if included != EXPECTED["included_ids"]:
        errors.append(f"included participant IDs are {sorted(included)}, expected {sorted(EXPECTED['included_ids'])}")
    if excluded != EXPECTED["excluded_ids"]:
        errors.append(f"excluded participant IDs are {sorted(excluded)}, expected {sorted(EXPECTED['excluded_ids'])}")
    if actual_saturation != EXPECTED["saturation"]:
        errors.append(f"saturation is {actual_saturation}, expected {EXPECTED['saturation']} from interview order")
    assert not errors, "; ".join(errors)


def test_prioritized_theme_evidence(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    expected_ids = set(EXPECTED["top_theme_ids"])
    rows = _entity_rows(root, expected_ids, ("theme_id", "pain_point_id", "code", "id"))
    errors = []
    for theme_id in EXPECTED["top_theme_ids"]:
        if theme_id not in rows:
            errors.append(f"missing prioritized theme {theme_id}")
            continue
        row = rows[theme_id]
        expected = EXPECTED["themes"][theme_id]
        checks = [
            ("interview_count", ["interview_count", "distinct_interview_count", "participant_count"], float),
            ("mean_intensity", ["mean_intensity", "average_intensity", "intensity_score"], float),
            ("support_ticket_count", ["support_ticket_count", "ticket_count", "support_count"], float),
            ("priority_score", ["priority_score", "prioritization_score", "score"], float),
            ("rank", ["rank", "priority_rank"], float),
        ]
        for label, aliases, _ in checks:
            try:
                actual = _metric(row, aliases)
            except (KeyError, ValueError) as exc:
                errors.append(f"{theme_id} lacks usable {label}: {exc}")
                continue
            tolerance = 0.02 if label in {"mean_intensity", "priority_score"} else 0.001
            if abs(actual - expected[label]) > tolerance:
                errors.append(f"{theme_id} {label} is {actual}, expected {expected[label]:.4f}")
        trace_value = _lookup(row, ["observation_ids", "evidence_ids", "source_ids", "interview_observation_ids"], default=[])
        trace_ids = set(_collect_ids(trace_value, r"O\d{3}"))
        if not trace_ids or not trace_ids.issubset(expected["observation_ids"]):
            errors.append(f"{theme_id} does not trace its calculation to valid observation IDs")
    assert not errors, "; ".join(errors)


def test_funnel_group_metrics(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    expected_ids = set(EXPECTED["funnel"])
    rows = _entity_rows(root, expected_ids, ("import_outcome", "group", "cohort", "name", "id"))
    errors = []
    for outcome, expected in EXPECTED["funnel"].items():
        if outcome not in rows:
            errors.append(f"missing funnel group {outcome}")
            continue
        row = rows[outcome]
        try:
            count = _metric(row, ["account_count", "accounts", "denominator", "n", "total"])
            activated = _metric(
                row, ["activated_within_7d_count", "activated_count", "launch_count", "success_count"]
            )
            rate = _rate_pct(_find_value(row, ["activation_rate_pct", "activation_rate", "launch_rate_pct", "rate"]))
        except (KeyError, ValueError) as exc:
            errors.append(f"{outcome} lacks usable metrics: {exc}")
            continue
        if int(round(count)) != expected["account_count"]:
            errors.append(f"{outcome} account count is {count}, expected {expected['account_count']}")
        if int(round(activated)) != expected["activated_count"]:
            errors.append(f"{outcome} activated count is {activated}, expected {expected['activated_count']}")
        if abs(rate - expected["activation_rate_pct"]) > 0.05:
            errors.append(f"{outcome} activation rate is {rate:.4f}%, expected {expected['activation_rate_pct']:.4f}%")
    assert not errors, "; ".join(errors)


def test_activation_gap(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    eligible = _metric(root, ["eligible_account_count", "target_account_count", "analysis_account_count"])
    gap = _pp(
        _find_value(
            root,
            [
                "clean_minus_validation_activation_gap_percentage_points",
                "activation_gap_percentage_points",
                "clean_vs_validation_gap_pp",
                "activation_gap_pp",
            ],
        )
    )
    assert int(round(eligible)) == EXPECTED["eligible_count"], (
        f"eligible target-account count is {eligible}, expected {EXPECTED['eligible_count']}"
    )
    assert abs(gap - EXPECTED["gap_pp"]) <= 0.05, (
        f"clean-versus-validation activation gap is {gap:.4f} points, expected {EXPECTED['gap_pp']:.4f}"
    )


def test_experiment_variant_metrics(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    expected_ids = set(EXPECTED["experiment"])
    rows = _entity_rows(root, expected_ids, ("variant", "arm", "group", "name", "id"))
    errors = []
    for variant, expected in EXPECTED["experiment"].items():
        if variant not in rows:
            errors.append(f"missing experiment arm {variant}")
            continue
        row = rows[variant]
        try:
            randomized = _metric(row, ["randomized_count", "sample_size", "participant_count", "n"])
            successes = _metric(row, ["primary_success_count", "success_count", "completed_unaided_count"])
            success_rate = _rate_pct(
                _find_value(row, ["primary_success_rate_pct", "primary_success_rate", "success_rate_pct", "success_rate"])
            )
            guardrail_count = _metric(row, ["guardrail_event_count", "invalid_record_count", "safety_event_count"])
            guardrail_rate = _rate_pct(
                _find_value(row, ["guardrail_rate_pct", "guardrail_rate", "invalid_record_rate_pct"])
            )
        except (KeyError, ValueError) as exc:
            errors.append(f"{variant} lacks usable experiment metrics: {exc}")
            continue
        if int(round(randomized)) != expected["randomized_count"]:
            errors.append(f"{variant} randomized count is {randomized}, expected {expected['randomized_count']}")
        if int(round(successes)) != expected["primary_success_count"]:
            errors.append(f"{variant} primary successes are {successes}, expected {expected['primary_success_count']}")
        if abs(success_rate - expected["primary_success_rate_pct"]) > 0.05:
            errors.append(f"{variant} primary rate is {success_rate:.4f}%, expected {expected['primary_success_rate_pct']:.4f}%")
        if int(round(guardrail_count)) != expected["guardrail_event_count"]:
            errors.append(f"{variant} guardrail events are {guardrail_count}, expected {expected['guardrail_event_count']}")
        if abs(guardrail_rate - expected["guardrail_rate_pct"]) > 0.05:
            errors.append(f"{variant} guardrail rate is {guardrail_rate:.4f}%, expected {expected['guardrail_rate_pct']:.4f}%")
    assert not errors, "; ".join(errors)


def test_experiment_thresholds_and_decision(submission: tuple[Any, str | None]) -> None:
    root = _usable_or_skip(submission)
    uplift = _pp(
        _find_value(
            root,
            ["absolute_primary_uplift_percentage_points", "primary_uplift_percentage_points", "uplift_pp"],
        )
    )
    guardrail_delta = _pp(
        _find_value(root, ["guardrail_delta_percentage_points", "guardrail_increase_pp", "guardrail_delta_pp"])
    )
    primary_passed = _yes(_find_value(root, ["primary_threshold_passed", "primary_passed", "uplift_passed"]))
    guardrail_passed = _yes(_find_value(root, ["guardrail_passed", "safety_guardrail_passed"]))
    call_value = _find_value(root, ["decision_call", "roadmap_decision", "call"])
    if isinstance(call_value, dict):
        call_value = _lookup(call_value, ["call", "value", "status", "recommendation"])
    solution_value = _find_value(root, ["selected_solution_id", "recommended_solution_id", "chosen_solution_id"])
    errors = []
    if abs(uplift - EXPECTED["uplift_pp"]) > 0.05:
        errors.append(f"primary uplift is {uplift:.4f} points, expected {EXPECTED['uplift_pp']:.4f}")
    if abs(guardrail_delta - EXPECTED["guardrail_delta_pp"]) > 0.05:
        errors.append(
            f"guardrail delta is {guardrail_delta:.4f} points, expected {EXPECTED['guardrail_delta_pp']:.4f}"
        )
    if primary_passed != EXPECTED["primary_passed"]:
        errors.append(f"primary threshold pass is {primary_passed}, expected {EXPECTED['primary_passed']}")
    if guardrail_passed != EXPECTED["guardrail_passed"]:
        errors.append(f"guardrail pass is {guardrail_passed}, expected {EXPECTED['guardrail_passed']}")
    if _key(call_value) != _key(EXPECTED["decision"]):
        errors.append(f"decision call is {call_value!r}, expected {EXPECTED['decision']}")
    if _key(solution_value) != _key(EXPECTED["solution_id"]):
        errors.append(f"selected solution is {solution_value!r}, expected {EXPECTED['solution_id']}")
    assert not errors, "; ".join(errors)
