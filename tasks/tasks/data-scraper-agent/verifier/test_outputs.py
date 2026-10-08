from __future__ import annotations

import csv
import json
import os
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT = RESULTS / "output.json"
PROJECT = RESULTS / "model_monitor"


ALIASES = {
    "model_id": ("model_id", "id", "modelId", "modelID"),
    "name": ("name", "title", "model_name", "modelName"),
    "vendor": ("vendor", "provider", "publisher"),
    "version": ("version", "release", "model_version"),
    "canonical_url": ("canonical_url", "canonicalUrl", "url", "link", "model_url"),
    "updated_at": ("updated_at", "updated", "last_updated", "published", "modified_at"),
    "status": ("status", "lifecycle", "availability"),
    "capabilities": ("capabilities", "features", "tasks", "modalities"),
    "context_tokens": ("context_tokens", "context_window", "max_context", "contextLength"),
    "input_price_per_million": ("input_price_per_million", "input_price", "price", "price_per_million"),
    "license": ("license", "usage_license", "terms"),
    "relevance_score": ("relevance_score", "score", "ai_score", "compatibility_score"),
    "priority": ("priority", "tier", "priority_level", "rank_band"),
    "reason": ("reason", "rationale", "explanation", "notes", "why"),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonicalize(raw_url: str, base_url: str) -> str:
    absolute = urljoin(base_url.rstrip("/") + "/", str(raw_url).strip())
    parts = urlsplit(absolute)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", "", ""))


def node_text(node) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def find_class(node, tag: str, class_name: str):
    return next((item for item in node.iter(tag) if class_name in item.get("class", "").split()), None)


def parse_card(card, config: dict) -> dict | None:
    heading = card.find("h2")
    link = find_class(heading, "a", "model-link") if heading is not None else None
    name = node_text(link)
    vendor_node = find_class(card, "span", "vendor")
    version_node = find_class(card, "span", "version")
    context_node = find_class(card, "span", "context")
    price_node = find_class(card, "span", "input-price")
    license_node = find_class(card, "span", "license")
    description_node = card.find("p")
    try:
        updated_at = card.get("data-updated", "").strip()
        date.fromisoformat(updated_at)
        context_tokens = int(context_node.get("data-tokens", ""))
        input_price = float(price_node.get("data-usd-per-million", ""))
    except (AttributeError, TypeError, ValueError):
        return None
    record = {
        "model_id": card.get("data-model-id", "").strip(),
        "name": name,
        "vendor": node_text(vendor_node),
        "version": node_text(version_node).removeprefix("v"),
        "canonical_url": canonicalize(link.get("href", ""), config["catalog_base_url"]) if link is not None else "",
        "updated_at": updated_at,
        "status": card.get("data-status", "").strip().lower(),
        "capabilities": sorted({node_text(node).lower() for node in card.findall(".//ul[@class='capabilities']/li") if node_text(node)}),
        "context_tokens": context_tokens,
        "input_price_per_million": input_price,
        "license": node_text(license_node).lower(),
        "description": node_text(description_node),
    }
    if any(record.get(field) in (None, "", []) for field in config["eligibility"]["required_fields"]):
        return None
    return record


def eligible(record: dict, config: dict) -> bool:
    rules = config["eligibility"]
    text = (record["name"] + " " + record["description"]).lower()
    return (
        record["status"] in rules["allowed_statuses"]
        and bool(set(record["capabilities"]) & set(rules["any_capability"]))
        and record["context_tokens"] >= rules["min_context_tokens"]
        and record["input_price_per_million"] <= rules["max_input_price_per_million"]
        and record["license"] in rules["allowed_licenses"]
        and not any(term.lower() in text for term in rules["blocked_terms"])
    )


def learned_signals(feedback: dict, config: dict) -> dict[str, set[str]]:
    rules = config["feedback"]
    positive = [r for r in feedback["records"] if r.get("decision") in rules["positive_decisions"]]
    negative = [r for r in feedback["records"] if r.get("decision") in rules["negative_decisions"]]

    def count(rows: list[dict], field: str, plural: bool = False) -> Counter:
        values = []
        for row in rows:
            value = row.get(field, [] if plural else "")
            values.extend(value if plural else [value])
        return Counter(value for value in values if value)

    pv, nv = count(positive, "vendor"), count(negative, "vendor")
    pc, nc = count(positive, "capabilities", True), count(negative, "capabilities", True)
    pl, nl = count(positive, "license"), count(negative, "license")
    return {
        "positive_vendors": {x for x, n in pv.items() if n >= rules["positive_vendor_min"] and nv[x] == 0},
        "positive_capabilities": {x for x, n in pc.items() if n >= rules["positive_capability_min"] and nc[x] == 0},
        "negative_vendors": {x for x, n in nv.items() if n >= rules["negative_vendor_min"] and pv[x] == 0},
        "negative_licenses": {x for x, n in nl.items() if n >= rules["negative_license_min"] and pl[x] == 0},
    }


def band_points(value: float, bands: list[dict], threshold_key: str) -> int:
    for band in bands:
        threshold = band[threshold_key]
        if (threshold_key.startswith("min") and value >= threshold) or (
            threshold_key.startswith("max") and value <= threshold
        ):
            return int(band["points"])
    return 0


def score(record: dict, config: dict, signals: dict[str, set[str]]) -> tuple[int, str]:
    scoring = config["scoring"]
    focus = set(config["eligibility"]["any_capability"])
    caps = set(record["capabilities"])
    points = min(scoring["capability_points_cap"], len(focus & caps) * scoring["capability_points_each"])
    points += band_points(record["context_tokens"], scoring["context_bands"], "min_tokens")
    points += band_points(record["input_price_per_million"], scoring["price_bands"], "max_usd")
    points += scoring["license_points"].get(record["license"], 0)
    if record["updated_at"] >= scoring["fresh_since"]:
        points += scoring["fresh_points"]
    adjustments = scoring["feedback_adjustments"]
    if record["vendor"] in signals["positive_vendors"]:
        points += adjustments["positive_vendor"]["points"]
    points += len(caps & signals["positive_capabilities"]) * adjustments["positive_capability"]["points"]
    if record["vendor"] in signals["negative_vendors"]:
        points += adjustments["negative_vendor"]["points"]
    if record["license"] in signals["negative_licenses"]:
        points += adjustments["negative_license"]["points"]
    points = max(scoring["clamp"][0], min(scoring["clamp"][1], points))
    thresholds = scoring["priority_thresholds"]
    priority = "high" if points >= thresholds["high"] else "medium" if points >= thresholds["medium"] else "low"
    return points, priority


def expected_state() -> dict:
    config = read_json(DATA / "monitor_config.json")
    parsed = []
    cards_seen = 0
    for path in sorted(DATA.glob("catalog_page_*.html")):
        source = path.read_text(encoding="utf-8")
        if source.lstrip().lower().startswith("<!doctype"):
            source = source.split("\n", 1)[1]
        root = ET.fromstring(source)
        cards = [node for node in root.iter("article") if "model-card" in node.get("class", "").split()]
        cards_seen += len(cards)
        parsed.extend(row for card in cards if (row := parse_card(card, config)) is not None)
    latest = {}
    for row in parsed:
        incumbent = latest.get(row["canonical_url"])
        if incumbent is None or (row["updated_at"], row["model_id"]) > (
            incumbent["updated_at"],
            incumbent["model_id"],
        ):
            latest[row["canonical_url"]] = row
    eligible_rows = {url: row for url, row in latest.items() if eligible(row, config)}
    prior = read_json(DATA / config["storage"]["existing_file"])["records"]
    final = {row["canonical_url"]: dict(row) for row in prior}
    changes = {}
    signals = learned_signals(read_json(DATA / "feedback.json"), config)
    for url, row in eligible_rows.items():
        previous = final.get(url)
        changed = previous is None
        if previous is not None:
            for field in config["storage"]["material_fields"]:
                current_value, previous_value = row.get(field), previous.get(field)
                if field == "capabilities":
                    current_value, previous_value = sorted(current_value or []), sorted(previous_value or [])
                if current_value != previous_value:
                    changed = True
                    break
        final[url] = {**(previous or {}), **row}
        if changed:
            expected_score, priority = score(row, config, signals)
            changes[row["model_id"]] = {**row, "relevance_score": expected_score, "priority": priority}
    return {
        "config": config,
        "signals": signals,
        "latest": latest,
        "eligible": eligible_rows,
        "changes": changes,
        "final": final,
        "cards_seen": cards_seen,
        "cards_parseable": len(parsed),
    }


def all_mappings(value) -> list[dict]:
    found = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            found.extend(all_mappings(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(all_mappings(nested))
    return found


def flattened(mapping: dict) -> dict:
    result = {}
    for node in all_mappings(mapping):
        for key, value in node.items():
            if not isinstance(value, (dict, list)) or key in {"capabilities", "features", "tasks", "modalities"}:
                result.setdefault(key, value)
    return result


def pick(mapping: dict, logical: str):
    flat = flattened(mapping)
    lower = {str(key).lower(): value for key, value in flat.items()}
    for alias in ALIASES[logical]:
        if alias in flat:
            return flat[alias]
        if alias.lower() in lower:
            return lower[alias.lower()]
    return None


def as_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        return float(cleaned)
    except ValueError:
        return None


def as_capabilities(value) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                value = stripped
        if isinstance(value, str):
            value = [part.strip() for part in value.replace(";", ",").split(",")]
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip().lower() for item in value if str(item).strip()})


def normalize_record(raw: dict, base_url: str) -> dict:
    result = {logical: pick(raw, logical) for logical in ALIASES}
    result["model_id"] = str(result["model_id"] or "").strip()
    result["name"] = str(result["name"] or "").strip()
    result["vendor"] = str(result["vendor"] or "").strip()
    result["version"] = str(result["version"] or "").strip().removeprefix("v")
    result["canonical_url"] = canonicalize(result["canonical_url"] or "", base_url)
    result["updated_at"] = str(result["updated_at"] or "").strip()
    result["status"] = str(result["status"] or "").strip().lower()
    result["capabilities"] = as_capabilities(result["capabilities"])
    result["context_tokens"] = as_number(result["context_tokens"])
    result["input_price_per_million"] = as_number(result["input_price_per_million"])
    result["license"] = str(result["license"] or "").strip().lower()
    result["relevance_score"] = as_number(result["relevance_score"])
    priority_aliases = {"urgent": "high", "top": "high", "normal": "medium", "mid": "medium", "defer": "low"}
    priority = str(result["priority"] or "").strip().lower()
    result["priority"] = priority_aliases.get(priority, priority)
    result["reason"] = str(result["reason"] or "").strip()
    return result


def extract_feed(payload) -> list[dict]:
    candidate_keys = ("items", "records", "models", "changes", "results", "feed", "added", "updated", "new_items", "changed_items")
    lists = []

    def walk(value, depth: int = 0):
        if depth > 4:
            return
        if isinstance(value, list):
            if any(isinstance(item, dict) and pick(item, "model_id") is not None for item in value):
                lists.append(value)
            return
        if isinstance(value, dict):
            for key in candidate_keys:
                if key in value:
                    walk(value[key], depth + 1)

    if isinstance(payload, list):
        lists.append(payload)
    else:
        walk(payload)
    raw_records = []
    seen_objects = set()
    for values in lists:
        for raw in values:
            if isinstance(raw, dict) and id(raw) not in seen_objects and pick(raw, "model_id") is not None:
                raw_records.append(raw)
                seen_objects.add(id(raw))
    return raw_records


def submission() -> tuple[object, list[dict]]:
    payload = read_json(OUTPUT)
    config = read_json(DATA / "monitor_config.json")
    records = [normalize_record(raw, config["catalog_base_url"]) for raw in extract_feed(payload)]
    return payload, records


def record_lists(value) -> list[list[dict]]:
    found = []
    if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
        if any(pick(row, "model_id") is not None for row in value):
            found.append(value)
    if isinstance(value, dict):
        for nested in value.values():
            found.extend(record_lists(nested))
    return found


def storage_candidates() -> list[tuple[str, list[dict]]]:
    candidates = []
    for path in PROJECT.rglob("*") if PROJECT.is_dir() else []:
        if not path.is_file() or path.resolve() == OUTPUT.resolve():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                for rows in record_lists(read_json(path)):
                    candidates.append((str(path), rows))
            elif suffix == ".csv":
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                if rows:
                    candidates.append((str(path), rows))
            elif suffix in {".db", ".sqlite", ".sqlite3"}:
                connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                try:
                    tables = [row[0] for row in connection.execute("select name from sqlite_master where type='table'")]
                    for table in tables:
                        safe_table = table.replace('"', '""')
                        cursor = connection.execute(f'SELECT * FROM "{safe_table}"')
                        columns = [item[0] for item in cursor.description]
                        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                        if rows:
                            candidates.append((f"{path}:{table}", rows))
                finally:
                    connection.close()
        except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError):
            continue
    return candidates


def test_artifact_and_change_feed():
    assert OUTPUT.is_file(), "missing /root/results/output.json"
    assert PROJECT.is_dir(), "missing /root/results/model_monitor project"
    assert any(path.suffix == ".py" for path in PROJECT.rglob("*")), "project has no runnable Python source"
    _, actual = submission()
    expected = expected_state()
    assert actual, "output JSON contains no identifiable model feed"
    ids = [row["model_id"] for row in actual]
    assert len(ids) == len(set(ids)), "change feed contains duplicate model IDs"
    assert set(expected["changes"]) <= set(ids), "one or more added/materially updated models are missing"
    eligible_ids = {row["model_id"] for row in expected["eligible"].values()}
    assert set(ids) <= eligible_ids, "feed includes an unusable or ineligible model"


def test_collection_normalization():
    expected = expected_state()
    _, actual_rows = submission()
    actual = {row["model_id"]: row for row in actual_rows}
    assert set(expected["changes"]) <= set(actual), "required changes are unavailable for collection checks"
    for model_id, wanted in expected["changes"].items():
        got = actual[model_id]
        assert got["canonical_url"] == wanted["canonical_url"], f"{model_id}: wrong canonical URL"
        assert "?" not in got["canonical_url"] and "#" not in got["canonical_url"] and not got["canonical_url"].endswith("/")
        for field in ("name", "vendor", "version", "updated_at", "status", "license"):
            assert got[field] == wanted[field], f"{model_id}: wrong {field}"
        assert got["capabilities"] == wanted["capabilities"], f"{model_id}: wrong capabilities"
        assert got["context_tokens"] == wanted["context_tokens"], f"{model_id}: wrong context"
        assert got["input_price_per_million"] is not None
        assert abs(got["input_price_per_million"] - wanted["input_price_per_million"]) < 1e-9, f"{model_id}: wrong price"


def test_feedback_aware_enrichment():
    expected = expected_state()
    _, actual_rows = submission()
    actual = {row["model_id"]: row for row in actual_rows}
    assert set(expected["changes"]) <= set(actual), "required changes are unavailable for enrichment checks"
    feedback_affected = 0
    for model_id, wanted in expected["changes"].items():
        got = actual[model_id]
        assert got["relevance_score"] == wanted["relevance_score"], f"{model_id}: wrong score"
        assert got["priority"] == wanted["priority"], f"{model_id}: wrong priority"
        assert got["reason"], f"{model_id}: compatibility reason is missing"
        if wanted["vendor"] in expected["signals"]["positive_vendors"] | expected["signals"]["negative_vendors"]:
            feedback_affected += 1
    assert feedback_affected >= 5, "fixture did not exercise enough vendor feedback cases"


def test_persistent_state_consistency():
    expected = expected_state()
    config = expected["config"]
    candidates = storage_candidates()
    assert candidates, "no readable JSON, CSV, or SQLite model store was found in the project"
    expected_ids = {row["model_id"] for row in expected["final"].values()}
    normalized_candidates = []
    for label, rows in candidates:
        normalized = [normalize_record(row, config["catalog_base_url"]) for row in rows]
        overlap = len(expected_ids & {row["model_id"] for row in normalized})
        normalized_candidates.append((overlap, label, normalized))
    _, label, stored = max(normalized_candidates, key=lambda item: item[0])
    stored_by_url = {row["canonical_url"]: row for row in stored if row["canonical_url"]}
    assert len(stored_by_url) == len(stored), f"{label} has blank or duplicate canonical identities"
    assert set(stored_by_url) == set(expected["final"]), f"{label} does not contain the exact post-run identity set"
    material_fields = config["storage"]["material_fields"]
    for url, wanted in expected["eligible"].items():
        got = stored_by_url[url]
        for field in material_fields:
            expected_value = wanted[field]
            actual_value = got[field]
            if field == "capabilities":
                assert actual_value == sorted(expected_value), f"{wanted['model_id']}: persisted capabilities are stale"
            elif field in {"context_tokens", "input_price_per_million"}:
                assert actual_value is not None and abs(actual_value - float(expected_value)) < 1e-9, f"{wanted['model_id']}: persisted {field} is stale"
            else:
                assert actual_value == expected_value, f"{wanted['model_id']}: persisted {field} is stale"
