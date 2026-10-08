from __future__ import annotations

import html
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import pytest


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/output.json"))
if not DATA.is_absolute() or not OUTPUT.is_absolute():
    raise ValueError("Verifier data and output paths must be absolute")

MISSING = object()
INVALID = object()


def key_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


ALIASES = {
    "rank": {"rank", "position", "order", "displayrank", "displayposition"},
    "id": {"id", "itemid", "storyid", "hnid"},
    "title": {"title", "headline", "name", "storytitle"},
    "url": {"url", "link", "href", "linkurl", "destination", "destinationurl"},
    "points": {"points", "point", "score", "scorepoints", "votes"},
    "comments": {"comments", "comment", "commentcount", "commentscount", "numcomments", "discussioncount"},
    "count": {"count", "total", "totalcount", "storycount", "storiescount"},
}


def aliased(mapping: dict, logical: str) -> tuple[bool, object]:
    wanted = ALIASES[logical]
    for key, value in mapping.items():
        if key_name(key) in wanted:
            return True, value
    return False, MISSING


class SnapshotParser(HTMLParser):
    """Independent fixture reader used to derive expected facts from the frozen HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stories: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.current: dict | None = None
        self.in_titleline = False
        self.capture: str | None = None
        self.capture_id: str | None = None
        self.buffer: list[str] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def start_capture(self, kind: str, item_id: str | None = None) -> None:
        self.capture = kind
        self.capture_id = item_id
        self.buffer = []

    def stop_capture(self) -> str:
        text = " ".join("".join(self.buffer).split())
        self.capture = None
        self.capture_id = None
        self.buffer = []
        return text

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self.attrs_dict(attrs)
        classes = set(values.get("class", "").split())
        if tag == "tr" and "athing" in classes and values.get("id", "").isdigit():
            self.current = {
                "rank": None,
                "id": values["id"],
                "title": "",
                "url": "",
                "points": None,
                "comments": None,
            }
        elif tag == "span" and self.current is not None and "rank" in classes:
            self.start_capture("rank")
        elif tag == "span" and self.current is not None and "titleline" in classes:
            self.in_titleline = True
        elif tag == "span" and "score" in classes:
            match = re.fullmatch(r"score_(\d+)", values.get("id", ""))
            if match and match.group(1) in self.by_id:
                self.start_capture("score", match.group(1))
        elif tag == "a":
            href = values.get("href", "")
            if self.current is not None and self.in_titleline and not self.current["url"]:
                self.current["url"] = href
                self.start_capture("title")
            else:
                match = re.fullmatch(r"item\?id=(\d+)", href)
                if match and match.group(1) in self.by_id:
                    self.start_capture("item_link", match.group(1))

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.capture == "title" and self.current is not None:
            self.current["title"] = self.stop_capture()
        elif tag == "a" and self.capture == "item_link" and self.capture_id:
            item_id = self.capture_id
            text = self.stop_capture()
            match = re.fullmatch(r"(\d+)\s+comments?", text, flags=re.IGNORECASE)
            if match:
                self.by_id[item_id]["comments"] = int(match.group(1))
            elif text.casefold() == "discuss":
                self.by_id[item_id]["comments"] = 0
        elif tag == "span" and self.capture == "rank" and self.current is not None:
            text = self.stop_capture()
            match = re.search(r"\d+", text)
            self.current["rank"] = int(match.group()) if match else None
        elif tag == "span" and self.capture == "score" and self.capture_id:
            item_id = self.capture_id
            text = self.stop_capture()
            match = re.fullmatch(r"(\d+)\s+points?", text, flags=re.IGNORECASE)
            if match:
                self.by_id[item_id]["points"] = int(match.group(1))
        elif tag == "tr" and self.current is not None:
            if self.current["title"] and self.current["url"]:
                self.stories.append(self.current)
                self.by_id[self.current["id"]] = self.current
            self.current = None
            self.in_titleline = False
            if self.capture in {"title", "rank"}:
                self.stop_capture()


def expected_stories() -> list[dict]:
    parser = SnapshotParser()
    parser.feed((DATA / "hn_frontpage_snapshot.html").read_text(encoding="utf-8"))
    parser.close()
    return parser.stories


EXPECTED = expected_stories()
EXPECTED_BY_ID = {row["id"]: row for row in EXPECTED}


def looks_like_story(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    signals = sum(aliased(value, field)[0] for field in ("title", "url", "rank", "id"))
    return signals >= 2


def find_story_collection(root: object) -> tuple[list[dict], bool, object]:
    candidates: list[tuple[int, list[dict], bool, object]] = []

    def visit(node: object, inherited_count: tuple[bool, object] = (False, MISSING)) -> None:
        if isinstance(node, dict):
            own_count = aliased(node, "count")
            active_count = own_count if own_count[0] else inherited_count
            values = list(node.values())
            story_values = [value for value in values if isinstance(value, dict) and looks_like_story(value)]
            if len(story_values) >= 2 and len(story_values) >= max(2, int(len(values) * 0.75)):
                records = []
                for map_key, record in node.items():
                    copy = dict(record)
                    if not aliased(copy, "id")[0]:
                        copy["id"] = str(map_key)
                    records.append(copy)
                candidates.append((len(records), records, active_count[0], active_count[1]))
            for value in values:
                visit(value, active_count)
        elif isinstance(node, list):
            records = [item for item in node if isinstance(item, dict)]
            if records and len(records) == len(node) and sum(looks_like_story(item) for item in records) >= max(1, int(len(records) * 0.75)):
                candidates.append((len(records), records, inherited_count[0], inherited_count[1]))
            for value in node:
                if isinstance(value, (dict, list)) and not looks_like_story(value):
                    visit(value, inherited_count)

    root_count = aliased(root, "count") if isinstance(root, dict) else (False, MISSING)
    visit(root, root_count)
    if not candidates:
        return [], root_count[0], root_count[1]
    _, records, count_present, count = max(candidates, key=lambda row: row[0])
    if not count_present and root_count[0]:
        count_present, count = root_count
    return records, count_present, count


def to_int(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return INVALID
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else INVALID
    if isinstance(value, str):
        cleaned = html.unescape(value).strip()
        if cleaned.casefold() in {"null", "none", "n/a", "na", "unavailable", "missing", ""}:
            return None
        if cleaned.casefold() == "discuss":
            return 0
        match = re.search(r"-?\d+", cleaned.replace(",", ""))
        return int(match.group()) if match else INVALID
    return INVALID


def to_id(value: object) -> object:
    if value is None or isinstance(value, bool):
        return INVALID
    if isinstance(value, (int, str)):
        match = re.search(r"\d+", str(value))
        return match.group() if match else INVALID
    return INVALID


def clean_title(value: object) -> object:
    if not isinstance(value, str):
        return INVALID
    plain = re.sub(r"<[^>]+>", "", html.unescape(value))
    return " ".join(plain.split())


def clean_url(value: object) -> object:
    if not isinstance(value, str):
        return INVALID
    return html.unescape(value).strip()


def normalized_story(raw: dict) -> dict:
    result: dict[str, object] = {"present": {}}
    converters = {
        "rank": to_int,
        "id": to_id,
        "title": clean_title,
        "url": clean_url,
        "points": to_int,
        "comments": to_int,
    }
    for logical, converter in converters.items():
        present, value = aliased(raw, logical)
        result["present"][logical] = present
        result[logical] = converter(value) if present else MISSING
    return result


def load_submission() -> dict:
    if not OUTPUT.is_file():
        return {"error": "missing", "stories": [], "count_present": False, "count": MISSING}
    try:
        root = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable: {exc}", "stories": [], "count_present": False, "count": MISSING}
    raw_stories, count_present, count = find_story_collection(root)
    if not raw_stories:
        return {"error": "no story collection", "stories": [], "count_present": count_present, "count": to_int(count) if count_present else MISSING}
    return {
        "error": None,
        "stories": [normalized_story(row) for row in raw_stories],
        "count_present": count_present,
        "count": to_int(count) if count_present else MISSING,
    }


SUBMISSION = load_submission()


def submitted_by_id() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for row in SUBMISSION["stories"]:
        if isinstance(row["id"], str):
            records.setdefault(row["id"], row)
    return records


def comparable_url(value: object) -> object:
    if not isinstance(value, str):
        return value
    absolute = urljoin("https://news.ycombinator.com/", value)
    parts = urlsplit(absolute)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    path = parts.path or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, query, parts.fragment))


def test_artifact_contract() -> None:
    assert OUTPUT.is_file(), "The requested /root/results/output.json artifact is missing."
    assert SUBMISSION["error"] is None, f"The artifact is not a usable story JSON document: {SUBMISSION['error']}."
    assert SUBMISSION["count_present"], "The JSON does not expose the requested total story count."
    assert isinstance(SUBMISSION["count"], int) and not isinstance(SUBMISSION["count"], bool), "The total story count is not an integer."
    assert SUBMISSION["stories"], "The JSON story collection is empty."
    for index, story in enumerate(SUBMISSION["stories"], start=1):
        missing = [field for field, present in story["present"].items() if not present]
        assert not missing, f"Story entry {index} lacks requested logical values: {missing}."
        assert isinstance(story["rank"], int) and story["rank"] > 0, f"Story entry {index} has an unusable rank."
        assert isinstance(story["id"], str) and story["id"], f"Story entry {index} has an unusable item ID."
        assert isinstance(story["title"], str) and story["title"], f"Story entry {index} has an unusable title."
        assert isinstance(story["url"], str) and story["url"], f"Story entry {index} has an unusable URL."
        assert story["points"] is None or isinstance(story["points"], int), f"Story entry {index} has non-numeric points."
        assert story["comments"] is None or isinstance(story["comments"], int), f"Story entry {index} has a non-numeric comment count."


def test_coverage_and_order() -> None:
    assert SUBMISSION["error"] is None, "Coverage cannot be established because the story collection is unavailable."
    expected_ids = [row["id"] for row in EXPECTED]
    actual_ids = [row["id"] for row in SUBMISSION["stories"]]
    assert len(actual_ids) == len(expected_ids) == 30, f"Expected 30 ranked stories, found {len(actual_ids)}."
    assert SUBMISSION["count"] == 30, f"The reported total is {SUBMISSION['count']!r}, expected 30."
    assert actual_ids == expected_ids, "The item IDs are incomplete, duplicated, include a non-story row, or are not in displayed page order."
    assert [row["rank"] for row in SUBMISSION["stories"]] == [row["rank"] for row in EXPECTED], "Displayed ranks do not match the source order."


@pytest.mark.parametrize("expected", EXPECTED, ids=lambda row: row["id"])
def test_story_identity(expected: dict) -> None:
    actual = submitted_by_id().get(expected["id"])
    if actual is None:
        return  # Missing or wrong IDs are penalized only by coverage_and_order.
    assert actual["title"] == expected["title"], f"{expected['id']} has the wrong decoded visible title."
    assert comparable_url(actual["url"]) == comparable_url(expected["url"]), f"{expected['id']} has the wrong destination link."


SCORED_EXPECTED = [row for row in EXPECTED if row["points"] is not None]


@pytest.mark.parametrize("expected", SCORED_EXPECTED, ids=lambda row: row["id"])
def test_engagement_metadata(expected: dict) -> None:
    actual = submitted_by_id().get(expected["id"])
    if actual is None:
        return  # Coverage owns missing items; this criterion owns metadata on matched items.
    assert actual["points"] == expected["points"], f"{expected['id']} has the wrong point count."
    assert actual["comments"] == expected["comments"], f"{expected['id']} has the wrong comment count."


UNAVAILABLE_EXPECTED = [row for row in EXPECTED if row["points"] is None]


@pytest.mark.parametrize("expected", UNAVAILABLE_EXPECTED, ids=lambda row: row["id"])
def test_unavailable_metadata(expected: dict) -> None:
    actual = submitted_by_id().get(expected["id"])
    if actual is None:
        return  # Coverage owns missing items.
    assert actual["points"] is None, f"{expected['id']} has no score in the source but received a fabricated or leaked point value."
    assert actual["comments"] is None, f"{expected['id']} has no comment link in the source but received a fabricated or leaked count."
