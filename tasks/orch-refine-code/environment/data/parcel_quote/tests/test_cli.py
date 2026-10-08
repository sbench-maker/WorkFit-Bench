from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "courier_quote.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_quote_command_emits_one_json_object():
    request = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))[31]
    expected = json.loads((FIXTURES / "expected_quotes.json").read_text(encoding="utf-8"))[31]
    result = run_cli("quote", json.dumps(request))
    assert result.returncode == 0
    assert json.loads(result.stdout) == expected
    assert result.stderr == ""


def test_batch_reports_invalid_lines_and_continues():
    result = run_cli("batch", str(FIXTURES / "batch_mixed.jsonl"))
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 2
    assert [row.get("request_id") for row in rows if "request_id" in row] == ["CASE-0001", "CASE-0002"]
    assert rows[1] == {"line": 2, "error": "unknown service: drone"}
    assert rows[3]["line"] == 4
    assert rows[4] == {"line": 5, "error": "missing field: coupon"}


def test_usage_is_stable():
    result = run_cli()
    assert result.returncode == 64
    assert result.stdout == ""
    assert result.stderr.strip() == "usage: courier-quote {quote JSON|batch PATH}"
