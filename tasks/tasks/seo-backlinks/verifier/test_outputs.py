from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest


OUTPUT = Path("/root/results/backlink_audit.json")
DATA = Path("/root/data")


def canon(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def key_value(mapping: dict, aliases: list[str], recursive: bool = True):
    wanted = {canon(alias) for alias in aliases}
    for key, value in mapping.items():
        if canon(key) in wanted:
            return value
    if recursive:
        for child in mapping.values():
            if isinstance(child, dict):
                found = key_value(child, aliases, recursive=True)
                if found is not None:
                    return found
    return None


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        return float(match.group()) if match else None
    return None


def as_percent(value):
    parsed = number(value)
    if parsed is None:
        return None
    if isinstance(value, str) and "%" in value:
        return parsed
    return parsed * 100 if 0 <= parsed <= 1 else parsed


def field_number(mapping: dict, aliases: list[str], *, percent: bool = False):
    value = key_value(mapping, aliases)
    if isinstance(value, list):
        return float(len(value))
    return as_percent(value) if percent else number(value)


def find_profile(report: dict, site: str):
    site_keys = {canon(site), canon(site.split(".", 1)[0])}
    sections = []
    for node in walk(report):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if canon(key) in site_keys and isinstance(value, dict):
                sections.append(value)
        identity = key_value(node, ["site", "domain", "site_name", "destination_site"], recursive=False)
        if isinstance(identity, str) and canon(identity) in site_keys:
            sections.append(node)
    if not sections:
        return None
    # A report can organize the same site's evidence by analysis section.
    # Combine those sections before checking its metrics and anchor mix.
    profile = {}
    for section in sections:
        profile.update(section)
    return profile


def find_section(report: dict, aliases: list[str], required_token: str | None = None):
    wanted = {canon(alias) for alias in aliases}
    for node in walk(report):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            ck = canon(key)
            if (ck in wanted or any(alias in ck for alias in wanted)) and isinstance(value, (dict, list)):
                if required_token is None or required_token in ck:
                    return value
    return None


def object_domain(item):
    if isinstance(item, str):
        return item.strip().lower()
    if isinstance(item, dict):
        value = key_value(item, ["domain", "source_domain", "referring_domain", "name"], recursive=False)
        return value.strip().lower() if isinstance(value, str) else None
    return None


def list_domains(value) -> set[str]:
    if isinstance(value, dict):
        # Supports maps keyed by domain as well as wrappers around a domain list.
        obvious = {str(key).lower() for key in value if "." in str(key)}
        if obvious:
            return obvious
        for child in value.values():
            found = list_domains(child)
            if found:
                return found
        return set()
    if not isinstance(value, list):
        return set()
    return {domain for item in value if (domain := object_domain(item))}


def list_objects(value) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if any("." in str(key) for key in value):
            return [dict(child, domain=key) if isinstance(child, dict) else {"domain": key, "value": child} for key, child in value.items()]
        for child in value.values():
            found = list_objects(child)
            if found:
                return found
    return []


def find_named_list(report: dict, aliases: list[str]):
    wanted = {canon(alias) for alias in aliases}
    for node in walk(report):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            ck = canon(key)
            if (ck in wanted or any(alias in ck for alias in wanted)) and isinstance(value, (list, dict)):
                return value
    return None


def load_report():
    if not OUTPUT.is_file():
        return None, "the requested /root/results/backlink_audit.json file is missing"
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"the requested artifact is not readable JSON: {exc}"
    if not isinstance(value, dict):
        return None, "the JSON report must be an object so its audit sections are usable"
    return value, None


def require_report():
    report, error = load_report()
    if error:
        pytest.skip(f"artifact root failure already isolated by test_artifact_usability: {error}")
    return report


@pytest.fixture(scope="module")
def source():
    links = read_csv("backlinks.csv")
    domain_rows = read_csv("referring_domains.csv")
    pages_rows = read_csv("site_pages.csv")
    context = json.loads((DATA / "site_context.json").read_text(encoding="utf-8"))
    return {
        "links": links,
        "domains": {row["domain"]: row for row in domain_rows},
        "pages": {(row["site"], row["path"]): row for row in pages_rows},
        "context": context,
        "target": next(site for site, row in context["sites"].items() if row["role"] == "target"),
        "competitor": next(site for site, row in context["sites"].items() if row["role"] == "competitor"),
    }


def active_links(source, site):
    return [row for row in source["links"] if row["destination_site"] == site and row["verification_status"] == "verified_active"]


def classify_anchor(text: str, site: str, context: dict) -> str:
    value = " ".join(text.lower().strip().split())
    rules = context["sites"][site]
    if value.startswith("http://") or value.startswith("https://") or value.strip("/") == site:
        return "url"
    if any(term in value for term in rules["brand_terms"]):
        return "branded"
    if value in rules["exact_keywords"]:
        return "exact"
    if value in rules["generic_anchors"]:
        return "generic"
    if any(phrase in value for phrase in rules["partial_phrases"]):
        return "partial"
    return "long_tail"


def anchor_rows(profile: dict) -> dict[str, dict]:
    raw = key_value(profile, ["anchor_distribution", "anchor_mix", "anchors", "anchor_text_distribution", "distribution"])
    if not isinstance(raw, (dict, list)):
        return {}
    aliases = {
        "branded": {"branded", "brand"},
        "url": {"url", "naked", "nakedurl", "nakedlink"},
        "generic": {"generic"},
        "exact": {"exact", "exactmatch", "exactkeyword"},
        "partial": {"partial", "partialmatch", "partialkeyword"},
        "long_tail": {"longtail", "natural", "other"},
    }
    result = {}
    items = raw.items() if isinstance(raw, dict) else enumerate(raw)
    for key, item in items:
        label = str(key)
        if isinstance(item, dict):
            label = str(key_value(item, ["type", "category", "anchor_type", "name"], recursive=False) or key)
        canonical_label = canon(label)
        category = next((name for name, names in aliases.items() if canonical_label in {canon(v) for v in names}), None)
        if category:
            if isinstance(item, dict):
                count = field_number(item, ["count", "links", "backlinks", "number"])
                pct = field_number(item, ["pct", "percent", "percentage", "share", "ratio"], percent=True)
            else:
                count, pct = None, as_percent(item)
            result[category] = {"count": count, "percent": pct}
    return result


def page_rows(profile: dict, aliases: list[str]) -> list[dict]:
    raw = key_value(profile, aliases)
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                rows.append(dict(value, path=key))
            elif number(value) is not None:
                rows.append({"path": key, "active_backlinks": value})
        return rows
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def page_path(item: dict):
    value = key_value(item, ["path", "page", "url", "destination_path", "target_page"], recursive=False)
    if not isinstance(value, str):
        return None
    if value.startswith("http"):
        match = re.match(r"https?://[^/]+(.*)", value)
        return (match.group(1) or "/") if match else value
    return value


def direct_risk_names(source, site: str | None = None) -> set[str]:
    names = set()
    active_domains = {
        row["source_domain"] for row in source["links"]
        if row["verification_status"] == "verified_active"
        and (site is None or row["destination_site"] == site)
    }
    for name in active_domains:
        row = source["domains"][name]
        if (
            row["known_pbn"] == "yes"
            or row["penalty_status"] != "none"
            or int(row["indexed_pages"]) == 0
            or int(row["outbound_links_per_page"]) >= 10_000
            or row["hacked_content"] == "yes"
            or (row["paid_sitewide"] == "yes" and row["topic_fit"] == "unrelated")
        ):
            names.add(name)
    return names


def test_artifact_usability(source):
    report, error = load_report()
    assert error is None, error
    for site in [source["target"], source["competitor"]]:
        profile = find_profile(report, site)
        assert profile is not None, f"no identifiable backlink profile was found for {site}"
        assert anchor_rows(profile), f"no usable anchor mix was found for {site}"
        assert page_rows(profile, ["top_linked_pages", "top_pages", "linked_pages", "pages_by_backlinks"]), f"no linked-page analysis was found for {site}"
    assert find_section(report, ["competitor_gap", "link_gap", "gap_analysis", "backlink_gap"]) is not None, "competitor link-gap analysis is missing"
    assert find_named_list(report, ["disavow_candidates", "disavow_domains", "high_risk_domains", "toxic_domains"]) is not None, "a separate disavow-candidate review is missing"
    serialized = json.dumps(report, ensure_ascii=False).lower()
    assert "snapshot" in serialized or "point-in-time" in serialized, "the artifact does not identify its point-in-time snapshot scope"


def test_profile_metrics_and_anchor_distribution(source):
    report = require_report()
    for site in [source["target"], source["competitor"]]:
        profile = find_profile(report, site)
        assert profile is not None, f"profile missing for {site}"
        active = active_links(source, site)
        expected = {
            "active": len(active),
            "domains": len({row["source_domain"] for row in active}),
            "follow": sum(row["rel"] == "follow" for row in active),
        }
        got_active = field_number(profile, ["active_backlinks", "live_backlinks", "verified_active_links", "current_backlinks"])
        got_domains = field_number(profile, ["referring_domains", "active_referring_domains", "ref_domains", "linking_domains"])
        got_follow_pct = field_number(profile, ["follow_ratio_percent", "follow_percent", "dofollow_ratio", "follow_share"], percent=True)
        assert got_active == expected["active"], f"{site} active backlink total is {got_active}, expected {expected['active']}"
        assert got_domains == expected["domains"], f"{site} referring-domain total is {got_domains}, expected {expected['domains']}"
        assert got_follow_pct is not None and math.isclose(got_follow_pct, expected["follow"] * 100 / expected["active"], abs_tol=0.11), f"{site} follow share is not reconciled to active links"
        got_anchors = anchor_rows(profile)
        expected_anchors = Counter(classify_anchor(row["anchor_text"], site, source["context"]) for row in active)
        for category in ["branded", "url", "generic", "exact", "partial", "long_tail"]:
            assert category in got_anchors, f"{site} anchor mix omits {category}"
            row = got_anchors[category]
            assert row["count"] == expected_anchors[category] or (
                row["percent"] is not None and math.isclose(row["percent"], expected_anchors[category] * 100 / len(active), abs_tol=0.11)
            ), f"{site} {category} anchor value does not match the inferred anchor texts"


def test_referring_domain_quality_and_top_pages(source):
    report = require_report()
    for site in [source["target"], source["competitor"]]:
        profile = find_profile(report, site)
        active = active_links(source, site)
        names = {row["source_domain"] for row in active}
        expected_bands = Counter(
            "high" if int(source["domains"][name]["authority_score"]) >= 70 else "medium" if int(source["domains"][name]["authority_score"]) >= 40 else "low"
            for name in names
        )
        quality = key_value(profile, ["referring_domain_authority_bands", "authority_bands", "quality_distribution", "domain_quality"])
        average = field_number(profile, ["average_domain_authority", "avg_authority", "mean_authority", "average_authority"])
        quality_ok = False
        if isinstance(quality, dict):
            values = {canon(key): number(value) if not isinstance(value, dict) else field_number(value, ["count", "domains", "number"]) for key, value in quality.items()}
            quality_ok = all(values.get(canon(band)) == expected_bands[band] for band in ["high", "medium", "low"])
        expected_average = sum(int(source["domains"][name]["authority_score"]) for name in names) / len(names)
        quality_ok = quality_ok or (average is not None and math.isclose(average, expected_average, abs_tol=0.11))
        assert quality_ok, f"{site} needs a correct authority-band distribution or average authority to substantiate referring-domain quality"

        counts = Counter(row["destination_path"] for row in active)
        expected_top = [path for path, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
        got_rows = page_rows(profile, ["top_linked_pages", "top_pages", "linked_pages", "pages_by_backlinks"])
        got = {page_path(item): field_number(item, ["active_backlinks", "backlinks", "link_count", "links", "count"]) for item in got_rows}
        for path in expected_top:
            assert path in got and got[path] == counts[path], f"{site} leading linked page {path} is absent or has the wrong active-link count"


def test_gap_sets_and_prospect_evidence(source):
    report = require_report()
    target_active = {row["source_domain"] for row in active_links(source, source["target"])}
    competitor_active = {row["source_domain"] for row in active_links(source, source["competitor"])}
    competitor_only = competitor_active - target_active
    gap_value = find_named_list(report, ["competitor_only_domains", "competitor_only_referring_domains", "link_gap_domains", "gap_domains"])
    gap_count = None
    if gap_value is not None:
        gap_domains = list_domains(gap_value)
        if gap_domains:
            assert gap_domains == competitor_only, "the represented competitor-only domain set does not match active snapshot links"
        else:
            gap_count = number(gap_value)
    if gap_value is None or (not list_domains(gap_value) and gap_count is None):
        gap_count = field_number(report, ["competitor_only_count", "link_gap_count", "gap_domain_count"])
    assert list_domains(gap_value) == competitor_only or gap_count == len(competitor_only), "the report needs the correct competitor-only gap set or count"

    raw_prospects = find_named_list(report, ["ranked_outreach_prospects", "outreach_prospects", "viable_opportunities", "link_building_opportunities", "ranked_opportunities"])
    prospects = list_objects(raw_prospects)
    assert 1 <= len(prospects) <= 10, "the ranked competitor-only prospect list must contain between 1 and 10 usable entries"
    seen = set()
    risky = direct_risk_names(source)
    for item in prospects:
        name = object_domain(item)
        assert name and name not in seen, "ranked prospects need unique identifiable domains"
        seen.add(name)
        assert name in competitor_only, f"{name} is not an active competitor-only referring domain"
        info = source["domains"][name]
        assert name not in risky and info["topic_fit"] in {"high", "medium"} and info["language"] == "en", f"{name} is not a viable outreach prospect"
        expected_links = [row for row in active_links(source, source["competitor"]) if row["source_domain"] == name]
        authority = field_number(item, ["authority_score", "authority", "domain_authority", "da"])
        link_count = field_number(item, ["competitor_active_links", "active_links", "backlinks", "link_count"])
        assert authority == int(info["authority_score"]), f"{name} has unsupported authority evidence"
        assert link_count == len(expected_links), f"{name} has unsupported competitor-link evidence"


def test_disavow_candidates_and_false_positive_controls(source):
    report = require_report()
    raw = find_named_list(report, ["disavow_candidates", "disavow_domains", "high_risk_domains", "toxic_domains"])
    items = list_objects(raw)
    got = list_domains(raw)
    expected = direct_risk_names(source, source["target"])
    assert got == expected, f"disavow candidates differ from the domains with direct evidence; missing={sorted(expected-got)}, extra={sorted(got-expected)}"
    evidence_terms = {"pbn", "penalty", "penal", "deindex", "indexed", "outbound", "linkfarm", "hacked", "paid", "sitewide", "manualaction", "zeroindexed"}
    by_domain = {object_domain(item): item for item in items}
    for name in expected:
        serialized = canon(json.dumps(by_domain.get(name, {}), ensure_ascii=False))
        assert any(term in serialized for term in evidence_terms), f"{name} is listed without observable manipulation, penalty, indexing, or placement evidence"
    false_positives = {"nofollow-index.test", "small-security-blog.test", "thin-profile.test"}
    assert not got & false_positives, "nofollow, low authority, or thinness alone was incorrectly treated as disavow evidence"


def test_unknown_and_reclamation_handling(source):
    report = require_report()
    for site in [source["target"], source["competitor"]]:
        profile = find_profile(report, site)
        all_site = [row for row in source["links"] if row["destination_site"] == site]
        expected_unknown = sum(row["verification_status"] == "unverifiable_js" for row in all_site)
        expected_removed = sum(row["verification_status"] == "verified_removed" for row in all_site)
        unknown = field_number(profile, ["unverifiable_links", "unknown_links", "unverified_links", "unverifiable_js"])
        removed = field_number(profile, ["verified_removed_links", "removed_links", "lost_verified_links"])
        assert unknown == expected_unknown, f"{site} must preserve {expected_unknown} JS-unverifiable links as unknown"
        assert removed == expected_removed, f"{site} verified-removed count must not absorb unknown rows"

        active = active_links(source, site)
        expected_reclamation = Counter(
            row["destination_path"] for row in active
            if int(source["pages"][(site, row["destination_path"])]["http_status"]) == 404
        )
        got_rows = page_rows(profile, ["reclamation_pages", "link_reclamation", "broken_link_opportunities", "404_pages"])
        got = {page_path(item): field_number(item, ["active_backlinks", "backlinks", "link_count", "links", "count"]) for item in got_rows}
        assert got == dict(expected_reclamation), f"{site} active backlinks to 404 pages are not fully and accurately surfaced for reclamation"
    text = json.dumps(report, ensure_ascii=False).lower()
    assert ("velocity" in text or "trend" in text) and ("cannot" in text or "not " in text or "insufficient" in text), "the single-snapshot report must explicitly avoid a link-velocity or trend inference"
