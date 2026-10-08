from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
EXPECTED_ROOT = Path(os.environ.get("TASK_EXPECTED_ROOT", "/verifier/expected"))
SCRIPT = RESULTS_ROOT / "churn_pipeline.py"
FEATURES = {
    "utilization_rate",
    "sessions_per_active_user",
    "api_calls",
    "invoice_amount",
    "case_count",
    "urgent_case_count",
    "avg_first_response_hours",
    "days_since_activity",
    "tenure_days",
}


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _run(script: Path, data_root: Path, results_root: Path) -> subprocess.CompletedProcess[str]:
    results_root.mkdir(parents=True, exist_ok=True)
    trace = results_root / "bigframes_trace.json"
    trace.unlink(missing_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(data_root / "emulator")
    env["BIGFRAMES_FIXTURE_ROOT"] = str(data_root)
    env["BIGFRAMES_RESULTS_ROOT"] = str(results_root)
    env["BIGFRAMES_TRACE_PATH"] = str(trace)
    return subprocess.run(
        ["python3", str(script)],
        cwd="/root" if Path("/root").is_dir() else str(script.parent),
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


@pytest.fixture(scope="session")
def pipeline_run() -> subprocess.CompletedProcess[str]:
    if not SCRIPT.is_file():
        return subprocess.CompletedProcess(["python3", str(SCRIPT)], 127, "", "pipeline script is missing")
    return _run(SCRIPT, DATA_ROOT, RESULTS_ROOT)


def _read_trace(root: Path = RESULTS_ROOT) -> list[dict]:
    path = root / "bigframes_trace.json"
    assert path.is_file(), "bigframes_trace.json is missing; the pipeline did not execute through the fixture emulator"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, list), "BigFrames trace must be a list of observable service operations"
    return value


def _find_event(trace: list[dict], name: str) -> dict:
    matches = [row for row in trace if row.get("event") == name]
    assert matches, f"BigFrames trace has no {name!r} operation"
    return matches[-1]


def _flatten_json(value, prefix="") -> dict[str, object]:
    flattened: dict[str, object] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_json(child, child_prefix))
    else:
        flattened[_normalized_key(prefix.split(".")[-1])] = value
    return flattened


def _metric(payload: dict, *aliases: str):
    flattened = _flatten_json(payload)
    for alias in aliases:
        key = _normalized_key(alias)
        if key in flattened:
            return flattened[key]
    raise AssertionError(f"metrics.json is missing a metric represented by one of {aliases}")


def _read_scores(path: Path) -> list[dict[str, object]]:
    assert path.is_file(), f"missing requested score artifact: {path}"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames, "churn_scores.csv has no header"
        key_map = {_normalized_key(name): name for name in reader.fieldnames}
        id_name = next(
            (key_map[key] for key in ("accountid", "customerid", "account") if key in key_map),
            None,
        )
        probability_name = next(
            (
                key_map[key]
                for key in ("churnprobability", "riskprobability", "predictedlabelprobs", "probability")
                if key in key_map
            ),
            None,
        )
        assert id_name is not None, "score CSV needs an account identifier column"
        assert probability_name is not None, "score CSV needs a churn-probability column"
        rows = []
        for raw in reader:
            try:
                probability = float(raw[probability_name])
            except (TypeError, ValueError):
                raise AssertionError(f"non-numeric churn probability for {raw.get(id_name)!r}") from None
            rows.append({"account_id": str(raw[id_name]).strip(), "probability": probability})
        return rows


def _expected_scores() -> list[dict[str, object]]:
    return _read_scores(EXPECTED_ROOT / "churn_scores.csv")


def test_pipeline_is_runnable(pipeline_run):
    """The requested implementation executes offline and produces all three named artifacts."""
    assert SCRIPT.is_file(), "the requested /root/results/churn_pipeline.py artifact is missing"
    assert pipeline_run.returncode == 0, (
        "churn_pipeline.py did not run successfully against the bundled emulator:\n"
        + pipeline_run.stderr[-3000:]
    )
    assert (RESULTS_ROOT / "churn_scores.csv").is_file(), "pipeline did not write churn_scores.csv"
    assert (RESULTS_ROOT / "metrics.json").is_file(), "pipeline did not write metrics.json"
    json.loads((RESULTS_ROOT / "metrics.json").read_text(encoding="utf-8"))
    _read_scores(RESULTS_ROOT / "churn_scores.csv")


def test_pipeline_honors_fixture_contract(pipeline_run):
    """The runnable pipeline responds to a corrected fixture instead of embedding the visible answers."""
    assert pipeline_run.returncode == 0, "baseline execution must succeed before checking fixture adaptability"
    baseline = {row["account_id"]: row["probability"] for row in _read_scores(RESULTS_ROOT / "churn_scores.csv")}
    with tempfile.TemporaryDirectory(prefix="bqbf-fixture-") as fixture_tmp, tempfile.TemporaryDirectory(
        prefix="bqbf-result-"
    ) as result_tmp:
        fixture = Path(fixture_tmp) / "data"
        shutil.copytree(DATA_ROOT, fixture)
        usage_path = fixture / "warehouse" / "monthly_usage.csv"
        with usage_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        changed = 0
        for row in rows:
            if row["account_id"] == "ACCT-0001" and row["month"] == "2026-09-01":
                row["active_users"] = "0"
                row["sessions"] = "0"
                row["api_calls"] = "0"
                row["last_activity_date"] = "2026-09-01"
                changed += 1
        assert changed == 1, "author fixture mutation target is ambiguous"
        with usage_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        rerun = _run(SCRIPT, fixture, Path(result_tmp))
        assert rerun.returncode == 0, "pipeline ignored the documented relocatable fixture contract: " + rerun.stderr[-1500:]
        altered = {row["account_id"]: row["probability"] for row in _read_scores(Path(result_tmp) / "churn_scores.csv")}
        assert set(altered) == set(baseline), "changing feature values must not change the eligible scoring cohort"
        assert altered["ACCT-0001"] > baseline["ACCT-0001"] + 0.10, (
            "ACCT-0001 did not become materially riskier after its September engagement was removed; "
            "the pipeline may be hard-coded or may not derive features from the fixture"
        )


def test_remote_bigframes_workflow(pipeline_run):
    """Observable emulator operations preserve the requested cloud-side BigFrames workflow."""
    assert pipeline_run.returncode == 0, "pipeline execution failed"
    trace = _read_trace()
    reads = [row for row in trace if row.get("event") == "read_gbq"]
    assert {row.get("table") for row in reads} == {
        "skillbench.customers",
        "skillbench.monthly_usage",
        "skillbench.support_cases",
    }, "the pipeline must read all three documented BigQuery tables"
    assert not any(row.get("raw_sql") for row in reads), "raw SQL bypasses the requested DataFrame workflow"
    ordering = _find_event(trace, "ordering_mode")
    assert str(ordering.get("value")).lower() == "partial", "partial ordering mode was not enabled"
    for operation in ("create_model", "evaluate", "predict"):
        _find_event(trace, operation)
    assert any(row.get("event") in {"merge", "join"} for row in trace), (
        "the documented tables were not joined through the remote DataFrame surface"
    )
    source_downloads = [
        row for row in trace if row.get("event") == "materialize" and row.get("source_table")
    ]
    assert not source_downloads, "a full source-backed frame was materialized locally"


def test_training_cohort_and_model_contract(pipeline_run):
    """Model creation uses the exact documented cohort, label, feature meanings, and persisted identity."""
    assert pipeline_run.returncode == 0, "pipeline execution failed"
    model = _find_event(_read_trace(), "create_model")
    assert model.get("model_name") == "skillbench.churn_model", "model was persisted under the wrong identity"
    assert model.get("replace") is True, "the named model must be replaceable on reruns"
    assert str(model.get("model_type", "")).upper() in {"LOGISTIC_REG", "LOGISTIC_REGRESSION"}, (
        "the task requires logistic regression"
    )
    assert model.get("training_rows") == 706, "training cohort does not match the documented filters"
    assert model.get("label_positive") == 188 and model.get("label_negative") == 518, (
        "training labels do not match the deduplicated June-August cohort"
    )
    assert set(model.get("feature_columns", [])) == FEATURES, (
        "training data does not use the complete documented feature contract"
    )


def test_evaluation_metrics(pipeline_run):
    """The metrics artifact faithfully reports the model evaluation rather than unrelated summaries."""
    assert pipeline_run.returncode == 0, "pipeline execution failed"
    actual = json.loads((RESULTS_ROOT / "metrics.json").read_text(encoding="utf-8"))
    expected = json.loads((EXPECTED_ROOT / "metrics.json").read_text(encoding="utf-8"))
    assert str(_metric(actual, "model_name", "model", "model_id")) == expected["model_name"]
    assert int(_metric(actual, "evaluated_rows", "evaluation_rows", "row_count")) == expected["evaluated_rows"]
    for key, aliases in {
        "roc_auc": ("roc_auc", "auc", "rocauc"),
        "accuracy": ("accuracy",),
        "log_loss": ("log_loss", "logloss"),
    }.items():
        observed = float(_metric(actual, *aliases))
        assert math.isclose(observed, float(expected[key]), rel_tol=1e-8, abs_tol=1e-10), (
            f"reported {key}={observed} does not match the emulator evaluation {expected[key]}"
        )


def test_scoring_scope_and_order(pipeline_run):
    """Every and only eligible September account is present once in useful priority order."""
    assert pipeline_run.returncode == 0, "pipeline execution failed"
    actual = _read_scores(RESULTS_ROOT / "churn_scores.csv")
    expected = _expected_scores()
    actual_ids = [row["account_id"] for row in actual]
    expected_ids = {row["account_id"] for row in expected}
    assert len(actual_ids) == len(set(actual_ids)), "an eligible account appears more than once"
    assert set(actual_ids) == expected_ids, "score file omits eligible accounts or includes ineligible/internal accounts"
    probabilities = [row["probability"] for row in actual]
    assert all(0.0 <= value <= 1.0 for value in probabilities), "churn probabilities must be in [0, 1]"
    assert all(left >= right for left, right in zip(probabilities, probabilities[1:])), (
        "churn_scores.csv is not prioritized from highest to lowest risk"
    )


@pytest.mark.parametrize(
    "account_id",
    [
        "ACCT-0109", "ACCT-0028", "ACCT-0190", "ACCT-0133",
        "ACCT-0001", "ACCT-0050", "ACCT-0118", "ACCT-0175",
        "ACCT-0032", "ACCT-0144", "ACCT-0201", "ACCT-0239",
    ],
)
def test_score_probabilities(pipeline_run, account_id):
    """Representative high-, middle-, and low-risk probabilities match the deterministic model."""
    assert pipeline_run.returncode == 0, "pipeline execution failed"
    actual = {row["account_id"]: row["probability"] for row in _read_scores(RESULTS_ROOT / "churn_scores.csv")}
    expected = {row["account_id"]: row["probability"] for row in _expected_scores()}
    assert account_id in actual, f"eligible account {account_id} is missing"
    assert math.isclose(actual[account_id], expected[account_id], rel_tol=1e-8, abs_tol=1e-9), (
        f"{account_id} probability does not match the documented features and deterministic logistic model"
    )
