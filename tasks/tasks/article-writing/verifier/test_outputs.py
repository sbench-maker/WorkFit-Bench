from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import re

import pytest


OUTPUT = Path("/root/results/harbor_launch.md")
FACTS_PATH = Path("/root/data/approved_facts.json")


def _read_article() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _normalize(text: str) -> str:
    text = text.casefold()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _plain_word_count(text: str) -> int:
    without_urls = re.sub(r"https?://\S+", " ", text)
    without_markdown = re.sub(r"[`*_>#\[\]()]", " ", without_urls)
    return len(re.findall(r"\b[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*\b", without_markdown))


def _has_all(text: str, patterns: list[str]) -> bool:
    return all(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


FACT_CASES = [
    pytest.param(
        [
            r"\bsix[ -]week\b",
            r"\b1842\s+work orders?\b",
            r"\b14\s+coordinators?\b",
            r"\b(?:three|3)\s+(?:harborline\s+)?branches?\b",
        ],
        "pilot scale: six weeks, 1,842 work orders, 14 coordinators, and three branches",
        id="pilot-scale",
    ),
    pytest.param(
        [
            r"(?:6\s*(?:minutes?|mins?|m)\s*40\s*(?:seconds?|secs?|s)|6\s*:\s*40)",
            r"(?:4\s*(?:minutes?|mins?|m)\s*35\s*(?:seconds?|secs?|s)|4\s*:\s*35)",
            r"31\s*(?:%|percent)",
        ],
        "scheduling time: 6:40 to 4:35, 31% lower",
        id="scheduling-time",
    ),
    pytest.param(
        [r"12[.]4\s*(?:%|percent)", r"7[.]1\s*(?:%|percent)", r"5[.]3\s*percentage[ -]points?"],
        "after-hours reassignment: 12.4% to 7.1%, down 5.3 percentage points",
        id="after-hours-reassignment",
    ),
    pytest.param(
        [r"82\s*(?:%|percent)", r"88\s*(?:%|percent)", r"on[ -]time"],
        "on-time arrival: 82% to 88%",
        id="on-time-arrival",
    ),
    pytest.param(
        [r"11\s+(?:of|out of)\s+14", r"(?:final|last)\s+(?:two|2)\s+weeks?", r"(?:four|4)\s+days?"],
        "adoption: 11 of 14 coordinators, at least four days per week in the final two weeks",
        id="adoption-signal",
    ),
    pytest.param(
        [
            r"(?:june\s+18(?:th)?(?:,)?\s+2026|18(?:th)?\s+june\s+2026)",
            r"\bgrowth\s+(?:and|&)\s+scale\b",
        ],
        "launch: June 18, 2026 on Growth and Scale",
        id="launch-details",
    ),
]


TARGET_CASES = [
    pytest.param(r"25\s*(?:%|percent)", "25% scheduling-time threshold", id="scheduling-target"),
    pytest.param(r"(?:below|under|less than|<)\s*8\s*(?:%|percent)", "below-8% reassignment threshold", id="reassignment-target"),
]


def test_artifact_usability() -> None:
    assert OUTPUT.is_file(), "the requested /root/results/harbor_launch.md file is missing"
    raw = _read_article()
    assert raw.strip(), "the newsletter is empty or is not readable UTF-8 text"
    words = _plain_word_count(raw)
    assert 900 <= words <= 1200, (
        f"the newsletter has {words} normalized prose words; the requested range is 900–1,200"
    )


@pytest.mark.parametrize(("patterns", "description"), FACT_CASES)
def test_required_campaign_facts(patterns: list[str], description: str) -> None:
    article = _normalize(_read_article())
    assert _has_all(article, patterns), (
        f"the newsletter does not clearly cover the approved {description}; "
        "omitting this brief-mandated anchor weakens the launch story"
    )


@pytest.mark.parametrize(("number_pattern", "description"), TARGET_CASES)
def test_launch_thresholds_are_labeled_as_targets(number_pattern: str, description: str) -> None:
    article = _normalize(_read_article())
    match = re.search(number_pattern, article, flags=re.IGNORECASE)
    assert match, f"the newsletter omits the approved {description}"
    window = article[max(0, match.start() - 180) : min(len(article), match.end() + 180)]
    has_target_label = re.search(
        r"\b(target|targets|targeting|goal|goals|aim|aims|intend|intends|after launch|post-launch|sustain)\b",
        window,
    )
    calls_it_observed = re.search(
        r"\b(pilot (?:result|results|outcome|outcomes)|harborline (?:achieved|reached|recorded|saw))\b",
        window,
    )
    assert has_target_label and not calls_it_observed, (
        f"the {description} is not clearly framed as a launch target, or is incorrectly presented "
        "as a measured Harborline result"
    )


PROHIBITED_CLAIMS = [
    (r"\broute guard\b", "the superseded product name Route Guard"),
    (r"\bjune\s+12(?:th)?(?:,)?\s+2026\b", "the superseded June 12 launch date"),
    (r"\b(?:about|roughly|approximately|nearly)?\s*2000\s+(?:pilot\s+)?work orders?\b", "the rough 2,000-work-order estimate"),
    (r"\b(?:two|2)\s+(?:employee[ -])?hours?\s+(?:saved|back)\s+per\s+coordinator\b", "the unmeasured two-hours-saved claim"),
    (r"\bzero\s+missed appointments?\b", "the unapproved zero-missed-appointments claim"),
    (r"\b(?:all|every)\s+(?:paid\s+)?plans?\b", "the superseded all-plans packaging claim"),
    (r"(?:\$\s*49|49\s+dollars?).{0,50}(?:dispatcher|month)|(?:dispatcher|month).{0,50}(?:\$\s*49|49\s+dollars?)", "the unapproved $49 price"),
    (r"\b(?:will|is going to)\s+(?:expand|launch).{0,80}\b(?:commercial field service|emergency restoration)\b", "an unapproved future-market commitment"),
]


def test_unapproved_or_superseded_claims_are_excluded() -> None:
    article = _normalize(_read_article())
    found = [label for pattern, label in PROHIBITED_CLAIMS if re.search(pattern, article, flags=re.IGNORECASE)]
    assert not found, "the newsletter publishes material the packet marks unapproved or superseded: " + "; ".join(found)


def _quoted_passages(text: str) -> list[str]:
    passages = re.findall(r"[“\"]([^”\"\n]{15,500})[”\"]", text)
    passages.extend(
        re.sub(r"^>\s*", "", line).strip()
        for line in text.splitlines()
        if re.match(r"^>\s*\S", line)
    )
    return [passage for passage in passages if len(re.findall(r"\b\w+\b", passage)) >= 5]


def _quote_match(candidate: str, approved: list[str]) -> bool:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", _normalize(candidate))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for source in approved:
        expected = re.sub(r"[^a-z0-9 ]+", " ", _normalize(source))
        expected = re.sub(r"\s+", " ", expected).strip()
        if normalized in expected or expected in normalized:
            return True
        if SequenceMatcher(None, normalized, expected).ratio() >= 0.88:
            return True
    return False


def test_direct_quotes_are_source_faithful() -> None:
    article = _read_article()
    facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    approved = [item["quote"] for item in facts["approved_quotes"]]
    invented = [quote for quote in _quoted_passages(article) if not _quote_match(quote, approved)]
    assert not invented, (
        "the newsletter presents direct customer wording that does not match an approved quotation: "
        + " | ".join(invented[:3])
    )
