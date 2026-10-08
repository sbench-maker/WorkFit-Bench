from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "vendor_review.md"


def _submission() -> str | None:
    try:
        text = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return text if text.strip() else None


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _money_values(text: str) -> list[float]:
    values: list[float] = []
    pattern = re.compile(
        r"(?:(?:US)?\$|USD\s*)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*([kmb])?",
        re.IGNORECASE,
    )
    factors = {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}
    for match in pattern.finditer(text):
        number = float(match.group(1).replace(",", ""))
        values.append(number * factors[(match.group(2) or "").casefold()])
    return values


def _percent_values(text: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*%", text)
    ]


def _has_close(values: list[float], expected: float, tolerance: float) -> bool:
    return any(math.isclose(value, expected, abs_tol=tolerance, rel_tol=0) for value in values)


def _contexts(text: str) -> list[str]:
    chunks = [line.strip() for line in text.splitlines() if line.strip()]
    chunks.extend(part.strip() for part in re.split(r"\n\s*\n", text) if part.strip())
    return chunks


def _context_with(text: str, *tokens: str) -> list[str]:
    wanted = [token.casefold() for token in tokens]
    return [chunk for chunk in _contexts(text) if all(token in chunk.casefold() for token in wanted)]


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _expected_costs() -> tuple[float, float, float]:
    context = (DATA_DIR / "procurement_context.md").read_text(encoding="utf-8")
    atlas_doc = (DATA_DIR / "atlaspay_renewal.md").read_text(encoding="utf-8")
    beacon_doc = (DATA_DIR / "beaconap_proposal.md").read_text(encoding="utf-8")

    volume_match = re.search(
        r"([\d,]+) in 2027; ([\d,]+) in 2028; ([\d,]+) in 2029", context
    )
    assert volume_match, "authoring fixture lost the three-year invoice forecast"
    volumes = {
        2027 + index: int(raw.replace(",", ""))
        for index, raw in enumerate(volume_match.groups())
    }

    atlas_rate = float(re.search(r"2027: \$([\d.]+) per", atlas_doc).group(1))
    atlas_minimum = float(re.search(r"\$([\d,]+) annual minimum", atlas_doc).group(1).replace(",", ""))
    atlas_escalator = float(re.search(r"increase (\d+)%", atlas_doc).group(1)) / 100
    atlas_support = float(re.search(r"\$([\d,]+) per year", atlas_doc).group(1).replace(",", ""))
    atlas_training = float(re.search(r"one-time \$([\d,]+) charge", atlas_doc).group(1).replace(",", ""))
    atlas_exit = float(re.search(r"mandatory \$([\d,]+) professional", atlas_doc).group(1).replace(",", ""))
    atlas_total = 0.0
    for offset, year in enumerate(volumes):
        factor = (1 + atlas_escalator) ** offset
        atlas_total += max(atlas_minimum * factor, volumes[year] * atlas_rate * factor)
        atlas_total += atlas_support
    atlas_total += atlas_training + atlas_exit

    beacon_base = float(re.search(r"subscription: \$([\d,]+)", beacon_doc).group(1).replace(",", ""))
    included = int(re.search(r"including ([\d,]+) processed", beacon_doc).group(1).replace(",", ""))
    overage = float(re.search(r"overage: \$([\d.]+) per", beacon_doc).group(1))
    beacon_escalator = float(re.search(r"increase (\d+)%", beacon_doc).group(1)) / 100
    beacon_support = float(re.search(r"\$([\d,]+) per year", beacon_doc).group(1).replace(",", ""))
    one_time = [
        float(value.replace(",", ""))
        for value in re.search(
            r"implementation \$([\d,]+); Northstar LegacyERP connector and data migration \$([\d,]+); user/admin training \$([\d,]+)",
            beacon_doc,
        ).groups()
    ]
    dual_run = float(re.search(r"adds \$([\d,]+) in transition", beacon_doc).group(1).replace(",", ""))
    beacon_total = 0.0
    for offset, year in enumerate(volumes):
        factor = (1 + beacon_escalator) ** offset
        beacon_total += beacon_base * factor
        beacon_total += max(0, volumes[year] - included) * overage * factor
        beacon_total += beacon_support
    beacon_total += sum(one_time) + dual_run
    return atlas_total, beacon_total, beacon_total - atlas_total


def _expected_performance() -> tuple[float, float, int]:
    daily = _read_csv("atlaspay_daily_performance.csv")
    scheduled = sum(int(row["scheduled_minutes"]) for row in daily)
    downtime = sum(int(row["unplanned_downtime_minutes"]) for row in daily)
    availability = 100 * (scheduled - downtime) / scheduled

    tickets = _read_csv("atlaspay_support_tickets.csv")
    sev1 = [row for row in tickets if row["severity"].casefold() == "sev1"]
    compliant = sum(
        int(row["first_response_minutes"]) <= int(row["contract_target_minutes"])
        for row in sev1
    )
    compliance = 100 * compliant / len(sev1)
    return availability, compliance, compliant


def test_artifact_usability():
    text = _submission()
    assert text is not None, f"the requested readable Markdown review is missing at {OUTPUT}"
    assert len(text) >= 700, "the review is too slight to support a procurement sign-off"
    folded = _fold(text)
    assert "atlaspay" in folded and "beaconap" in folded, "both compared vendors must be covered"
    concepts = {
        "cost": ("tco", "total cost"),
        "performance": ("performance", "availability", "uptime", "sla"),
        "security/contract": ("security", "breach", "dpa", "contract"),
        "recommendation": ("recommend", "sign-off", "signoff"),
        "negotiation": ("negotiat", "condition for", "contract change"),
    }
    missing = [name for name, aliases in concepts.items() if not any(alias in folded for alias in aliases)]
    assert not missing, f"the review omits explicitly requested decision content: {missing}"


def test_three_year_tco_and_delta():
    text = _submission()
    if text is None:
        return
    atlas_expected, beacon_expected, delta_expected = _expected_costs()
    money = _money_values(text)
    tolerance_atlas = max(250.0, atlas_expected * 0.0015)
    tolerance_beacon = max(250.0, beacon_expected * 0.0015)
    assert _has_close(money, atlas_expected, tolerance_atlas), (
        f"AtlasPay three-year TCO should be about ${atlas_expected:,.2f}; a wrong total can reverse the procurement decision"
    )
    assert _has_close(money, beacon_expected, tolerance_beacon), (
        f"BeaconAP three-year TCO should be about ${beacon_expected:,.2f}; mandatory transition costs or escalated overages appear missing"
    )
    assert _has_close(money, delta_expected, max(250.0, delta_expected * 0.002)), (
        f"the review should quantify the roughly ${delta_expected:,.2f} three-year difference"
    )
    folded = _fold(text)
    atlas_position = folded.find("atlaspay")
    beacon_position = folded.find("beaconap")
    assert atlas_position >= 0 and beacon_position >= 0
    assert any(term in folded for term in ("lower", "less", "cheaper", "saving", "more", "higher")), (
        "the TCO comparison needs to state which option costs more, not only list disconnected totals"
    )


def test_observed_performance_facts():
    text = _submission()
    if text is None:
        return
    availability, compliance, compliant_count = _expected_performance()
    percentages = _percent_values(text)
    assert _has_close(percentages, availability, 0.06), (
        f"AtlasPay observed availability should be approximately {availability:.2f}%"
    )
    assert _has_close(percentages, compliance, 0.2), (
        f"AtlasPay Sev-1 response compliance should be approximately {compliance:.1f}%"
    )
    folded = _fold(text)
    count_forms = (
        rf"{compliant_count}\s*(?:of|/)\s*12",
        rf"seven\s+of\s+twelve" if compliant_count == 7 else r"a^",
    )
    assert any(re.search(pattern, folded) for pattern in count_forms), (
        "the Sev-1 rate should be traceable to the observed compliant-ticket count"
    )
    atlas_observed = _context_with(text, "atlaspay", "observ")
    assert atlas_observed, "AtlasPay record-derived results must be clearly identified as observed evidence"


def test_material_side_by_side_facts():
    text = _submission()
    if text is None:
        return
    folded = _fold(text)
    checks: dict[str, bool] = {}
    checks["SLA commitments"] = (
        _has_close(_percent_values(" ".join(_context_with(text, "atlaspay"))), 99.90, 0.011)
        and _has_close(_percent_values(" ".join(_context_with(text, "beaconap"))), 99.95, 0.011)
    )
    checks["LegacyERP distinction"] = (
        "legacyerp" in folded and "custom connector" in folded and "native" in folded
    )
    checks["replacement timing"] = bool(
        re.search(r"(?:2027[-/]03[-/]01|(?:march|mar\.?)[ ]+1(?:st)?[,]?[ ]+2027)", folded)
    )
    export_context = " ".join(_context_with(text, "export"))
    checks["exit treatment"] = (
        _has_close(_money_values(export_context), 35_000, 30)
        and "include" in export_context.casefold()
    )
    checks["reference delays"] = bool(
        re.search(r"(?:2|two)\s*(?:of|/)\s*(?:3|three)", folded)
        and ("late" in folded or "delay" in folded)
    )
    passed = sum(checks.values())
    assert passed >= 4, (
        "the side-by-side view misses material frozen facts: "
        + ", ".join(name for name, ok in checks.items() if not ok)
    )
