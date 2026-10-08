from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "prioritization_brief.json"
CUTOFF = datetime.fromisoformat("2026-08-31T23:59:59")
CAPACITY = 14.0
PROBLEM_ID_RE = re.compile(r"^P\d{2}$", re.I)
INITIATIVE_ID_RE = re.compile(r"^I\d{2}$", re.I)


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def read_output() -> object | None:
    if not OUTPUT.is_file():
        return None
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def direct_entity_id(record: dict, kind: str) -> str | None:
    pattern = PROBLEM_ID_RE if kind == "problem" else INITIATIVE_ID_RE
    preferred = (
        {"problemid", "needid", "opportunityid", "customerproblemid"}
        if kind == "problem"
        else {"initiativeid", "ideaid", "proposalid", "projectid"}
    )
    for key, value in record.items():
        if norm_key(key) in preferred and isinstance(value, str) and pattern.fullmatch(value.strip()):
            return value.strip().upper()
    for value in record.values():
        if isinstance(value, str) and pattern.fullmatch(value.strip()):
            return value.strip().upper()
    return None


def walk_records(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_records(child)


FIELD_ALIASES = {
    "opportunity": {"opportunity", "opportunityscore", "opportunityvalue", "score"},
    "importance": {"importance", "weightedimportance", "importanceaverage", "avgimportance"},
    "satisfaction": {"satisfaction", "weightedsatisfaction", "satisfactionaverage", "avgsatisfaction"},
    "rice": {"rice", "ricescore", "priorityscore", "score"},
    "reach": {"reach", "totalreach", "reachablecustomersq4", "customersreached"},
    "impact": {"impact", "weightedimpact", "impactpercustomer"},
    "confidence": {"confidence", "confidencepct", "confidencepercent"},
    "effort": {"effort", "effortpersonmonths", "personmonths", "effortpm"},
    "rank": {"rank", "priority", "position", "order"},
}


def field_number(record: dict, field: str) -> float | None:
    aliases = FIELD_ALIASES[field]
    for key, value in record.items():
        if norm_key(key) in aliases:
            parsed = as_number(value)
            if parsed is not None:
                return parsed
    return None


def record_quality(record: dict, kind: str) -> int:
    fields = ("opportunity", "importance", "satisfaction", "rank") if kind == "problem" else (
        "rice", "reach", "impact", "confidence", "effort", "rank"
    )
    return sum(field_number(record, field) is not None for field in fields) + len(record) // 10


def entity_records(document: object, kind: str) -> dict[str, dict]:
    candidates: dict[str, list[dict]] = defaultdict(list)
    for record in walk_records(document):
        entity_id = direct_entity_id(record, kind)
        if entity_id:
            candidates[entity_id].append(record)
    return {
        entity_id: max(rows, key=lambda row: record_quality(row, kind))
        for entity_id, rows in candidates.items()
    }


def longest_ranked_ids(value: object, kind: str) -> list[str]:
    best: list[str] = []
    if isinstance(value, list):
        ids = []
        for item in value:
            if isinstance(item, dict):
                entity_id = direct_entity_id(item, kind)
            elif isinstance(item, str):
                pattern = PROBLEM_ID_RE if kind == "problem" else INITIATIVE_ID_RE
                entity_id = item.strip().upper() if pattern.fullmatch(item.strip()) else None
            else:
                entity_id = None
            if entity_id:
                ids.append(entity_id)
        if len(ids) > len(best) and len(ids) == len(set(ids)):
            best = ids
        for child in value:
            nested = longest_ranked_ids(child, kind)
            if len(nested) > len(best):
                best = nested
    elif isinstance(value, dict):
        for child in value.values():
            nested = longest_ranked_ids(child, kind)
            if len(nested) > len(best):
                best = nested
    return best


def truthy_selection(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return norm_key(value) in {"yes", "true", "selected", "recommended", "include", "included", "q4"}
    return False


def selected_ids(document: object) -> set[str]:
    selected: set[str] = set()
    selection_keys = {
        "selected", "recommended", "inq4", "q4selected", "portfolioselected", "decision"
    }
    for record in walk_records(document):
        initiative_id = direct_entity_id(record, "initiative")
        if initiative_id and any(
            norm_key(key) in selection_keys and truthy_selection(value)
            for key, value in record.items()
        ):
            selected.add(initiative_id)

    def visit(value: object, parent_key: str = "") -> None:
        key_norm = norm_key(parent_key)
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, str(key))
        elif isinstance(value, list):
            explicit_list = (
                ("selected" in key_norm or "recommended" in key_norm or "portfolio" in key_norm)
                and ("initiative" in key_norm or "ids" in key_norm or "set" in key_norm)
            )
            if explicit_list:
                for child in value:
                    if isinstance(child, str) and INITIATIVE_ID_RE.fullmatch(child.strip()):
                        selected.add(child.strip().upper())
                    elif isinstance(child, dict):
                        entity_id = direct_entity_id(child, "initiative")
                        if entity_id:
                            selected.add(entity_id)
            for child in value:
                visit(child, parent_key)

    visit(document)
    return selected


def valid_rating(value: str) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 1 <= parsed <= 5 and str(parsed) == value.strip() else None


@lru_cache(maxsize=1)
def expected() -> dict:
    problems = {row["problem_id"]: row for row in read_csv("problem_catalog.csv")}
    weights = {row["customer_segment"]: float(row["planning_weight"]) for row in read_csv("segment_weights.csv")}
    latest = {}
    for row in read_csv("survey_responses.csv"):
        importance = valid_rating(row["importance_rating"])
        satisfaction = valid_rating(row["satisfaction_rating"])
        try:
            submitted = datetime.fromisoformat(row["submitted_at"])
        except ValueError:
            continue
        if not (
            row["account_status"] == "active"
            and row["response_status"] == "complete"
            and submitted <= CUTOFF
            and importance is not None
            and satisfaction is not None
            and row["problem_id"] in problems
            and row["customer_segment"] in weights
        ):
            continue
        key = (row["respondent_id"], row["problem_id"])
        candidate = (submitted, row["response_id"], importance, satisfaction, row["customer_segment"])
        if key not in latest or candidate[:2] > latest[key][:2]:
            latest[key] = candidate
    grouped = defaultdict(lambda: defaultdict(list))
    for (respondent_id, problem_id), (_, _, importance, satisfaction, segment) in latest.items():
        del respondent_id
        grouped[problem_id][segment].append(((importance - 1) / 4, (satisfaction - 1) / 4))
    problem_values = {}
    for problem_id in problems:
        importance = 0.0
        satisfaction = 0.0
        for segment, weight in weights.items():
            observations = grouped[problem_id][segment]
            importance += weight * sum(row[0] for row in observations) / len(observations)
            satisfaction += weight * sum(row[1] for row in observations) / len(observations)
        problem_values[problem_id] = {
            "importance": importance,
            "satisfaction": satisfaction,
            "opportunity": importance * (1 - satisfaction),
        }
    problem_order = sorted(
        problems, key=lambda pid: (-problem_values[pid]["opportunity"], -problem_values[pid]["importance"], pid)
    )

    initiative_catalog = {row["initiative_id"]: row for row in read_csv("initiative_catalog.csv")}
    reaches = defaultdict(list)
    for row in read_csv("initiative_problem_reach.csv"):
        reaches[row["initiative_id"]].append(row)
    initiative_values = {}
    for initiative_id, item in initiative_catalog.items():
        if item["planning_status"] != "candidate":
            continue
        total_reach = sum(int(row["reachable_customers_q4"]) for row in reaches[initiative_id])
        weighted = sum(
            int(row["reachable_customers_q4"]) * problem_values[row["problem_id"]]["opportunity"]
            for row in reaches[initiative_id]
        )
        impact = weighted / total_reach
        confidence = float(item["confidence_pct"]) / 100
        effort = float(item["effort_person_months"])
        initiative_values[initiative_id] = {
            "reach": total_reach,
            "impact": impact,
            "confidence": confidence,
            "effort": effort,
            "rice": total_reach * impact * confidence / effort,
            "dependencies": [value for value in item["dependency_ids"].split(";") if value],
            "exclusive_group": item["exclusive_group"] or None,
        }
    initiative_order = sorted(
        initiative_values,
        key=lambda iid: (-initiative_values[iid]["rice"], initiative_values[iid]["effort"], iid),
    )

    selected: set[str] = set()
    groups: set[str] = set()

    def closure(initiative_id: str) -> set[str]:
        result = {initiative_id}
        for dependency in initiative_values[initiative_id]["dependencies"]:
            result |= closure(dependency)
        return result

    for initiative_id in initiative_order:
        if initiative_id in selected:
            continue
        missing = closure(initiative_id) - selected
        added_effort = sum(initiative_values[item]["effort"] for item in missing)
        used = sum(initiative_values[item]["effort"] for item in selected)
        bundle_groups = {
            initiative_values[item]["exclusive_group"]
            for item in missing if initiative_values[item]["exclusive_group"]
        }
        has_internal_conflict = len(bundle_groups) != sum(
            1 for item in missing if initiative_values[item]["exclusive_group"]
        )
        if groups & bundle_groups or has_internal_conflict or used + added_effort > CAPACITY + 1e-9:
            continue
        selected |= missing
        groups |= bundle_groups
    return {
        "problem_values": problem_values,
        "problem_order": problem_order,
        "initiative_values": initiative_values,
        "initiative_order": initiative_order,
        "selected": selected,
        "initiative_catalog": initiative_catalog,
    }


def require_document() -> object:
    document = read_output()
    if document is None:
        pytest.skip("Artifact is missing or unreadable; artifact usability records the root failure.")
    return document


def reported_rank(record: dict, entity_id: str, ordered_ids: list[str]) -> int | None:
    explicit = field_number(record, "rank")
    if explicit is not None:
        return int(explicit) if explicit.is_integer() else None
    if entity_id in ordered_ids:
        return ordered_ids.index(entity_id) + 1
    return None


def test_artifact_usability_and_scope():
    assert OUTPUT.is_file(), "The requested prioritization_brief.json is missing."
    document = read_output()
    assert isinstance(document, (dict, list)), "The requested file must be readable JSON with structured content."
    problem_ids = set(entity_records(document, "problem"))
    initiative_ids = set(entity_records(document, "initiative"))
    expected_data = expected()
    assert set(expected_data["problem_order"]) <= problem_ids, (
        "The brief does not expose every catalogued customer problem, so the ranking cannot be reviewed."
    )
    assert set(expected_data["initiative_catalog"]) <= initiative_ids, (
        "The brief does not expose every proposed initiative, including the withdrawn exclusion."
    )


def test_problem_opportunity_scores():
    document = require_document()
    records = entity_records(document, "problem")
    expected_data = expected()
    mismatches = []
    for problem_id, values in expected_data["problem_values"].items():
        record = records.get(problem_id, {})
        actual = field_number(record, "opportunity")
        if actual is None or not math.isclose(actual, values["opportunity"], abs_tol=0.0015):
            mismatches.append((problem_id, actual, round(values["opportunity"], 6)))
    assert not mismatches, (
        f"Opportunity Scores do not reflect the valid latest, segment-weighted survey data: {mismatches[:5]}"
    )


def test_problem_ranking():
    document = require_document()
    records = entity_records(document, "problem")
    listed = longest_ranked_ids(document, "problem")
    expected_order = expected()["problem_order"]
    actual = [reported_rank(records.get(pid, {}), pid, listed) for pid in expected_order]
    assert actual == list(range(1, len(expected_order) + 1)), (
        f"The Opportunity Score ranking is inconsistent with the frozen research; got ranks {actual}."
    )


def test_initiative_rice_scores():
    document = require_document()
    records = entity_records(document, "initiative")
    mismatches = []
    for initiative_id, values in expected()["initiative_values"].items():
        record = records.get(initiative_id, {})
        actual = field_number(record, "rice")
        if actual is None or not math.isclose(actual, values["rice"], rel_tol=0.002, abs_tol=0.05):
            mismatches.append((initiative_id, actual, round(values["rice"], 6)))
    assert not mismatches, (
        f"RICE scores do not combine mapped opportunity, reach, confidence, and effort correctly: {mismatches[:5]}"
    )


def test_candidate_rice_ranking():
    document = require_document()
    records = entity_records(document, "initiative")
    listed = [item for item in longest_ranked_ids(document, "initiative") if item != "I14"]
    expected_order = expected()["initiative_order"]
    actual = [reported_rank(records.get(iid, {}), iid, listed) for iid in expected_order]
    assert actual == list(range(1, len(expected_order) + 1)), (
        f"The candidate initiative ranking is inconsistent with RICE; got ranks {actual}."
    )


def test_q4_selected_set():
    document = require_document()
    actual = selected_ids(document)
    desired = expected()["selected"]
    assert actual == desired, (
        f"The recommended Q4 set is {sorted(actual)}, expected {sorted(desired)} after the declared ranked walk."
    )


def test_q4_constraints_and_withdrawn_exclusion():
    document = require_document()
    actual = selected_ids(document)
    expected_data = expected()
    values = expected_data["initiative_values"]
    assert "I14" not in actual, "Withdrawn initiative I14 must not enter the Q4 recommendation."
    unknown = actual - set(values)
    assert not unknown, f"The Q4 set contains ineligible or unknown initiatives: {sorted(unknown)}"
    effort = sum(values[item]["effort"] for item in actual)
    assert effort <= CAPACITY + 1e-9, f"The Q4 set uses {effort:.1f} person-months, above the 14.0 limit."
    missing_dependencies = {
        item: sorted(set(values[item]["dependencies"]) - actual)
        for item in actual if set(values[item]["dependencies"]) - actual
    }
    assert not missing_dependencies, f"The Q4 set omits required dependencies: {missing_dependencies}"
    used_groups = [values[item]["exclusive_group"] for item in actual if values[item]["exclusive_group"]]
    assert len(used_groups) == len(set(used_groups)), "The Q4 set contains mutually exclusive alternatives."
