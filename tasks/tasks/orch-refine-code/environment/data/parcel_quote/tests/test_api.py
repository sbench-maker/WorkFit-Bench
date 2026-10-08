from __future__ import annotations

import json
from pathlib import Path

import pytest

from courier_quote import quote_manifest, quote_parcel


FIXTURES = Path(__file__).parent / "fixtures"
REQUESTS = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIXTURES / "expected_quotes.json").read_text(encoding="utf-8"))


def test_generated_quotes_match_frozen_regression_examples():
    assert [quote_parcel(row) for row in REQUESTS] == EXPECTED


def test_manifest_matches_individual_calls_and_preserves_order():
    sample = REQUESTS[17:49]
    assert quote_manifest(sample) == [quote_parcel(row) for row in sample]


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"weight_grams": 0}, "weight_grams must be an integer from 1 to 50000"),
        ({"origin_zone": True}, "origin_zone must be an integer from 1 to 8"),
        ({"service": "drone"}, "unknown service: drone"),
        ({"coupon": "SAVE20"}, "unknown coupon: SAVE20"),
        ({"residential": 1}, "residential must be a boolean"),
    ],
)
def test_validation_messages_are_stable(patch, message):
    request = dict(REQUESTS[0])
    request.update(patch)
    with pytest.raises(ValueError, match=f"^{message}$"):
        quote_parcel(request)


def test_manifest_requires_a_list():
    with pytest.raises(TypeError, match="^requests must be a list$"):
        quote_manifest(tuple(REQUESTS[:2]))


def test_extra_request_fields_do_not_change_output():
    request = dict(REQUESTS[4], audit_label="internal-only")
    assert quote_parcel(request) == EXPECTED[4]
