from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest


OUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/output.json"))
EXPECTED_IDS = {f"RMT-{number}" for number in range(241, 247)}
SNAPSHOT_ID = "remotion-mirror-2026-08-15"
BASE = "https://www.remotion.dev/docs"
EXPECTED_SOURCES = {
    "RMT-241": {f"{BASE}/use-video-config"},
    "RMT-242": {f"{BASE}/sequence"},
    "RMT-243": {f"{BASE}/delay-render", f"{BASE}/cancel-render"},
    "RMT-244": {f"{BASE}/lambda/rendermediaonlambda", f"{BASE}/lambda/getrenderprogress"},
    "RMT-245": {f"{BASE}/offthreadvideo"},
    "RMT-246": {f"{BASE}/staticfile"},
}


def _norm_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _canonical_url(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("url", value.get("href", value.get("source", "")))
    raw = str(value).strip()
    parts = urlsplit(raw)
    path = parts.path[:-3] if parts.path.endswith(".md") else parts.path
    path = path.rstrip("/")
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, "", ""))


def _read_payload() -> tuple[dict | None, str | None]:
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "top-level JSON value is not an object"
    return value, None


def _pick(record: dict, names: tuple[str, ...], default: object = None) -> object:
    for name in names:
        if name in record:
            return record[name]
    return default


def _normalize_cases(payload: dict | None) -> dict[str, dict] | None:
    if payload is None:
        return None
    collection = _pick(payload, ("cases", "responses", "tickets", "items"))
    if isinstance(collection, dict):
        rows = []
        for key, value in collection.items():
            row = dict(value) if isinstance(value, dict) else {"answer": value}
            row.setdefault("case_id", key)
            rows.append(row)
    elif isinstance(collection, list):
        rows = collection
    else:
        return None
    normalized: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        case_id = str(_pick(row, ("case_id", "id", "ticket_id", "case"), "")).upper().strip()
        answer = _pick(row, ("answer", "guidance", "response", "resolution"), "")
        sources = _pick(row, ("sources", "pages", "citations", "urls"), [])
        caveats = _pick(row, ("caveats", "limitations", "notes"), [])
        if isinstance(sources, (str, dict)):
            sources = [sources]
        if isinstance(caveats, str):
            caveats = [caveats]
        if not isinstance(sources, list) or not isinstance(caveats, list):
            return None
        if case_id in normalized:
            normalized[case_id]["duplicate"] = True
        else:
            normalized[case_id] = {
                "answer": str(answer),
                "sources": {_canonical_url(source) for source in sources if str(source).strip()},
                "caveats": [str(item) for item in caveats],
                "duplicate": False,
            }
    return normalized


def _submission_or_skip() -> tuple[dict, dict[str, dict]]:
    payload, error = _read_payload()
    cases = _normalize_cases(payload)
    if error or cases is None:
        pytest.skip("artifact could not be normalized; the root representation failure is assigned to artifact_scope")
    assert payload is not None
    return payload, cases


def _combined(case: dict) -> str:
    return _norm_text(case["answer"] + " " + " ".join(case["caveats"]))


def _has(text: str, phrase: str) -> bool:
    return _norm_text(phrase) in text


def test_artifact_scope():
    payload, error = _read_payload()
    assert OUT.is_file(), "the requested output.json is missing"
    assert error is None and payload is not None, f"output.json is not readable UTF-8 JSON: {error}"
    cases = _normalize_cases(payload)
    assert cases is not None, "the handoff does not expose a recognizable case collection"
    snapshot = _pick(payload, ("snapshot_id", "snapshot", "documentation_snapshot"), "")
    assert str(snapshot) == SNAPSHOT_ID, "the handoff does not identify the supplied documentation snapshot"
    assert set(cases) == EXPECTED_IDS, f"queued case coverage differs: expected {sorted(EXPECTED_IDS)}, got {sorted(cases)}"
    for case_id, case in cases.items():
        assert not case["duplicate"], f"{case_id} appears more than once"
        assert len(case["answer"].strip()) >= 35, f"{case_id} has no substantive support answer"
        assert case["sources"], f"{case_id} has no supporting page"


@pytest.mark.parametrize("case_id", sorted(EXPECTED_IDS))
def test_page_discovery(case_id: str):
    _, cases = _submission_or_skip()
    if case_id not in cases:
        pytest.skip("missing case is scored by artifact_scope, not duplicated here")
    assert cases[case_id]["sources"] == EXPECTED_SOURCES[case_id], (
        f"{case_id} does not use its minimal canonical supporting page set: {sorted(cases[case_id]['sources'])}"
    )


@pytest.mark.parametrize("case_id", sorted(EXPECTED_IDS))
def test_guidance_accuracy(case_id: str):
    _, cases = _submission_or_skip()
    if case_id not in cases:
        pytest.skip("missing case is scored by artifact_scope, not duplicated here")
    text = _combined(cases[case_id])
    if case_id == "RMT-241":
        for term in ("useVideoConfig", "width", "height", "fps", "durationInFrames", "composition"):
            assert _has(text, term), f"RMT-241 omits documented fact: {term}"
        assert any(_has(text, phrase) for phrase in ("React component", "inside React", "within React")), (
            "RMT-241 does not state that useVideoConfig is a React hook"
        )
    elif case_id == "RMT-242":
        assert _has(text, "Sequence") and _has(text, "global frame 90"), "RMT-242 does not anchor the Sequence at frame 90"
        assert re.search(r"local frame 0|returns? 0", text), "RMT-242 gives no correct local frame at global frame 90"
        assert re.search(r"0 (through|to) 59", text), "RMT-242 does not state the 60-frame local mounted range"
        assert any(_has(text, phrase) for phrase in ("hidden before", "hides the title before", "not mounted before", "starts at global frame 90")), "RMT-242 misses pre-start behavior"
    elif case_id == "RMT-243":
        for term in ("delayRender", "handle", "continueRender", "success", "cancelRender"):
            assert _has(text, term), f"RMT-243 omits async render state: {term}"
        assert any(_has(text, phrase) for phrase in ("rejection", "on failure", "on error", "if it fails")), (
            "RMT-243 does not cover the asynchronous failure path"
        )
        assert any(_has(text, phrase) for phrase in ("same handle", "that handle", "the handle")), "RMT-243 does not connect continueRender to the delay handle"
        assert any(_has(text, phrase) for phrase in ("must not be called after", "only after success", "instead of continuing")), "RMT-243 could still release a failed preload"
    elif case_id == "RMT-244":
        for term in ("renderId", "bucketName", "getRenderProgress", "done", "outputFile"):
            assert _has(text, term), f"RMT-244 omits Lambda render fact: {term}"
        assert _has(text, "region") and _has(text, "same"), "RMT-244 misses the same-region constraint"
        assert _has(text, "fatalErrorEncountered") or _has(text, "errors"), "RMT-244 does not require checking render errors"
        assert any(_has(text, phrase) for phrase in ("do not construct", "rather than constructing", "not completion")), "RMT-244 does not correct the unsafe worker assumption"
    elif case_id == "RMT-245":
        assert _has(text, "pauseWhenBuffering") and _has(text, "OffthreadVideo"), "RMT-245 does not name the relevant behavior"
        assert _has(text, "Player") or _has(text, "Studio"), "RMT-245 omits interactive playback context"
        assert any(_has(text, phrase) for phrase in ("no effect during", "does not affect", "no effect in")), "RMT-245 incorrectly leaves render behavior ambiguous"
        assert _has(text, "render") and _has(text, "Chrome") and _has(text, "Edge"), "RMT-245 misses render or browser scope"
    elif case_id == "RMT-246":
        for term in ("staticFile", "team intro.mp4", "public", "base path"):
            assert _has(text, term), f"RMT-246 omits asset guidance: {term}"
        assert any(_has(text, phrase) for phrase in ("URL encodes", "URL encode", "encodes the space")), "RMT-246 does not address the filename space"
        assert any(_has(text, phrase) for phrase in ("relative to public", "do not include public", "without public")), "RMT-246 leaves the staticFile argument incorrect"
