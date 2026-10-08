from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_FILE", str(RESULTS / "output.json")))
SCRIPT = Path(os.environ.get("TASK_RETRIEVER_FILE", str(RESULTS / "retriever.py")))
MISSING = object()


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(row: dict, aliases: tuple[str, ...], default=MISSING):
    wanted = {_token(alias) for alias in aliases}
    for key, value in row.items():
        if _token(key) in wanted:
            return value
    if default is MISSING:
        raise KeyError(f"none of {aliases!r} is present")
    return default


def _section(root: object, aliases: tuple[str, ...]):
    if isinstance(root, list):
        return root
    wanted = {_token(alias) for alias in aliases}
    queue = [root]
    seen: set[int] = set()
    while queue:
        node = queue.pop(0)
        if not isinstance(node, dict) or id(node) in seen:
            continue
        seen.add(id(node))
        for key, value in node.items():
            if _token(key) in wanted:
                return value
        queue.extend(value for value in node.values() if isinstance(value, dict))
    return None


def _records(section: object, id_aliases: tuple[str, ...], pattern: str) -> list[dict]:
    records: list[dict] = []
    wanted = {_token(alias) for alias in id_aliases}

    def visit(node: object, inferred_id: object = None) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        has_id = any(_token(key) in wanted for key in node)
        if has_id or inferred_id is not None:
            row = dict(node)
            if not has_id:
                row[id_aliases[0]] = inferred_id
            records.append(row)
            return
        for key, value in node.items():
            inferred = key if isinstance(value, (dict, list)) and re.fullmatch(pattern, str(key), re.I) else None
            visit(value, inferred)

    visit(section)
    return records


def _canonical_point_id(value: object):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    return value


def _normalize_root(root: object) -> dict:
    section = _section(root, ("queries", "results", "search_results", "batch_results", "responses"))
    if section is None and isinstance(root, dict) and any(re.fullmatch(r"Q\d{3}", str(key), re.I) for key in root):
        section = root
    if section is None:
        return {"error": "no identifiable batch query-result section"}
    if isinstance(section, dict) and section and all(re.fullmatch(r"Q\d{3}", str(key), re.I) for key in section):
        rows = []
        for key, value in section.items():
            if isinstance(value, list):
                rows.append({"query_id": key, "hits": value})
            elif isinstance(value, dict):
                if not value or all(re.fullmatch(r"\d+", str(point_key)) for point_key in value):
                    rows.append({"query_id": key, "hits": value})
                else:
                    row = dict(value)
                    if _field(row, ("query_id", "request_id", "query", "id"), None) is None:
                        row["query_id"] = key
                    rows.append(row)
    else:
        rows = _records(section, ("query_id", "request_id", "query", "id"), r"Q\d{3}")
    if not rows:
        return {"error": "query-result section contains no identifiable query groups"}
    queries = []
    for row in rows:
        query_id = _field(row, ("query_id", "request_id", "query", "id"), None)
        hits_value = _field(row, ("hits", "matches", "points", "neighbors", "results"), None)
        if isinstance(hits_value, dict):
            hit_rows = _records(hits_value, ("point_id", "document_id", "point", "id"), r"\d+")
        elif isinstance(hits_value, list):
            hit_rows = [item for item in hits_value if isinstance(item, dict)]
        else:
            hit_rows = [] if hits_value == [] else None
        hits = None
        if hit_rows is not None:
            hits = []
            for hit in hit_rows:
                score = _field(hit, ("score", "similarity", "cosine_score", "cosine"), None)
                try:
                    score = float(score) if score is not None else None
                except (TypeError, ValueError):
                    score = None
                hits.append(
                    {
                        "point_id": _canonical_point_id(
                            _field(hit, ("point_id", "document_id", "point", "id"), None)
                        ),
                        "score": score,
                        "payload": _field(hit, ("payload", "metadata", "document", "source_payload"), None),
                    }
                )
        queries.append({"query_id": str(query_id) if query_id is not None else None, "hits": hits})
    return {"queries": queries}


def _normalize_file(path: Path) -> dict:
    if not path.is_file():
        return {"error": f"missing file: {path}"}
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable JSON: {exc}"}
    normalized = _normalize_root(root)
    normalized["root"] = root
    return normalized


def _load_inputs() -> tuple[dict, list[dict], list[dict]]:
    spec = json.loads((DATA / "collection_spec.json").read_text(encoding="utf-8"))
    with (DATA / "knowledge_points.jsonl").open(encoding="utf-8") as handle:
        points = [json.loads(line) for line in handle if line.strip()]
    requests = json.loads((DATA / "query_requests.json").read_text(encoding="utf-8"))
    return spec, points, requests


def _condition_matches(payload: dict, condition: dict) -> bool:
    key = condition["key"]
    value = payload.get(key)
    if "match" in condition:
        match = condition["match"]
        if "value" in match:
            return value == match["value"]
        if "any" in match:
            choices = match["any"]
            return any(item in choices for item in value) if isinstance(value, list) else value in choices
    if "range" in condition:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        bounds = condition["range"]
        return (
            ("gt" not in bounds or value > bounds["gt"])
            and ("gte" not in bounds or value >= bounds["gte"])
            and ("lt" not in bounds or value < bounds["lt"])
            and ("lte" not in bounds or value <= bounds["lte"])
        )
    return False


def _filter_matches(payload: dict, query_filter: dict) -> bool:
    must = query_filter.get("must", [])
    must_not = query_filter.get("must_not", [])
    should = query_filter.get("should", [])
    return (
        all(_condition_matches(payload, item) for item in must)
        and not any(_condition_matches(payload, item) for item in must_not)
        and (not should or any(_condition_matches(payload, item) for item in should))
    )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator


def _expected() -> dict:
    _, points, requests = _load_inputs()
    by_id = {row["point_id"]: row for row in points}
    queries = {}
    for request in requests:
        eligible = [row for row in points if _filter_matches(row["payload"], request["filter"])]
        ranked = sorted(
            (
                {
                    "point_id": row["point_id"],
                    "score": _cosine(request["query_vector"], row["vector"]),
                    "payload": row["payload"],
                }
                for row in eligible
            ),
            key=lambda row: (-row["score"], row["point_id"]),
        )[: request["limit"]]
        queries[request["query_id"]] = {
            "hits": ranked,
            "eligible_ids": {row["point_id"] for row in eligible},
        }
    return {"queries": queries, "point_by_id": by_id}


def _usable_submission() -> dict:
    normalized = _normalize_file(OUTPUT)
    if normalized.get("error"):
        pytest.skip("artifact-level parser failure is scored only by test_artifact_and_replay")
    if any(row["query_id"] is None or row["hits"] is None for row in normalized["queries"]):
        pytest.skip("unidentifiable query groups or hit lists are scored only by test_artifact_and_replay")
    return normalized


def _grouped(normalized: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in normalized["queries"]:
        if row["query_id"] not in grouped:
            grouped[row["query_id"]] = row["hits"]
    return grouped


def _semantic_signature(normalized: dict) -> dict[str, list[object]]:
    return {
        query_id: [hit["point_id"] for hit in hits]
        for query_id, hits in _grouped(normalized).items()
    }


def test_artifact_and_replay():
    """The two requested files are usable and the documented offline replay reproduces their hit IDs."""
    issues = []
    submitted = _normalize_file(OUTPUT)
    if submitted.get("error"):
        issues.append(submitted["error"])
    elif any(row["query_id"] is None or row["hits"] is None for row in submitted["queries"]):
        issues.append("output lacks an identifiable query ID or hit list in at least one result group")
    if not SCRIPT.is_file():
        issues.append(f"missing repeatable retriever: {SCRIPT}")
    else:
        with tempfile.TemporaryDirectory(prefix="qdrant-replay-") as tmp:
            replay_path = Path(tmp) / "output.json"
            process = subprocess.run(
                ["python3", str(SCRIPT), "--data-dir", str(DATA), "--output", str(replay_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if process.returncode != 0:
                issues.append(f"retriever replay failed: {(process.stderr or process.stdout)[-1200:]}")
            else:
                replayed = _normalize_file(replay_path)
                if replayed.get("error"):
                    issues.append(f"retriever replay produced {replayed['error']}")
                elif not submitted.get("error"):
                    if _semantic_signature(replayed) != _semantic_signature(submitted):
                        issues.append("retriever replay does not reproduce the submitted query-to-hit IDs")
    assert not issues, "; ".join(issues)


def test_query_coverage():
    """Every frozen request is represented exactly once, without unrelated query groups."""
    actual = _usable_submission()["queries"]
    expected_ids = list(_expected()["queries"])
    actual_ids = [row["query_id"] for row in actual]
    assert sorted(actual_ids) == sorted(expected_ids) and len(actual_ids) == len(set(actual_ids)), (
        f"query coverage differs: expected {expected_ids}, got {actual_ids}; "
        "missing or duplicate requests make the batch handoff incomplete"
    )


def test_filter_eligibility_and_hit_counts():
    """Returned point IDs remain inside each request's complete filter and use the correct top-k cardinality."""
    actual = _grouped(_usable_submission())
    expected = _expected()["queries"]
    issues = []
    for query_id in sorted(set(actual) & set(expected)):
        hits = actual[query_id]
        expected_hits = expected[query_id]["hits"]
        if len(hits) != len(expected_hits):
            issues.append(f"{query_id} returned {len(hits)} hits, expected {len(expected_hits)}")
        ineligible = [
            hit["point_id"]
            for hit in hits
            if hit["point_id"] not in expected[query_id]["eligible_ids"]
        ]
        if ineligible:
            issues.append(f"{query_id} contains filter-ineligible point IDs {ineligible}")
    assert not issues, "; ".join(issues)


def test_ranked_point_ids():
    """Complete hit lists are in exact nearest-neighbor order after filtering."""
    actual = _grouped(_usable_submission())
    expected = _expected()["queries"]
    issues = []
    checked = 0
    for query_id in sorted(set(actual) & set(expected)):
        expected_ids = [hit["point_id"] for hit in expected[query_id]["hits"]]
        actual_ids = [hit["point_id"] for hit in actual[query_id]]
        if len(actual_ids) != len(expected_ids):
            continue
        checked += 1
        if actual_ids != expected_ids:
            issues.append(f"{query_id}: expected ranked IDs {expected_ids}, got {actual_ids}")
    assert checked > 0, "no complete query result was available for ranking review"
    assert not issues, "; ".join(issues)


def test_similarity_scores():
    """Scores on correctly identified hits agree with cosine similarity within numerical tolerance."""
    actual = _grouped(_usable_submission())
    expected = _expected()["queries"]
    issues = []
    checked = 0
    for query_id in sorted(set(actual) & set(expected)):
        expected_hits = expected[query_id]["hits"]
        actual_hits = actual[query_id]
        if [hit["point_id"] for hit in actual_hits] != [hit["point_id"] for hit in expected_hits]:
            continue
        for actual_hit, expected_hit in zip(actual_hits, expected_hits):
            checked += 1
            score = actual_hit["score"]
            if score is None or not math.isfinite(score) or abs(score - expected_hit["score"]) > 1e-5:
                issues.append(
                    f"{query_id}/{expected_hit['point_id']} score {score!r} does not match "
                    f"cosine {expected_hit['score']:.8f}"
                )
    assert checked > 0, "no correctly identified hit list was available for score review"
    assert not issues, "; ".join(issues)


def test_hit_payload_fidelity():
    """Known hits expose their full source metadata and do not include stored vectors in payloads."""
    actual = _grouped(_usable_submission())
    sources = _expected()["point_by_id"]
    issues = []
    checked = 0
    for query_id, hits in actual.items():
        for hit in hits:
            point_id = hit["point_id"]
            if point_id not in sources:
                continue
            checked += 1
            payload = hit["payload"]
            if payload != sources[point_id]["payload"]:
                issues.append(f"{query_id}/{point_id} payload differs from the source point")
            if isinstance(payload, dict) and any(_token(key) in {"vector", "embedding", "densevector"} for key in payload):
                issues.append(f"{query_id}/{point_id} exposes a stored vector inside its payload")
    assert checked > 0, "no known returned point was available for payload review"
    assert not issues, "; ".join(issues)
