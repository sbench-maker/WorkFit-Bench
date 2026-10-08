from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
REPORT = RESULTS / "GEO-ANALYSIS.md"
PLATFORMS = ["Google AI Overviews", "ChatGPT", "Perplexity"]


def _read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_csv(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _report_text() -> str:
    if not REPORT.is_file():
        return ""
    try:
        return REPORT.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _expected_scores() -> dict[str, int]:
    profile = json.loads((DATA / "site_profile.json").read_text(encoding="utf-8"))
    model = json.loads((DATA / "scoring_model.json").read_text(encoding="utf-8"))
    ids = set(profile["priority_page_ids"])
    pages = [p for p in _read_jsonl("site_pages.jsonl") if p["page_id"] in ids]
    snapshot = date.fromisoformat(profile["snapshot_date"])

    c_values, s_values, a_values = [], [], []
    for page in pages:
        c_values.append(
            (30 if 134 <= page["best_passage_word_count"] <= 167 else 0)
            + (20 if page["best_passage_start_pct"] <= 30 else 0)
            + (20 if 40 <= page["direct_answer_words"] <= 60 else 0)
            + (15 if page["specific_fact_count"] >= 2 else 0)
            + (15 if page["attributed_claim_count"] >= 1 else 0)
        )
        s_values.append(
            (30 if page["h1_count"] == 1 else 0)
            + (30 if page["heading_levels_valid"] else 0)
            + (20 if page["question_heading_count"] >= 1 else 0)
            + (20 if page["table_count"] >= 1 or page["list_count"] >= 1 else 0)
        )
        age = (snapshot - date.fromisoformat(page["updated_date"])).days
        a_values.append(
            (25 if page["author_credentials"] else 0)
            + (25 if age <= 90 else 0)
            + (25 if page["primary_source_count"] >= 1 else 0)
            + (25 if page["first_hand_evidence"] else 0)
        )
    components = {
        "citability": sum(c_values) / len(c_values),
        "structure": sum(s_values) / len(s_values),
        "authority": sum(a_values) / len(a_values),
    }

    eligible_pct = 100 * sum(p["status_code"] == 200 and p["indexable"] and p["canonical_path"] == p["path"] for p in pages) / len(pages)
    ssr_pct = 100 * sum(p["rendered_word_count"] and p["server_word_count"] / p["rendered_word_count"] >= 0.80 for p in pages) / len(pages)
    access = _read_csv("crawler_access.csv")
    technical = {}
    for platform, crawler in model["component_rules"]["technical"]["platform_crawlers"].items():
        scoped = [row for row in access if row["crawler"] == crawler]
        access_pct = 100 * sum(row["allowed"] == "1" for row in scoped) / len(scoped)
        technical[platform] = 0.35 * eligible_pct + 0.40 * ssr_pct + 0.25 * access_pct

    confirmed = Counter(row["platform"] for row in _read_csv("brand_mentions.csv") if row["confirmed"] == "1")
    targets = model["component_rules"]["brand"]["source_targets"]
    source_scores = {source: min(100.0, 100 * confirmed[source] / target) for source, target in targets.items()}
    brand = {
        platform: sum(source_scores[source] * weight for source, weight in weights.items())
        for platform, weights in model["component_rules"]["brand"]["platform_source_weights"].items()
    }
    observations = _read_csv("query_observations.csv")
    visibility = {}
    for platform in PLATFORMS:
        scoped = [row for row in observations if row["platform"] == platform]
        visibility[platform] = 100 * sum(row["cited"] == "1" for row in scoped) / len(scoped)

    raw = {}
    for platform, weights in model["platform_weights"].items():
        values = {**components, "technical": technical[platform], "brand": brand[platform], "visibility": visibility[platform]}
        raw[platform] = sum(values[key] * weight for key, weight in weights.items())
    return {
        "overall": round(sum(raw.values()) / len(raw)),
        **{platform: round(value) for platform, value in raw.items()},
    }


def _normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip().lower() for line in text.splitlines() if line.strip()]


def _score_near_label(text: str, labels: list[str]) -> int | None:
    lines = _normalized_lines(text)
    out_of_pattern = re.compile(r"(?<!\d)(\d{1,3})(?:\.\d+)?\s*(?:/\s*100|out\s+of\s+100)")
    percent_pattern = re.compile(r"(?<!\d)(\d{1,3})(?:\.\d+)?\s*(?:percent|%)")
    for line in lines:
        if any(label.lower() in line for label in labels):
            match = out_of_pattern.search(line)
            if match:
                return int(match.group(1))
            if "score" in line or "readiness" in line:
                match = percent_pattern.search(line)
                if match:
                    return int(match.group(1))
    return None


def _line_has(text: str, subjects: list[str], statuses: list[str], objects: list[str] | None = None) -> bool:
    for line in _normalized_lines(text):
        if "|" in line:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            contexts = [" ".join(cells[index:index + 2]) for index in range(len(cells))]
        else:
            contexts = [clause.strip() for clause in re.split(r"[.;]", line) if clause.strip()]
        for context in contexts:
            if not any(subject.lower() in context for subject in subjects):
                continue
            if not any(status.lower() in context for status in statuses):
                continue
            if objects and not any(obj.lower() in context for obj in objects):
                continue
            return True
    return False


@pytest.mark.parametrize(
    ("score_name", "labels"),
    [
        ("overall", ["geo readiness", "overall readiness", "overall score"]),
        ("Google AI Overviews", ["google ai overviews", "google aio"]),
        ("ChatGPT", ["chatgpt"]),
        ("Perplexity", ["perplexity"]),
    ],
)
def test_readiness_scores(score_name: str, labels: list[str]):
    text = _report_text()
    actual = _score_near_label(text, labels)
    expected = _expected_scores()[score_name]
    assert actual is not None, f"no normalized /100 or percent score was found near {score_name}"
    assert actual == expected, f"{score_name} readiness is {actual}, expected {expected} from the frozen scoring model"


def test_crawler_access_diagnosis():
    text = _report_text()
    blocked = ["block", "disallow", "denied", "not allowed", "inaccessible"]
    allowed = ["allow", "accessible", "permitted", "open"]
    checks = [
        _line_has(text, ["oai-searchbot"], blocked, ["/guides/"]),
        _line_has(text, ["perplexitybot"], blocked, ["/compare/"]),
        _line_has(text, ["claudebot"], blocked, ["sitewide", "entire site", "disallow: /", "all paths"]),
        _line_has(text, ["gptbot"], allowed),
        _line_has(text, ["chatgpt-user"], allowed),
    ]
    assert all(checks), "crawler findings must distinguish the exact search-path blocks and the two allowed OpenAI agents"


def test_rendering_eligibility_and_llms_diagnosis():
    text = _report_text().lower()
    for path in ["/guides/vector-routing", "/compare/relay-vs-orbit", "/pricing", "/blog/benchmark-2026"]:
        assert path in text, f"SSR diagnosis omits affected priority path {path}"
    assert "/integrations/novaqueue" in text and "/integrations" in text and "canonical" in text, "P011's non-self-canonical eligibility defect is missing"
    assert "/about" in text and ("noindex" in text or "non-indexable" in text or "not indexable" in text), "P012's indexability defect is missing"
    assert "llms.txt" in text and "/docs/legacy-auth" in text and ("404" in text or "stale" in text or "broken" in text), "llms.txt must be reported as present with its stale legacy-auth entry"
    caution = re.search(r"llms\.txt[\s\S]{0,900}(?:zero[^\n]{0,80}(?:weight|point)|not[^\n]{0,80}(?:ranking|citation)[^\n]{0,40}(?:lever|factor)|no[^\n]{0,80}evidence)", text)
    assert caution, "the report overstates or fails to qualify llms.txt despite the supplied zero-weight evidence policy"


def test_brand_signal_diagnosis():
    text = _report_text().lower()
    expectations = {"reddit": 12, "youtube": 4, "linkedin": 15}
    for platform, count in expectations.items():
        pattern = rf"(?:{count}\s+(?:confirmed\s+)?{platform}|{platform}[^\n]{{0,80}}{count}\s+(?:confirmed\s+)?mentions?)"
        assert re.search(pattern, text), f"confirmed {platform} count {count} is absent or misreported"
    wikipedia_absence = re.search(r"(?:no|zero|0)\s+confirmed\s+wikipedia|wikipedia[^\n]{0,100}(?:no|zero|0)\s+confirmed", text)
    assert wikipedia_absence, "the report must not count the different-entity Wikipedia record as a confirmed brand mention"
