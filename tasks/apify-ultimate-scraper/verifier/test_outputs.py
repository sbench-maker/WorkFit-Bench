from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest


OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def _canon_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _lookup(mapping: dict, *aliases: str, default=None):
    indexed = {_canon_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        key = _canon_key(alias)
        if key in indexed:
            return indexed[key]
    return default


def _as_scalar(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _text(value):
    value = _as_scalar(value)
    return None if value is None else str(value).strip()


def _number(value):
    value = _as_scalar(value)
    if value is None or value == "":
        return None
    return float(str(value).replace(",", ""))


def _extract_parts(payload) -> tuple[list, dict]:
    if isinstance(payload, list):
        return payload, {}
    if not isinstance(payload, dict):
        return [], {}
    leads = _lookup(payload, "leads", "prospects", "records", "items", "results", "data")
    if isinstance(leads, dict):
        leads = _lookup(leads, "leads", "records", "items", "results", default=[])
    if not isinstance(leads, list):
        candidates = [value for value in payload.values() if isinstance(value, list) and all(isinstance(x, dict) for x in value)]
        leads = max(candidates, key=len) if candidates else []
    summary = _lookup(payload, "run_summary", "summary", "scrape_summary", "metadata", default={})
    return leads, summary if isinstance(summary, dict) else {}


def _normalize_lead(row: dict) -> dict:
    return {
        "place_id": _text(_lookup(row, "place_id", "placeId", "source_place_id", "source_id", "id")),
        "business_name": _text(_lookup(row, "business_name", "businessName", "title", "name")),
        "address": _text(_lookup(row, "address", "formatted_address", "street_address")),
        "city": _text(_lookup(row, "city", "locality")),
        "state": _text(_lookup(row, "state", "region")),
        "category": _text(_lookup(row, "category", "categoryName", "business_category")),
        "rating": _number(_lookup(row, "rating", "totalScore", "score")),
        "reviews_count": _number(_lookup(row, "reviews_count", "reviewsCount", "review_count", "reviews")),
        "website": _text(_lookup(row, "website", "website_url", "site")),
        "phone": _text(_lookup(row, "phone", "telephone", "phones")),
        "email": (_text(_lookup(row, "email", "primary_email", "business_email", "emails")) or "").casefold() or None,
        "linkedin_url": _text(_lookup(row, "linkedin_url", "linkedInUrl", "linkedin", "linkedin_company_url")),
    }


def _submission():
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, [], {}
    raw_leads, summary = _extract_parts(payload)
    if not all(isinstance(row, dict) for row in raw_leads):
        return payload, [], summary
    return payload, [_normalize_lead(row) for row in raw_leads], summary


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    return (urlparse(url).hostname or "").casefold().removeprefix("www.") or None


def _location_key(row: dict) -> tuple[str, str]:
    return (
        re.sub(r"[^a-z0-9]", "", row["title"].casefold()),
        re.sub(r"[^a-z0-9]", "", row["address"].casefold()),
    )


def _select_email(row: dict, q: dict) -> str | None:
    domain = _domain(row.get("website"))
    if not domain or domain in {item.casefold() for item in q["free_email_domains"]}:
        return None
    blocked = {item.casefold() for item in q["blocked_local_parts"]}
    rank = {name: index for index, name in enumerate(q["email_preference"])}
    choices = set()
    for raw in row.get("emails") or []:
        email = str(raw).strip().casefold()
        if email.count("@") != 1:
            continue
        local, email_domain = email.split("@")
        if email_domain == domain and local not in blocked:
            choices.add(email)
    if not choices:
        return None
    return sorted(choices, key=lambda email: (rank.get(email.split("@", 1)[0], rank.get("other", 999)), email))[0]


@pytest.fixture(scope="session")
def truth():
    brief = json.loads((DATA / "brief.json").read_text(encoding="utf-8"))
    places = json.loads((DATA / "mock_apify/places_source.json").read_text(encoding="utf-8"))
    contacts = {row["placeId"]: row for row in json.loads((DATA / "mock_apify/contacts_source.json").read_text(encoding="utf-8"))}
    enriched = []
    for place in places[: brief["search"]["maximum_places"]]:
        merged = dict(place)
        merged.update(contacts.get(place["placeId"], {}))
        enriched.append(merged)

    q = brief["qualification"]
    city_state = {tuple(value.split(", ")) for value in q["eligible_city_state"]}
    eligible = []
    for row in enriched:
        email = _select_email(row, q)
        if (
            (row["city"], row["state"]) in city_state
            and row["categoryName"] in set(q["eligible_categories"])
            and float(row["totalScore"]) >= q["minimum_rating"]
            and int(row["reviewsCount"]) >= q["minimum_reviews"]
            and row.get("website")
            and email
        ):
            copy = dict(row)
            copy["selected_email"] = email
            eligible.append(copy)

    winners = {}
    for row in eligible:
        key = _location_key(row)
        priority = (-int(row["reviewsCount"]), -float(row["totalScore"]), row["placeId"])
        if key not in winners or priority < winners[key][0]:
            winners[key] = (priority, row)
    expected = {row["placeId"]: row for _, row in winners.values()}

    place_input = {
        "searchStringsArray": brief["search"]["search_terms"],
        "locationQuery": brief["search"]["location_query"],
        "language": brief["search"]["language"],
        "maxCrawledPlaces": brief["search"]["maximum_places"],
    }
    place_digest = hashlib.sha256(
        ("compass/crawler-google-places\n" + json.dumps(place_input, sort_keys=True, separators=(",", ":"))).encode()
    ).hexdigest()[:12]
    enrich_input = {"datasetId": f"ds_{place_digest}", "maxRequestsPerCrawl": len(enriched)}
    enrich_digest = hashlib.sha256(
        ("compass/enrich-google-maps-dataset-with-contacts\n" + json.dumps(enrich_input, sort_keys=True, separators=(",", ":"))).encode()
    ).hexdigest()[:12]
    return {
        "brief": brief,
        "enriched": enriched,
        "eligible": eligible,
        "expected": expected,
        "place_run": f"run_{place_digest}",
        "place_dataset": f"ds_{place_digest}",
        "enrich_run": f"run_{enrich_digest}",
        "enrich_dataset": f"ds_{enrich_digest}",
    }


def test_qualified_lead_scope(truth):
    _, leads, _ = _submission()
    actual_ids = [row["place_id"] for row in leads if row["place_id"]]
    assert len(actual_ids) == len(set(actual_ids)), "a source place ID appears more than once in the CRM list"
    assert set(actual_ids) == set(truth["expected"]), (
        "the lead set does not exactly match the campaign qualification and location-level deduplication rules"
    )


def test_business_field_fidelity(truth):
    _, leads, _ = _submission()
    checked = 0
    for lead in leads:
        expected = truth["expected"].get(lead["place_id"])
        if expected is None:
            continue
        checked += 1
        required = ["business_name", "address", "city", "state", "category", "rating", "reviews_count", "website"]
        missing = [field for field in required if lead[field] is None]
        assert not missing, f"{lead['place_id']} is missing requested CRM business fields: {missing}"
        assert lead["business_name"].casefold() == expected["title"].casefold()
        assert _canon_key(lead["address"]) == _canon_key(expected["address"])
        assert lead["city"].casefold() == expected["city"].casefold()
        assert lead["state"].casefold() == expected["state"].casefold()
        assert lead["category"].casefold() == expected["categoryName"].casefold()
        assert lead["rating"] == pytest.approx(float(expected["totalScore"]), abs=1e-9)
        assert lead["reviews_count"] == pytest.approx(float(expected["reviewsCount"]), abs=1e-9)
        assert _domain(lead["website"]) == _domain(expected["website"])
    assert checked, "no submitted lead could be tied to a qualified source listing"


@pytest.mark.parametrize("aspect", ["contacts", "location_winners", "shared_domain_branches"])
def test_contact_and_dedup_integrity(truth, aspect):
    _, leads, _ = _submission()
    output = {row["place_id"]: row for row in leads if row["place_id"] in truth["expected"]}
    if aspect == "contacts":
        assert output, "no qualified submitted contacts were available to inspect"
        for place_id, lead in output.items():
            expected = truth["expected"][place_id]
            assert lead["email"] == expected["selected_email"], f"{place_id} does not use the best usable website-domain email"
            expected_phone = expected.get("phone") or next(iter(expected.get("phones") or []), None)
            assert lead["phone"] == expected_phone, f"{place_id} has the wrong primary phone"
            assert lead["linkedin_url"] == expected.get("linkedInUrl"), f"{place_id} has the wrong LinkedIn contact value"
    elif aspect == "location_winners":
        submitted_keys = []
        for place_id in output:
            submitted_keys.append(_location_key(truth["expected"][place_id]))
        assert len(submitted_keys) == len(set(submitted_keys)), "duplicate representations of one physical location remain"
        expected_alt_winners = {place_id for place_id in truth["expected"] if place_id.startswith("plc_alt_")}
        assert expected_alt_winners.issubset(output), "fresher alternate location records were not selected by the winner rule"
    else:
        by_domain = {}
        for place_id, source in truth["expected"].items():
            by_domain.setdefault(_domain(source["website"]), set()).add(place_id)
        multi_branch = {domain: ids for domain, ids in by_domain.items() if domain and len(ids) >= 2}
        assert multi_branch, "fixture calibration error: no qualifying shared-domain branches"
        for domain, expected_ids in multi_branch.items():
            assert expected_ids.issubset(output), f"distinct qualified branches sharing {domain} were collapsed"


def test_scrape_traceability(truth):
    _, _, summary = _submission()
    summary_values = {_canon_key(key): value for key, value in summary.items()}

    def value(*aliases):
        for alias in aliases:
            if _canon_key(alias) in summary_values:
                return summary_values[_canon_key(alias)]
        return None

    assert _text(value("places_actor", "search_actor")) == "compass/crawler-google-places"
    assert _text(value("enrichment_actor", "contact_actor")) == "compass/enrich-google-maps-dataset-with-contacts"
    place_run = _text(value("places_run_id", "search_run_id")) or ""
    place_dataset = _text(value("places_dataset_id", "source_dataset_id")) or ""
    enrich_run = _text(value("enrichment_run_id", "contact_run_id")) or ""
    enrich_dataset = _text(value("enrichment_dataset_id", "contact_dataset_id")) or ""
    assert re.fullmatch(r"run_[0-9a-f]{12}", place_run), "places run reference is missing or not usable"
    assert re.fullmatch(r"ds_[0-9a-f]{12}", place_dataset), "places dataset reference is missing or not usable"
    assert re.fullmatch(r"run_[0-9a-f]{12}", enrich_run), "enrichment run reference is missing or not usable"
    assert re.fullmatch(r"ds_[0-9a-f]{12}", enrich_dataset), "enrichment dataset reference is missing or not usable"
    assert place_run != enrich_run and place_dataset != enrich_dataset, "the two stages must have distinct service references"
    assert _number(value("raw_places_count", "scraped_count")) == len(truth["enriched"])
    assert _number(value("enriched_records_count", "enriched_count")) == len(truth["enriched"])
    assert _number(value("qualified_leads_count", "lead_count")) == len(truth["expected"])
