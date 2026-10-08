from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULT_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
ORIGINAL = DATA_ROOT / "parcel_quote"
SUBMITTED = RESULT_ROOT / "parcel_quote"
NOTES = RESULT_ROOT / "refactor_notes.md"
FIXTURES = ORIGINAL / "tests" / "fixtures"


def run_process(
    repository: Path,
    args: list[str],
    *,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repository), existing_pythonpath) if part
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        args,
        cwd=repository,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def run_probe(repository: Path, code: str, payload: object) -> object:
    completed = run_process(
        repository,
        [sys.executable, "-c", code],
        stdin=json.dumps(payload),
    )
    assert completed.returncode == 0, (
        f"probe could not execute against {repository}:\n"
        f"stdout={completed.stdout}\nstderr={completed.stderr}"
    )
    return json.loads(completed.stdout)


def parsed_json_lines(text: str) -> list[object]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_artifact_usability():
    assert SUBMITTED.is_dir(), "the complete refactored repository is missing"
    package = SUBMITTED / "courier_quote"
    assert package.is_dir() and (package / "__init__.py").is_file(), (
        "the handoff does not contain a runnable courier_quote package"
    )
    assert NOTES.is_file() and len(NOTES.read_text(encoding="utf-8").strip()) >= 100, (
        "refactor_notes.md is missing or too short to hand off the structural changes and checks"
    )
    compiled = run_process(
        SUBMITTED,
        [sys.executable, "-m", "compileall", "-q", str(package)],
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


def test_public_api_quotes_all_frozen_cases():
    requests = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "expected_quotes.json").read_text(encoding="utf-8"))
    code = r'''
import json, sys
from courier_quote import quote_parcel
requests = json.load(sys.stdin)
json.dump([quote_parcel(row) for row in requests], sys.stdout, separators=(",", ":"))
'''
    actual = run_probe(SUBMITTED, code, requests)
    assert actual == expected, (
        "one or more of the 240 frozen parcel quotes changed; pricing, rounding, "
        "surcharge order, or the returned public shape is not behavior-preserving"
    )


def test_manifest_and_public_import_contract():
    requests = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))
    payload = [requests[83], requests[4], requests[219]]
    code = r'''
import json, sys
import courier_quote
from courier_quote import quote_manifest, quote_parcel
rows = json.load(sys.stdin)
report = {
  "exports": sorted(courier_quote.__all__),
  "manifest": quote_manifest(rows),
  "individual": [quote_parcel(row) for row in rows],
}
try:
    quote_manifest(tuple(rows))
except Exception as exc:
    report["tuple_error"] = [type(exc).__name__, str(exc)]
bad = dict(rows[1], service="drone")
try:
    quote_manifest([rows[0], bad, rows[2]])
except Exception as exc:
    report["atomic_error"] = [type(exc).__name__, str(exc)]
json.dump(report, sys.stdout, separators=(",", ":"))
'''
    actual = run_probe(SUBMITTED, code, payload)
    assert actual["exports"] == ["quote_manifest", "quote_parcel"], (
        "the package-level public imports or __all__ contract changed"
    )
    assert actual["manifest"] == actual["individual"], (
        "quote_manifest no longer matches individual quotes in input order"
    )
    assert actual.get("tuple_error", [None])[0] == "TypeError", (
        "quote_manifest must reject a non-list without returning partial results"
    )
    assert actual.get("atomic_error", [None])[0] == "ValueError", (
        "quote_manifest must fail atomically when any request is invalid"
    )


def test_cli_single_quote_and_usage():
    requests = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))
    for request in (requests[0], requests[118], requests[239]):
        argument = json.dumps(request, separators=(",", ":"))
        expected = run_process(
            ORIGINAL,
            [sys.executable, "-m", "courier_quote.cli", "quote", argument],
        )
        actual = run_process(
            SUBMITTED,
            [sys.executable, "-m", "courier_quote.cli", "quote", argument],
        )
        assert actual.returncode == expected.returncode == 0
        assert parsed_json_lines(actual.stdout) == parsed_json_lines(expected.stdout)
        assert actual.stderr == expected.stderr == ""
    expected_usage = run_process(ORIGINAL, [sys.executable, "-m", "courier_quote.cli"])
    actual_usage = run_process(SUBMITTED, [sys.executable, "-m", "courier_quote.cli"])
    assert (
        actual_usage.returncode,
        actual_usage.stdout,
        actual_usage.stderr,
    ) == (
        expected_usage.returncode,
        expected_usage.stdout,
        expected_usage.stderr,
    ), "CLI usage text, stream, or exit status changed"


def test_cli_batch_mixed_behavior():
    requests = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))
    bad_service = dict(requests[8], service="drone")
    missing_coupon = dict(requests[9])
    del missing_coupon["coupon"]
    lines = [
        json.dumps(requests[7]),
        "",
        json.dumps(bad_service),
        "{broken-json",
        json.dumps(requests[10]),
        json.dumps(missing_coupon),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mixed.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        expected = run_process(
            ORIGINAL,
            [sys.executable, "-m", "courier_quote.cli", "batch", str(path)],
        )
        actual = run_process(
            SUBMITTED,
            [sys.executable, "-m", "courier_quote.cli", "batch", str(path)],
        )
    assert actual.returncode == expected.returncode == 2, (
        "a mixed batch must continue but exit 2 when any nonblank line is invalid"
    )
    assert parsed_json_lines(actual.stdout) == parsed_json_lines(expected.stdout), (
        "batch JSON results, error text, continuation, or physical line numbering changed"
    )
    assert actual.stderr == expected.stderr == ""


def test_validation_and_boundary_contracts():
    base = {
        "request_id": "BOUNDARY",
        "origin_zone": 4,
        "destination_zone": 5,
        "service": "ground",
        "weight_grams": 1000,
        "declared_value_cents": 56250,
        "residential": False,
        "fragile": True,
        "coupon": "SAVE15",
    }
    probes: list[object] = []
    for patch in (
        {},
        {"weight_grams": 1001},
        {"weight_grams": 20000},
        {"weight_grams": 20001},
        {"declared_value_cents": 56251},
        {"origin_zone": 8, "destination_zone": 8},
        {"service": "same_day", "weight_grams": 10000},
        {"service": "same_day", "weight_grams": 10001},
        {"service": "same_day", "origin_zone": 1, "destination_zone": 3},
        {"origin_zone": True},
        {"declared_value_cents": -1},
        {"fragile": 1},
        {"coupon": "save15"},
    ):
        probes.append(dict(base, **patch))
    missing = dict(base)
    del missing["request_id"]
    probes.extend([missing, ["not", "an", "object"]])
    code = r'''
import json, sys
from courier_quote import quote_parcel
answers = []
for row in json.load(sys.stdin):
    try:
        answers.append({"ok": quote_parcel(row)})
    except Exception as exc:
        answers.append({"error_type": type(exc).__name__, "message": str(exc)})
json.dump(answers, sys.stdout, separators=(",", ":"))
'''
    expected = run_probe(ORIGINAL, code, probes)
    actual = run_probe(SUBMITTED, code, probes)
    assert actual == expected, (
        "an independent validation, availability, rounding, or surcharge-boundary probe changed"
    )
