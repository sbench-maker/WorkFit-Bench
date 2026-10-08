from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter
from pathlib import Path, PurePosixPath

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "quantization_plan.json"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


MODELS = {row["model_id"]: row for row in _read_csv("models.csv")}
GPUS = {row["gpu_id"]: row for row in _read_csv("gpu_inventory.csv")}
REQUESTS = _read_csv("deployment_requests.csv")
POLICY = json.loads((DATA_DIR / "planning_policy.json").read_text(encoding="utf-8"))
REQUEST_BY_ID = {row["request_id"]: row for row in REQUESTS}
CHUNKS = [REQUESTS[index : index + 22] for index in range(0, len(REQUESTS), 22)]


def _truth(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return str(value).strip().lower() in {"true", "yes", "1", "enabled"}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _get(mapping, *aliases, default=None):
    if not isinstance(mapping, dict):
        return default
    indexed = {_key(str(name)): value for name, value in mapping.items()}
    for alias in aliases:
        normalized = _key(alias)
        if normalized in indexed:
            return indexed[normalized]
    return default


def _number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def _mode(value) -> str | None:
    if value is None:
        return None
    compact = _key(str(value))
    if compact in {"nf4", "4bit", "nf44bit", "4bitnf4", "bnb4bit", "int4"}:
        return "nf4_4bit"
    if compact in {"int8", "8bit", "int88bit", "8bitint8", "bnb8bit"}:
        return "int8_8bit"
    if compact in {"fp16", "float16", "fullprecision", "halfprecision"}:
        return "fp16"
    if compact in {"reject", "rejected", "infeasible", "declined", "none"}:
        return "reject"
    return str(value).strip().lower()


def _placement(value, mode: str | None, cpu_offload) -> str | None:
    compact = _key(str(value)) if value is not None else ""
    if compact in {"native", "gpu", "gpuonly", "ondevice"}:
        return "native"
    if compact in {"cpuoffload", "offload", "hybrid", "gpucpu"}:
        return "cpu_offload"
    if compact in {"reject", "rejected", "none", "infeasible"} or mode == "reject":
        return "reject"
    amount = _number(cpu_offload)
    if amount is not None:
        return "cpu_offload" if amount > 0 else "native"
    return None


def _dtype(value) -> str | None:
    if value is None:
        return None
    compact = _key(str(value))
    if compact in {"bf16", "bfloat16", "torchbfloat16"}:
        return "bfloat16"
    if compact in {"fp16", "float16", "torchfloat16", "half"}:
        return "float16"
    return compact


def _plans_from_payload(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON must be an object or a plan list")
    for name in ("plans", "decisions", "deployments", "requests", "deployment_plan"):
        value = _get(payload, name)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _get(value, "plans", "decisions", "items", "records")
            if isinstance(nested, list):
                return nested
    raise ValueError("no plan list was found")


def _normalize_plan(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("plan list contains a non-object")
    memory = _get(raw, "memory", "memory_estimate", "memory_plan", default={})
    config = _get(raw, "configuration", "configs", default={})
    mode = _mode(_get(raw, "mode", "decision", "quantization_mode", "precision"))
    status_raw = _get(raw, "status", "result")
    status_key = _key(str(status_raw)) if status_raw is not None else ""
    status = "rejected" if mode == "reject" or status_key in {"rejected", "reject", "infeasible", "declined"} else "accepted"
    quant = _get(raw, "quantization_config", "quantization_kwargs", "bnb_config", "bitsandbytes_config")
    load = _get(raw, "model_load_config", "load_kwargs", "load_config", "from_pretrained_kwargs", "model_kwargs")
    if quant is None and isinstance(config, dict):
        quant = _get(config, "quantization_config", "quantization_kwargs", "bnb_config", "bitsandbytes")
    if load is None and isinstance(config, dict):
        load = _get(config, "model_load_config", "load_kwargs", "load_config", "from_pretrained_kwargs")
    cpu = _get(raw, "cpu_offload_gb", "weight_offloaded_cpu_gb", "cpu_weight_gb", "offloaded_weight_gb")
    if cpu is None:
        cpu = _get(memory, "cpu_offload_gb", "cpu_weight_gb", "offloaded_weight_gb")
    return {
        "request_id": _get(raw, "request_id", "request", "id"),
        "model_id": _get(raw, "model_id", "model"),
        "gpu_id": _get(raw, "gpu_id", "gpu", "device_id"),
        "status": status,
        "mode": mode,
        "placement": _placement(_get(raw, "placement", "deployment", "device_placement"), mode, cpu),
        "available_gpu_weight_gb": _number(
            _get(raw, "available_gpu_weight_gb", "gpu_available_for_weights_gb", "available_weight_gb", "weight_budget_gb")
            if _get(raw, "available_gpu_weight_gb", "gpu_available_for_weights_gb", "available_weight_gb", "weight_budget_gb") is not None
            else _get(memory, "available_gpu_weight_gb", "available_weight_gb", "weight_budget_gb")
        ),
        "estimated_weight_gb": _number(
            _get(raw, "estimated_weight_gb", "estimated_total_weight_gb", "weight_memory_gb", "model_weight_gb")
            if _get(raw, "estimated_weight_gb", "estimated_total_weight_gb", "weight_memory_gb", "model_weight_gb") is not None
            else _get(memory, "estimated_weight_gb", "weight_memory_gb", "model_weight_gb")
        ),
        "gpu_weight_gb": _number(
            _get(raw, "gpu_weight_gb", "weight_on_gpu_gb", "resident_weight_gb")
            if _get(raw, "gpu_weight_gb", "weight_on_gpu_gb", "resident_weight_gb") is not None
            else _get(memory, "gpu_weight_gb", "weight_on_gpu_gb", "resident_weight_gb")
        ),
        "cpu_offload_gb": _number(cpu),
        "accuracy_loss_pct": _number(_get(raw, "accuracy_loss_pct", "expected_accuracy_loss_pct", "loss_pct")),
        "quantization_config": quant,
        "model_load_config": load,
        "operator_note": _get(raw, "operator_note", "note", "reason", "explanation"),
    }


def _submission() -> tuple[dict, list[dict], dict[str, dict]]:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    raw_plans = _plans_from_payload(payload)
    plans = [_normalize_plan(row) for row in raw_plans]
    by_id: dict[str, dict] = {}
    for plan in plans:
        request_id = plan["request_id"]
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("a plan has no request ID")
        if request_id in by_id:
            raise ValueError(f"duplicate plan for {request_id}")
        by_id[request_id] = plan
    return payload if isinstance(payload, dict) else {}, plans, by_id


def _submission_or_skip() -> tuple[dict, list[dict], dict[str, dict]]:
    try:
        return _submission()
    except Exception as exc:
        pytest.skip(f"artifact readability and coverage are scored only once: {exc}")


def _expected(request: dict) -> dict:
    model = MODELS[request["model_id"]]
    gpu = GPUS[request["gpu_id"]]
    cap = float(request["max_accuracy_loss_pct"])
    available = float(gpu["vram_gb"]) - float(gpu["reserved_vram_gb"]) - float(request["nonweight_gpu_gb"])
    selected = None
    for mode in POLICY["mode_priority"]:
        loss_source = POLICY["accuracy_loss_source"][mode]
        loss = float(loss_source) if isinstance(loss_source, (int, float)) else float(model[loss_source])
        support_source = POLICY["mode_support_source"][mode]
        supported = bool(support_source) if isinstance(support_source, bool) else _truth(model[support_source])
        if mode != "fp16":
            supported = supported and _truth(gpu["bitsandbytes_compatible"])
        if not supported or loss > cap + 1e-12:
            continue
        weight = float(model["parameters_b"]) * float(POLICY["weight_gb_per_billion_parameters"][mode])
        if weight <= available + 1e-12:
            selected = (mode, loss, weight, "native", weight, 0.0)
            break
        spill = weight - max(available, 0.0)
        offload = POLICY["offload"]
        if (
            _truth(request["allow_cpu_offload"])
            and request["latency_class"] in offload["allowed_latency_classes"]
            and available >= weight * float(offload["minimum_gpu_weight_fraction"]) - 1e-12
            and spill <= float(gpu["cpu_offload_capacity_gb"]) + 1e-12
        ):
            selected = (mode, loss, weight, "cpu_offload", max(available, 0.0), spill)
            break
    if selected is None:
        return {
            "status": "rejected", "mode": "reject", "placement": "reject",
            "available": round(available, 2), "weight": None, "gpu_weight": None,
            "cpu_weight": None, "loss": None,
        }
    mode, loss, weight, placement, gpu_weight, cpu_weight = selected
    return {
        "status": "accepted", "mode": mode, "placement": placement,
        "available": round(available, 2), "weight": round(weight, 2),
        "gpu_weight": round(gpu_weight, 2), "cpu_weight": round(cpu_weight, 2),
        "loss": round(loss, 2),
    }


EXPECTED = {request["request_id"]: _expected(request) for request in REQUESTS}


def _close(actual, expected) -> bool:
    return actual is not None and math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=0.011)


def _config_value(config, *names, default=None):
    return _get(config, *names, default=default)


def _skip_modules(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {part.strip() for part in re.split(r"[|,]", value) if part.strip()}
    if isinstance(value, list):
        return {str(part).strip() for part in value if str(part).strip()}
    raise ValueError("INT8 skipped modules must be a list or delimited string")


def _max_memory_values(config: dict) -> tuple[float | None, float | None]:
    raw = _config_value(config, "max_memory", "memory_limits")
    if not isinstance(raw, dict):
        return None, None
    cpu = _number(_get(raw, "cpu", "host"))
    gpu = None
    for key, value in raw.items():
        if _key(str(key)) in {"0", "gpu0", "cuda0", "gpu"}:
            gpu = _number(value)
            break
    return gpu, cpu


def _summary(payload: dict) -> dict:
    summary = _get(payload, "summary", "totals", "rollup", default={})
    if not isinstance(summary, dict):
        return {}
    memory = _get(summary, "memory", "memory_totals", default={})
    return {
        "status": _get(summary, "counts_by_status", "status_counts", "by_status") or {
            "accepted": _get(summary, "accepted"), "rejected": _get(summary, "rejected")
        },
        "mode": _get(summary, "counts_by_mode", "mode_counts", "by_mode"),
        "placement": _get(summary, "counts_by_placement", "placement_counts", "by_placement"),
        "weight": _number(_get(summary, "total_estimated_weight_gb", "aggregate_estimated_weight_gb", "estimated_weight_total_gb", "total_weight_gb") if _get(summary, "total_estimated_weight_gb", "aggregate_estimated_weight_gb", "estimated_weight_total_gb", "total_weight_gb") is not None else _get(memory, "total_estimated_weight_gb", "total_weight_gb")),
        "gpu": _number(_get(summary, "total_gpu_weight_gb", "aggregate_gpu_weight_gb", "gpu_weight_total_gb") if _get(summary, "total_gpu_weight_gb", "aggregate_gpu_weight_gb", "gpu_weight_total_gb") is not None else _get(memory, "total_gpu_weight_gb", "gpu_weight_gb")),
        "cpu": _number(_get(summary, "total_cpu_offload_gb", "aggregate_cpu_offload_gb", "cpu_offload_total_gb") if _get(summary, "total_cpu_offload_gb", "aggregate_cpu_offload_gb", "cpu_offload_total_gb") is not None else _get(memory, "total_cpu_offload_gb", "cpu_offload_gb")),
    }


def _normalized_counts(value, kind: str) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        if kind == "mode":
            normalized = _mode(raw_key)
        elif kind == "placement":
            normalized = _placement(raw_key, None, None)
        else:
            compact = _key(str(raw_key))
            normalized = "rejected" if compact in {"reject", "rejected", "declined", "infeasible"} else "accepted" if compact in {"accept", "accepted", "deployed"} else str(raw_key)
        if normalized:
            output[normalized] = int(raw_value)
    return output


def test_artifact_is_readable_and_covers_queue():
    assert OUTPUT.is_file(), "quantization_plan.json was not produced"
    payload, plans, by_id = _submission()
    expected_ids = set(REQUEST_BY_ID)
    assert set(by_id) == expected_ids, "the plan must cover every queued request exactly once"
    assert len(plans) == len(REQUESTS), "the plan contains duplicates or extra requests"
    for request_id, plan in by_id.items():
        request = REQUEST_BY_ID[request_id]
        assert plan["model_id"] == request["model_id"], f"{request_id} is not traceable to its queued model"
        assert plan["gpu_id"] == request["gpu_id"], f"{request_id} is not traceable to its queued GPU"


@pytest.mark.parametrize("chunk", CHUNKS, ids=lambda rows: f"{rows[0]['request_id']}-{rows[-1]['request_id']}")
def test_mode_and_placement_decisions(chunk):
    _, _, by_id = _submission_or_skip()
    for request in chunk:
        request_id = request["request_id"]
        if request_id not in by_id:
            continue
        actual, expected = by_id[request_id], EXPECTED[request_id]
        assert actual["status"] == expected["status"], f"{request_id} has the wrong acceptance status"
        assert actual["mode"] == expected["mode"], f"{request_id} does not use the least-memory feasible mode"
        assert actual["placement"] == expected["placement"], f"{request_id} has the wrong native/offload placement"


@pytest.mark.parametrize("chunk", CHUNKS, ids=lambda rows: f"{rows[0]['request_id']}-{rows[-1]['request_id']}")
def test_memory_and_accuracy_values(chunk):
    _, _, by_id = _submission_or_skip()
    for request in chunk:
        request_id = request["request_id"]
        if request_id not in by_id:
            continue
        actual = by_id[request_id]
        model, gpu = MODELS[request["model_id"]], GPUS[request["gpu_id"]]
        available = round(float(gpu["vram_gb"]) - float(gpu["reserved_vram_gb"]) - float(request["nonweight_gpu_gb"]), 2)
        assert _close(actual["available_gpu_weight_gb"], available), f"{request_id} reports the wrong GPU weight budget"
        if actual["status"] == "rejected" or actual["mode"] == "reject":
            declared = {"weight": None, "gpu_weight": None, "cpu_weight": None, "loss": None}
        elif actual["mode"] in POLICY["mode_priority"]:
            mode = actual["mode"]
            weight = round(float(model["parameters_b"]) * float(POLICY["weight_gb_per_billion_parameters"][mode]), 2)
            loss_source = POLICY["accuracy_loss_source"][mode]
            loss = round(float(loss_source) if isinstance(loss_source, (int, float)) else float(model[loss_source]), 2)
            if actual["placement"] == "native":
                gpu_weight, cpu_weight = weight, 0.0
            elif actual["placement"] == "cpu_offload":
                gpu_weight = round(max(available, 0.0), 2)
                cpu_weight = round(weight - gpu_weight, 2)
            else:
                continue
            declared = {"weight": weight, "gpu_weight": gpu_weight, "cpu_weight": cpu_weight, "loss": loss}
        else:
            continue
        for actual_key, expected_key in (
            ("estimated_weight_gb", "weight"),
            ("gpu_weight_gb", "gpu_weight"),
            ("cpu_offload_gb", "cpu_weight"),
            ("accuracy_loss_pct", "loss"),
        ):
            if declared[expected_key] is None:
                assert actual[actual_key] is None, f"{request_id} fabricates {actual_key} for a rejected request"
            else:
                assert _close(actual[actual_key], declared[expected_key]), f"{request_id} reports the wrong {actual_key}"


@pytest.mark.parametrize("chunk", CHUNKS, ids=lambda rows: f"{rows[0]['request_id']}-{rows[-1]['request_id']}")
def test_bitsandbytes_and_load_configuration(chunk):
    _, _, by_id = _submission_or_skip()
    for request in chunk:
        request_id = request["request_id"]
        if request_id not in by_id:
            continue
        model, gpu = MODELS[request["model_id"]], GPUS[request["gpu_id"]]
        plan = by_id[request_id]
        quant, load = plan["quantization_config"], plan["model_load_config"]
        if plan["status"] == "rejected" or plan["mode"] == "reject":
            assert quant in (None, {}, False) and load in (None, {}, False), f"{request_id} exposes runnable settings despite rejection"
            continue
        if plan["mode"] not in POLICY["mode_priority"]:
            continue
        assert isinstance(load, dict), f"{request_id} has no model-loading kwargs"
        assert _key(str(_config_value(load, "device_map", "device"))) in {"auto", "automatic"}, f"{request_id} does not use automatic device placement"
        expected_dtype = "bfloat16" if plan["mode"] == "nf4_4bit" and _truth(gpu["supports_bf16"]) else "float16"
        assert _dtype(_config_value(load, "torch_dtype", "dtype")) == expected_dtype, f"{request_id} uses an unsupported model dtype"

        if plan["mode"] == "fp16":
            assert quant in (None, {}, False), f"{request_id} should not attach a quantization config to FP16"
        elif plan["mode"] == "nf4_4bit":
            assert isinstance(quant, dict), f"{request_id} has no 4-bit configuration"
            assert _truth(_config_value(quant, "load_in_4bit")), f"{request_id} does not enable 4-bit loading"
            assert not _truth(_config_value(quant, "load_in_8bit", default=False)), f"{request_id} enables conflicting 4-bit and 8-bit loading"
            assert _key(str(_config_value(quant, "bnb_4bit_quant_type", "quant_type"))) == "nf4", f"{request_id} does not use NF4"
            assert _truth(_config_value(quant, "bnb_4bit_use_double_quant", "use_double_quant", "double_quant")), f"{request_id} does not enable double quantization"
            assert _dtype(_config_value(quant, "bnb_4bit_compute_dtype", "compute_dtype")) == expected_dtype, f"{request_id} has the wrong 4-bit compute dtype"
        else:
            assert isinstance(quant, dict), f"{request_id} has no INT8 configuration"
            assert _truth(_config_value(quant, "load_in_8bit")), f"{request_id} does not enable 8-bit loading"
            assert not _truth(_config_value(quant, "load_in_4bit", default=False)), f"{request_id} enables conflicting 8-bit and 4-bit loading"
            assert not _truth(_config_value(quant, "llm_int8_has_fp16_weight", "has_fp16_weight", default=False)), f"{request_id} keeps FP16 weights and loses the intended memory saving"
            threshold_policy = POLICY["int8_threshold"]
            cap = float(request["max_accuracy_loss_pct"])
            expected_threshold = threshold_policy["accuracy_sensitive_value"] if cap <= threshold_policy["accuracy_sensitive_cap_at_or_below_pct"] + 1e-12 else threshold_policy["default_value"]
            assert _close(_number(_config_value(quant, "llm_int8_threshold", "int8_threshold", "threshold")), expected_threshold), f"{request_id} has the wrong INT8 outlier threshold"
            expected_skip = {value for value in model["int8_skip_modules"].split("|") if value}
            assert _skip_modules(_config_value(quant, "llm_int8_skip_modules", "skip_modules", default=[])) == expected_skip, f"{request_id} does not preserve the model-specific INT8 skip list"

        if plan["placement"] == "cpu_offload":
            gpu_limit, cpu_limit = _max_memory_values(load)
            expected_gpu_limit = float(gpu["vram_gb"]) - float(gpu["reserved_vram_gb"])
            assert _close(gpu_limit, expected_gpu_limit), f"{request_id} has the wrong GPU max_memory limit"
            assert _close(cpu_limit, float(gpu["cpu_offload_capacity_gb"])), f"{request_id} has the wrong CPU max_memory limit"
            folder = _config_value(load, "offload_folder", "offload_dir")
            assert isinstance(folder, str) and PurePosixPath("/root/results/offload") in (PurePosixPath(folder), *PurePosixPath(folder).parents), f"{request_id} offloads outside /root/results/offload"
            assert _truth(_config_value(load, "offload_state_dict", default=False)), f"{request_id} does not enable state-dict offload"


def test_summary_reconciles_with_plans():
    payload, plans, _ = _submission_or_skip()
    summary = _summary(payload)
    expected_status = Counter(item["status"] for item in plans)
    expected_mode = Counter(item["mode"] for item in plans)
    expected_placement = Counter(item["placement"] for item in plans)
    actual_status = _normalized_counts(summary["status"], "status")
    actual_mode = _normalized_counts(summary["mode"], "mode")
    actual_placement = _normalized_counts(summary["placement"], "placement")
    # Some reports summarize only accepted deployment modes/placements and put
    # rejected requests solely in counts_by_status. Reconcile that representation
    # without weakening the per-request decision checks above.
    if "reject" not in actual_mode and "rejected" in actual_status:
        actual_mode["reject"] = actual_status["rejected"]
    if "reject" not in actual_placement and "rejected" in actual_status:
        actual_placement["reject"] = actual_status["rejected"]
    assert actual_status == {key: expected_status.get(key, 0) for key in ("accepted", "rejected")}, "status totals do not reconcile to the queue"
    assert actual_mode == {key: expected_mode.get(key, 0) for key in ("nf4_4bit", "int8_8bit", "fp16", "reject")}, "mode totals do not reconcile to the queue"
    assert actual_placement == {key: expected_placement.get(key, 0) for key in ("native", "cpu_offload", "reject")}, "placement totals do not reconcile to the queue"
    for actual, key in ((summary["weight"], "estimated_weight_gb"), (summary["gpu"], "gpu_weight_gb"), (summary["cpu"], "cpu_offload_gb")):
        expected_total = round(sum(item[key] or 0.0 for item in plans), 2)
        assert _close(actual, expected_total), f"aggregate {key} memory does not reconcile to the queue"
