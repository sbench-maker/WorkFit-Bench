from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from pypdf import PdfReader


OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/qbr-2026-Q2.pdf"))
if not OUTPUT.is_absolute():
    raise ValueError("Verifier output path must be absolute")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().replace("–", "-").replace("—", "-"))


def read_pdf() -> tuple[int, str, str | None]:
    if not OUTPUT.is_file():
        return 0, "", "requested PDF is missing"
    try:
        reader = PdfReader(OUTPUT)
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    return len(reader.pages), "", "PDF is encrypted"
            except Exception:
                return len(reader.pages), "", "PDF is encrypted"
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return len(reader.pages), text, None
    except Exception as exc:
        return 0, "", f"PDF could not be opened: {exc}"


PAGES, TEXT, PDF_ERROR = read_pdf()
FLAT = normalize(TEXT)


def windows(labels: tuple[str, ...], radius: int = 420) -> list[str]:
    regions: list[str] = []
    for label in labels:
        needle = normalize(label)
        start = 0
        while True:
            idx = FLAT.find(needle, start)
            if idx < 0:
                break
            regions.append(FLAT[max(0, idx - radius): min(len(FLAT), idx + len(needle) + radius)])
            start = idx + len(needle)
    return regions


MONEY_RE = re.compile(
    r"(?:\$\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>k|m|million|thousand)?\s*(?:usd|dollars?)?",
    re.IGNORECASE,
)


def money_values(fragment: str) -> list[float]:
    values: list[float] = []
    for match in MONEY_RE.finditer(fragment):
        token = match.group(0)
        suffix = (match.group("suffix") or "").casefold()
        # Bare small numbers are page labels, counts, or percentages—not money.
        if "$" not in token and not suffix and not re.search(r"(?:usd|dollars?)", token, re.I):
            continue
        value = float(match.group("num").replace(",", ""))
        if suffix in {"k", "thousand"}:
            value *= 1_000
        elif suffix in {"m", "million"}:
            value *= 1_000_000
        values.append(value)
    return values


def has_money(fragment: str, expected: float, rel: float = 0.007) -> bool:
    tolerance = max(100.0, abs(expected) * rel)
    return any(abs(value - expected) <= tolerance for value in money_values(fragment))


def percentages(fragment: str) -> list[float]:
    return [float(value) for value in re.findall(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*%", fragment)]


def has_percent(fragment: str, expected: float, tolerance: float = 0.25) -> bool:
    return any(abs(abs(value) - abs(expected)) <= tolerance for value in percentages(fragment))


def point_values(fragment: str) -> list[float]:
    patterns = [
        r"(-?\d+(?:\.\d+)?)\s*(?:percentage\s*)?(?:points?|pts?|pp)\b",
        r"(?:down|fell|declined|decreased|drop(?:ped)?)\s+(?:by\s+)?(-?\d+(?:\.\d+)?)\s*(?:percentage\s*)?(?:points?|pts?|pp)",
    ]
    values: list[float] = []
    for pattern in patterns:
        values.extend(float(value) for value in re.findall(pattern, fragment, re.I))
    return values


def require_readable() -> None:
    if PDF_ERROR or not TEXT.strip():
        pytest.skip("Downstream semantic checks are not run because the artifact-readability test reports the root PDF failure.")


def test_artifact_usability_and_requested_scope():
    assert OUTPUT.is_file(), "The requested qbr-2026-Q2.pdf is missing."
    assert PDF_ERROR is None, PDF_ERROR
    assert PAGES >= 1, "The requested QBR PDF contains no pages."
    assert len(TEXT.split()) >= 200, "The readable text is too sparse to carry the requested executive review."
    concepts = {
        "revenue trend": ("revenue", "sales trend"),
        "margin trend": ("gross margin", "margin trend"),
        "customer health": ("customer health", "customer story", "churn"),
        "next-quarter pipeline": ("q3 pipeline", "pipeline entering", "next-quarter pipeline", "next quarter pipeline"),
        "opportunities": ("opportunit", "upside"),
        "risks": ("risk", "exposure"),
    }
    missing = [name for name, aliases in concepts.items() if not any(alias in FLAT for alias in aliases)]
    assert not missing, f"The PDF omits requested QBR decision areas: {missing}."


@pytest.mark.parametrize("case", ["revenue", "gross_margin", "net_margin"])
def test_financial_performance_accuracy(case: str):
    require_readable()
    if case == "revenue":
        region = " ".join(windows(("revenue", "quarter headline"), 300))
        assert has_money(region, 1_250_000), "Q2 revenue is not reported as approximately $1.25M."
        assert has_percent(region, 11.607, 0.3), "The approximately 11.6% quarter-over-quarter revenue growth is missing or wrong."
        assert has_percent(region, 25.0, 0.25), "The 25.0% year-over-year revenue growth is missing or wrong."
    elif case == "gross_margin":
        region = " ".join(windows(("gross margin", "gross profit"), 360))
        assert has_money(region, 750_000), "Q2 gross profit is not reported as approximately $750K."
        assert has_percent(region, 60.0), "Q2 gross margin is not reported as 60.0%."
        assert any(abs(abs(value) - 3.0) <= 0.15 for value in point_values(region)), (
            "The 3.0-point gross-margin decline from Q1 is missing or wrong."
        )
    elif case == "net_margin":
        region = " ".join(windows(("net margin", "operating income", "operating expenses"), 320))
        assert has_money(region, 510_000), "Q2 operating expenses are not reported as approximately $510K."
        assert has_money(region, 240_000), "Q2 simplified operating income is not reported as approximately $240K."
        assert has_percent(region, 19.2), "Q2 simplified net margin is not reported as 19.2%."


@pytest.mark.parametrize("case", ["customer_flow", "concentration", "pipeline"])
def test_customer_health_and_pipeline_accuracy(case: str):
    require_readable()
    if case == "customer_flow":
        region = " ".join(windows(("new customers", "new logos", "customers churned", "churned"), 300))
        assert re.search(r"\b18\b", region), "The report does not show the 18 Q2 new-business wins."
        assert re.search(r"\b5\b", region), "The report does not show the five Q2 customer churns."
    elif case == "concentration":
        region = " ".join(windows(("aster peak logistics", "c001", "largest customer", "concentration"), 280))
        assert "aster peak logistics" in region or "c001" in region, "The largest customer is not identified."
        assert has_money(region, 270_000), "Largest-customer Q2 revenue is not approximately $270K."
        assert has_percent(region, 21.6), "Largest-customer concentration is not reported as 21.6%."
    else:
        gross_region = " ".join(windows(("gross pipeline", "q3 pipeline", "pipeline entering"), 320))
        assert re.search(r"\b36\b", gross_region), "The Q3 pipeline does not show 36 open opportunities."
        assert has_money(gross_region, 1_936_000), "Gross Q3 pipeline is not approximately $1.936M."


@pytest.mark.parametrize("case", ["paypal_reconciliation", "data_gap"])
def test_reconciliation_and_limitations(case: str):
    require_readable()
    if case == "paypal_reconciliation":
        region = " ".join(windows(("paypal", "settlement validation", "booked paypal"), 430))
        matching_values = [value for value in money_values(region) if abs(value - 269_767) <= 2_000]
        assert len(matching_values) >= 2 or (matching_values and re.search(r"\b(?:match|reconcil|zero|\$0\s+variance|no variance)", region)), (
            "The report does not demonstrate that Q2 PayPal gross activity and booked PayPal-channel revenue both equal about $269,767."
        )
        assert "transaction date" in region or "transaction-date" in region, "PayPal reconciliation does not state the transaction-date basis."
        assert "fee" in region and re.search(r"(?:not|do not|does not|exclude|excluding).{0,70}(?:revenue|recognized)", region), (
            "The report does not distinguish processing fees from recognized revenue."
        )
    else:
        region = " ".join(windows(("data limitation", "sync interruption", "sync gap", "stale"), 380))
        assert re.search(r"(?:crm|hubspot).{0,100}(?:sync|stale|incomplete)|(?:sync|stale|incomplete).{0,100}(?:crm|hubspot)", region), (
            "The material CRM completeness limitation is not visible."
        )
        assert re.search(r"\b4\b|\bfour\b", region) and "stage" in region, (
            "The report does not explain that four open-deal stages may be stale."
        )
        assert re.search(r"(?:confidence|refresh|verify|update|caution|limitation)", region), (
            "The CRM gap is mentioned without explaining its decision impact or follow-up."
        )
