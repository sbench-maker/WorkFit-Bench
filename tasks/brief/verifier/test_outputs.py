from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT_PATH = RESULTS_DIR / "output.json"


def _read_payload() -> tuple[object | None, str | None]:
    if not OUTPUT_PATH.is_file():
        return None, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"output.json is not readable JSON: {exc}"


def _payload_or_skip() -> object:
    payload, error = _read_payload()
    if error:
        pytest.skip(f"artifact parse failure is scored once by test_artifact_usability: {error}")
    return payload


def _normalize(value: object) -> str:
    text = str(value).lower()
    text = text.replace("–", "-").replace("—", "-").replace("’", "'")
    text = re.sub(r"(?<=\d)[,\s](?=\d{3}\b)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _blob(payload: object) -> str:
    return _normalize(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _units(payload: object) -> list[str]:
    """Collect representation-neutral semantic units without assuming exact keys."""
    units: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            direct: list[str] = []
            for key, item in value.items():
                direct.append(str(key))
                if isinstance(item, (str, int, float, bool)) or item is None:
                    direct.append(str(item))
                elif isinstance(item, list) and all(
                    isinstance(part, (str, int, float, bool)) or part is None for part in item
                ):
                    direct.extend(str(part) for part in item)
            if direct:
                units.append(_normalize(" ".join(direct)))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            if all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
                units.append(_normalize(" ".join(str(item) for item in value)))
            for item in value:
                visit(item)
        elif isinstance(value, str):
            units.append(_normalize(value))

    visit(payload)
    return units


def _has_patterns(text: str, patterns: tuple[str, ...]) -> bool:
    return all(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _some_unit(payload: object, patterns: tuple[str, ...]) -> bool:
    return any(_has_patterns(unit, patterns) for unit in _units(payload))


FACT_CASES = [
    (
        "incident identity",
        (r"cobalt metrics|\bcobalt\b", r"unauthori[sz]ed", r"oauth|service token"),
    ),
    (
        "reconciled population and regions",
        (r"\b18420\b", r"\b4860\b", r"\b12940\b", r"\b620\b", r"eea|europe"),
    ),
    (
        "affected data categories",
        (r"\bname", r"email", r"organi[sz]ation", r"product.?usage|usage event", r"support"),
    ),
    (
        "support-note sensitivity flag",
        (r"\b312\b", r"\b27\b", r"accessibility|accommodation"),
    ),
    (
        "excluded credential/payment fields",
        (r"no (?:payment|payment card)|payment card.{0,80}(?:not|no|without)", r"password", r"social security|government id"),
    ),
    (
        "root cause remains open",
        (r"root cause", r"unknown|unconfirmed|not (?:yet )?(?:known|confirmed|established)|unresolved"),
    ),
]


@pytest.mark.parametrize("label,patterns", FACT_CASES, ids=[case[0] for case in FACT_CASES])
def test_incident_facts(label: str, patterns: tuple[str, ...]) -> None:
    payload = _payload_or_skip()
    text = _blob(payload)
    assert _has_patterns(text, patterns), f"the brief omits or misstates the {label}, which would distort incident scope"


TIMELINE_CASES = [
    (
        "supported activity-window start",
        (r"2026-08-29|29 (?:august|aug)", r"16:04", r"window|activity|export|start|earliest"),
    ),
    (
        "first retained suspicious event",
        (r"02:58", r"first|earliest", r"suspicious|oauth|event|use"),
    ),
    (
        "03:15 corrected meaning",
        (r"03:15", r"escalat|prelim|not (?:the )?first"),
    ),
    (
        "vendor confirmation and provisional awareness",
        (r"05:30", r"confirm|awareness"),
    ),
    (
        "containment boundary",
        (r"07:10", r"disable|contain|end|revok"),
    ),
    (
        "initial vendor notification",
        (r"07:42", r"initial|notif|alert|sent"),
    ),
]


@pytest.mark.parametrize("label,patterns", TIMELINE_CASES, ids=[case[0] for case in TIMELINE_CASES])
def test_timeline_reconciliation(label: str, patterns: tuple[str, ...]) -> None:
    payload = _payload_or_skip()
    assert _some_unit(payload, patterns), (
        f"the brief does not correctly distinguish the {label}; unreconciled event times could start the wrong response clock"
    )


AGREEMENT_CASES = [
    ("vendor MSA", (r"agr-vend-001", r"indemn|liabil|incorporat")),
    ("vendor DPA", (r"dpa-vend-001", r"24\s*(?:hours?|h\b)", r"confirm")),
    ("Helio agreement", (r"cust-hel-044", r"helio", r"48\s*[- ]?\s*(?:hours?|h\b)")),
    ("Aster agreement", (r"cust-ast-117", r"aster", r"48\s*[- ]?\s*(?:hours?|h\b)")),
    ("Meridian agreement", (r"cust-mer-208", r"meridian", r"undue delay|no fixed")),
    ("Pinnacle agreement", (r"cust-pin-309", r"pinnacle", r"no (?:negotiated )?(?:incident )?addendum|standard confidentiality")),
    ("cyber policy", (r"cyb-2026-04", r"72\s*(?:hours?|h\b)", r"25000|25,000|25k", r"consent|approval")),
]


@pytest.mark.parametrize("label,patterns", AGREEMENT_CASES, ids=[case[0] for case in AGREEMENT_CASES])
def test_agreement_and_deadline_coverage(label: str, patterns: tuple[str, ...]) -> None:
    payload = _payload_or_skip()
    assert _some_unit(payload, patterns), (
        f"the brief does not connect the {label} to its material incident term, leaving a time-sensitive obligation untriaged"
    )


GAP_CASES = [
    ("CRM export", (r"\bcrm\b", r"unavailable|failed|not available|missing")),
    (
        "production and early log gap",
        (r"production|application", r"audit|logs?", r"29.?30 (?:august|aug)|2026-08-29", r"incomplete|unavailable|missing|gap"),
    ),
    ("DPA Annex B", (r"annex b", r"missing|unavailable|not (?:included|available|supplied)")),
    ("outside-counsel portal", (r"outside.?counsel", r"portal", r"not connected|unavailable|missing|no (?:portal )?export")),
]


@pytest.mark.parametrize("label,patterns", GAP_CASES, ids=[case[0] for case in GAP_CASES])
def test_source_limitations(label: str, patterns: tuple[str, ...]) -> None:
    payload = _payload_or_skip()
    assert _some_unit(payload, patterns), (
        f"the brief does not disclose the {label} limitation, so readers could mistake partial inputs for a complete search"
    )
