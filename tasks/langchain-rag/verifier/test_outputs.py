from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
FIXTURE = DATA_ROOT / "solara_support_rag"
PROJECT = RESULTS_ROOT / "solara_support_rag"
SCRIPT = PROJECT / "rag_cli.py"
BATCH_OUTPUT = RESULTS_ROOT / "output.json"
EXPECTED_PATH = Path(__file__).with_name("expected_answers.json")


def canon(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def get_key(mapping: dict, aliases: list[str]):
    wanted = {canon(alias) for alias in aliases}
    for key, value in mapping.items():
        if canon(key) in wanted:
            return value
    return None


def source_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
    if isinstance(value, dict):
        direct = get_key(value, ["source_id", "source", "citation_id", "id"])
        if isinstance(direct, str) and direct.strip():
            return [direct.strip()]
        doc_id = get_key(value, ["doc_id", "document_id", "document"])
        section_id = get_key(value, ["section_id", "section", "section_slug"])
        if isinstance(doc_id, str) and isinstance(section_id, str):
            return [f"{doc_id}#{section_id}"]
        nested = []
        for item in value.values():
            nested.extend(source_ids(item))
        return nested
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(source_ids(item))
        return result
    return []


def normalize_status(value: object, *, answer: str, citations: list[str]) -> str:
    token = canon(value) if value is not None else ""
    if token in {"answered", "answer", "ok", "success", "complete", "grounded"}:
        return "answered"
    if token in {"insufficient", "noevidence", "nomatch", "notfound", "unsupported", "unknown"}:
        return "insufficient"
    text = answer.casefold()
    if not citations and any(phrase in text for phrase in ("no active", "no matching", "insufficient", "not found")):
        return "insufficient"
    return token


def normalize_payload(payload: object) -> tuple[dict[str, dict] | None, str | None]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = get_key(payload, ["answers", "results", "responses", "items"])
    else:
        return None, "top-level JSON must be an object or list"
    if not isinstance(rows, list):
        return None, "could not find an answers/results/responses list"
    normalized: dict[str, dict] = {}
    duplicates: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return None, f"response {index} is not an object"
        query_id = get_key(row, ["query_id", "question_id", "id", "request_id"])
        answer = get_key(row, ["answer", "response", "text", "content"])
        raw_citations = get_key(row, ["citations", "sources", "source_ids", "references"])
        citations = list(dict.fromkeys(source_ids(raw_citations)))
        if not isinstance(query_id, str) or not query_id.strip():
            return None, f"response {index} has no usable query ID"
        if not isinstance(answer, str):
            answer = "" if answer is None else str(answer)
        query_id = query_id.strip()
        if query_id in normalized:
            duplicates.append(query_id)
        normalized[query_id] = {
            "answer": answer.strip(),
            "citations": citations,
            "status": normalize_status(
                get_key(row, ["status", "state", "result_status", "outcome"]),
                answer=answer,
                citations=citations,
            ),
        }
    if duplicates:
        return None, f"duplicate query IDs: {sorted(set(duplicates))[:5]}"
    return normalized, None


def read_answers(path: Path) -> tuple[dict[str, dict] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"answer file is unavailable or invalid: {exc}"
    return normalize_payload(payload)


def run_cli(arguments: list[str], *, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=PROJECT if PROJECT.is_dir() else RESULTS_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


@dataclass
class FreshRun:
    build: subprocess.CompletedProcess[str]
    answer: subprocess.CompletedProcess[str]
    output: Path
    index: Path


@pytest.fixture(scope="module")
def fresh_run(tmp_path_factory) -> FreshRun:
    run_root = tmp_path_factory.mktemp("fresh-rag")
    index = run_root / "index"
    output = run_root / "answers.json"
    if not SCRIPT.is_file():
        missing = subprocess.CompletedProcess([], 127, "", "rag_cli.py is missing")
        return FreshRun(missing, missing, output, index)
    build = run_cli(
        [
            "build",
            "--corpus",
            str(FIXTURE / "knowledge_base"),
            "--catalog",
            str(FIXTURE / "section_catalog.csv"),
            "--index",
            str(index),
        ]
    )
    if build.returncode == 0:
        answer = run_cli(
            [
                "answer",
                "--index",
                str(index),
                "--queries",
                str(FIXTURE / "batch_queries.jsonl"),
                "--output",
                str(output),
            ]
        )
    else:
        answer = subprocess.CompletedProcess([], 125, "", "answer skipped because build failed")
    return FreshRun(build, answer, output, index)


def load_expected() -> dict[str, dict]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def load_queries() -> dict[str, dict]:
    return {
        row["query_id"]: row
        for row in (
            json.loads(line)
            for line in (FIXTURE / "batch_queries.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def representative_ids() -> list[str]:
    expected = load_expected()
    chosen = [f"Q{scope:02d}-1" for scope in range(1, 13)]
    seen_topics = {expected[query_id]["source_id"].split("#", 1)[1] for query_id in chosen}
    for query_id in sorted(expected):
        source_id = expected[query_id].get("source_id")
        if not source_id:
            continue
        topic = source_id.split("#", 1)[1]
        if topic not in seen_topics:
            chosen.append(query_id)
            seen_topics.add(topic)
    return chosen


REPRESENTATIVE_IDS = representative_ids()


def both_outputs(fresh_run: FreshRun) -> list[tuple[str, dict[str, dict]]]:
    assert fresh_run.build.returncode == 0, f"fresh index build failed: {fresh_run.build.stderr[-1200:]}"
    assert fresh_run.answer.returncode == 0, f"fresh batch answer failed: {fresh_run.answer.stderr[-1200:]}"
    sample, sample_error = read_answers(BATCH_OUTPUT)
    runtime, runtime_error = read_answers(fresh_run.output)
    assert sample_error is None and sample is not None, f"submitted batch output is unusable: {sample_error}"
    assert runtime_error is None and runtime is not None, f"fresh runtime output is unusable: {runtime_error}"
    return [("submitted", sample), ("fresh runtime", runtime)]


def test_artifact_and_batch_output_are_usable(fresh_run):
    """The runnable project, persisted index, README, and batch answer artifact are usable."""
    assert PROJECT.is_dir(), "the runnable project is missing from /root/results/solara_support_rag"
    assert SCRIPT.is_file(), "rag_cli.py is missing from the runnable project"
    readme = PROJECT / "README.md"
    assert readme.is_file() and readme.read_text(encoding="utf-8").strip(), "the project README is missing or empty"
    default_index = PROJECT / "index"
    assert default_index.is_dir() and any(path.is_file() for path in default_index.rglob("*")), (
        "the requested default persistent index is empty or missing"
    )
    answers, error = read_answers(BATCH_OUTPUT)
    assert error is None and answers is not None, error
    help_run = run_cli(["--help"], timeout=10)
    assert help_run.returncode == 0 and "build" in help_run.stdout and "answer" in help_run.stdout, (
        "rag_cli.py does not expose the documented build and answer commands"
    )
    assert fresh_run.build.returncode == 0 and fresh_run.answer.returncode == 0, (
        f"the project cannot reproduce its batch result: build={fresh_run.build.stderr[-500:]}, "
        f"answer={fresh_run.answer.stderr[-500:]}"
    )


def test_index_reloads_without_source_corpus(tmp_path):
    """A newly built index answers correctly after its Markdown and catalog are removed."""
    assert SCRIPT.is_file(), "rag_cli.py is missing"
    source_root = tmp_path / "fixture"
    corpus = source_root / "corpus"
    corpus.mkdir(parents=True)
    active_doc = "NOVA-7-EU-OPS-ACT"
    retired_doc = "NOVA-7-EU-OPS-RET"
    active_source = f"{active_doc}#thermal-failover"
    retired_source = f"{retired_doc}#thermal-failover"
    (corpus / "active.md").write_text(
        "# Current Nova manual\n\n## thermal-failover — Thermal failover\n\n"
        "For Nova 7 EU operators, thermal saturation requires a controlled failover.\n"
        "Operational directive: At 67% thermal saturation, shift to amber relay and page Team Quartz.\n",
        encoding="utf-8",
    )
    (corpus / "retired.md").write_text(
        "# Retired Nova manual\n\n## thermal-failover — Thermal failover\n\n"
        "Operational directive: At 94% thermal saturation, power-cycle every relay.\n",
        encoding="utf-8",
    )
    catalog = source_root / "catalog.csv"
    fields = [
        "source_id", "doc_id", "section_id", "section_title", "product", "release", "region",
        "audience", "status", "effective_date", "source_file",
    ]
    with catalog.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for doc_id, status, filename in ((active_doc, "active", "active.md"), (retired_doc, "retired", "retired.md")):
            writer.writerow(
                {
                    "source_id": active_source if status == "active" else retired_source,
                    "doc_id": doc_id,
                    "section_id": "thermal-failover",
                    "section_title": "Thermal failover",
                    "product": "Nova", "release": "7", "region": "eu", "audience": "operator",
                    "status": status, "effective_date": "2026-02-01", "source_file": f"corpus/{filename}",
                }
            )
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        json.dumps(
            {
                "query_id": "DYN-1",
                "question": "When does thermal saturation require failover, which relay, and who is paged?",
                "filters": {"product": "Nova", "release": "7", "region": "eu", "audience": "operator", "status": "active"},
                "top_k": 2,
            }
        ) + "\n",
        encoding="utf-8",
    )
    index = tmp_path / "persisted-index"
    output = tmp_path / "dynamic-output.json"
    built = run_cli(["build", "--corpus", str(corpus), "--catalog", str(catalog), "--index", str(index)])
    assert built.returncode == 0 and index.is_dir(), f"dynamic index build failed: {built.stderr[-800:]}"
    source_root.rename(tmp_path / "source-unavailable")
    answered = run_cli(["answer", "--index", str(index), "--queries", str(queries), "--output", str(output)])
    assert answered.returncode == 0, f"saved index could not answer after source removal: {answered.stderr[-800:]}"
    rows, error = read_answers(output)
    assert error is None and rows is not None and "DYN-1" in rows, error
    row = rows["DYN-1"]
    normalized_answer = canon(row["answer"])
    assert row["status"] == "answered" and active_source in row["citations"], (
        "the reloaded index did not retrieve the active dynamically indexed section"
    )
    assert all(token in normalized_answer for token in ("67", "amberrelay", "teamquartz")), (
        "the reloaded index did not ground the dynamic answer in the active directive"
    )
    assert retired_source not in row["citations"], "the retired dynamic procedure leaked into the answer"


@pytest.mark.parametrize("query_id", REPRESENTATIVE_IDS)
def test_retrieval_citations_match_relevant_sections(fresh_run, query_id):
    """Representative questions cite their exact answer-bearing section in both outputs."""
    expected = load_expected()[query_id]
    for label, rows in both_outputs(fresh_run):
        assert query_id in rows, f"{label} output omits {query_id}"
        row = rows[query_id]
        assert expected["source_id"] in row["citations"], (
            f"{label} {query_id} does not cite its relevant answer-bearing section; got {row['citations']}"
        )


def test_metadata_scope_and_insufficient_handling(fresh_run):
    """Every citation matches all query filters, while unsupported scopes stay unanswered."""
    queries = load_queries()
    catalog_rows = list(csv.DictReader((FIXTURE / "section_catalog.csv").read_text(encoding="utf-8").splitlines()))
    by_source = {row["source_id"]: row for row in catalog_rows}
    expected = load_expected()
    for label, rows in both_outputs(fresh_run):
        defects = []
        for query_id, exp in expected.items():
            row = rows.get(query_id)
            if row is None:
                continue
            if exp["status"] == "insufficient":
                if row["status"] != "insufficient" or row["citations"]:
                    defects.append(f"{query_id} should be insufficient with no citation")
                continue
            if row["status"] != "answered":
                defects.append(f"{query_id} should be answered")
            filters = {key: str(value).casefold() for key, value in queries[query_id]["filters"].items()}
            for citation in row["citations"]:
                source = by_source.get(citation)
                if source is None:
                    defects.append(f"{query_id} cites unknown source {citation}")
                    continue
                if any(str(source.get(key, "")).casefold() != value for key, value in filters.items()):
                    defects.append(f"{query_id} cites out-of-scope source {citation}")
        assert not defects, f"{label} scope defects: {defects[:8]}"


def test_batch_query_coverage(fresh_run):
    """Both artifacts contain exactly one usable response for every bundled query."""
    expected_ids = set(load_expected())
    for label, rows in both_outputs(fresh_run):
        assert set(rows) == expected_ids, (
            f"{label} query coverage differs: missing={sorted(expected_ids - set(rows))[:8]}, "
            f"unexpected={sorted(set(rows) - expected_ids)[:8]}"
        )
        empty = [query_id for query_id, row in rows.items() if not row["answer"]]
        assert not empty, f"{label} contains empty answers: {empty[:8]}"


@pytest.mark.parametrize("query_id", REPRESENTATIVE_IDS)
def test_grounded_answer_facts(fresh_run, query_id):
    """Representative answers preserve every material fact in the cited directive."""
    expected = load_expected()[query_id]
    for label, rows in both_outputs(fresh_run):
        answer = canon(rows[query_id]["answer"])
        missing = []
        for alternatives in expected["required_groups"]:
            if not any(canon(candidate) in answer for candidate in alternatives):
                missing.append(alternatives)
        assert not missing, f"{label} {query_id} omits material directive facts: {missing}"
