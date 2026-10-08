from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))


def _jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _alias(mapping: dict, aliases: set[str]):
    for key, value in mapping.items():
        if _token(key) in aliases:
            return value
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip().rstrip("%"))
        except ValueError:
            return None
        if value.strip().endswith("%"):
            parsed /= 100.0
        return parsed if math.isfinite(parsed) else None
    return None


def _integer(value: object) -> int | None:
    number = _number(value)
    if number is None or abs(number - round(number)) > 1e-9:
        return None
    return int(round(number))


def _numeric_vector(value: object) -> list[float] | None:
    if not isinstance(value, list) or not value:
        return None
    converted = [_number(item) for item in value]
    if any(item is None for item in converted):
        return None
    return [float(item) for item in converted]


@lru_cache(maxsize=1)
def source() -> dict:
    rows = _jsonl(DATA_DIR / "checkpoint_rows.jsonl")
    manifest_payload = json.loads((DATA_DIR / "tensor_manifest.json").read_text(encoding="utf-8"))
    activation_rows = _jsonl(DATA_DIR / "calibration_activations.jsonl")
    manifest = {item["tensor_id"]: item for item in manifest_payload["tensors"]}
    row_map = {
        (row["tensor_id"], int(row["output_row"])): [float(value) for value in row["weights"]]
        for row in rows
    }
    sums: dict[str, list[float]] = {}
    counts: dict[str, int] = defaultdict(int)
    for row in activation_rows:
        name = row["tensor_id"]
        if name not in sums:
            sums[name] = [0.0] * len(row["input_rms"])
        sums[name] = [left + float(right) for left, right in zip(sums[name], row["input_rms"])]
        counts[name] += 1
    means = {name: [value / counts[name] for value in values] for name, values in sums.items()}
    return {
        "rows": row_map,
        "manifest": manifest,
        "means": means,
        "counts": counts,
    }


@lru_cache(maxsize=1)
def submission() -> object:
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


ID_ALIASES = {"tensorid", "tensor", "name", "parameter", "parametername"}
ROW_ALIASES = {"outputrow", "row", "rowindex", "outputindex"}
VALUES_ALIASES = {"weights", "values", "data", "prunedweights", "weightvalues"}


def normalize_checkpoint(payload: object) -> tuple[dict[tuple[str, int], list[float]], set[tuple[str, int]]]:
    source_rows = source()["rows"]
    known_tensors = {key[0] for key in source_rows}
    found: dict[tuple[str, int], list[float]] = {}
    duplicates: set[tuple[str, int]] = set()

    def add(name: object, row_index: object, values: object) -> bool:
        if not isinstance(name, str) or name not in known_tensors:
            return False
        row_number = _integer(row_index)
        vector = _numeric_vector(values)
        if row_number is None or vector is None:
            return False
        key = (name, row_number)
        if key not in source_rows:
            return False
        if key in found:
            duplicates.add(key)
        else:
            found[key] = vector
        return True

    def add_matrix(name: object, value: object) -> bool:
        if not isinstance(name, str) or name not in known_tensors or not isinstance(value, list):
            return False
        vectors = [_numeric_vector(row) for row in value]
        if not vectors or any(row is None for row in vectors):
            return False
        for index, row in enumerate(vectors):
            add(name, index, row)
        return True

    def walk(node: object, context_tensor: str | None = None) -> None:
        if isinstance(node, dict):
            explicit_tensor = _alias(node, ID_ALIASES)
            tensor = explicit_tensor if isinstance(explicit_tensor, str) else context_tensor
            row_index = _alias(node, ROW_ALIASES)
            values = _alias(node, VALUES_ALIASES)
            consumed_values = False
            if tensor is not None and row_index is not None and values is not None:
                consumed_values = add(tensor, row_index, values)
            elif tensor is not None and values is not None:
                consumed_values = add_matrix(tensor, values)

            for key, value in node.items():
                if key in known_tensors:
                    if not add_matrix(key, value):
                        walk(value, key)
                elif value is values and consumed_values:
                    continue
                elif value is explicit_tensor:
                    continue
                else:
                    walk(value, tensor)
        elif isinstance(node, list):
            if context_tensor is not None and add_matrix(context_tensor, node):
                return
            for value in node:
                walk(value, context_tensor)

    walk(payload)
    return found, duplicates


LAYER_ALIASES = {"layer", "layerindex", "block", "blockindex"}
METRIC_ALIASES = {
    "eligible_tensor_count": {"eligibletensorcount", "eligibletensors", "tensorcount"},
    "eligible_weights": {"eligibleweights", "totalweights", "weightcount"},
    "retained_weights": {"retainedweights", "keptweights", "nonzeroweights"},
    "pruned_weights": {"prunedweights", "zeroedweights", "zeroweights"},
    "sparsity": {"sparsity", "eligiblesparsity", "sparsityratio"},
    "pattern_groups": {"patterngroups", "nmgroups", "groupcount"},
    "pattern_violations": {"patternviolations", "nmviolations", "violations"},
}


def _layer_from_key(key: object) -> int | None:
    if isinstance(key, int) and 0 <= key <= 3:
        return key
    match = re.search(r"(?:layer|block)[_ -]*([0-3])\b", str(key).lower())
    return int(match.group(1)) if match else None


def _layer_value(value: object) -> int | None:
    direct = _integer(value)
    if direct is not None and 0 <= direct <= 3:
        return direct
    return _layer_from_key(value)


def normalize_layer_summaries(payload: object) -> dict[int, dict[str, float]]:
    found: dict[int, dict[str, float]] = {}

    def walk(node: object, context_layer: int | None = None) -> None:
        if isinstance(node, dict):
            explicit = _layer_value(_alias(node, LAYER_ALIASES))
            layer = explicit if explicit is not None else context_layer
            metrics: dict[str, float] = {}
            for canonical, aliases in METRIC_ALIASES.items():
                value = _number(_alias(node, aliases))
                if value is not None:
                    metrics[canonical] = value
            if layer is not None and len(metrics) >= 2:
                if layer not in found or len(metrics) > len(found[layer]):
                    found[layer] = metrics
            for key, value in node.items():
                keyed_layer = _layer_from_key(key)
                walk(value, keyed_layer if keyed_layer is not None else layer)
        elif isinstance(node, list):
            for value in node:
                walk(value, context_layer)

    walk(payload)
    return found


GLOBAL_ALIASES = {
    "checkpoint_rows": {"checkpointrows", "rowcount", "totalrows"},
    "eligible_tensor_count": {"eligibletensorcount", "eligibletensors"},
    "excluded_tensor_count": {"excludedtensorcount", "excludedtensors", "ineligibletensorcount"},
    "eligible_weights": {"eligibleweights", "totaleligibleweights"},
    "retained_weights": {"retainedweights", "keptweights"},
    "pruned_weights": {"prunedweights", "zeroedweights"},
    "eligible_sparsity": {"eligiblesparsity", "sparsity", "sparsityratio"},
    "pattern_groups": {"patterngroups", "nmgroups"},
    "pattern_violations": {"patternviolations", "nmviolations"},
    "calibration_samples": {"calibrationsamplespereligibletensor", "calibrationsamples", "samplecount"},
    "excluded_unchanged": {"excludedtensorsunchanged", "excludedunchanged", "ineligibleunchanged"},
}


def normalize_global_validation(payload: object) -> dict[str, object]:
    candidates: list[dict[str, object]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            metrics: dict[str, object] = {}
            for canonical, aliases in GLOBAL_ALIASES.items():
                value = _alias(node, aliases)
                if canonical == "excluded_unchanged":
                    if isinstance(value, bool):
                        metrics[canonical] = value
                    elif isinstance(value, str) and value.strip().lower() in {"true", "yes", "pass", "passed"}:
                        metrics[canonical] = True
                    elif isinstance(value, str) and value.strip().lower() in {"false", "no", "fail", "failed"}:
                        metrics[canonical] = False
                else:
                    number = _number(value)
                    if number is not None:
                        metrics[canonical] = number
            if len(metrics) >= 3 and _alias(node, LAYER_ALIASES) is None:
                candidates.append(metrics)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return max(candidates, key=len, default={})


def expected_keep(name: str, values: list[float], start: int) -> set[int]:
    activation = source()["means"][name]
    indices = list(range(start, start + 4))
    return set(sorted(indices, key=lambda index: (-abs(values[index]) * activation[index], index))[:2])


def _group_is_edge(name: str, values: list[float], start: int) -> bool:
    kept = expected_keep(name, values, start)
    magnitude_kept = set(sorted(range(start, start + 4), key=lambda index: (-abs(values[index]), index))[:2])
    activation = source()["means"][name]
    scores = [abs(values[index]) * activation[index] for index in range(start, start + 4)]
    cutoff = sorted(scores, reverse=True)[1]
    has_tie = sum(abs(score - cutoff) <= 1e-15 for score in scores) > 1
    return has_tie or kept != magnitude_kept


def _assert_groups(*, edge: bool) -> None:
    actual, _ = normalize_checkpoint(submission())
    checked = 0
    errors: list[str] = []
    for key, source_values in source()["rows"].items():
        name, row_index = key
        if not source()["manifest"][name]["eligible"] or key not in actual:
            continue
        if len(actual[key]) != len(source_values):
            continue
        for start in range(0, len(source_values), 4):
            if _group_is_edge(name, source_values, start) != edge:
                continue
            checked += 1
            keep = expected_keep(name, source_values, start)
            actual_values = actual[key]
            nonzero = {index for index in range(start, start + 4) if abs(actual_values[index]) > 1e-12}
            if nonzero != keep:
                errors.append(f"{name} row {row_index} cols {start}-{start + 3}: kept {sorted(nonzero)}, expected {sorted(keep)}")
                continue
            for index in range(start, start + 4):
                expected_value = source_values[index] if index in keep else 0.0
                if not math.isclose(actual_values[index], expected_value, rel_tol=0.0, abs_tol=1e-9):
                    errors.append(f"{name} row {row_index} col {index}: {actual_values[index]} != {expected_value}")
    assert checked > 0, "no assessable eligible groups were found in the submitted checkpoint"
    assert not errors, "incorrect activation-aware 2:4 groups; " + "; ".join(errors[:8])


def test_checkpoint_scope_and_excluded_integrity() -> None:
    actual, duplicates = normalize_checkpoint(submission())
    expected = source()["rows"]
    assert not duplicates, f"checkpoint rows are duplicated: {sorted(duplicates)[:5]}"
    assert set(actual) == set(expected), (
        f"checkpoint scope differs: missing={sorted(set(expected) - set(actual))[:5]}, "
        f"unexpected={sorted(set(actual) - set(expected))[:5]}"
    )
    shape_errors = [key for key in expected if len(actual[key]) != len(expected[key])]
    assert not shape_errors, f"checkpoint row shapes changed: {shape_errors[:5]}"
    excluded_errors = []
    for key, expected_values in expected.items():
        if source()["manifest"][key[0]]["eligible"]:
            continue
        if any(not math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12) for left, right in zip(actual[key], expected_values)):
            excluded_errors.append(key)
    assert not excluded_errors, f"excluded dense tensors were changed: {excluded_errors[:5]}"


def test_activation_aware_pruning_standard_groups() -> None:
    _assert_groups(edge=False)


def test_activation_aware_pruning_conflicts_and_ties() -> None:
    _assert_groups(edge=True)


def test_summary_reconciles_with_checkpoint() -> None:
    layer_summaries = normalize_layer_summaries(submission())
    assert set(layer_summaries) == {0, 1, 2, 3}, f"layer summary must cover layers 0-3; found {sorted(layer_summaries)}"
    expected_layer = {
        "eligible_tensor_count": 7,
        "eligible_weights": 672,
        "retained_weights": 336,
        "pruned_weights": 336,
        "sparsity": 0.5,
        "pattern_groups": 168,
        "pattern_violations": 0,
    }
    for layer, metrics in layer_summaries.items():
        missing = set(expected_layer) - set(metrics)
        assert not missing, f"layer {layer} summary lacks decision metrics: {sorted(missing)}"
        for key, expected in expected_layer.items():
            assert math.isclose(float(metrics[key]), float(expected), rel_tol=0.0, abs_tol=1e-9), (
                f"layer {layer} {key}={metrics[key]}, expected {expected}"
            )

    validation = normalize_global_validation(submission())
    expected_global = {
        "checkpoint_rows": 240,
        "eligible_tensor_count": 28,
        "excluded_tensor_count": 2,
        "eligible_weights": 2688,
        "retained_weights": 1344,
        "pruned_weights": 1344,
        "eligible_sparsity": 0.5,
        "pattern_groups": 672,
        "pattern_violations": 0,
        "calibration_samples": 128,
    }
    missing = set(expected_global) - set(validation)
    assert not missing, f"global validation lacks reconciliation metrics: {sorted(missing)}"
    for key, expected in expected_global.items():
        assert math.isclose(float(validation[key]), float(expected), rel_tol=0.0, abs_tol=1e-9), (
            f"global validation {key}={validation[key]}, expected {expected}"
        )
    assert validation.get("excluded_unchanged") is True, "global validation must confirm excluded tensors are unchanged"
