from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULT_ROOT = Path(os.environ.get("TASK_RESULT_ROOT", "/root/results"))
PROJECT = RESULT_ROOT / "research_app"
SOURCE_PROJECT = DATA_ROOT / "research_app"
INDEX_PATH = SOURCE_PROJECT / "mock/search_index.json"
SERVER_PATH = SOURCE_PROJECT / "mock/mock_server.py"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def mock_service(*, trailing_slash: bool = False):
    port = _free_port()
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "requests.jsonl"
        env = os.environ.copy()
        env["MOCK_LOG_PATH"] = str(log_path)
        process = subprocess.Popen(
            [sys.executable, str(SERVER_PATH), "--index", str(INDEX_PATH), "--port", str(port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout is not None
            ready = process.stdout.readline().strip()
            assert ready == str(port), "offline mock did not start"
            suffix = "/" if trailing_slash else ""
            yield f"http://127.0.0.1:{port}{suffix}", log_path
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


def run_cli(query: str, base_url: str, key: str = "fc-test-canary-7391") -> dict:
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(PROJECT / "src"),
        "FIRECRAWL_API_URL": base_url,
        "FIRECRAWL_API_KEY": key,
    })
    completed = subprocess.run(
        [sys.executable, "-m", "research_app.cli", query],
        cwd=PROJECT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert completed.returncode == 0, f"CLI failed: {completed.stderr[:500]}"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"CLI did not emit one JSON object: {completed.stdout[:500]}") from exc
    assert isinstance(payload, dict), "CLI output must be a JSON object"
    return payload


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def assert_contract(payload: dict, query: str) -> None:
    assert payload.get("query") == query, "output must identify the submitted query"
    results = payload.get("results")
    assert isinstance(results, list) and len(results) <= 3, "results must be a shortlist of at most three items"
    for row in results:
        assert isinstance(row, dict), "each result must be an object"
        assert all(key in row for key in ("title", "url", "snippet", "content", "error")), "result fields do not match the documented CLI contract"
        assert isinstance(row["title"], str) and isinstance(row["url"], str) and isinstance(row["snippet"], str)
        assert row["content"] is None or isinstance(row["content"], str)
        assert row["error"] is None or isinstance(row["error"], str)


def test_artifact_and_cli_contract():
    assert PROJECT.is_dir(), "completed project is missing at /root/results/research_app"
    assert (PROJECT / "src/research_app/research.py").is_file(), "research integration source is missing"
    with mock_service() as (base_url, _):
        payload = run_cli("urban cooling", base_url)
    assert_contract(payload, "urban cooling")
    assert len(payload["results"]) == 3, "a normal query should return three hydrated candidates"


def test_discovery_precedes_selective_hydration():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    expected = [r["url"] for r in index["queries"]["battery recycling"] if r["url"].startswith(("http://", "https://"))][:3]
    with mock_service() as (base_url, log_path):
        run_cli("battery recycling", base_url)
        events = read_log(log_path)
    assert [event["path"] for event in events] == ["/v1/search", "/v1/scrape", "/v1/scrape", "/v1/scrape"], "integration must search once before selectively scraping three pages"
    assert events[0]["body"] == {"query": "battery recycling", "limit": 5}, "search request does not match the discovery contract"
    scraped = [event["body"].get("url") for event in events[1:]]
    assert scraped == expected, "hydration must target the first three usable ranked URLs only"
    assert all(event["body"].get("formats") == ["markdown"] for event in events[1:]), "scrape requests must ask for markdown"


def test_ranking_and_individual_failure_isolation():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    source_rows = [r for r in index["queries"]["battery recycling"] if r["url"].startswith(("http://", "https://"))][:3]
    with mock_service() as (base_url, _):
        payload = run_cli("battery recycling", base_url)
    assert_contract(payload, "battery recycling")
    results = payload["results"]
    assert [row["url"] for row in results] == [row["url"] for row in source_rows], "result order must preserve discovery ranking after unusable URLs are filtered"
    for actual, source in zip(results, source_rows):
        assert actual["title"] == source["title"] and actual["snippet"] == source["description"], "discovery metadata changed during hydration"
    assert results[0]["content"] is None and results[0]["error"], "failed page must be retained with a useful error"
    assert all(row["content"] and row["error"] is None for row in results[1:]), "one failed page must not block later successful hydration"


def test_runtime_configuration_and_credential_safety():
    canary = "fc-test-canary-7391"
    with mock_service(trailing_slash=True) as (base_url, log_path):
        payload = run_cli("battery recycling", base_url, canary)
        events = read_log(log_path)
    assert events and all(event["authorization"] == f"Bearer {canary}" for event in events), "configured credential must be sent as the bearer token"
    assert canary not in json.dumps(payload), "credential leaked into CLI output"
    forbidden = (canary, "fc-live-", "fc-secret-")
    for path in PROJECT.rglob("*"):
        if path.is_file() and path.stat().st_size < 1_000_000:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not any(marker in text for marker in forbidden), f"credential-like value is committed in {path.relative_to(PROJECT)}"
