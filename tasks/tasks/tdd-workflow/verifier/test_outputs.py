from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET

import pytest


SUBMISSION_ROOT = Path(os.environ.get("SUBMISSION_ROOT", "/root/results"))
DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/root/data"))
REPO = SUBMISSION_ROOT / "checkout-ledger"
BASELINE = DATA_ROOT / "checkout-ledger"


def run(command: list[str], *, cwd: Path, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=check,
    )


def python_json(repo: Path, script: str, payload: object | None = None) -> object:
    process = run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=repo,
        timeout=30,
    )
    assert process.returncode == 0, f"public API probe failed:\n{process.stdout}"
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"public API probe did not emit one JSON value: {exc}\n{process.stdout}")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo, timeout=30)


def test_artifact_usability():
    assert REPO.is_dir(), "missing requested /root/results/checkout-ledger repository"
    for relative in ("checkout_quote/__init__.py", "checkout.plan.md", "docs/testing/checkout.tdd.md", ".git"):
        assert (REPO / relative).exists(), f"completed repository is missing {relative}"
    status = git(REPO, "status", "--porcelain")
    assert status.returncode == 0, f"delivered artifact is not a readable Git repository:\n{status.stdout}"
    substantive_changes = []
    for line in status.stdout.splitlines():
        path = line[3:].strip()
        generated = line.startswith("?? ") and (
            path == ".coverage"
            or "/__pycache__/" in f"/{path}"
            or path.endswith("/__pycache__/")
            or path == ".pytest_cache/"
            or path.startswith(".pytest_cache/")
        )
        if not generated:
            substantive_changes.append(line)
    assert not substantive_changes, (
        "delivered Git worktree has uncommitted source or documentation files:\n"
        + "\n".join(substantive_changes)
    )
    probe = python_json(
        REPO,
        """
        import json
        import checkout_quote
        print(json.dumps({"callable": callable(checkout_quote.calculate_quote)}))
        """,
    )
    assert probe == {"callable": True}, "public calculate_quote library entry point is unavailable"


QUOTE_CASES = [
    (
        "mixed_cart",
        {
            "items": [
                {"sku": "BOOK", "unit_price": "19.99", "quantity": 1, "kind": "merchandise", "taxable": True},
                {"sku": "GIFT-25", "unit_price": "25.00", "quantity": 1, "kind": "gift_card", "taxable": False},
            ],
            "promo_code": "SAVE10",
            "tax_rate": "0.0825",
        },
        {"subtotal": "44.99", "discount": "2.00", "tax": "1.48", "total": "44.47"},
    ),
    (
        "line_rounding",
        {
            "items": [
                {"sku": "A", "unit_price": "0.05", "quantity": 1, "kind": "merchandise", "taxable": False},
                {"sku": "B", "unit_price": "0.05", "quantity": 1, "kind": "merchandise", "taxable": False},
                {"sku": "G", "unit_price": "10.00", "quantity": 1, "kind": "gift_card", "taxable": False},
            ],
            "promo_code": "SAVE10",
            "tax_rate": "0.25",
        },
        {"subtotal": "10.10", "discount": "0.02", "tax": "0.00", "total": "10.08"},
    ),
    (
        "taxable_and_nontaxable_merchandise",
        {
            "items": [
                {"sku": "T", "unit_price": "10.05", "quantity": 2, "kind": "merchandise", "taxable": True},
                {"sku": "N", "unit_price": "8.25", "quantity": 1, "kind": "merchandise", "taxable": False},
                {"sku": "G", "unit_price": "5.00", "quantity": 2, "kind": "gift_card", "taxable": False},
            ],
            "promo_code": "SAVE10",
            "tax_rate": "0.075",
        },
        {"subtotal": "38.35", "discount": "2.84", "tax": "1.36", "total": "36.87"},
    ),
    (
        "blank_promo",
        {
            "items": [
                {"sku": "M", "unit_price": "1.15", "quantity": 3, "kind": "merchandise", "taxable": True},
                {"sku": "G", "unit_price": "20.00", "quantity": 1, "kind": "gift_card", "taxable": False},
            ],
            "promo_code": "  ",
            "tax_rate": "0.10",
        },
        {"subtotal": "23.45", "discount": "0.00", "tax": "0.35", "total": "23.80"},
    ),
]


@pytest.mark.parametrize("name,payload,expected", QUOTE_CASES, ids=[case[0] for case in QUOTE_CASES])
def test_quote_business_rules(name, payload, expected):
    result = python_json(
        REPO,
        """
        import json, sys
        from checkout_quote import calculate_quote
        payload = json.loads(sys.stdin.read()) if False else None
        embedded = json.loads(%r)
        print(json.dumps(calculate_quote(embedded), sort_keys=True))
        """ % json.dumps(payload),
    )
    assert result == expected, f"{name} quote is {result}, expected {expected}; checkout would charge the wrong amount"


def test_library_and_adapter_validation_contract():
    result = python_json(
        REPO,
        """
        import json
        from checkout_quote import QuoteError, calculate_quote
        from checkout_quote.api import quote_response

        base_item = {"sku": "M", "unit_price": "10.00", "quantity": 1, "kind": "merchandise", "taxable": True}
        invalid = [
            {"items": [], "tax_rate": "0"},
            {"items": [base_item], "promo_code": "SAVE20", "tax_rate": "0"},
            {"items": [{**base_item, "quantity": 0}], "tax_rate": "0"},
            {"items": [{**base_item, "quantity": True}], "tax_rate": "0"},
            {"items": [{**base_item, "unit_price": "1.001"}], "tax_rate": "0"},
            {"items": [{**base_item, "kind": "gift_card", "taxable": True}], "tax_rate": "0"},
            {"items": [base_item], "tax_rate": "0.2501"},
        ]
        rows = []
        for payload in invalid:
            try:
                calculate_quote(payload)
                library_error = False
            except QuoteError:
                library_error = True
            status, body = quote_response(payload)
            rows.append({
                "library_error": library_error,
                "status": status,
                "code": body.get("error", {}).get("code"),
                "has_total": "quote" in body,
            })
        valid = {"items": [base_item], "promo_code": None, "tax_rate": "0.05"}
        status, body = quote_response(valid)
        print(json.dumps({"invalid": rows, "valid_matches": status == 200 and body.get("quote") == calculate_quote(valid)}))
        """,
    )
    assert result["valid_matches"], "HTTP adapter does not return the same valid quote as the library"
    for index, row in enumerate(result["invalid"]):
        assert row == {"library_error": True, "status": 400, "code": "invalid_quote", "has_total": False}, (
            f"invalid case {index} did not fail consistently without a partial quote: {row}"
        )


def test_live_http_route_contract():
    payload = QUOTE_CASES[0][1]
    expected = QUOTE_CASES[0][2]
    result = python_json(
        REPO,
        """
        import json, threading
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        from checkout_quote.api import create_server

        server = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        def post(path, raw):
            request = Request(base + path, data=raw, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urlopen(request, timeout=2) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as exc:
                return exc.code, json.loads(exc.read())
        try:
            valid = post("/quote", json.dumps(json.loads(%r)).encode())
            malformed = post("/quote", b"{broken")
            unknown = post("/unknown", b"{}")
            print(json.dumps({"valid": valid, "malformed": malformed, "unknown": unknown}))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        """ % json.dumps(payload),
    )
    assert result["valid"] == [200, {"quote": expected}], "live POST /quote differs from the corrected library quote"
    assert result["malformed"][0] == 400 and result["malformed"][1].get("error", {}).get("code") == "invalid_quote"
    assert result["unknown"][0] == 404, "unknown HTTP routes must remain distinguishable from invalid quotes"


def test_suite_coverage_and_regression_protection(tmp_path):
    coverage_file = tmp_path / "coverage.json"
    junit_file = tmp_path / "submitted.xml"
    suite = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--cov=checkout_quote",
            f"--cov-report=json:{coverage_file}",
            "--cov-fail-under=80",
            f"--junitxml={junit_file}",
            "tests",
        ],
        cwd=REPO,
        timeout=120,
    )
    assert suite.returncode == 0, f"submitted suite or 80% line threshold failed:\n{suite.stdout}"
    coverage = json.loads(coverage_file.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    assert coverage >= 80, f"line coverage is {coverage:.2f}%, below the requested 80%"
    junit = ET.parse(junit_file).getroot()
    skipped = [node.get("name", "") for node in junit.iter("testcase") if node.find("skipped") is not None]
    assert not skipped, f"submitted suite contains skipped tests: {skipped}"

    baseline_copy = tmp_path / "baseline"
    shutil.copytree(BASELINE, baseline_copy)
    submitted_tests = REPO / "tests"
    assert submitted_tests.is_dir(), "submitted repository has no tests directory to protect the regression"
    shutil.rmtree(baseline_copy / "tests")
    shutil.copytree(submitted_tests, baseline_copy / "tests")
    baseline_run = run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=baseline_copy, timeout=120)
    assert baseline_run.returncode != 0, (
        "submitted tests also pass against the frozen defective implementation; they do not protect the reported regression"
    )


def test_red_green_git_checkpoints(tmp_path):
    assert git(REPO, "rev-parse", "--verify", "task-baseline^{commit}").returncode == 0, "seed baseline tag is missing"
    ancestry = git(REPO, "merge-base", "--is-ancestor", "task-baseline", "HEAD")
    assert ancestry.returncode == 0, "task-baseline is not reachable from the delivered HEAD"
    commits_result = git(REPO, "rev-list", "--reverse", "task-baseline..HEAD")
    assert commits_result.returncode == 0
    commits = [line for line in commits_result.stdout.splitlines() if line]
    assert len(commits) >= 2, "RED and GREEN must be preserved as separate commits after the seeded baseline"

    red_hash = None
    green_hash = None
    production_seen = False
    history_copy = tmp_path / "history"
    shutil.copytree(REPO, history_copy)
    for commit in commits:
        changed = git(REPO, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).stdout.splitlines()
        changes_production = any(path.startswith("checkout_quote/") and path.endswith(".py") for path in changed)
        changes_tests = any(path.startswith("tests/") and path.endswith(".py") for path in changed)
        if changes_production:
            production_seen = True
        if red_hash is None and changes_tests and not production_seen:
            git(history_copy, "checkout", "-q", commit)
            red_run = run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=history_copy, timeout=120)
            if red_run.returncode != 0:
                red_hash = commit
                continue
        if red_hash is not None and changes_production:
            git(history_copy, "checkout", "-q", commit)
            green_run = run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=history_copy, timeout=120)
            if green_run.returncode == 0:
                green_hash = commit
                break

    assert red_hash is not None, "no reachable tests-first checkpoint reproduces RED before production code changes"
    assert green_hash is not None, "no later separate production checkpoint reproduces GREEN"
