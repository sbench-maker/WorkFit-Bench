from __future__ import annotations

import csv
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "index.html"


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("–", "-").replace("—", "-")).strip().lower()


class DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.external_refs: list[str] = []
        self.interactive_tags: list[str] = []
        self.script_text: list[str] = []
        self.has_viewport = False
        self._suppressed = 0
        self._in_script = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.table_rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag in {"style", "template"}:
            self._suppressed += 1
        if tag == "script":
            self._in_script += 1
        if tag == "meta" and normalize(attr.get("name") or "") == "viewport":
            self.has_viewport = True
        if tag in {"button", "input", "select", "details", "summary"}:
            self.interactive_tags.append(tag)
        for key in ("src", "href"):
            ref = (attr.get(key) or "").strip()
            if re.match(r"^(?:https?:)?//", ref, flags=re.I):
                self.external_refs.append(ref)
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(normalize(" ".join(self._cell)))
            self._cell = None
        if tag == "tr" and self._row is not None:
            self.table_rows.append(self._row)
            self._row = None
        if tag == "script" and self._in_script:
            self._in_script -= 1
        if tag in {"style", "template"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.script_text.append(data)
        if not self._suppressed and not self._in_script:
            self.visible_parts.append(data)
            if self._cell is not None:
                self._cell.append(data)

    @property
    def text(self) -> str:
        return normalize(" ".join(self.visible_parts))


@pytest.fixture(scope="module")
def artifact() -> tuple[str, DashboardParser]:
    assert OUTPUT.is_file(), f"missing requested artifact: {OUTPUT}"
    raw = OUTPUT.read_text(encoding="utf-8")
    parser = DashboardParser()
    parser.feed(raw)
    return raw, parser


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def known_ids() -> dict[str, set[str]]:
    interview_text = (DATA_DIR / "interview_notes.md").read_text(encoding="utf-8")
    usability_text = (DATA_DIR / "usability_sessions.md").read_text(encoding="utf-8")
    stakeholder_text = (DATA_DIR / "stakeholder_notes.md").read_text(encoding="utf-8")
    return {
        "interview": set(re.findall(r"\bI-\d{2}\b", interview_text)),
        "usability": set(re.findall(r"\bU-\d{2}\b", usability_text)),
        "support": {row["ticket_id"] for row in read_csv("support_tickets.csv")},
        "survey": {row["response_id"] for row in read_csv("survey_responses.csv")},
        "analytics": {row["metric_id"] for row in read_csv("workflow_metrics.csv")},
        "sales": {row["note_id"] for row in read_csv("sales_notes.csv")},
        "stakeholder": set(re.findall(r"\bK-\d{2}\b", stakeholder_text)),
    }


def ids_in_artifact(text: str) -> set[str]:
    return {match.upper() for match in re.findall(r"\b(?:I|U|T|S|M|L|K)-\d{2,3}\b", text, flags=re.I)}


def has_all(text: str, *tokens: str) -> bool:
    return all(normalize(token) in text for token in tokens)


def test_artifact_usability(artifact: tuple[str, DashboardParser]) -> None:
    raw, parser = artifact
    assert len(raw.encode("utf-8")) >= 5_000, "index.html is too small to function as the requested research dashboard"
    assert re.search(r"<!doctype\s+html|<html\b", raw, flags=re.I), "output is not an HTML document"
    assert not parser.external_refs, f"self-contained dashboard depends on remote assets: {parser.external_refs}"
    scripts = " ".join(parser.script_text).lower()
    has_native_interaction = bool(parser.interactive_tags) and (
        "addeventlistener" in scripts or "onclick" in raw.lower() or "details" in parser.interactive_tags
    )
    assert has_native_interaction, "dashboard has no usable built-in interactive control"


@pytest.mark.parametrize(
    ("source", "minimum"),
    [
        ("interview", 4),
        ("usability", 2),
        ("support", 4),
        ("survey", 2),
        ("analytics", 4),
        ("sales", 2),
        ("stakeholder", 1),
    ],
)
def test_source_traceability(artifact: tuple[str, DashboardParser], source: str, minimum: int) -> None:
    _, parser = artifact
    text = parser.text
    present = ids_in_artifact(text) & known_ids()[source]
    assert len(present) >= minimum, (
        f"only {len(present)} traceable {source} IDs found; the dashboard does not let reviewers inspect a representative {source} basis"
    )
    assert source in text or (source == "analytics" and "metric" in text), f"{source} evidence is not clearly distinguished"
    if source == "stakeholder":
        assert re.search(r"internal|not user evidence|hypothesis|opinion", text), (
            "stakeholder material is not clearly separated from user evidence"
        )


@pytest.mark.parametrize(
    "fact",
    [
        "critical_quote",
        "support_distribution",
        "cycle_delay",
        "recheck_metric",
        "survey_split",
        "reminder_uncertainty",
    ],
)
def test_factual_anchors(artifact: tuple[str, DashboardParser], fact: str) -> None:
    _, parser = artifact
    text = parser.text
    if fact == "critical_quote":
        supplied = [
            "i keep checking the request, my inbox, and chat because none of them tells me who has it now.",
            "another reminder without the amount and deadline just becomes noise.",
            "we only have one approver. a timeline would be more machinery than we need.",
        ]
        found = sum(normalize(quote) in text for quote in supplied)
        assert found >= 2, "fewer than two decision-critical supplied quotes are preserved verbatim"
    elif fact == "support_distribution":
        counts = Counter(row["category"] for row in read_csv("support_tickets.csv"))
        assert has_all(text, str(counts["status_unknown"]), str(counts["ownership_confusion"]), "220"), (
            "dashboard omits or changes the ticket counts that distinguish status from ownership pain"
        )
    elif fact == "cycle_delay":
        assert re.search(r"64\s*/\s*168", text) and re.search(r"38(?:\.1)?\s*%", text), (
            "overall over-48-hour approval metric is missing or inaccurate"
        )
        assert re.search(r"32\s*/\s*56", text) and re.search(r"57(?:\.1)?\s*%", text), (
            "enterprise delay segment is missing or inaccurate"
        )
    elif fact == "recheck_metric":
        assert re.search(r"49\s*/\s*64", text) and re.search(r"76(?:\.6)?\s*%", text), (
            "recheck behavior among delayed approvals is missing or inaccurate"
        )
    elif fact == "survey_split":
        assert re.search(r"34\s*/\s*72", text) and re.search(r"19\s*/\s*72", text), (
            "overall survey alternative split is missing or inaccurate"
        )
        assert re.search(r"11\s*/\s*18", text), "small-account reminder preference is not surfaced"
    elif fact == "reminder_uncertainty":
        assert re.search(r"(?:22\s*/\s*73|30(?:\.1)?\s*%)", text), "reminder open metric is missing"
        assert re.search(r"(?:9\s*/\s*73|12(?:\.3)?\s*%)", text), "post-reminder completion metric is missing"
        assert re.search(r"no (?:holdout|control)|not causal|cannot (?:attribute|infer)|descriptive", text), (
            "observational reminder completion is presented without its decision-critical causal limitation"
        )


def test_decision_scope_completeness(artifact: tuple[str, DashboardParser]) -> None:
    _, parser = artifact
    text = parser.text
    component_aliases = {
        "evidence": ("evidence", "source ledger"),
        "themes": ("theme", "pattern"),
        "alternatives": ("alternative", "opportunity", "option"),
        "recommendation": ("recommend", "proposed move"),
        "decision memo": ("decision memo", "decision brief", "recommended move"),
        "experiments": ("experiment", "pilot", "test queue"),
        "limitations": ("limitation", "evidence gap", "assumption"),
    }
    missing = [name for name, aliases in component_aliases.items() if not any(alias in text for alias in aliases)]
    assert not missing, f"dashboard omits requested decision components: {missing}"
    named_options = {
        "status visibility": bool(re.search(r"status (?:timeline|history|visibility)|shared status", text)),
        "reminders": "reminder" in text,
        "ownership controls": bool(re.search(r"owner(?:ship)?(?:,| and|-| )+(?:due|control|date)|ownership control", text)),
    }
    assert all(named_options.values()), f"not all three named alternatives are meaningfully represented: {named_options}"


def test_cross_section_consistency(artifact: tuple[str, DashboardParser]) -> None:
    _, parser = artifact
    text = parser.text
    option_mentions = {
        "status": len(re.findall(r"status (?:timeline|history|visibility)|shared status", text)),
        "reminder": text.count("reminder"),
        "ownership": len(re.findall(r"owner(?:ship)?(?:,| and|-| )+(?:due|control|date)|ownership control", text)),
    }
    assert max(option_mentions.values()) >= 3 and "recommend" in text, (
        "the selected alternative is not identifiable across the executive readout, comparison, and memo"
    )
    measure_terms = len(re.findall(r"\b(?:metric|measure|success|threshold)\b", text))
    threshold_values = re.findall(r"(?:at least|below|under|no (?:more|worse) than|\+)\s*\d+(?:\.\d+)?\s*(?:%|of\b|seconds?|hours?|participants?|relative)?", text)
    assert measure_terms >= 3 and len(threshold_values) >= 2, (
        "experiment queue lacks at least two concrete measurable success thresholds"
    )

    # Numeric matrices are optional, but if supplied their visible totals must reconcile.
    scored_rows = 0
    for row in parser.table_rows:
        values = [int(cell) for cell in row if re.fullmatch(r"\d{1,2}", cell)]
        if len(values) >= 5 and all(1 <= value <= 5 for value in values[:4]):
            scored_rows += 1
            assert values[4] == sum(values[:4]), f"opportunity total {values[4]} does not equal component sum {sum(values[:4])}"
    if scored_rows:
        assert scored_rows >= 3, "numeric opportunity matrix compares too few alternatives to support the decision"
