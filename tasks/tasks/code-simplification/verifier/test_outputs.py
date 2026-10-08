from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path("/root/data/checkout_project")
CASES_PATH = PROJECT_DIR / "tests" / "behavior_cases.json"
OUTPUT_MODULE = Path("/root/results/pricing.py")
OUTPUT_NOTES = Path("/root/results/refactor_notes.md")
FOCUS_GROUPS = ("coupon", "rounding", "shipping", "tax_credit", "tier", "validation")

sys.path.insert(0, str(PROJECT_DIR))

_MODULE = None
_MODULE_ERROR: Exception | None = None


def _load_candidate():
    global _MODULE, _MODULE_ERROR
    if _MODULE is not None:
        return _MODULE
    if _MODULE_ERROR is not None:
        raise _MODULE_ERROR
    try:
        import checkout  # noqa: F401 - establishes the package for relative imports

        spec = importlib.util.spec_from_file_location("checkout._submitted_pricing", OUTPUT_MODULE)
        if spec is None or spec.loader is None:
            raise ImportError("could not create an import specification")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE = module
        return module
    except Exception as exc:
        _MODULE_ERROR = exc
        raise


def _cases() -> list[dict]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and len(payload) == 240
    return payload


def _candidate_or_group_failure(focus: str):
    try:
        return _load_candidate()
    except Exception as exc:
        if focus == FOCUS_GROUPS[0]:
            pytest.fail(f"submitted pricing module could not be loaded: {type(exc).__name__}: {exc}")
        pytest.skip("module load failure already reported for this criterion")


def _run_case(function, case: dict) -> tuple[dict | None, dict | None, list[str], dict]:
    submitted_order = copy.deepcopy(case["order"])
    initial_order = copy.deepcopy(submitted_order)
    events: list[str] = []
    result = None
    exception = None
    try:
        result = function(submitted_order, events)
    except Exception as exc:
        exception = {"type": type(exc).__name__, "message": str(exc)}
    return result, exception, events, {"before": initial_order, "after": submitted_order}


def test_artifact_delivery() -> None:
    assert OUTPUT_MODULE.is_file(), "the requested /root/results/pricing.py is missing"
    assert OUTPUT_NOTES.is_file(), "the requested /root/results/refactor_notes.md is missing"
    source = OUTPUT_MODULE.read_text(encoding="utf-8")
    notes = OUTPUT_NOTES.read_text(encoding="utf-8")
    assert source.strip(), "the revised pricing module is empty"
    assert notes.strip(), "the refactor notes are empty"
    compile(source, str(OUTPUT_MODULE), "exec")
    _load_candidate()


@pytest.mark.parametrize("focus", FOCUS_GROUPS)
def test_quote_results_and_errors(focus: str) -> None:
    module = _candidate_or_group_failure(focus)
    failures = []
    selected = [case for case in _cases() if case["focus"] == focus]
    assert selected, f"fixture has no cases for focus group {focus}"
    for case in selected:
        result, exception, _events, order_state = _run_case(module.calculate_order_quote, case)
        expected = case["expected"]
        expected_exception = expected.get("exception")
        if expected_exception != exception:
            failures.append(
                f"{case['case_id']}: exception {exception!r}, expected {expected_exception!r}"
            )
        elif expected_exception is None and result != expected["result"]:
            failures.append(
                f"{case['case_id']}: result {result!r}, expected {expected['result']!r}"
            )
        if order_state["after"] != order_state["before"]:
            failures.append(f"{case['case_id']}: input order was mutated")
    assert not failures, "behavior regressions:\n" + "\n".join(failures[:12])


@pytest.mark.parametrize("focus", FOCUS_GROUPS)
def test_audit_event_sequences(focus: str) -> None:
    module = _candidate_or_group_failure(focus)
    failures = []
    for case in (row for row in _cases() if row["focus"] == focus):
        _result, _exception, events, _order_state = _run_case(
            module.calculate_order_quote, case
        )
        if events != case["expected"]["events"]:
            failures.append(
                f"{case['case_id']}: events {events!r}, expected {case['expected']['events']!r}"
            )
    assert not failures, "audit sequence regressions:\n" + "\n".join(failures[:12])


def test_drop_in_public_contract() -> None:
    module = _load_candidate()
    function = getattr(module, "calculate_order_quote", None)
    assert callable(function), "module does not expose callable calculate_order_quote"
    signature = inspect.signature(function)
    try:
        signature.bind(order={})
        signature.bind(order={}, audit_events=[])
    except TypeError as exc:
        pytest.fail(f"public order/audit_events calling forms are incompatible: {exc}")
