from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "gate_packet.json"


def _canon_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _canon_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _load_submission() -> Any:
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lookup(mapping: dict, aliases: Iterable[str]) -> Any:
    normalized = {_canon_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        key = _canon_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def _find_value(document: Any, aliases: Iterable[str]) -> Any:
    for node in _walk(document):
        if isinstance(node, dict):
            value = _lookup(node, aliases)
            if value is not None:
                return value
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if match:
            number = float(match.group())
            if "%" in value:
                number /= 100
            return number
    return None


def _submission_text(document: Any) -> str:
    return json.dumps(document, ensure_ascii=False).lower() if document is not None else ""


def _endpoint_rows(document: Any) -> dict[str, dict]:
    expected_names = {
        "EP-01": "clinically meaningful symptom recovery at week 16",
        "EP-02": "pfi 8 patient reported function response at week 16",
        "EP-03": "plasma nx 17 reduction at week 4",
        "EP-04": "clinician global improvement at week 16",
        "EP-05": "work or study days regained through week 16",
        "EP-06": "wearable derived daily step change at week 8",
    }
    found: dict[str, dict] = {}
    for node in _walk(document):
        if not isinstance(node, dict):
            continue
        identifier = _lookup(node, ["endpoint_id", "endpoint id", "id"])
        name = _lookup(node, ["endpoint_name", "endpoint", "name"])
        matched = None
        if identifier is not None:
            ident_text = str(identifier).upper().replace("_", "-")
            match = re.search(r"EP-?0?[1-6]", ident_text)
            if match:
                digits = re.search(r"[1-6]", match.group()).group()
                matched = f"EP-0{digits}"
        if matched is None and name is not None:
            normalized_name = _canon_text(name)
            for endpoint_id, expected_name in expected_names.items():
                if normalized_name == expected_name or expected_name in normalized_name:
                    matched = endpoint_id
                    break
        if matched and (
            _lookup(node, ["classification", "class", "role", "endpoint_class"]) is not None
            or _lookup(node, ["composite", "composite_score", "score"]) is not None
        ):
            found[matched] = node
    return found


def _classification(value: Any) -> str:
    text = _canon_text(value)
    if "exploratory" in text:
        return "EXPLORATORY"
    if "key secondary" in text or "keysecondary" in _canon_key(value):
        return "KEY-SECONDARY"
    if "primary" in text and "cannot" not in text and "not primary" not in text:
        return "PRIMARY"
    return text.upper()


def _dict_with_value(document: Any, aliases: Iterable[str]) -> dict | None:
    for node in _walk(document):
        if isinstance(node, dict) and _lookup(node, aliases) is not None:
            return node
    return None


def _metric(mapping: dict | None, aliases: Iterable[str]) -> float | None:
    return _as_float(_lookup(mapping or {}, aliases))


def test_endpoint_assessment() -> None:
    document = _load_submission() or {}
    rows = _endpoint_rows(document)
    expected = {
        "EP-01": (87.6, "PRIMARY"),
        "EP-02": (85.3, "KEY-SECONDARY"),
        "EP-03": (53.9, "EXPLORATORY"),
        "EP-04": (75.3, "KEY-SECONDARY"),
        "EP-05": (72.5, "KEY-SECONDARY"),
        "EP-06": (69.5, "KEY-SECONDARY"),
    }
    errors = []
    missing = sorted(set(expected) - set(rows))
    if missing:
        errors.append(f"missing endpoint assessments: {missing}")
    for endpoint_id, (expected_score, expected_class) in expected.items():
        row = rows.get(endpoint_id)
        if row is None:
            continue
        score = _metric(row, ["composite", "composite_score", "score", "weighted_score"])
        classification = _classification(_lookup(row, ["classification", "class", "role", "endpoint_class"]))
        if score is None or abs(score - expected_score) > 0.11:
            errors.append(f"{endpoint_id} score is {score}, expected {expected_score}")
        if classification != expected_class:
            errors.append(f"{endpoint_id} class is {classification!r}, expected {expected_class}")
    primary_ids = [endpoint_id for endpoint_id, row in rows.items() if _classification(_lookup(row, ["classification", "class", "role", "endpoint_class"])) == "PRIMARY"]
    if primary_ids != ["EP-01"]:
        errors.append(f"sole primary should be EP-01, found {primary_ids}")
    text = _submission_text(document)
    surrogate_visible = "ep-03" in text and "surrogate" in text and ("unvalidated" in text or "not validated" in text)
    if not surrogate_visible:
        errors.append("EP-03's unvalidated surrogate risk is not visibly surfaced")
    assert not errors, "; ".join(errors)


def test_sample_size_estimate() -> None:
    document = _load_submission() or {}
    sample = _dict_with_value(document, ["n_total_with_dropout", "total_required_n", "required_total_n", "required_n", "total_sample_size"])
    total = _metric(sample, ["n_total_with_dropout", "total_required_n", "required_total_n", "required_n", "total_sample_size"])
    dropout = _metric(sample, ["dropout_assumed", "dropout_fraction", "dropout", "attrition"])
    design = _lookup(sample or {}, ["design", "analysis", "outcome_type"])
    errors = []
    if total is None or abs(total - 484) > 0.01:
        errors.append(f"dropout-adjusted total is {total}, expected 484")
    if dropout is None or abs(dropout - 0.18) > 0.0001:
        errors.append(f"dropout assumption is {dropout}, expected 0.18")
    if design is None or "proportion" not in _canon_text(design):
        errors.append(f"design is {design!r}, expected a two-arm proportions design")
    per_arm = _metric(sample, ["n_per_arm_with_dropout", "adjusted_n_per_arm", "per_arm_with_dropout"])
    if per_arm is not None and abs(per_arm - 242) > 0.01:
        errors.append(f"reported dropout-adjusted per-arm n is {per_arm}, expected 242")
    assert not errors, "; ".join(errors)


def test_phase_gate_result() -> None:
    document = _load_submission() or {}
    gate = _dict_with_value(document, ["verdict", "gate_verdict", "phase_gate_decision"])
    verdict = _lookup(gate or {}, ["verdict", "gate_verdict", "phase_gate_decision"])
    composite = _metric(gate, ["composite", "composite_score", "feasibility_score", "gate_score"])
    dimensions = _lookup(gate or {}, ["breakdown", "dimension_scores", "dimensions", "scores"])
    if not isinstance(dimensions, dict):
        dimensions = gate or {}
    expected_dimensions = {
        "recruitment_feasibility": 72.9,
        "endpoint_readiness": 100.0,
        "statistical_power": 87.3,
        "operational_complexity": 44.0,
        "budget_fit": 80.4,
    }
    errors = []
    if _canon_key(verdict) != "gowithconditions":
        errors.append(f"phase-gate verdict is {verdict!r}, expected GO-WITH-CONDITIONS")
    if composite is None or abs(composite - 78.7) > 0.11:
        errors.append(f"phase-gate composite is {composite}, expected 78.7")
    for name, expected in expected_dimensions.items():
        actual = _metric(dimensions, [name])
        if actual is None or abs(actual - expected) > 0.11:
            errors.append(f"{name} is {actual}, expected {expected}")
    assert not errors, "; ".join(errors)


def test_selected_site_aggregation() -> None:
    document = _load_submission() or {}
    metrics = _dict_with_value(document, ["bottom_up_enrollment_forecast", "crm_enrollment_forecast", "selected_site_forecast"])
    selected_sites = _metric(metrics, ["selected_sites", "site_count", "selected_site_count"])
    eligible = _metric(metrics, ["eligible_population", "selected_eligible_pool", "eligible_pool"])
    forecast = _metric(metrics, ["bottom_up_enrollment_forecast", "crm_enrollment_forecast", "selected_site_forecast", "forecast_enrollment"])
    errors = []
    if selected_sites is None or abs(selected_sites - 18) > 0.01:
        errors.append(f"selected-site count is {selected_sites}, expected 18")
    if eligible is None or abs(eligible - 1420) > 0.01:
        errors.append(f"selected-site eligible pool is {eligible}, expected 1420")
    if forecast is None or abs(forecast - 381.7) > 0.11:
        errors.append(f"bottom-up enrollment forecast is {forecast}, expected 381.7")
    assert not errors, "; ".join(errors)
