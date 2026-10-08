from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from pathlib import Path


OUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/ideation_memo.md"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
ID_PATTERN = re.compile(r"\b(?:OBS|ASM|MEC|ENB|IDEA)-\d{3}\b", re.IGNORECASE)


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(value.replace("—", "-").replace("–", "-").split())


def read_submission() -> tuple[str, str | None]:
    if not OUT.is_file():
        return "", f"missing requested artifact: {OUT}"
    try:
        text = OUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "", f"ideation memo is not readable UTF-8 text: {exc}"
    return text, None


def _heading_candidates(text: str) -> list[tuple[int, int, str]]:
    """Return possible concept-card starts while accepting common Markdown variants."""
    candidates: list[tuple[int, int, str]] = []
    offset = 0
    excluded = {
        "retreat decision note", "summary", "introduction", "overview", "recommendation",
        "problem move", "structural transfer", "falsifiable prediction",
        "smallest discriminating experiment", "kill risk", "risk", "experiment", "prediction",
    }
    marker = re.compile(r"^(?:card|direction|concept|idea|research bet)\s*(?:\d+|[a-d])\b", re.I)
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        title = None
        level = 9
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
        else:
            bold = re.match(r"^\*\*(.+?)\*\*\s*$", stripped)
            plain = re.match(r"^((?:Card|Direction|Concept|Idea)\s*(?:\d+|[A-D])\b.+)$", stripped, re.I)
            if bold:
                title = bold.group(1).strip()
            elif plain:
                title = plain.group(1).strip()
        if title:
            clean = norm(re.sub(r"^[\dA-Da-d]+[.)\s:-]+", "", title))
            explicit = bool(marker.match(title) or marker.match(re.sub(r"^(?:\d+|[a-d])[.)\s:-]+", "", title, flags=re.I)))
            if clean not in excluded and explicit and len(title) <= 180 and not re.search(r"[─▶→]", title):
                candidates.append((offset, offset + len(line), title))
        offset += len(line)
    return candidates


def extract_cards(text: str) -> list[dict]:
    starts = _heading_candidates(text)
    cards = []
    for idx, (start, body_start, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(text)
        cards.append({"title": title, "text": text[body_start:end].strip()})
    return cards


def load_pack() -> tuple[dict[str, dict], dict[str, set[str]]]:
    records: dict[str, dict] = {}
    categories = {key: set() for key in ("OBS", "ASM", "MEC", "ENB", "IDEA")}
    for filename, id_key, prefix in (
        ("lab_observations.csv", "obs_id", "OBS"),
        ("assumptions.csv", "assumption_id", "ASM"),
        ("enablers.csv", "enabler_id", "ENB"),
        ("prior_ideas.csv", "idea_id", "IDEA"),
    ):
        with (DATA / filename).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                record_id = row[id_key].upper()
                records[record_id] = row
                categories[prefix].add(record_id)
    with (DATA / "mechanism_cards.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                record_id = row["mechanism_id"].upper()
                records[record_id] = row
                categories["MEC"].add(record_id)
    return records, categories


def cited_ids(text: str) -> set[str]:
    return {match.group(0).upper() for match in ID_PATTERN.finditer(text)}


def test_artifact_usability():
    text, error = read_submission()
    assert error is None, error
    cards = extract_cards(text)
    failures = []
    if len(text.strip()) < 1200:
        failures.append("the memo is too slight to contain four usable research cards")
    if len(cards) != 4:
        failures.append(f"found {len(cards)} identifiable research cards, expected exactly four")
    short = [card["title"] for card in cards if len(card["text"]) < 180]
    if short:
        failures.append(f"these cards do not contain a developed concept: {short}")
    assert not failures, "; ".join(failures)


def test_pack_traceability_by_card():
    text, error = read_submission()
    assert error is None, error
    cards = extract_cards(text)
    assert len(cards) == 4, (
        "pack traceability cannot be assigned by card because the memo does not expose exactly four "
        "identifiable card sections"
    )
    records, categories = load_pack()
    failures = []
    for index, card in enumerate(cards, 1):
        ids = cited_ids(card["text"])
        unknown = sorted(ids - set(records))
        if unknown:
            failures.append(f"card {index} cites unknown pack IDs: {unknown}")
        soft_or_hidden = {
            record_id for record_id in ids & categories["ASM"]
            if norm(records[record_id].get("constraint_type", "")) in {"soft", "hidden"}
        }
        if not soft_or_hidden:
            failures.append(f"card {index} does not identify a valid soft or hidden assumption it challenges")
        if not (ids & categories["MEC"]):
            failures.append(f"card {index} does not cite a valid cross-domain mechanism card")
        if not (ids & (categories["OBS"] | categories["ENB"])):
            failures.append(f"card {index} has no valid observation or enabler grounding")
    assert not failures, "; ".join(failures)
