import json
import os
import subprocess
import sys
from pathlib import Path

DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))

def expected(case):
    site = json.loads((DATA / case / "site_data.json").read_text())
    req = json.loads((DATA / case / "request.json").read_text())
    return sorted(
        [r for r in site["records"] if r["category"] == req["target_category"] and r["status"] != req["exclude_status"]],
        key=lambda r: r["id"],
    )

def normalize(payload):
    if isinstance(payload, dict):
        for key in ("records", "items", "results", "controls"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    assert isinstance(payload, list), "output must be a JSON record list or an object containing one"
    rows = []
    for row in payload:
        assert isinstance(row, dict), "each output record must be an object"
        aliases = {str(k).lower().replace("_", ""): v for k, v in row.items()}
        rows.append({
            "id": aliases.get("id") or aliases.get("controlid"),
            "name": aliases.get("name") or aliases.get("title"),
            "category": aliases.get("category") or aliases.get("type"),
            "status": aliases.get("status") or aliases.get("state"),
            "risk": aliases.get("risk") or aliases.get("risklevel"),
        })
    return sorted(rows, key=lambda r: str(r["id"]))

def run_case(case, output):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(DATA / "starter") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(RESULTS / "collector.py"), "--case", str(DATA / case), "--output", str(output)],
        text=True, capture_output=True, timeout=20, env=env,
    )

def test_artifact_usability(tmp_path):
    assert (RESULTS / "collector.py").is_file(), "completed collector.py is missing"
    assert (RESULTS / "output.json").is_file(), "primary output.json is missing"
    normalize(json.loads((RESULTS / "output.json").read_text()))
    probe = tmp_path / "probe.json"
    proc = run_case("primary", probe)
    assert proc.returncode == 0, f"documented CLI failed: {proc.stderr}"
    assert probe.is_file(), "CLI did not write its requested output path"

def test_primary_results():
    actual = normalize(json.loads((RESULTS / "output.json").read_text()))
    want = expected("primary")
    assert actual == want, "primary output omits, duplicates, includes ineligible, or alters catalog controls"

def test_stateful_interactive_flow(tmp_path):
    output = tmp_path / "flow.json"
    proc = run_case("primary", output)
    assert proc.returncode == 0, proc.stderr
    trace = json.loads(output.with_suffix(".trace.json").read_text())
    assert trace and trace[0].get("type", trace[0].get("event", "")) != "interact"
    assert trace[0].get("url") and (trace[0].get("event") == "scrape" or trace[0].get("type") == "scrape" or trace[0].get("endpoint") == "scrape"), "workflow must begin with scrape"
    interactions = [e for e in trace if e.get("endpoint") == "interact"]
    assert interactions, "collector never escalated to interact"
    sessions = {e.get("session_id") for e in trace}
    assert len(sessions) == 1 and None not in sessions, "filtering and pagination must preserve one browser session"
    actions = [a for e in interactions for a in e.get("actions", [])]
    assert any(a.get("type") == "fill" for a in actions) and any(a.get("selector") == "#apply" for a in actions), "requested category filter was not applied"
    extracts = sum(a.get("type") == "extract" for a in actions)
    nexts = sum(a.get("selector") == "button.next" for a in actions)
    page_size = json.loads((DATA / "primary" / "site_data.json").read_text())["page_size"]
    eligible_and_deprecated = [r for r in json.loads((DATA / "primary" / "site_data.json").read_text())["records"] if r["category"] == "security"]
    pages = (len(eligible_and_deprecated) + page_size - 1) // page_size
    assert extracts >= pages and nexts >= pages - 1, "collector did not extract and paginate through the complete filtered result set"

def test_regression_case(tmp_path):
    output = tmp_path / "regression.json"
    proc = run_case("regression", output)
    assert proc.returncode == 0, f"collector is not reusable for the bundled second case: {proc.stderr}"
    assert normalize(json.loads(output.read_text())) == expected("regression"), "regression case results are incomplete, hard-coded, or incorrect"
