from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _load_data(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _key_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _get(record: dict, *aliases: str):
    wanted = {_key_name(alias) for alias in aliases}
    for key, value in record.items():
        if _key_name(str(key)) in wanted:
            return value
    return None


def _find_list(payload: dict, aliases: tuple[str, ...]) -> list | None:
    wanted = {_key_name(alias) for alias in aliases}
    queue = [(payload, 0)]
    while queue:
        current, depth = queue.pop(0)
        if not isinstance(current, dict):
            continue
        for key, value in current.items():
            if _key_name(str(key)) in wanted and isinstance(value, list):
                return value
        if depth < 2:
            queue.extend((value, depth + 1) for value in current.values() if isinstance(value, dict))
    return None


@lru_cache(maxsize=1)
def _submission() -> tuple[dict | None, str | None]:
    if not OUTPUT_PATH.is_file():
        return None, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"requested artifact is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "output.json must contain a JSON object with the requested collections"
    return payload, None


@lru_cache(maxsize=1)
def _source_maps() -> tuple[dict[str, str], set[str]]:
    raw = _load_data("issues.json")
    aliases: dict[str, str] = {}
    work_keys = {row["work_item_key"] for row in raw}
    for row in raw:
        key = row["work_item_key"]
        issue_id = row["issue_id"]
        for value in (
            key,
            issue_id,
            f"{row['provider']}:{issue_id}",
            f"{row['provider']}#{issue_id}",
            f"{row['provider']}/{issue_id}",
        ):
            aliases[value.lower()] = key
    return aliases, work_keys


def _scalar_identifiers(value) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        found.append(str(value))
    elif isinstance(value, list):
        for item in value:
            found.extend(_scalar_identifiers(item))
    elif isinstance(value, dict):
        provider = _get(value, "provider", "tracker")
        issue_id = _get(value, "issue_id", "ticket_id", "id", "ref")
        if provider is not None and issue_id is not None:
            found.append(f"{provider}:{issue_id}")
        for alias in ("work_item_key", "work_key", "canonical_id", "issue_id", "ticket_id", "id", "ref"):
            item = _get(value, alias)
            if item is not None and item is not value:
                found.extend(_scalar_identifiers(item))
    return found


def _resolve_work_key(record) -> str | None:
    aliases, work_keys = _source_maps()
    if isinstance(record, str):
        values = [record]
    elif isinstance(record, dict):
        values = []
        for alias in (
            "work_item_key", "work_key", "canonical_id", "canonical_key", "ticket_id", "issue_id", "item_id", "id", "key",
            "source_refs", "tracker_refs", "references", "sources",
        ):
            value = _get(record, alias)
            if value is not None:
                values.extend(_scalar_identifiers(value))
    else:
        return None
    for value in values:
        cleaned = str(value).strip()
        if cleaned in work_keys:
            return cleaned
        matched = aliases.get(cleaned.lower())
        if matched:
            return matched
    return None


def _ranked_records(payload: dict) -> list:
    rows = _find_list(payload, ("prioritized_inbox", "priority_inbox", "ranked_inbox", "ranked_issues", "inbox", "issues"))
    if not isinstance(rows, list):
        return []
    indexed = list(enumerate(rows))
    ranks = []
    for index, row in indexed:
        rank = _get(row, "rank", "position", "priority_rank") if isinstance(row, dict) else None
        if isinstance(rank, (int, float)) and not isinstance(rank, bool):
            ranks.append((float(rank), index, row))
        else:
            return rows
    return [row for _, _, row in sorted(ranks)]


def _packet_records(payload: dict) -> list:
    rows = _find_list(payload, ("execution_packets", "execute_packets", "execution_queue", "execute_queue", "ready_packets", "executions"))
    if not isinstance(rows, list):
        return []
    ranked = []
    for index, row in enumerate(rows):
        pos = _get(row, "queue_position", "position", "rank", "order") if isinstance(row, dict) else None
        if isinstance(pos, (int, float)) and not isinstance(pos, bool):
            ranked.append((float(pos), index, row))
        else:
            return rows
    return [row for _, _, row in sorted(ranked)]


def _reason_values(record: dict) -> list[str]:
    values = []
    for alias in ("reasons", "review_reasons", "reason", "blockers", "flags", "warnings"):
        value = _get(record, alias)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
    decision = _get(record, "execution_decision", "decision", "state", "status")
    if isinstance(decision, str):
        values.append(decision)
    routing = _get(record, "routing", "route", "repository_match")
    if isinstance(routing, dict):
        state = _get(routing, "status", "state", "decision")
        if isinstance(state, str):
            values.append(state)
    return values


def _looks_review(record: dict) -> bool:
    text = " ".join(_reason_values(record)).lower()
    markers = ("review", "blocked", "untrusted", "unknown", "ambiguous", "missing", "tie", "manual", "human", "unsafe", "hold", "triage")
    return any(marker in text for marker in markers)


def _review_records(payload: dict, inbox: list) -> list:
    rows = _find_list(payload, ("review_queue", "review_items", "needs_review", "manual_review", "exceptions"))
    if isinstance(rows, list):
        return rows
    return [row for row in inbox if isinstance(row, dict) and _looks_review(row)]


def _require_submission() -> dict:
    payload, error = _submission()
    if error:
        pytest.skip(f"semantic checks skipped because artifact usability failed: {error}")
    assert payload is not None
    return payload


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _word_set(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower()))


@lru_cache(maxsize=1)
def _expected() -> dict:
    raw = _load_data("issues.json")
    policy = _load_data("triage_policy.json")
    okrs = _load_data("okrs.json")
    repositories = _load_data("repositories.json")
    contexts = _load_data("icpg_context.json")
    author_rows = {row["author_id"]: row for row in _load_data("authors.json")}
    terminal = set(policy["terminal_statuses"])

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in raw:
        groups[row["work_item_key"]].append(row)
    provider_order = {name: pos for pos, name in enumerate(policy["provider_preference"])}
    priority_order = {name: pos for pos, name in enumerate(("P0", "P1", "P2", "P3"))}
    merged: dict[str, dict] = {}
    for work_key, rows in groups.items():
        primary = min(rows, key=lambda row: (provider_order.get(row["provider"], 99), row["issue_id"]))
        due_dates = [row["due_date"] for row in rows if row.get("due_date")]
        merged[work_key] = {
            "work_item_key": work_key,
            "title": primary["title"],
            "body": " ".join(row.get("body", "") for row in rows),
            "status": primary["status"],
            "priority": min((row["priority"] for row in rows), key=lambda value: priority_order.get(value, 99)),
            "updated_at": max((row["updated_at"] for row in rows), key=_parse_time),
            "due_date": min(due_dates) if due_dates else None,
            "labels": sorted({value for row in rows for value in row.get("labels", [])}),
            "okr_refs": sorted({value for row in rows for value in row.get("okr_refs", [])}),
            "components": sorted({value for row in rows for value in row.get("components", [])}),
            "authors": sorted({row["author_id"] for row in rows}),
            "blocker_keys": sorted({value for row in rows for value in row.get("blocker_keys", [])}),
        }
    for item in merged.values():
        item["blocked"] = any(
            blocker in merged and merged[blocker]["status"] not in terminal for blocker in item["blocker_keys"]
        )

    today = date.fromisoformat(policy["as_of_date"])
    active_okr_points = {row["okr_id"]: row["alignment_points"] for row in okrs if row["state"] == "active"}

    def calculate_score(item: dict) -> tuple[int, dict]:
        if item["due_date"]:
            due_delta = (date.fromisoformat(item["due_date"]) - today).days
            if due_delta < 0:
                due = 18
            elif due_delta <= 2:
                due = 14
            elif due_delta <= 7:
                due = 9
            elif due_delta <= 14:
                due = 4
            else:
                due = 0
        else:
            due = 0
        days = (today - _parse_time(item["updated_at"]).date()).days
        recency = 12 if days <= 1 else 8 if days <= 7 else 4 if days <= 30 else 1
        parts = {
            "priority": policy["ranking"]["priority_points"].get(item["priority"], 0),
            "due": due,
            "recency": recency,
            "impact": 6 if {"security", "data-loss"} & set(item["labels"]) else 0,
            "okr": max((active_okr_points.get(ref, 0) for ref in item["okr_refs"]), default=0),
            "blocked_penalty": -policy["ranking"]["blocked_penalty"] if item["blocked"] else 0,
        }
        return sum(parts.values()), parts

    ranked = []
    for item in merged.values():
        if item["status"] in terminal:
            continue
        item = dict(item)
        item["score"], item["score_breakdown"] = calculate_score(item)
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -item["score"],
            date.fromisoformat(item["due_date"]) if item["due_date"] else date.max,
            -_parse_time(item["updated_at"]).timestamp(),
            item["work_item_key"],
        )
    )

    repo_by_id = {row["repo_id"]: row for row in repositories}

    def route(item: dict) -> dict:
        item_words = _word_set(" ".join((item["title"], item["body"], " ".join(item["labels"]), " ".join(item["components"]))))
        scores = {}
        for repo in repositories:
            if not repo["enabled"]:
                continue
            component_hits = len(set(item["components"]) & set(repo["components"]))
            keyword_hits = len(item_words & set(repo["keywords"]))
            scores[repo["repo_id"]] = component_hits * policy["routing"]["component_match_points"] + keyword_hits
        best = max(scores.values(), default=0)
        winners = sorted(repo_id for repo_id, score in scores.items() if score == best and score > 0)
        return {
            "status": "matched" if len(winners) == 1 else "missing" if best == 0 else "ambiguous",
            "repo_id": winners[0] if len(winners) == 1 else None,
            "candidates": winners,
        }

    radius_order = {"high": 0, "medium": 1, "low": 2}

    def expected_context(item: dict, repo_id: str) -> list[dict]:
        item_words = _word_set(" ".join((item["title"], item["body"], " ".join(item["labels"]), " ".join(item["components"]))))
        matches = []
        for row in contexts:
            if row["repo_id"] != repo_id:
                continue
            score = len(item_words & set(row["keywords"]))
            if score >= policy["context"]["minimum_score"]:
                matches.append({**row, "relevance_score": score})
        matches.sort(key=lambda row: (-row["relevance_score"], radius_order[row["blast_radius"]], row["symbol"]))
        return matches[: policy["context"]["max_symbols"]]

    review: dict[str, set[str]] = {}
    routes = {}
    ready = []
    expected_contexts = {}
    for item in ranked:
        key = item["work_item_key"]
        item_route = route(item)
        routes[key] = item_route
        reasons: set[str] = set()
        if item["blocked"]:
            reasons.add("blocked")
        for author_id in item["authors"]:
            if author_id not in author_rows:
                reasons.add("unknown_author")
            elif not author_rows[author_id]["trusted_for_execution"]:
                reasons.add("untrusted_author")
        if item_route["status"] == "ambiguous":
            reasons.add("ambiguous_repo")
        elif item_route["status"] == "missing":
            reasons.add("missing_repo")
        if reasons:
            review[key] = reasons
        elif len(ready) < policy["execution"]["ready_packet_count"]:
            ready.append(key)
            expected_contexts[key] = expected_context(item, item_route["repo_id"])

    return {
        "raw": raw,
        "policy": policy,
        "merged": merged,
        "ranked": ranked,
        "ranked_keys": [item["work_item_key"] for item in ranked],
        "scores": {item["work_item_key"]: item["score"] for item in ranked},
        "routes": routes,
        "repositories": repo_by_id,
        "ready": ready,
        "review": review,
        "contexts": expected_contexts,
    }


def _extract_score(record: dict):
    value = _get(record, "score", "priority_score", "triage_score", "rank_score")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _extract_repo(record: dict) -> tuple[str | None, str | None]:
    repo_id = _get(record, "repo_id", "repository_id", "repository", "repo")
    path = _get(record, "working_dir", "working_directory", "repo_path", "repository_path", "path")
    for alias in ("routing", "route", "repository_match", "repo_match", "target"):
        nested = _get(record, alias)
        if isinstance(nested, dict):
            repo_id = repo_id or _get(nested, "repo_id", "repository_id", "id", "name", "repo")
            path = path or _get(nested, "working_dir", "repo_path", "path")
    if isinstance(repo_id, dict):
        path = path or _get(repo_id, "path", "working_dir")
        repo_id = _get(repo_id, "repo_id", "id", "name")
    repo_id = str(repo_id) if repo_id is not None else None
    path = str(path) if path is not None else None
    repositories = _expected()["repositories"]
    if repo_id and repo_id not in repositories:
        for candidate_id, repo in repositories.items():
            if repo_id in {repo["name"], repo["path"]}:
                repo_id = candidate_id
                break
    if not repo_id and path:
        for candidate_id, repo in repositories.items():
            if path == repo["path"]:
                repo_id = candidate_id
                break
    return repo_id, path


def _extract_context(record: dict) -> list[dict]:
    value = None
    for alias in ("icpg_context", "context", "relevant_context", "symbols", "relevant_symbols", "code_context"):
        candidate = _get(record, alias)
        if candidate is not None:
            value = candidate
            break
    if isinstance(value, dict):
        for alias in ("symbols", "items", "matches", "entries", "context"):
            nested = _get(value, alias)
            if isinstance(nested, list):
                value = nested
                break
        else:
            value = [value]
    if not isinstance(value, list):
        return []
    normalized = []
    for row in value:
        if isinstance(row, str):
            normalized.append({"symbol": row, "file": None})
        elif isinstance(row, dict):
            symbol = _get(row, "symbol", "symbol_name", "name")
            file_path = _get(row, "file", "file_path", "path")
            if symbol is not None:
                normalized.append({"symbol": str(symbol), "file": str(file_path) if file_path is not None else None})
    return normalized


def test_inbox_scope_and_dedup():
    payload = _require_submission()
    records = _ranked_records(payload)
    actual = [_resolve_work_key(row) for row in records]
    expected = _expected()["ranked_keys"]
    assert None not in actual, "all inbox entries must resolve to a source work item"
    assert len(actual) == len(set(actual)), "cross-provider mirrors or another work item appear more than once"
    assert set(actual) == set(expected), "the inbox must contain every canonical live item and no terminal item"


def test_priority_scores_and_order():
    payload = _require_submission()
    records = _ranked_records(payload)
    actual_keys = [_resolve_work_key(row) for row in records]
    expected = _expected()
    assert actual_keys == expected["ranked_keys"], "inbox order does not follow the supplied merged-item scoring and tie-break policy"
    supplied_scores = {
        key: _extract_score(row)
        for key, row in zip(actual_keys, records)
        if key is not None and _extract_score(row) is not None
    }
    wrong = {key: value for key, value in supplied_scores.items() if value != expected["scores"][key]}
    assert not wrong, f"exposed triage scores disagree with the supplied policy for {sorted(wrong)[:5]}"


def test_execution_queue_safety_and_routing():
    payload = _require_submission()
    packets = _packet_records(payload)
    keys = [_resolve_work_key(row) for row in packets]
    expected = _expected()
    assert keys == expected["ready"], "execution queue is not the first configured number of highest-ranked eligible items"
    for key, packet in zip(keys, packets):
        assert key is not None
        expected_repo = expected["routes"][key]["repo_id"]
        repo_id, path = _extract_repo(packet)
        assert repo_id == expected_repo, f"{key} is routed to {repo_id!r}, expected configured repo {expected_repo!r}"
        if path is not None:
            assert path == expected["repositories"][expected_repo]["path"], f"{key} uses a path outside its configured repository"


def test_review_flag_coverage():
    payload = _require_submission()
    inbox = _ranked_records(payload)
    reviews = _review_records(payload, inbox)
    actual = [_resolve_work_key(row) for row in reviews]
    assert None not in actual, "all review flags must identify a source work item"
    assert len(actual) == len(set(actual)), "review flags should not duplicate the same canonical work item"
    assert set(actual) == set(_expected()["review"]), "blocked, untrusted, unknown-author, ambiguous-route, and missing-route items must be flagged for review"


def test_icpg_context_enrichment():
    payload = _require_submission()
    packets = _packet_records(payload)
    expected = _expected()
    failures = []
    for packet in packets:
        key = _resolve_work_key(packet)
        if key not in expected["contexts"]:
            continue
        repo_id = expected["routes"][key]["repo_id"]
        expected_rows = expected["contexts"][key]
        expected_symbols = {row["symbol"] for row in expected_rows}
        known = {
            (row["symbol"], row["file"])
            for row in _load_data("icpg_context.json")
            if row["repo_id"] == repo_id
        }
        actual_rows = _extract_context(packet)
        actual_symbols = {row["symbol"] for row in actual_rows}
        if not actual_rows:
            failures.append(f"{key}: missing iCPG context")
            continue
        if expected_rows and expected_rows[0]["symbol"] not in actual_symbols:
            failures.append(f"{key}: strongest relevant symbol is missing")
        if not actual_symbols <= expected_symbols:
            failures.append(f"{key}: includes unrelated or lower-ranked symbols {sorted(actual_symbols - expected_symbols)}")
        for row in actual_rows:
            if row["file"] is not None and (row["symbol"], row["file"]) not in known:
                failures.append(f"{key}: symbol/file pair is not in the routed repo context")
    assert not failures, "; ".join(failures[:8])
