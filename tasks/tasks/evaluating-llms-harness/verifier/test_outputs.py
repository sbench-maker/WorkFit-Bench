from __future__ import annotations

import json
import math
import os
import re
import statistics
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
REPORT_PATH = Path(os.environ.get("TASK_REPORT_PATH", "/root/results/benchmark_report.json"))


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def exclusion_reasons(row: dict, protocol: dict) -> list[str]:
    reasons: list[str] = []
    if row.get("status") != "completed":
        reasons.append("status")
    if not isinstance(row.get("score"), (int, float)) or isinstance(row.get("score"), bool):
        reasons.append("score")
    task = protocol["required_benchmarks"].get(row.get("task_name"))
    if task is None:
        reasons.append("task_name")
    else:
        for field in ("task_version", "metric_name", "num_fewshot"):
            if row.get(field) != task[field]:
                reasons.append(field)
    for field, expected in protocol["required_run_config"].items():
        if row.get(field) != expected:
            reasons.append(field)
    return reasons


def expected_facts() -> dict:
    models = read_json(DATA_DIR / "models.json")["models"]
    protocol = read_json(DATA_DIR / "evaluation_protocol.json")
    rows = [
        json.loads(line)
        for line in (DATA_DIR / "harness_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    excluded: dict[str, list[str]] = {}
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        reasons = exclusion_reasons(row, protocol)
        if reasons:
            excluded[row["run_id"]] = reasons
        else:
            grouped.setdefault((row["model_id"], row["task_name"]), []).append(float(row["score"]))

    summaries: dict[tuple[str, str], dict] = {}
    for model in models:
        for benchmark in protocol["required_benchmarks"]:
            values = grouped[(model["model_id"], benchmark)]
            std = statistics.stdev(values)
            summaries[(model["model_id"], benchmark)] = {
                "mean": statistics.fmean(values),
                "std": std,
                "ci": 1.96 * std / math.sqrt(len(values)),
                "n": len(values),
            }

    checkpoint_ids = [model["model_id"] for model in models if model["role"] == "checkpoint"]
    previous_id = next(model["model_id"] for model in models if model["role"] == "previous_release")
    baseline_id = next(model["model_id"] for model in models if model["role"] == "external_baseline")
    benchmarks = list(protocol["required_benchmarks"])
    macros = {
        model["model_id"]: statistics.fmean(summaries[(model["model_id"], task)]["mean"] for task in benchmarks)
        for model in models
    }
    policy = protocol["release_policy"]
    eligible: list[str] = []
    step_by_id = {model["model_id"]: model["training_step"] for model in models}
    for model_id in checkpoint_ids:
        seed_ok = all(
            summaries[(model_id, task)]["n"] >= policy["minimum_valid_seeds_per_benchmark"]
            for task in benchmarks
        )
        floor_ok = all(
            summaries[(model_id, task)]["mean"] >= protocol["required_benchmarks"][task]["minimum_score"]
            for task in benchmarks
        )
        regression_ok = all(
            summaries[(model_id, task)]["mean"]
            >= summaries[(previous_id, task)]["mean"] - policy["maximum_regression_vs_previous_release"]
            for task in benchmarks
        )
        baseline_ok = (
            macros[model_id] - macros[baseline_id]
            >= policy["minimum_macro_advantage_vs_external_baseline"]
        )
        if seed_ok and floor_ok and regression_ok and baseline_ok:
            eligible.append(model_id)
    selected = max(eligible, key=lambda model_id: step_by_id[model_id]) if eligible else None
    latest = max(checkpoint_ids, key=lambda model_id: step_by_id[model_id])
    return {
        "models": [model["model_id"] for model in models],
        "checkpoint_ids": checkpoint_ids,
        "benchmarks": benchmarks,
        "summaries": summaries,
        "excluded": excluded,
        "baseline_id": baseline_id,
        "selected": selected,
        "latest": latest,
    }


FACTS = expected_facts()
KNOWN_MODELS = set(FACTS["models"])
KNOWN_BENCHMARKS = set(FACTS["benchmarks"])

MODEL_KEYS = {"modelid", "model", "checkpointid", "checkpoint", "candidateid", "candidate"}
BENCHMARK_KEYS = {"benchmark", "task", "taskname", "evaluationtask"}
MEAN_KEYS = {"mean", "average", "avg", "meanscore", "aggregatescore"}
COUNT_KEYS = {
    "validseedcount", "validseeds", "validruncount", "validruns", "samplecount", "count", "n",
    "ncompatibleseeds",
}
STD_KEYS = {"samplestd", "std", "stdev", "standarddeviation", "seedstd", "samplesd"}
CI_KEYS = {
    "ci95halfwidth", "cihalfwidth", "confidencehalfwidth", "ci95", "confidenceinterval95",
    "cihalfwidth95",
}


def direct_value(node: dict, aliases: set[str]):
    for key, value in node.items():
        if norm_key(key) in aliases:
            return value
    return None


def number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*", value)
        if match:
            return float(match.group(1))
    return None


def context_nodes(node: object, model: str | None = None, benchmark: str | None = None, path: tuple[str, ...] = ()):
    if isinstance(node, dict):
        explicit_model = direct_value(node, MODEL_KEYS)
        explicit_benchmark = direct_value(node, BENCHMARK_KEYS)
        if isinstance(explicit_model, str) and explicit_model in KNOWN_MODELS:
            model = explicit_model
        if isinstance(explicit_benchmark, str) and explicit_benchmark in KNOWN_BENCHMARKS:
            benchmark = explicit_benchmark
        yield node, model, benchmark, path
        for key, value in node.items():
            child_model = key if key in KNOWN_MODELS else model
            child_benchmark = key if key in KNOWN_BENCHMARKS else benchmark
            yield from context_nodes(value, child_model, child_benchmark, path + (str(key),))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from context_nodes(value, model, benchmark, path + (str(index),))


def parse_ci(node: dict, mean: float | None) -> float | None:
    raw = direct_value(node, CI_KEYS)
    direct = number(raw)
    if direct is not None:
        return direct
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        low, high = number(raw[0]), number(raw[1])
        if low is not None and high is not None:
            return abs(high - low) / 2.0
    if isinstance(raw, dict):
        low = number(direct_value(raw, {"low", "lower", "lowerbound"}))
        high = number(direct_value(raw, {"high", "upper", "upperbound"}))
        if low is not None and high is not None:
            return abs(high - low) / 2.0
    low = number(direct_value(node, {"ci95lower", "lower95", "cilower"}))
    high = number(direct_value(node, {"ci95upper", "upper95", "ciupper"}))
    if low is not None and high is not None:
        return abs(high - low) / 2.0
    return None


class ReportView:
    def __init__(self, payload: object, error: str | None = None):
        self.payload = payload
        self.error = error
        self.summaries: dict[tuple[str, str], dict] = {}
        self.baseline_deltas: dict[tuple[str, str], float] = {}
        self.exclusions: dict[str, str] = {}
        self.selected_candidates: set[str] = set()
        self.latest_is_held = False
        if error is None:
            self._extract()

    def _extract(self) -> None:
        for node, model, benchmark, path in context_nodes(self.payload):
            if model in KNOWN_MODELS and benchmark in KNOWN_BENCHMARKS:
                mean = number(direct_value(node, MEAN_KEYS))
                if mean is None and direct_value(node, {"seed", "runid"}) is None:
                    mean = number(direct_value(node, {"score"}))
                if mean is not None:
                    candidate = {
                        "mean": mean,
                        "n": number(direct_value(node, COUNT_KEYS)),
                        "std": number(direct_value(node, STD_KEYS)),
                        "ci": parse_ci(node, mean),
                    }
                    pair = (model, benchmark)
                    old = self.summaries.get(pair)
                    if old is None or sum(value is not None for value in candidate.values()) > sum(value is not None for value in old.values()):
                        self.summaries[pair] = candidate

            candidate_id = direct_value(node, {"candidateid", "candidate", "checkpointid", "checkpoint"})
            if not isinstance(candidate_id, str) or candidate_id not in KNOWN_MODELS:
                candidate_id = model
            task_name = direct_value(node, BENCHMARK_KEYS)
            if not isinstance(task_name, str) or task_name not in KNOWN_BENCHMARKS:
                task_name = benchmark
            delta = number(direct_value(node, {"deltavsexternalbaseline", "deltavsbaseline", "baselinedelta", "externalbaselinedelta"}))
            ref_type = direct_value(node, {"referencetype", "reference", "comparison"})
            ref_id = direct_value(node, {"referenceid", "baselinemodel", "baselineid"})
            is_baseline = (
                isinstance(ref_type, str) and "baseline" in norm_key(ref_type)
            ) or ref_id == FACTS["baseline_id"]
            if delta is None and is_baseline:
                delta = number(direct_value(node, {"delta", "difference", "change"}))
            if candidate_id in FACTS["checkpoint_ids"] and task_name in KNOWN_BENCHMARKS and delta is not None:
                self.baseline_deltas[(candidate_id, task_name)] = delta

            self._extract_recommendation(node, path)

        self._extract_exclusions(self.payload)

    def _extract_recommendation(self, node: dict, path: tuple[str, ...]) -> None:
        recommendation_context = any(
            token in norm_key(part)
            for part in path
            for token in ("recommend", "promotion", "release", "decision")
        )
        for key, value in node.items():
            normalized = norm_key(key)
            if normalized in {
                "selectedcheckpoint", "recommendedcheckpoint", "promotioncandidate", "releasecandidate", "promote",
                "checkpointtopromote",
            }:
                if isinstance(value, str) and value in FACTS["checkpoint_ids"]:
                    self.selected_candidates.add(value)
            if recommendation_context and normalized in {"checkpoint", "model", "modelid"}:
                if isinstance(value, str) and value in FACTS["checkpoint_ids"]:
                    self.selected_candidates.add(value)
            if normalized in {"latestcheckpointdecision", "latestdecision", "newestcheckpointdecision"}:
                if isinstance(value, str) and norm_key(value) in {"hold", "reject", "donotpromote", "notready", "blocked"}:
                    self.latest_is_held = True
                if value is False:
                    self.latest_is_held = True
            if isinstance(value, str) and recommendation_context:
                lower = value.lower()
                for model_id in FACTS["checkpoint_ids"]:
                    if re.search(rf"(?:promote|recommend)\s+{re.escape(model_id.lower())}", lower):
                        self.selected_candidates.add(model_id)
                latest = FACTS["latest"].lower()
                if re.search(rf"(?:hold|reject|do not promote)\s+{re.escape(latest)}", lower):
                    self.latest_is_held = True
        latest_context = any(FACTS["latest"].lower() == str(part).lower() for part in path)
        if latest_context and recommendation_context:
            outcome = direct_value(node, {"overall", "eligible", "passed", "pass", "approved"})
            if outcome is False or norm_key(outcome) in {"false", "no", "failed", "blocked", "rejected"}:
                self.latest_is_held = True

    def _extract_exclusions(self, node: object, path: tuple[str, ...] = ()) -> None:
        exclusion_context = any(
            token in norm_key(part)
            for part in path
            for token in ("exclusion", "incompatible", "discarded", "omitted", "invalidrun", "failedrun")
        )
        if isinstance(node, dict):
            run_id = direct_value(node, {"runid", "id"})
            reason_value = direct_value(node, {"reason", "reasons", "mismatch", "issue", "issues", "error"})
            included = direct_value(node, {"included", "comparable", "valid"})
            if isinstance(run_id, str) and run_id in {row_id for row_id in FACTS["excluded"]}:
                if exclusion_context or reason_value is not None or included is False:
                    self.exclusions[run_id] = json.dumps(node, sort_keys=True).lower()
            for key, value in node.items():
                self._extract_exclusions(value, path + (str(key),))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._extract_exclusions(value, path + (str(index),))
        elif isinstance(node, str) and exclusion_context and node in FACTS["excluded"]:
            self.exclusions.setdefault(node, "listed as excluded")


@pytest.fixture(scope="session")
def report_view() -> ReportView:
    if not REPORT_PATH.is_file():
        return ReportView(None, f"missing report: {REPORT_PATH}")
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ReportView(None, f"unreadable JSON report: {exc}")
    return ReportView(payload)


def require_readable(view: ReportView) -> None:
    if view.error:
        pytest.skip(f"artifact readability is scored once by test_artifact_usability: {view.error}")


@pytest.mark.parametrize("model_id", FACTS["models"])
def test_measurement_coverage_and_values(report_view: ReportView, model_id: str):
    require_readable(report_view)
    errors: list[str] = []
    for benchmark in FACTS["benchmarks"]:
        pair = (model_id, benchmark)
        actual = report_view.summaries.get(pair)
        expected = FACTS["summaries"][pair]
        if actual is None:
            errors.append(f"missing {model_id}/{benchmark}")
            continue
        for field in ("mean", "std", "ci"):
            if actual.get(field) is None:
                errors.append(f"{model_id}/{benchmark} lacks {field}")
            elif not math.isclose(
                actual[field], expected[field], rel_tol=0.0,
                abs_tol=5e-4 if field == "mean" else 5e-5,
            ):
                errors.append(f"{model_id}/{benchmark} {field}={actual[field]:.8f}, expected {expected[field]:.8f}")
    assert not errors, "; ".join(errors)


@pytest.mark.parametrize("checkpoint_id", FACTS["checkpoint_ids"])
def test_external_baseline_comparisons(report_view: ReportView, checkpoint_id: str):
    require_readable(report_view)
    errors: list[str] = []
    for benchmark in FACTS["benchmarks"]:
        pair = (checkpoint_id, benchmark)
        actual = report_view.baseline_deltas.get(pair)
        expected = (
            FACTS["summaries"][pair]["mean"]
            - FACTS["summaries"][(FACTS["baseline_id"], benchmark)]["mean"]
        )
        if actual is None:
            errors.append(f"missing baseline delta for {checkpoint_id}/{benchmark}")
        elif not math.isclose(actual, expected, rel_tol=1e-5, abs_tol=1e-6):
            errors.append(f"{checkpoint_id}/{benchmark} delta={actual:.8f}, expected {expected:.8f}")
    assert not errors, "; ".join(errors)


def test_comparability_exclusions(report_view: ReportView):
    require_readable(report_view)
    actual_ids = set(report_view.exclusions)
    expected_ids = set(FACTS["excluded"])
    assert actual_ids == expected_ids, (
        f"exclusion set differs: missing={sorted(expected_ids - actual_ids)}, "
        f"unexpected={sorted(actual_ids - expected_ids)}; this can contaminate aggregates or discard valid evidence"
    )
    token_aliases = {
        "status": ("status", "failed", "out_of_memory", "worker_lost", "oom"),
        "score": ("score", "numeric", "missing"),
        "task_version": ("task_version", "taskversion", "version"),
        "metric_name": ("metric_name", "metricname", "metric"),
        "num_fewshot": ("num_fewshot", "numfewshot", "fewshot", "few-shot"),
        "temperature": ("temperature",),
        "do_sample": ("do_sample", "dosample", "sampling"),
    }
    errors: list[str] = []
    for run_id, expected_tokens in FACTS["excluded"].items():
        explanation = report_view.exclusions[run_id]
        for token in expected_tokens:
            if not any(alias in explanation for alias in token_aliases[token]):
                errors.append(f"{run_id} does not explain its {token} incompatibility/failure")
    assert not errors, "; ".join(errors)


@pytest.mark.parametrize(
    "model_id,benchmark",
    [
        ("aurora-7b-step-500k", "gsm8k"),
        ("borealis-7b-baseline", "truthfulqa_mc2"),
        ("aurora-7b-step-300k", "mmlu"),
        ("aurora-7b-step-400k", "hellaswag"),
        ("aurora-7b-release-prev", "arc_challenge"),
    ],
)
def test_affected_valid_seed_counts(report_view: ReportView, model_id: str, benchmark: str):
    require_readable(report_view)
    pair = (model_id, benchmark)
    actual = report_view.summaries.get(pair)
    assert actual is not None, f"missing affected aggregate {model_id}/{benchmark}"
    expected_n = FACTS["summaries"][pair]["n"]
    assert actual.get("n") == expected_n, (
        f"{model_id}/{benchmark} reports valid seed count {actual.get('n')}, expected {expected_n}; "
        "the failed or incompatible run must not enter the aggregate"
    )


def test_release_decision(report_view: ReportView):
    require_readable(report_view)
    assert report_view.selected_candidates == {FACTS["selected"]}, (
        f"the report should select only {FACTS['selected']} under the supplied gates; "
        f"found {sorted(report_view.selected_candidates)}"
    )
    assert FACTS["latest"] != FACTS["selected"], "fixture must exercise a non-latest release decision"
    assert report_view.latest_is_held, (
        f"the report must explicitly hold {FACTS['latest']}, whose stronger aggregate performance masks a decisive gate failure"
    )
