from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "research_ideas.json"


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _lookup(mapping: Any, aliases: set[str]) -> Any:
    """Find a semantically named field recursively without fixing nesting or key style."""
    targets = {_norm_key(alias) for alias in aliases}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            if _norm_key(str(key)) in targets:
                return value
        for value in mapping.values():
            found = _lookup(value, aliases)
            if found is not None:
                return found
    return None


def _load_output() -> dict:
    assert OUTPUT.is_file(), f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"research portfolio is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "research portfolio must be a JSON object"
    return payload


def _candidate_list(payload: dict) -> list:
    value = _lookup(payload, {"candidate_portfolio", "candidates", "candidate_ideas", "ideas", "idea_portfolio"})
    return value if isinstance(value, list) else []


def _shortlist(payload: dict) -> list:
    value = _lookup(payload, {
        "ranked_shortlist", "ranked_top_3", "shortlist", "top_ideas", "top_three", "recommendations",
    })
    return value if isinstance(value, list) else []


def _winner(payload: dict) -> Any:
    return _lookup(payload, {"winner", "selected_idea", "top_choice", "chosen_direction", "selected_direction"})


def _identity(item: Any) -> str:
    if isinstance(item, str):
        return _norm_key(item)
    if isinstance(item, dict):
        for aliases in (
            {"candidate_id", "idea_id", "direction_id", "id"},
            {"title", "name", "direction", "idea"},
        ):
            value = _lookup(item, aliases)
            if isinstance(value, (str, int)) and str(value).strip():
                return _norm_key(str(value))
    return ""


def _resolved_entries(payload: dict, items: list) -> list[dict]:
    candidates = [item for item in _candidate_list(payload) if isinstance(item, dict)]
    by_identity = {_identity(item): item for item in candidates if _identity(item)}
    resolved: list[dict] = []
    for item in items:
        identity = _identity(item)
        base = by_identity.get(identity, {})
        if isinstance(item, dict):
            resolved.append({**base, **item})
        elif base:
            resolved.append(base)
        else:
            resolved.append({"reference": item})
    return resolved


def _winner_entry(payload: dict) -> dict:
    winner = _winner(payload)
    if isinstance(winner, dict):
        resolved = _resolved_entries(payload, [winner])
        return resolved[0] if resolved else winner
    resolved = _resolved_entries(payload, [winner])
    return resolved[0] if resolved else {}


def _refs(item: Any) -> set[str]:
    text = json.dumps(item, ensure_ascii=False)
    return set(re.findall(r"\b(?:OBS-\d{3}|PP-\d{2}|CHG-\d{2})\b", text, flags=re.IGNORECASE))


def _all_valid_refs() -> tuple[set[str], set[str], set[str]]:
    observations = {
        json.loads(line)["observation_id"]
        for line in (DATA / "observations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    prior = {row["project_id"] for row in json.loads((DATA / "prior_projects.json").read_text(encoding="utf-8"))}
    changes = {row["change_id"] for row in json.loads((DATA / "capability_changes.json").read_text(encoding="utf-8"))}
    return observations, prior, changes


def _find_number(item: Any, aliases: set[str]) -> float | None:
    value = _lookup(item, aliases)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group())
    return None


def _find_bool(item: Any, aliases: set[str]) -> bool | None:
    value = _lookup(item, aliases)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"false", "no", "none", "offline", "not used", "disabled"}:
            return False
        if normalized in {"true", "yes", "used", "enabled"}:
            return True
    return None


def _find_list(item: Any, aliases: set[str]) -> list:
    value = _lookup(item, aliases)
    return value if isinstance(value, list) else []


def test_artifact_scope_and_selection_structure():
    """The portfolio exposes the requested divergence, top three, and refined winner."""
    payload = _load_output()
    candidates = _candidate_list(payload)
    shortlist = _shortlist(payload)
    assert 12 <= len(candidates) <= 15, (
        f"found {len(candidates)} candidates; the user asked to explore 12-15 before converging"
    )
    candidate_ids = [_identity(item) for item in candidates]
    assert all(candidate_ids) and len(set(candidate_ids)) == len(candidate_ids), (
        "candidate ideas need stable, distinct identities so the decision trail is usable"
    )
    assert len(shortlist) == 3, f"found {len(shortlist)} shortlisted ideas; the requested decision set has three"
    shortlist_ids = [_identity(item) for item in shortlist]
    assert all(shortlist_ids) and len(set(shortlist_ids)) == 3, "the shortlist contains a missing or duplicate direction"
    assert set(shortlist_ids) <= set(candidate_ids), "every shortlisted direction must come from the explored candidate portfolio"
    winner = _winner_entry(payload)
    assert winner and _identity(winner) in set(shortlist_ids), "the refined winner must be one of the ranked top three"
    pitch = _lookup(winner, {"pitch", "two_sentence_pitch", "value_proposition"})
    experiments = _find_list(winner, {"validation_experiments", "experiments", "tests", "studies"})
    objection = _lookup(winner, {"strongest_objection", "hardest_objection", "objection", "skeptic_objection"})
    response = _lookup(winner, {"response", "objection_response", "rebuttal", "answer"})
    if isinstance(objection, dict):
        response = response or _lookup(objection, {"response", "objection_response", "rebuttal", "answer"})
        objection = _lookup(objection, {"objection", "concern", "challenge", "claim"})
    pilot = _lookup(winner, {
        "pilot", "two_week_pilot", "two_week_offline_pilot", "pilot_plan", "feasibility_pilot",
    })
    assert (
        isinstance(pitch, str) and pitch.strip()
    ) or (
        isinstance(pitch, dict) and len([value for value in pitch.values() if isinstance(value, str) and value.strip()]) >= 2
    ), "the winner is missing its requested two-part pitch"
    assert len(experiments) >= 2, "the winner needs multiple validation experiments, not a single vague activity"
    assert isinstance(objection, str) and objection.strip(), "the winner is missing the hardest objection"
    assert isinstance(response, str) and response.strip(), "the winner is missing a response to the objection"
    assert pilot is not None, "the winner is missing the requested two-week offline pilot"


def test_shortlist_evidence_references_are_valid():
    """Shortlist traceability uses real packet IDs and collectively covers prior work and new capabilities."""
    payload = _load_output()
    shortlist = _resolved_entries(payload, _shortlist(payload))
    observation_ids, prior_ids, change_ids = _all_valid_refs()
    valid = observation_ids | prior_ids | change_ids
    combined: set[str] = set()
    for index, entry in enumerate(shortlist, start=1):
        refs = {ref.upper() for ref in _refs(entry)}
        assert refs, f"shortlist entry {index} has no traceable packet references"
        unknown = refs - valid
        assert not unknown, f"shortlist entry {index} invents packet references: {sorted(unknown)}"
        assert refs & observation_ids, f"shortlist entry {index} is not traceable to any supplied observation"
        combined |= refs
    assert combined & prior_ids, "the shortlist never connects its judgment to prior project evidence"
    assert combined & change_ids, "the shortlist never connects its judgment to newly available or unavailable capabilities"


def test_winner_pilot_respects_frozen_constraints():
    """The stated pilot stays within the two-week offline envelope and uses only available assets."""
    payload = _load_output()
    winner = _winner_entry(payload)
    pilot = _lookup(winner, {"pilot", "two_week_pilot", "two_week_offline_pilot", "pilot_plan", "feasibility_pilot"})
    assert pilot is not None, "cannot assess feasibility because the winner has no pilot"
    brief = json.loads((DATA / "project_brief.json").read_text(encoding="utf-8"))
    limits = brief["pilot_constraints"]
    duration = _find_number(pilot, {"duration_days", "days", "length_days", "pilot_days", "duration"})
    if duration is None and isinstance(pilot, str):
        match = re.search(r"\b(\d+)\s*[- ]?day", pilot.lower())
        if match:
            duration = float(match.group(1))
        elif "two-week" in pilot.lower() or "two week" in pilot.lower():
            duration = 14.0
    assert duration is not None and 0 < duration <= limits["duration_days_max"], (
        "the pilot does not state a duration within the 14-day limit"
    )
    numeric_limits = [
        ({"engineering_person_days", "engineer_days", "engineering_days"}, "engineering_person_days_max"),
        ({"security_reviewer_hours", "security_hours", "reviewer_hours"}, "security_reviewer_hours_max"),
        ({"gpu_hours", "compute_gpu_hours", "gpu_budget_hours"}, "gpu_hours_max"),
    ]
    for aliases, limit_key in numeric_limits:
        value = _find_number(pilot, aliases)
        if value is not None:
            assert 0 <= value <= limits[limit_key], f"pilot exceeds {limit_key}: {value} > {limits[limit_key]}"
    pilot_text = json.dumps(pilot, ensure_ascii=False).lower()
    network = _find_bool(pilot, {"network_access", "network", "internet_access", "remote_access"})
    production = _find_bool(pilot, {"production_traffic", "production", "live_traffic"})
    external = _find_bool(pilot, {"external_participants", "external_users", "outside_participants"})
    assert network is not True, "the pilot explicitly enables network access despite the offline constraint"
    assert network is False or "offline" in pilot_text or "no network" in pilot_text, (
        "the requested pilot is offline, but the plan does not preserve that boundary"
    )
    assert production is not True, "the pilot relies on production traffic that the packet marks unavailable"
    assert external is not True, "the pilot relies on external participants that the packet marks unavailable"
    available_assets = set(brief["available_asset_ids"])
    used_assets = set(re.findall(r"ASSET-[A-Z0-9-]+", json.dumps(pilot).upper()))
    assert used_assets, "the pilot does not identify any of the packet's available offline assets"
    assert used_assets <= available_assets, f"the pilot names unavailable assets: {sorted(used_assets - available_assets)}"
