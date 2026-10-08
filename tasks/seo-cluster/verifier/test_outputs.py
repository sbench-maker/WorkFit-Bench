from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import pytest


RESULTS = Path("/root/results")
DATA = Path("/root/data")
PLAN_PATH = RESULTS / "cluster-plan.json"
MAP_PATH = RESULTS / "cluster-map.html"


def _norm_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _norm_url(raw: str) -> str:
    text = str(raw or "").strip()
    parsed = urlsplit(text if "://" in text else "https://" + text)
    return (parsed.netloc.lower() + parsed.path.rstrip("/")).lower()


def _first(mapping: dict, *keys, default=None):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _items(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return [value]


@pytest.fixture(scope="session")
def source():
    with (DATA / "keywords.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["keyword_id"]: row for row in rows}
    by_keyword = {_norm_text(row["keyword"]): row["keyword_id"] for row in rows}
    organic = {keyword_id: set() for keyword_id in by_id}
    with (DATA / "serp_results.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if _norm_text(row["result_type"]) == "organic" and 1 <= int(row["rank"]) <= 10:
                organic[row["keyword_id"]].add(_norm_url(row["result_url"]))
    overlaps = {
        (left, right): len(organic[left] & organic[right])
        for left in by_id
        for right in by_id
    }
    return {"rows": rows, "by_id": by_id, "by_keyword": by_keyword, "organic": organic, "overlaps": overlaps}


def _components(nodes, linked):
    remaining = set(nodes)
    groups = []
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        stack = [root]
        group = []
        while stack:
            current = stack.pop()
            group.append(current)
            neighbors = [other for other in remaining if linked(current, other)]
            for other in neighbors:
                remaining.remove(other)
                stack.append(other)
        groups.append(frozenset(group))
    return groups


@pytest.fixture(scope="session")
def expected(source):
    usable = [row["keyword_id"] for row in source["rows"] if _norm_text(row["intent_hint"]) != "navigational"]
    excluded = {row["keyword_id"] for row in source["rows"] if _norm_text(row["intent_hint"]) == "navigational"}
    pages = _components(usable, lambda left, right: source["overlaps"][left, right] >= 7)
    seed_page = next(page for page in pages if "kw001" in page)
    spoke_pages = [page for page in pages if page != seed_page]

    def page_overlap(left, right):
        return max(source["overlaps"][a, b] for a in left for b in right)

    page_keys = [min(page) for page in spoke_pages]
    pages_by_key = {min(page): page for page in spoke_pages}
    cluster_keys = _components(
        page_keys,
        lambda left, right: 4 <= page_overlap(pages_by_key[left], pages_by_key[right]) <= 6,
    )
    clusters = [frozenset(pages_by_key[key] for key in group) for group in cluster_keys]
    bridges = []
    for i, left in enumerate(spoke_pages):
        for right in spoke_pages[i + 1 :]:
            score = page_overlap(left, right)
            if 2 <= score <= 3:
                bridges.append((left, right, score))
    return {
        "usable": set(usable),
        "excluded": excluded,
        "pages": pages,
        "seed_page": seed_page,
        "spoke_pages": spoke_pages,
        "clusters": clusters,
        "bridges": bridges,
    }


def _keyword_id(value, source) -> str | None:
    if isinstance(value, dict):
        value = _first(value, "keyword_id", "id", "keyword", "name", "value")
    text = str(value or "").strip()
    if text in source["by_id"]:
        return text
    return source["by_keyword"].get(_norm_text(text))


def _load_plan_raw() -> tuple[dict | None, str | None]:
    try:
        value = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "top-level JSON value is not an object"
    return value, None


def _normalize_plan(raw: dict, source) -> dict:
    pillar_raw = _first(raw, "pillar", "pillar_page", "hub", default={})
    clusters_raw = _items(_first(raw, "clusters", "topic_clusters", "spoke_clusters", default=[]))
    pages = {}
    cluster_membership = {}

    def add_page(item, fallback_id, cluster_id, is_pillar=False):
        if not isinstance(item, dict):
            return None
        page_id = str(_first(item, "id", "page_id", "node_id", default=fallback_id))
        page_url = str(_first(item, "url", "target_url", "path", default=""))
        primary_value = _first(item, "primary_keyword_id", "primary_keyword", "keyword", "target_keyword")
        primary_id = _keyword_id(primary_value, source)
        refs = []
        for key in ("source_keyword_ids", "keyword_ids", "keywords", "target_keywords"):
            if key in item:
                refs.extend(_items(item[key]))
        refs.extend(_items(_first(item, "secondary_keywords", "secondary", "variants", default=[])))
        if primary_value is not None:
            refs.append(primary_value)
        keyword_ids = {keyword_id for value in refs if (keyword_id := _keyword_id(value, source))}
        if primary_id:
            keyword_ids.add(primary_id)
        pages[page_id] = {
            "id": page_id,
            "url": page_url,
            "title": str(_first(item, "title", "page_title", "name", default="")),
            "primary_id": primary_id,
            "keyword_ids": keyword_ids,
            "raw": item,
            "pillar": is_pillar,
        }
        cluster_membership[page_id] = cluster_id
        return page_id

    pillar_id = add_page(pillar_raw, "pillar", "pillar", True) if isinstance(pillar_raw, dict) else None
    for cluster_index, cluster_raw in enumerate(clusters_raw):
        if not isinstance(cluster_raw, dict):
            continue
        cluster_id = str(_first(cluster_raw, "id", "cluster_id", "name", "title", default=f"cluster-{cluster_index}"))
        posts = _items(_first(cluster_raw, "posts", "pages", "spokes", "articles", default=[]))
        for post_index, post in enumerate(posts):
            add_page(post, f"cluster-{cluster_index}-post-{post_index}", cluster_id)

    endpoint_aliases = {"pillar": pillar_id, "hub": pillar_id}
    for page_id, page in pages.items():
        endpoint_aliases[page_id] = page_id
        if page["url"]:
            endpoint_aliases[page["url"]] = page_id
            endpoint_aliases[_norm_url(page["url"])] = page_id
        if page["title"]:
            endpoint_aliases[_norm_text(page["title"])] = page_id

    assignments = {}
    excluded = set()
    assignment_conflicts = set()
    explicit = _items(_first(raw, "assignments", "keyword_assignments", "dispositions", default=[]))
    for item in explicit:
        if not isinstance(item, dict):
            continue
        keyword_id = _keyword_id(_first(item, "keyword_id", "keyword", "id"), source)
        if not keyword_id:
            continue
        disposition = _norm_text(_first(item, "disposition", "status", "action", default="assigned"))
        if disposition in {"excluded", "exclude", "removed", "navigational"}:
            excluded.add(keyword_id)
            continue
        target = str(_first(item, "page_id", "target_page", "page", "target", default=""))
        target_id = endpoint_aliases.get(target, endpoint_aliases.get(_norm_text(target), target))
        if keyword_id in assignments and assignments[keyword_id] != target_id:
            assignment_conflicts.add(keyword_id)
        assignments[keyword_id] = target_id

    for item in _items(_first(raw, "exclusions", "excluded_keywords", "excluded", default=[])):
        value = _first(item, "keyword_id", "keyword", "id") if isinstance(item, dict) else item
        if keyword_id := _keyword_id(value, source):
            excluded.add(keyword_id)
    for page_id, page in pages.items():
        for keyword_id in page["keyword_ids"]:
            if keyword_id in assignments and assignments[keyword_id] != page_id:
                assignment_conflicts.add(keyword_id)
            assignments.setdefault(keyword_id, page_id)
    assignment_conflicts.update(set(assignments) & excluded)

    links = []
    raw_links = _first(raw, "links", "internal_links", "link_matrix", "adjacency", default=[])
    if isinstance(raw_links, dict):
        expanded = []
        for source_endpoint, targets in raw_links.items():
            for target in _items(targets):
                if isinstance(target, dict):
                    expanded.append({"from": source_endpoint, **target})
                else:
                    expanded.append({"from": source_endpoint, "to": target})
        raw_links = expanded
    for item in _items(raw_links):
        if not isinstance(item, dict):
            continue
        source_value = str(_first(item, "from", "source", "source_id", default=""))
        target_value = str(_first(item, "to", "target", "target_id", "page_id", default=""))
        source_id = endpoint_aliases.get(source_value, endpoint_aliases.get(_norm_url(source_value), source_value))
        target_id = endpoint_aliases.get(target_value, endpoint_aliases.get(_norm_url(target_value), target_value))
        links.append(
            {
                "from": source_id,
                "to": target_id,
                "type": _norm_text(_first(item, "type", "relationship", "link_type", default="")),
                "anchor": str(_first(item, "anchor", "anchor_text", "text", default="")),
            }
        )
    return {
        "raw": raw,
        "pillar_id": pillar_id,
        "pages": pages,
        "clusters": cluster_membership,
        "assignments": assignments,
        "excluded": excluded,
        "assignment_conflicts": assignment_conflicts,
        "links": links,
    }


@pytest.fixture(scope="session")
def plan(source):
    raw, error = _load_plan_raw()
    if error:
        return {"error": error}
    try:
        normalized = _normalize_plan(raw, source)
        normalized["error"] = None
        return normalized
    except Exception as exc:  # Keep one malformed representation from exploding every case.
        return {"error": f"normalization failed: {exc}"}


def _require_plan(plan):
    if plan.get("error"):
        pytest.skip("plan readability/normalization is scored by artifact_usability")


def test_artifacts_are_readable_and_map_is_integrated(plan):
    assert PLAN_PATH.is_file(), "cluster-plan.json is missing, so the content plan cannot be used"
    assert not plan.get("error"), f"cluster-plan.json is not a usable machine-readable plan: {plan.get('error')}"
    assert plan["pillar_id"] in plan["pages"], "the plan does not expose a recognizable pillar page"
    assert len(plan["pages"]) >= 5, "the plan has too few target pages to be a usable hub-and-spoke plan"
    assert plan["links"], "the machine-readable plan does not expose an internal-link matrix"
    assert MAP_PATH.is_file(), "cluster-map.html is missing"
    html = MAP_PATH.read_text(encoding="utf-8")
    lower = html.lower()
    assert len(html) >= 2500 and "<svg" in lower and "indoor herb garden" in lower, (
        "the map is not a substantive visualization of the supplied topic"
    )
    assert "<script" in lower and any(token in lower for token in ("addeventlistener", "onclick", "onmouseover")), (
        "the requested interactive map has no observable interaction behavior"
    )
    assert not re.search(r"<script[^>]+src\s*=\s*['\"]https?://", html, flags=re.I), (
        "the offline map depends on a remote script"
    )


@pytest.mark.parametrize("case", ["coverage", "navigation", "same_page", "separation", "primary_choice"])
def test_serp_driven_keyword_dispositions(plan, source, expected, case):
    _require_plan(plan)
    if case == "coverage":
        all_disposed = set(plan["assignments"]) | set(plan["excluded"])
        assert all_disposed == set(source["by_id"]), (
            "every supplied keyword needs one traceable assigned-page or exclusion disposition"
        )
        assert not (set(plan["assignments"]) & set(plan["excluded"])), (
            "some keywords are simultaneously assigned and excluded"
        )
        assert not plan["assignment_conflicts"], (
            f"keywords have incompatible page dispositions: {sorted(plan['assignment_conflicts'])}"
        )
        assert all(value in plan["pages"] for value in plan["assignments"].values()), (
            "one or more keyword assignments point to a page absent from the plan"
        )
    elif case == "navigation":
        assert plan["excluded"] == expected["excluded"], (
            "the navigational terms are not cleanly excluded from the editorial cluster"
        )
    elif case == "same_page":
        for group in expected["pages"]:
            assigned_pages = {plan["assignments"].get(keyword_id) for keyword_id in group}
            assert None not in assigned_pages and len(assigned_pages) == 1, (
                f"high-overlap keywords {sorted(group)} were split even though the frozen SERPs support one target page"
            )
    elif case == "separation":
        for left, right in (("kw014", "kw036"), ("kw016", "kw030"), ("kw005", "kw027")):
            assert plan["assignments"].get(left) != plan["assignments"].get(right), (
                f"{left} and {right} were merged despite their materially different SERPs"
            )
    else:
        for group in expected["pages"]:
            page_id = plan["assignments"].get(next(iter(group)))
            page = plan["pages"].get(page_id, {})
            expected_primary = max(
                group,
                key=lambda keyword_id: int(source["by_id"][keyword_id]["monthly_volume"]),
            )
            assert page.get("primary_id") == expected_primary, (
                f"page {page_id} does not use the highest-volume merged keyword as its primary target"
            )


@pytest.mark.parametrize("case", ["pillar", "shape", "serp_clusters"])
def test_hub_and_spoke_architecture(plan, expected, case):
    _require_plan(plan)
    if case == "pillar":
        assert plan["pillar_id"] == plan["assignments"].get("kw001"), (
            "the seed keyword and its broad high-volume variants are not assigned to the pillar"
        )
        assert plan["pages"][plan["pillar_id"]]["primary_id"] == "kw001", (
            "the pillar does not target the broadest, highest-volume supplied keyword"
        )
    elif case == "shape":
        spoke_ids = [page_id for page_id in plan["pages"] if page_id != plan["pillar_id"]]
        clusters = defaultdict(list)
        for page_id in spoke_ids:
            clusters[plan["clusters"].get(page_id)].append(page_id)
        assert None not in clusters, "at least one spoke is not assigned to a named cluster"
        assert 2 <= len(clusters) <= 5, "the plan falls outside the supplied 2-5 cluster policy"
        assert all(2 <= len(page_ids) <= 4 for page_ids in clusters.values()), (
            "one or more clusters falls outside the supplied 2-4 spoke policy"
        )
        assert len(spoke_ids) == 12, "the SERP-supported page targets do not resolve to twelve distinct spokes"
    else:
        for expected_cluster in expected["clusters"]:
            output_cluster_ids = set()
            for expected_page in expected_cluster:
                keyword_id = next(iter(expected_page))
                page_id = plan["assignments"].get(keyword_id)
                output_cluster_ids.add(plan["clusters"].get(page_id))
            assert None not in output_cluster_ids and len(output_cluster_ids) == 1, (
                "pages with 4-6-result overlap were split across unrelated topic clusters"
            )
        for output_cluster in set(plan["clusters"].values()):
            represented = []
            for index, expected_cluster in enumerate(expected["clusters"]):
                if any(
                    plan["clusters"].get(plan["assignments"].get(next(iter(page)))) == output_cluster
                    for page in expected_cluster
                ):
                    represented.append(index)
            assert len(set(represented)) <= 1, "one cluster mixes pages whose frozen SERPs support separate subtopics"


@pytest.mark.parametrize("case", ["endpoints", "pillar_links", "incoming_density", "bridges_and_anchors"])
def test_internal_link_network(plan, source, expected, case):
    _require_plan(plan)
    links = plan["links"]
    page_ids = set(plan["pages"])
    edge_set = {(item["from"], item["to"]) for item in links}
    pillar_id = plan["pillar_id"]
    spoke_ids = page_ids - {pillar_id}
    if case == "endpoints":
        assert all(item["from"] in page_ids and item["to"] in page_ids for item in links), (
            "the link matrix contains endpoints that do not resolve to planned pages"
        )
        assert all(item["from"] != item["to"] for item in links), "self-links do not help readers navigate the cluster"
    elif case == "pillar_links":
        for spoke_id in spoke_ids:
            assert (pillar_id, spoke_id) in edge_set and (spoke_id, pillar_id) in edge_set, (
                f"spoke {spoke_id} is missing one direction of the required pillar connection"
            )
    elif case == "incoming_density":
        incoming = Counter(item["to"] for item in links)
        assert all(incoming[page_id] >= 3 for page_id in page_ids), (
            "at least one planned page has fewer than three incoming internal links"
        )
    else:
        for left_page, right_page, score in expected["bridges"]:
            if score != 3:
                continue
            left_id = plan["assignments"].get(next(iter(left_page)))
            right_id = plan["assignments"].get(next(iter(right_page)))
            assert (left_id, right_id) in edge_set or (right_id, left_id) in edge_set, (
                "a score-3 SERP bridge has no contextual cross-cluster link"
            )
        generic = {"click here", "read more", "learn more", "this article", "here"}
        assert all(_norm_text(item["anchor"]) and _norm_text(item["anchor"]) not in generic for item in links), (
            "the link matrix contains missing or generic anchor text instead of descriptive destination language"
        )
