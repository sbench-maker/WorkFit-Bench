from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


RESULTS_DIR = Path(os.environ.get("SKILLSBENCH_RESULTS", "/root/results"))
DATA_DIR = Path(os.environ.get("SKILLSBENCH_DATA", "/root/data"))
SUBMISSION = RESULTS_DIR / "checkout_spec.rb"
APP_DIR = DATA_DIR / "ticket_app"


MUTATIONS = {
    "wrong_total": (
        "discount = valid_promo ? 5.0 : 0.0",
        "discount = valid_promo ? 4.0 : 0.0",
    ),
    "missing_confirmation": (
        'layout("Order confirmed", <<~HTML))\n      <h1>Order confirmed</h1>',
        'layout("Reservation received", <<~HTML))\n      <h1>Reservation received</h1>',
    ),
    "sold_out_selectable": (
        'event["status"] == "sold_out"',
        "false",
    ),
    "invalid_promo_accepted": (
        'valid_promo = promo == "NIGHT5"',
        "valid_promo = true",
    ),
}


@dataclass(frozen=True)
class RunResult:
    returncode: int
    examples: int
    failures: int
    output: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and self.examples > 0 and self.failures == 0


def _failure_message(result: RunResult) -> str:
    excerpt = result.output[-4000:] if result.output else "RSpec produced no diagnostic output"
    return (
        f"returncode={result.returncode}, examples={result.examples}, failures={result.failures}\n"
        f"{excerpt}"
    )


def _mutate_app(app_path: Path, mutation: str | None) -> None:
    if mutation is None:
        return
    old, new = MUTATIONS[mutation]
    source = app_path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"authoring mutation {mutation!r} expected one source match, found {count}")
    app_path.write_text(source.replace(old, new, 1), encoding="utf-8")


@lru_cache(maxsize=None)
def run_submission(mutation: str | None = None) -> RunResult:
    if not SUBMISSION.is_file():
        return RunResult(2, 0, 0, f"missing submission: {SUBMISSION}")
    try:
        submitted_source = SUBMISSION.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return RunResult(2, 0, 0, f"cannot read submission as UTF-8: {exc}")

    with tempfile.TemporaryDirectory(prefix="ticket-spec-") as raw_tmp:
        root = Path(raw_tmp)
        copied_app = root / "data" / "ticket_app"
        copied_results = root / "results"
        shutil.copytree(APP_DIR, copied_app)
        copied_results.mkdir(parents=True)
        _mutate_app(copied_app / "app.rb", mutation)

        # Normalize the explicit task path while also accepting require_relative and
        # RUBYLIB-based specs. This changes location only, never submitted behavior.
        normalized_source = submitted_source.replace("/root/data/ticket_app", str(copied_app))
        spec_path = copied_results / "checkout_spec.rb"
        spec_path.write_text(normalized_source, encoding="utf-8")
        report_path = root / "rspec.json"
        env = os.environ.copy()
        env["TICKET_APP_SPEC_HELPER"] = str(copied_app / "spec_helper.rb")
        env["TICKET_EVENTS_PATH"] = str(copied_app / "events.json")
        env["RUBYLIB"] = str(copied_app) + os.pathsep + env.get("RUBYLIB", "")
        try:
            completed = subprocess.run(
                [
                    "rspec",
                    str(spec_path),
                    "--order",
                    "defined",
                    "--format",
                    "json",
                    "--out",
                    str(report_path),
                ],
                cwd=copied_results,
                env=env,
                capture_output=True,
                text=True,
                timeout=40,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return RunResult(2, 0, 0, f"could not execute RSpec: {exc}")

        examples = failures = 0
        report_note = ""
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                rows = report.get("examples", [])
                examples = len(rows) if isinstance(rows, list) else 0
                failures = sum(row.get("status") != "passed" for row in rows if isinstance(row, dict))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                report_note = f"\ninvalid RSpec JSON report: {exc}"
        else:
            report_note = "\nRSpec JSON report was not created"
        output = (completed.stdout or "") + (completed.stderr or "") + report_note
        return RunResult(completed.returncode, examples, failures, output)


def require_passing_baseline() -> RunResult:
    baseline = run_submission(None)
    if not baseline.passed:
        pytest.skip("the reference-app run is not usable for downstream mutation checks")
    return baseline


def test_artifact_runnable():
    """The submitted feature spec must execute cleanly on the frozen reference app."""
    baseline = run_submission(None)
    assert baseline.passed, (
        "checkout_spec.rb must contain executable RSpec examples that pass against the bundled Rack app; "
        + _failure_message(baseline)
    )


@pytest.mark.parametrize("mutation", ["wrong_total", "missing_confirmation"])
def test_successful_checkout_regressions(mutation):
    """The success journey must fail when its displayed total or confirmation state regresses."""
    require_passing_baseline()
    mutated = run_submission(mutation)
    assert mutated.returncode != 0 and mutated.failures > 0, (
        f"the spec still passed with the {mutation} checkout regression, so the search-to-confirmation "
        "journey does not protect this user-visible outcome; "
        + _failure_message(mutated)
    )


def test_sold_out_regression():
    """The spec must fail if Riverglass Matinee becomes selectable and purchasable."""
    require_passing_baseline()
    mutated = run_submission("sold_out_selectable")
    assert mutated.returncode != 0 and mutated.failures > 0, (
        "the spec still passed when the sold-out event became available, allowing an impossible checkout; "
        + _failure_message(mutated)
    )


def test_invalid_promo_regression():
    """The spec must fail if SUNSET10 is accepted and changes the two-ticket total."""
    require_passing_baseline()
    mutated = run_submission("invalid_promo_accepted")
    assert mutated.returncode != 0 and mutated.failures > 0, (
        "the spec still passed when SUNSET10 was accepted, so a customer-facing pricing regression would escape; "
        + _failure_message(mutated)
    )
