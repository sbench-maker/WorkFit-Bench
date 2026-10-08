#!/usr/bin/env python3
"""Deterministic offline HQQ runtime for the bundled miniature checkpoint.

The runtime is intentionally self-contained: it performs calibration-free,
group-wise affine weight quantization with half-quadratic refinement and writes
the portable bundle format documented in README.md.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable


DATA_DIR = Path(__file__).resolve().parent
WEIGHTS_PATH = DATA_DIR / "checkpoint_weights.jsonl"
MANIFEST_PATH = DATA_DIR / "model_manifest.json"
REQUEST_PATH = DATA_DIR / "deployment_request.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path = WEIGHTS_PATH) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row.get("values"), list):
            raise ValueError(f"invalid values at line {line_no}")
        rows.append(row)
    return rows


def rows_by_layer(rows: Iterable[dict] | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows if rows is not None else load_rows():
        grouped.setdefault(row["layer"], []).append(row)
    for layer_rows in grouped.values():
        layer_rows.sort(key=lambda item: int(item["row"]))
    return grouped


def _quantize_group(values: list[float], nbits: int) -> tuple[float, float, list[int]]:
    """Refine x ~= scale*q + zero using alternating discrete/LS updates."""
    levels = (1 << nbits) - 1
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return 1.0, round(low, 10), [0] * len(values)
    scale = (high - low) / levels
    zero = low
    codes = [0] * len(values)
    for _ in range(8):
        codes = [max(0, min(levels, int(math.floor((x - zero) / scale + 0.5)))) for x in values]
        mean_q = sum(codes) / len(codes)
        mean_x = sum(values) / len(values)
        variance = sum((q - mean_q) ** 2 for q in codes)
        if variance <= 1e-15:
            break
        new_scale = sum((q - mean_q) * (x - mean_x) for q, x in zip(codes, values)) / variance
        if new_scale <= 1e-15:
            break
        scale = new_scale
        zero = mean_x - scale * mean_q
    scale = round(scale, 10)
    zero = round(zero, 10)
    codes = [max(0, min(levels, int(math.floor((x - zero) / scale + 0.5)))) for x in values]
    return scale, zero, codes


def quantize_row(row: dict, nbits: int, group_size: int) -> tuple[dict, float, int]:
    values = [float(value) for value in row["values"]]
    groups = []
    squared_error = 0.0
    packed_bytes = 0
    for start in range(0, len(values), group_size):
        source = values[start : start + group_size]
        scale, zero, codes = _quantize_group(source, nbits)
        restored = [scale * code + zero for code in codes]
        squared_error += sum((a - b) ** 2 for a, b in zip(source, restored))
        packed_bytes += math.ceil(len(codes) * nbits / 8) + 4
        groups.append({"start": start, "scale": scale, "zero": zero, "codes": codes})
    output = {
        "layer": row["layer"],
        "row": int(row["row"]),
        "format": "hqq",
        "nbits": nbits,
        "group_size": group_size,
        "groups": groups,
    }
    return output, squared_error, packed_bytes


def preserve_row(row: dict) -> tuple[dict, int]:
    values = [float(value) for value in row["values"]]
    return {
        "layer": row["layer"],
        "row": int(row["row"]),
        "format": "fp16",
        "values": values,
    }, len(values) * 2


def evaluate_layer(layer: str, nbits: int, group_size: int) -> dict:
    request = load_json(REQUEST_PATH)
    if nbits not in request["allowed_nbits"] or group_size not in request["allowed_group_sizes"]:
        raise ValueError("configuration is outside the deployment request")
    layer_rows = rows_by_layer()[layer]
    squared_error = 0.0
    count = 0
    packed_bytes = 0
    for row in layer_rows:
        _, row_error, row_bytes = quantize_row(row, nbits, group_size)
        squared_error += row_error
        count += len(row["values"])
        packed_bytes += row_bytes
    return {
        "layer": layer,
        "nbits": nbits,
        "group_size": group_size,
        "rmse": math.sqrt(squared_error / count),
        "packed_bytes": packed_bytes,
    }


def candidate_table(layer: str) -> list[dict]:
    request = load_json(REQUEST_PATH)
    return [
        evaluate_layer(layer, nbits, group_size)
        for nbits in request["allowed_nbits"]
        for group_size in request["allowed_group_sizes"]
    ]


def normalize_config(payload: dict) -> dict:
    quant = payload.get("quantization", payload)
    layers = quant.get("layer_configs", quant.get("layers"))
    if isinstance(layers, list):
        layers = {item.get("layer", item.get("name")): item.get("config", item) for item in layers}
    if not isinstance(layers, dict):
        raise ValueError("layer_configs must be a mapping or list")
    return {
        "backend": quant.get("backend"),
        "axis": quant.get("axis", 1),
        "calibration_data_used": quant.get("calibration_data_used", False),
        "layer_configs": layers,
        "deployment_handoff": payload.get("deployment_handoff", payload.get("notes", "")),
    }


def validate_config(config: dict) -> None:
    manifest = load_json(MANIFEST_PATH)
    request = load_json(REQUEST_PATH)
    known = {item["name"] for item in manifest["layers"]}
    supplied = set(config["layer_configs"])
    if supplied != known:
        raise ValueError(f"layer coverage mismatch: missing={sorted(known-supplied)} extra={sorted(supplied-known)}")
    if config["axis"] != request["axis"]:
        raise ValueError("axis is incompatible with this checkpoint")
    if config["calibration_data_used"] is not False:
        raise ValueError("this deployment forbids calibration data")
    backend = config["backend"]
    backend_info = request["backends"].get(backend)
    if not backend_info or not backend_info["supported"]:
        raise ValueError(f"backend {backend!r} is not supported on the target")
    for layer in manifest["layers"]:
        name = layer["name"]
        layer_config = config["layer_configs"][name]
        if name in request["preserve_modules"]:
            if layer_config not in (None, "fp16", {"format": "fp16"}):
                raise ValueError(f"{name} must remain fp16")
            continue
        if not isinstance(layer_config, dict):
            raise ValueError(f"{name} requires a quantization config")
        if layer_config.get("nbits") not in request["allowed_nbits"]:
            raise ValueError(f"invalid nbits for {name}")
        if layer_config.get("group_size") not in request["allowed_group_sizes"]:
            raise ValueError(f"invalid group_size for {name}")


def build_bundle(config_payload: dict, output_dir: Path) -> dict:
    config = normalize_config(config_payload)
    validate_config(config)
    manifest = load_json(MANIFEST_PATH)
    request = load_json(REQUEST_PATH)
    grouped = rows_by_layer()
    output_rows = []
    per_layer_rmse = {}
    per_layer_bytes = {}
    total_error = 0.0
    total_quantized_values = 0
    total_bytes = 0
    for layer in manifest["layers"]:
        name = layer["name"]
        layer_error = 0.0
        layer_count = 0
        layer_bytes = 0
        layer_config = config["layer_configs"][name]
        for row in grouped[name]:
            if name in request["preserve_modules"]:
                encoded, used_bytes = preserve_row(row)
                output_rows.append(encoded)
                layer_bytes += used_bytes
            else:
                encoded, squared_error, used_bytes = quantize_row(
                    row, int(layer_config["nbits"]), int(layer_config["group_size"])
                )
                output_rows.append(encoded)
                layer_error += squared_error
                layer_count += len(row["values"])
                layer_bytes += used_bytes
        if layer_count:
            per_layer_rmse[name] = math.sqrt(layer_error / layer_count)
            total_error += layer_error
            total_quantized_values += layer_count
        else:
            per_layer_rmse[name] = 0.0
        per_layer_bytes[name] = layer_bytes
        total_bytes += layer_bytes

    output_dir.mkdir(parents=True, exist_ok=True)
    weights_name = "quantized_weights.jsonl"
    with (output_dir / weights_name).open("w", encoding="utf-8") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    source_bytes = sum(item["rows"] * item["columns"] * 2 for item in manifest["layers"])
    result = {
        "schema_version": "1.0",
        "model_id": manifest["model_id"],
        "quantization": {
            "method": "HQQ",
            "backend": config["backend"],
            "framework": request["framework"],
            "axis": config["axis"],
            "calibration_data_used": False,
            "layer_configs": config["layer_configs"],
        },
        "quality": {
            "per_layer_rmse": per_layer_rmse,
            "overall_rmse": math.sqrt(total_error / total_quantized_values),
        },
        "storage": {
            "source_fp16_bytes": source_bytes,
            "packed_bytes": total_bytes,
            "reduction_percent": (source_bytes - total_bytes) / source_bytes * 100.0,
            "per_layer_bytes": per_layer_bytes,
        },
        "artifacts": {"weights": weights_name},
        "deployment_handoff": config["deployment_handoff"],
    }
    (output_dir / "output.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_bundle(load_json(args.config), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
