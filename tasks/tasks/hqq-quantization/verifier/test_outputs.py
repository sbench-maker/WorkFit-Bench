from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
sys.path.insert(0, str(DATA_DIR))

import hqq_runtime


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _quant_section(report: dict) -> dict:
    section = _field(report, "quantization", "quantization_config", "quantizationConfig", "config", "settings")
    if section is None:
        section = report
    if not isinstance(section, dict):
        raise ValueError("quantization section is not an object")
    return section


def _layer_configs(report: dict) -> dict[str, dict | None | str]:
    section = _quant_section(report)
    raw = _field(section, "layer_configs", "layerConfigs", "layers", "modules")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        normalized = {}
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("layer config list contains a non-object")
            name = _field(item, "layer", "layer_name", "layerName", "name", "module")
            if not isinstance(name, str):
                raise ValueError("layer config is missing its layer name")
            normalized[name] = _field(item, "config", "settings", "quantization") or {
                k: v for k, v in item.items() if k not in {"layer", "layer_name", "layerName", "name", "module"}
            }
        return normalized
    raise ValueError("layer configurations are missing")


def _artifact_path(report: dict) -> Path:
    artifacts = _field(report, "artifacts", "files", "outputs") or {}
    relative = _field(artifacts, "weights", "weights_file", "weightsFile", "quantized_weights") if isinstance(artifacts, dict) else None
    if relative is None:
        relative = _field(report, "weights_file", "weightsFile", "quantized_weights_file") or "quantized_weights.jsonl"
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("weights artifact path is invalid")
    path = (RESULTS_DIR / relative).resolve()
    if RESULTS_DIR.resolve() not in path.parents:
        raise ValueError("weights artifact must remain inside /root/results")
    return path


def _read_encoded_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("rows", payload.get("weights"))
        if not isinstance(payload, list):
            raise ValueError("JSON weights artifact must be a list or contain rows")
        rows = payload
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("weights artifact contains a non-object row")
    return rows


def _submission() -> tuple[dict, dict[str, dict | None | str], list[dict]]:
    report = _read_json(RESULTS_DIR / "output.json")
    return report, _layer_configs(report), _read_encoded_rows(_artifact_path(report))


def _submission_or_skip() -> tuple[dict, dict[str, dict | None | str], list[dict]]:
    try:
        return _submission()
    except Exception as exc:
        pytest.skip(f"artifact readability is scored only by test_artifact_usability: {exc}")


def _field(row: dict, *names: str):
    wanted = {"".join(ch for ch in name.casefold() if ch.isalnum()) for name in names}
    for name in names:
        if name in row:
            return row[name]
    for key, value in row.items():
        if "".join(ch for ch in str(key).casefold() if ch.isalnum()) in wanted:
            return value
    return None


def _row_key(row: dict) -> tuple[str, int]:
    layer = _field(row, "layer", "name")
    index = _field(row, "row", "row_index", "rowIndex")
    if not isinstance(layer, str) or not isinstance(index, int):
        raise ValueError("encoded row lacks a valid layer and row index")
    return layer, index


def _normalized_groups(row: dict) -> list[dict]:
    raw = _field(row, "groups", "quant_groups", "quantGroups")
    if not isinstance(raw, list):
        raise ValueError(f"quantized row {_row_key(row)} has no group list")
    groups = []
    for group in raw:
        if not isinstance(group, dict):
            raise ValueError("quantization group is not an object")
        start = _field(group, "start", "offset")
        scale = _field(group, "scale")
        zero = _field(group, "zero", "zero_point", "zeroPoint")
        codes = _field(group, "codes", "q")
        if not isinstance(start, int) or not isinstance(codes, list):
            raise ValueError("quantization group is missing start or codes")
        groups.append({"start": start, "scale": float(scale), "zero": float(zero), "codes": [int(x) for x in codes]})
    return groups


def _decode(row: dict, width: int) -> tuple[list[float], int]:
    fmt = str(_field(row, "format", "storage_format") or "").lower()
    if fmt in {"fp16", "float16"}:
        values = _field(row, "values", "weights")
        if not isinstance(values, list) or len(values) != width:
            raise ValueError(f"preserved row {_row_key(row)} has the wrong width")
        return [float(value) for value in values], width * 2
    if fmt not in {"hqq", "quantized"}:
        raise ValueError(f"row {_row_key(row)} has unknown format {fmt!r}")
    nbits = int(_field(row, "nbits", "bits"))
    groups = _normalized_groups(row)
    output: list[float | None] = [None] * width
    packed_bytes = 0
    for group in groups:
        codes = group["codes"]
        if any(code < 0 or code >= (1 << nbits) for code in codes):
            raise ValueError(f"row {_row_key(row)} contains a code outside {nbits}-bit range")
        start = group["start"]
        if start < 0 or start + len(codes) > width:
            raise ValueError(f"row {_row_key(row)} has an out-of-range group")
        for offset, code in enumerate(codes):
            position = start + offset
            if output[position] is not None:
                raise ValueError(f"row {_row_key(row)} has overlapping groups")
            output[position] = group["scale"] * code + group["zero"]
        packed_bytes += math.ceil(len(codes) * nbits / 8) + 4
    if any(value is None for value in output):
        raise ValueError(f"row {_row_key(row)} does not cover all {width} weights")
    return [float(value) for value in output], packed_bytes


def _fixture() -> tuple[dict, dict, dict[tuple[str, int], dict]]:
    manifest = _read_json(DATA_DIR / "model_manifest.json")
    request = _read_json(DATA_DIR / "deployment_request.json")
    source = {_row_key(row): row for row in hqq_runtime.load_rows(DATA_DIR / "checkpoint_weights.jsonl")}
    return manifest, request, source


def _config_tuple(config: dict | None | str) -> tuple[int, int] | None:
    if config is None or (isinstance(config, str) and config.lower() in {"fp16", "float16", "none"}):
        return None
    if not isinstance(config, dict):
        raise ValueError("quantized layer config is not an object")
    fmt = str(config.get("format", "")).lower()
    if fmt in {"fp16", "float16"}:
        return None
    return int(config.get("nbits", config.get("bits"))), int(config.get("group_size", config.get("groupsize")))


def _payload_metrics(rows: list[dict]) -> tuple[dict[str, float], float, dict[str, int], int]:
    manifest, request, source = _fixture()
    widths = {layer["name"]: int(layer["columns"]) for layer in manifest["layers"]}
    encoded = {_row_key(row): row for row in rows}
    if len(encoded) != len(rows) or set(encoded) != set(source):
        raise ValueError("encoded row keys do not match the checkpoint exactly")
    layer_error: dict[str, float] = {layer["name"]: 0.0 for layer in manifest["layers"]}
    layer_count: dict[str, int] = {layer["name"]: 0 for layer in manifest["layers"]}
    layer_bytes: dict[str, int] = {layer["name"]: 0 for layer in manifest["layers"]}
    for key, source_row in source.items():
        layer = key[0]
        restored, used_bytes = _decode(encoded[key], widths[layer])
        original = [float(value) for value in source_row["values"]]
        if layer in request["preserve_modules"]:
            if any(abs(a - b) > 1e-12 for a, b in zip(original, restored)):
                raise ValueError(f"protected layer {layer} was altered")
        else:
            layer_error[layer] += sum((a - b) ** 2 for a, b in zip(original, restored))
            layer_count[layer] += len(original)
        layer_bytes[layer] += used_bytes
    rmse = {
        layer: math.sqrt(layer_error[layer] / layer_count[layer]) if layer_count[layer] else 0.0
        for layer in layer_error
    }
    total_count = sum(layer_count.values())
    overall = math.sqrt(sum(layer_error.values()) / total_count)
    return rmse, overall, layer_bytes, sum(layer_bytes.values())


def _payload_metrics_or_skip(rows: list[dict]) -> tuple[dict[str, float], float, dict[str, int], int]:
    try:
        return _payload_metrics(rows)
    except (KeyError, TypeError, ValueError) as exc:
        pytest.skip(f"payload structure is scored only by test_quantized_payload_integrity: {exc}")


def _metric_map(raw) -> dict[str, float]:
    if isinstance(raw, dict):
        return {str(key): float(value) for key, value in raw.items()}
    if isinstance(raw, list):
        output = {}
        for item in raw:
            if isinstance(item, dict):
                name = item.get("layer", item.get("name"))
                value = item.get("rmse", item.get("value"))
                if isinstance(name, str):
                    output[name] = float(value)
        return output
    raise ValueError("per-layer metric is neither a mapping nor a list")


def test_artifact_usability():
    report, configs, rows = _submission()
    manifest, _, _ = _fixture()
    assert report.get("model_id", report.get("model")) == manifest["model_id"], "output.json does not identify the supplied checkpoint"
    assert configs, "output.json has no readable layer configuration"
    assert rows, "the referenced quantized weights artifact is empty"


def test_deployment_configuration():
    report, configs, _ = _submission_or_skip()
    manifest, request, _ = _fixture()
    expected_layers = {layer["name"] for layer in manifest["layers"]}
    assert set(configs) == expected_layers, "layer configuration must cover every checkpoint layer exactly once"
    section = _quant_section(report)
    method = str(section.get("method", report.get("method", ""))).lower()
    assert method == "hqq", "the package is not identified as HQQ quantization"
    assert section.get("calibration_data_used", report.get("calibration_data_used")) is False, "calibration data was used despite the offline request"
    assert int(section.get("axis", request["axis"])) == request["axis"], "quantization axis does not match the checkpoint"
    preferred = next(
        name for name in request["preferred_backend_order"]
        if request["backends"][name]["supported"] and request["backends"][name]["optimized"]
    )
    backend = str(section.get("backend", report.get("backend", ""))).lower()
    assert backend == preferred, f"{backend!r} is not the preferred optimized backend for the target T4"
    for layer in manifest["layers"]:
        name = layer["name"]
        config = _config_tuple(configs[name])
        if name in request["preserve_modules"]:
            assert config is None, f"protected vocabulary endpoint {name} was assigned a quantization config"
        else:
            assert config is not None, f"quantizable layer {name} has no HQQ configuration"
            nbits, group_size = config
            assert nbits in request["allowed_nbits"] and group_size in request["allowed_group_sizes"], f"{name} uses a disallowed precision or group size"


def test_quantized_payload_integrity():
    report, configs, rows = _submission_or_skip()
    manifest, request, source = _fixture()
    expected_layers = {layer["name"] for layer in manifest["layers"]}
    if set(configs) != expected_layers:
        pytest.skip("layer configuration scope is scored only by test_deployment_configuration")
    encoded = {_row_key(row): row for row in rows}
    assert set(encoded) == set(source), "quantized payload does not cover the exact checkpoint row set"
    for layer in manifest["layers"]:
        name = layer["name"]
        config = _config_tuple(configs[name])
        for row_index in range(layer["rows"]):
            actual = encoded[(name, row_index)]
            source_row = source[(name, row_index)]
            if name in request["preserve_modules"]:
                restored, _ = _decode(actual, layer["columns"])
                assert restored == [float(value) for value in source_row["values"]], f"protected row {(name, row_index)} changed"
                continue
            assert config is not None
            nbits, group_size = config
            expected, _, _ = hqq_runtime.quantize_row(source_row, nbits, group_size)
            actual_groups = _normalized_groups(actual)
            expected_groups = expected["groups"]
            assert len(actual_groups) == len(expected_groups), f"row {(name, row_index)} has the wrong group count"
            for got, want in zip(actual_groups, expected_groups):
                assert got["start"] == want["start"] and got["codes"] == want["codes"], f"row {(name, row_index)} has incorrect packed codes"
                assert math.isclose(got["scale"], want["scale"], rel_tol=0.0, abs_tol=1e-9), f"row {(name, row_index)} has an incorrect scale"
                assert math.isclose(got["zero"], want["zero"], rel_tol=0.0, abs_tol=1e-9), f"row {(name, row_index)} has an incorrect zero point"


def test_quality_limits_and_minimum_size():
    report, configs, rows = _submission_or_skip()
    manifest, request, _ = _fixture()
    expected_layers = {layer["name"] for layer in manifest["layers"]}
    if set(configs) != expected_layers:
        pytest.skip("layer configuration scope is scored only by test_deployment_configuration")
    rmse, _, _, packed_bytes = _payload_metrics_or_skip(rows)
    expected_configs = {}
    for layer in manifest["layers"]:
        name = layer["name"]
        if name in request["preserve_modules"]:
            expected_configs[name] = None
            continue
        limit = request["quality_limits"][name]["max_rmse"]
        assert rmse[name] <= limit + 1e-9, f"{name} exceeds its reconstruction RMSE limit"
        valid = [item for item in hqq_runtime.candidate_table(name) if item["rmse"] <= limit + 1e-12]
        chosen = min(valid, key=lambda item: (item["packed_bytes"], item["rmse"], item["nbits"], item["group_size"]))
        expected_configs[name] = (chosen["nbits"], chosen["group_size"])
    actual_configs = {name: _config_tuple(config) for name, config in configs.items()}
    assert actual_configs == expected_configs, "layer choices are valid but do not form the smallest package under the stated tie-break"
    assert packed_bytes <= request["max_packed_bytes"], "quantized package exceeds the deployment byte ceiling"


def test_manifest_metrics_consistent():
    report, _, rows = _submission_or_skip()
    manifest, _, _ = _fixture()
    rmse, overall, layer_bytes, packed_bytes = _payload_metrics_or_skip(rows)
    quality = report.get("quality", report.get("metrics", {}))
    storage = report.get("storage", report.get("size", {}))
    assert isinstance(quality, dict) and isinstance(storage, dict), "output.json lacks quality or storage summaries"
    reported_rmse = _metric_map(quality.get("per_layer_rmse", quality.get("layers")))
    assert set(reported_rmse) == set(rmse), "per-layer RMSE summary does not cover every layer"
    for layer, value in rmse.items():
        assert math.isclose(reported_rmse[layer], value, rel_tol=1e-7, abs_tol=1e-9), f"reported RMSE for {layer} disagrees with the weights artifact"
    assert math.isclose(float(quality.get("overall_rmse")), overall, rel_tol=1e-7, abs_tol=1e-9), "overall RMSE does not reconcile to the payload"
    assert int(storage.get("packed_bytes")) == packed_bytes, "reported packed byte total does not reconcile to encoded groups"
    reported_layer_bytes = storage.get("per_layer_bytes")
    assert isinstance(reported_layer_bytes, dict) and {str(k): int(v) for k, v in reported_layer_bytes.items()} == layer_bytes, "per-layer byte accounting disagrees with the payload"
    source_bytes = sum(layer["rows"] * layer["columns"] * 2 for layer in manifest["layers"])
    assert int(storage.get("source_fp16_bytes")) == source_bytes, "source FP16 byte total is incorrect"
    expected_reduction = (source_bytes - packed_bytes) / source_bytes * 100.0
    assert math.isclose(float(storage.get("reduction_percent")), expected_reduction, rel_tol=1e-7, abs_tol=1e-7), "reported reduction percentage is inconsistent"
