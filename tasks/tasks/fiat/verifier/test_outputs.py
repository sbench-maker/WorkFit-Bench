from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def load_output() -> object:
    assert OUTPUT_PATH.is_file(), "output.json is missing, so the client has no recommendation"
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"output.json is not readable JSON: {exc}")
    assert isinstance(value, (dict, list)) and value, "output.json must contain a non-empty JSON object or array"
    return value


def load_optional() -> object | None:
    if not OUTPUT_PATH.is_file():
        return None
    try:
        value = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) and value else None


def require_doc() -> object:
    value = load_optional()
    if value is None:
        pytest.skip("artifact usability test records the single missing or unreadable JSON defect")
    return value


def scalar_text(value: object) -> str:
    parts: list[str] = []
    for node in walk(value):
        if isinstance(node, (str, int, float, bool)):
            parts.append(str(node))
    return " ".join(parts)


SECTION_ALIASES = {
    "support": {"support", "supported", "eligibility", "availability", "capability", "capabilities"},
    "recommendation": {"recommendation", "recommendedroute", "primaryroute", "bestroute", "topchoice", "preferredoption", "primaryrecommendation"},
    "viable": {"viablepaymentroutes", "viableroutes", "usablepaymentroutes", "eligibleoptions", "availablemethods", "routecomparison", "paymentoptions"},
    "fallback": {"fallback", "fallbackroute", "alternative", "backup", "directfallback", "viablefallback"},
    "market": {"marketreference", "indicativemarketprice", "referenceprice", "price", "bestprice"},
    "wallet": {"wallet", "walletfunding", "walletplan", "fundingshortfall", "recommendation", "primaryrecommendation"},
    "deposits": {"walletdepositoptions", "depositoptions", "availabledepositmethods", "eligibledeposits", "fundingmethods"},
}


def find_sections(doc: object, section: str) -> list[object]:
    aliases = SECTION_ALIASES[section]
    found: list[object] = []
    for node in walk(doc):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if norm(key) in aliases:
                found.append(value)
    return found


def section_text(doc: object, section: str) -> str:
    return " ".join(scalar_text(value) for value in find_sections(doc, section))


def contains_code(value: object, code: str) -> bool:
    return norm(code) in norm(scalar_text(value))


def find_method_records(doc: object, code: str) -> list[dict]:
    target = norm(code)
    records: list[dict] = []
    for node in walk(doc):
        if not isinstance(node, dict):
            continue
        direct_values = [norm(value) for value in node.values() if isinstance(value, (str, int, float))]
        direct_keys = [norm(key) for key in node]
        if target in direct_values or target in direct_keys:
            records.append(node)
    return records


def numbers(value: object) -> list[float]:
    found: list[float] = []
    for node in walk(value):
        if isinstance(node, bool):
            continue
        if isinstance(node, (int, float)):
            found.append(float(node))
        elif isinstance(node, str):
            for match in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", node):
                try:
                    found.append(float(match.replace(",", "")))
                except ValueError:
                    pass
    return found


def has_number(value: object, expected: float, tolerance: float = 0.011) -> bool:
    return any(abs(actual - expected) <= tolerance for actual in numbers(value))


def record_with_numbers(doc: object, code: str, expected: tuple[float, ...]) -> bool:
    for record in find_method_records(doc, code):
        if all(has_number(record, number) for number in expected):
            return True
    return False


def positive_support(value: object) -> bool:
    positive = {"true", "yes", "supported", "available", "eligible", "confirmed"}
    for node in walk(value):
        if not isinstance(node, dict):
            continue
        for key, item in node.items():
            if norm(key) in {"supported", "issupported", "available", "eligible", "status"}:
                if item is True or norm(item) in positive:
                    return True
    text = scalar_text(value).lower()
    return ("supported" in text or "available" in text) and not re.search(r"\b(not|un)supported\b", text)


def explicitly_viable(record: dict) -> bool:
    for key, value in record.items():
        if norm(key) in {"viable", "eligible", "usable", "available", "status"}:
            return value is True or norm(value) in {"yes", "true", "viable", "eligible", "usable", "available", "active"}
    return False


def viable_codes(doc: object) -> set[str]:
    known = {"AUD_WALLET", "VISA_CARD", "MASTER_CARD", "OSKO_TRANSFER", "EASY_CARD", "P2P_PAYID", "P2P_BANK"}
    codes: set[str] = set()
    for section in find_sections(doc, "viable"):
        for code in known:
            if contains_code(section, code):
                codes.add(code)
    for code in known:
        if any(explicitly_viable(record) for record in find_method_records(doc, code)):
            codes.add(code)
    return codes


def test_market_support_confirmation():
    """The deliverable positively confirms the requested AU/AUD/BTC BUY capability."""
    doc = require_doc()
    sections = find_sections(doc, "support")
    assert sections, "the recommendation does not expose a support or eligibility conclusion"
    support = sections[0]
    text = norm(scalar_text(support))
    assert "aud" in text and "btc" in text and "buy" in text, (
        "support conclusion must identify the AUD/BTC BUY request; otherwise it could refer to a distractor market"
    )
    assert ("au" in text or "australia" in text) and positive_support(support), (
        "the artifact does not positively confirm support for the Australian request"
    )


def test_payment_route_eligibility_and_ranking():
    """All amount-eligible active routes are compared and the lowest BUY quote is recommended."""
    doc = require_doc()
    codes = viable_codes(doc)
    expected = {"AUD_WALLET", "VISA_CARD", "MASTER_CARD"}
    assert expected <= codes, (
        f"usable route comparison is missing {sorted(expected - codes)}; the client cannot compare the current options"
    )
    invalid = {"OSKO_TRANSFER", "EASY_CARD", "P2P_PAYID", "P2P_BANK"}
    assert not (codes & invalid), (
        f"routes that are suspended or outside the requested limits are presented as usable: {sorted(codes & invalid)}"
    )
    recommendation = section_text(doc, "recommendation")
    assert contains_code(recommendation, "AUD_WALLET"), (
        "AUD_WALLET has the lowest valid BUY quotation and should be the primary route"
    )
    assert not any(contains_code(recommendation, code) for code in invalid), (
        "the primary recommendation includes a suspended or limit-ineligible route"
    )


def test_current_prices_costs_and_fallback():
    """Current quotations, purchase costs, market reference, and direct fallback agree with the frozen data."""
    doc = require_doc()
    assert record_with_numbers(doc, "AUD_WALLET", (103200.0, 1857.60)), (
        "AUD_WALLET must show the current 103,200 AUD/BTC quote and AUD 1,857.60 estimate"
    )
    assert record_with_numbers(doc, "VISA_CARD", (104500.0, 1881.00)), (
        "Visa must show the current 104,500 AUD/BTC quote and AUD 1,881.00 estimate"
    )
    assert record_with_numbers(doc, "MASTER_CARD", (104650.0, 1883.70)), (
        "Mastercard must show the current 104,650 AUD/BTC quote and AUD 1,883.70 estimate"
    )
    market = section_text(doc, "market")
    assert has_number(market, 103150.0), "the indicative market reference should be AUD 103,150 per BTC"
    fallback = section_text(doc, "fallback")
    assert contains_code(fallback, "VISA_CARD") and has_number(fallback, 1881.0), (
        "Visa is the lowest-cost direct fallback that does not require topping up the wallet"
    )


def test_wallet_shortfall_and_deposit_options():
    """The wallet shortfall is correct and only eligible deposit routes are offered for that amount."""
    doc = require_doc()
    wallet = section_text(doc, "wallet")
    assert has_number(wallet, 450.0) and has_number(wallet, 1407.60), (
        "the wallet plan must reconcile the AUD 450 balance to the AUD 1,407.60 shortfall"
    )
    deposits = section_text(doc, "deposits")
    assert contains_code(deposits, "PAYID_DEPOSIT") and contains_code(deposits, "AUD_BANK_DEPOSIT"), (
        "both active deposit methods whose limits cover AUD 1,407.60 should be offered"
    )
    assert not contains_code(deposits, "CARD_DEPOSIT") and not contains_code(deposits, "CASH_AGENT_DEPOSIT"), (
        "a suspended deposit method or one whose minimum exceeds the shortfall is presented as available"
    )


def test_regional_action_links():
    """The regional BUY and DEPOSIT actions point to the requested pair and fiat currency."""
    doc = require_doc()
    text = scalar_text(doc)
    assert "https://www.binance.com/en-AU/crypto/buy/AUD/BTC" in text, (
        "the Australian-English AUD/BTC buy action link is missing"
    )
    assert "https://www.binance.com/en-AU/fiat/deposit/AUD" in text, (
        "the wallet-funding recommendation needs the Australian-English AUD deposit link"
    )
