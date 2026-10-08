from __future__ import annotations

import copy
import builtins
import json
from pathlib import Path

import pytest

from checkout.pricing import calculate_order_quote


CASES = json.loads((Path(__file__).parent / "behavior_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["case_id"])
def test_frozen_quote_behavior(case: dict) -> None:
    events: list[str] = []
    expected = case["expected"]
    if "exception" in expected:
        exception_type = getattr(builtins, expected["exception"]["type"])
        with pytest.raises(exception_type, match=f"^{__import__('re').escape(expected['exception']['message'])}$"):
            calculate_order_quote(copy.deepcopy(case["order"]), events)
    else:
        assert calculate_order_quote(copy.deepcopy(case["order"]), events) == expected["result"]
    assert events == expected["events"]
