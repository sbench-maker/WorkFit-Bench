from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


OUTPUT_PATH = Path(
    os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/migration_note.md")
).resolve()
DATA_DIR = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data")).resolve()


def output_text() -> str:
    if not OUTPUT_PATH.is_file():
        pytest.fail("/root/results/migration_note.md is missing; the engineer has no migration handoff")
    try:
        return OUTPUT_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"migration_note.md is not readable UTF-8 text: {exc}")


def normalized(text: str) -> str:
    text = text.replace("→", " becomes ").replace("⇒", " becomes ")
    return re.sub(r"\s+", " ", text).strip()


def compact_code(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def fenced_code(text: str) -> str:
    blocks = re.findall(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", text, flags=re.DOTALL)
    return "\n".join(blocks)


def current_chunk_ids() -> set[str]:
    rows = [json.loads(line) for line in (DATA_DIR / "document_chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    return {
        row["chunk_id"]
        for row in rows
        if row["library_id"] == "/northstar-labs/fluxcache-python/v4.2.0"
    }


def test_official_versioned_library_selection():
    text = normalized(output_text())
    lower = text.lower()
    exact_id = "/northstar-labs/fluxcache-python/v4.2.0" in lower
    descriptive_identity = all(term in lower for term in ("fluxcache python", "4.2.0", "official"))
    assert exact_id or descriptive_identity, (
        "the note does not identify the official FluxCache Python 4.2.0 documentation target; "
        "guidance could be drawn from the archived client or community wrapper"
    )


def test_snapshot_section_citation_coverage():
    text = output_text()
    cited = set(re.findall(r"\bFC42-[A-Z]+-\d{3}\b", text, flags=re.IGNORECASE))
    cited = {item.upper() for item in cited}
    valid = current_chunk_ids()
    assert cited <= valid, f"the note cites unknown current-snapshot section IDs: {sorted(cited - valid)}"
    required_topics = {
        "installation": {"FC42-INSTALL-002"},
        "client setup": {"FC42-IMPORTS-003", "FC42-AUTH-004", "FC42-CONFIG-005"},
        "transaction retries": {"FC42-RETRY-006", "FC42-RETRY-007", "FC42-TX-008", "FC42-TX-009"},
        "migration and shutdown": {"FC42-LIFECYCLE-010", "FC42-MIGRATE-011", "FC42-MIGRATE-012"},
    }
    missing_topics = [topic for topic, ids in required_topics.items() if not (cited & ids)]
    assert not missing_topics, (
        f"supporting section IDs do not cover these requested topics: {missing_topics}; "
        "the engineer cannot trace material advice to the snapshot"
    )


def test_install_constraint():
    text = compact_code(output_text())
    exact_range = 'fluxcache[asyncio]>=4.2,<4.3' in text
    compatible_release = re.search(r"fluxcache\[asyncio\](?:~=|==)4\.2(?:\.\d+)?(?:\.\*)?", text) is not None
    assert exact_range or compatible_release, (
        "the installation guidance does not include the asyncio extra constrained to the 4.2 release line"
    )


def test_secure_async_client_configuration():
    text = output_text()
    compact = compact_code(text)
    required = {
        "4.2 async client import": "fromfluxcache.aioimportasyncfluxclient",
        "environment-backed credential": "envtokencredential",
        "credential variable name": "fluxcache_token",
        "bounded connection pool": "max_connections=40",
        "per-attempt timeout": "request_timeout=5.0",
    }
    missing = [label for label, token in required.items() if token not in compact]
    assert not missing, f"the 4.2 async client setup is missing: {missing}"
    unsafe_patterns = [
        r"(?i)\b(?:token|api[_-]?key|password)\s*=\s*['\"](?!FLUXCACHE_TOKEN\b|\$|\{)[^'\"]{6,}['\"]",
        r"\bsk-[A-Za-z0-9_-]{8,}\b",
    ]
    assert not any(re.search(pattern, text) for pattern in unsafe_patterns), (
        "the example appears to embed a credential-like value instead of reading the named environment variable"
    )


def test_retry_policy():
    text = normalized(output_text())
    compact = compact_code(text)
    required_tokens = [
        "retrypolicy",
        "max_attempts=4",
        "conflicterror",
        "temporarilyunavailableerror",
        "exponential",
        "jitter",
    ]
    missing = [token for token in required_tokens if token not in compact]
    assert not missing, f"the documented bounded transient retry policy is missing: {missing}"
    assert re.search(r"(?:initial|first).{0,60}(?:three|3).{0,30}retr", text, flags=re.IGNORECASE), (
        "the note does not clarify that four attempts means the initial call plus at most three retries"
    )


def test_transaction_retry_boundary():
    text = normalized(output_text())
    compact = compact_code(text)
    assert "transaction(" in compact and "idempotency_key=" in compact, (
        "the example does not attach an idempotency key to the transaction"
    )
    assert re.search(r"(?:stable|same|reuse|unchanged).{0,100}(?:idempotency|job[_ ]?id)|(?:idempotency|job[_ ]?id).{0,100}(?:stable|same|reuse|unchanged)", text, flags=re.IGNORECASE), (
        "the note does not say the invoice transaction key must remain stable across attempts"
    )
    assert re.search(r"(?:only|requires?|when).{0,90}idempotency|idempotency.{0,90}(?:only|requires?|when)", text, flags=re.IGNORECASE), (
        "the note omits the commit retry boundary: transactions retry only when the key is present"
    )
    for error_name in ("AuthenticationError", "ValidationError", "QuotaExceededError"):
        match = re.search(
            rf"(?:do not|don't|never|not|non[- ]retryable|excluded).{{0,110}}{error_name}|"
            rf"{error_name}.{{0,110}}(?:do not|don't|never|not|non[- ]retryable|excluded)",
            text,
            flags=re.IGNORECASE,
        )
        assert match, f"{error_name} is not clearly identified as non-retryable; the worker could loop pointlessly"


def test_v3_migration_map():
    text = normalized(output_text())
    lower = text.lower()
    required_names = (
        "asyncclient",
        "asyncfluxclient",
        "pool_size",
        "max_connections",
        "retry_count",
        "retrypolicy",
        "close_async",
        "aclose",
    )
    missing = [name for name in required_names if name not in lower]
    assert not missing, f"the v3-to-4.2 migration map is incomplete: {missing}"
    assert re.search(r"(?:remove|replace|becomes|old|v3|must not|deprecated)", lower), (
        "legacy and replacement names are present but are not clearly framed as a migration away from v3"
    )
    code = fenced_code(text)
    forbidden_in_example = {
        "v3 top-level AsyncClient import": r"from\s+fluxcache\s+import\s+AsyncClient",
        "pool_size keyword": r"\bpool_size\s*=",
        "retry_count keyword": r"\bretry_count\s*=",
        "close_async call": r"\.close_async\s*\(",
    }
    used = [label for label, pattern in forbidden_in_example.items() if re.search(pattern, code)]
    assert not used, f"the ready-to-adapt fenced example still uses removed v3 forms: {used}"


def test_shutdown_lifecycle():
    text = normalized(output_text())
    compact = compact_code(text)
    automatic = "asyncwithasyncfluxclient(" in compact
    manual = re.search(r"await\s+\w+\.aclose\s*\(\s*\)", text) is not None
    assert automatic, "the example does not use the async client context manager for reliable pool shutdown"
    assert manual or "aclose()" in text, "the note omits aclose() for the manual-ownership case"
    assert re.search(r"(?:success|exception|error|cancel|shutdown).{0,100}(?:close|pool)|(?:close|pool).{0,100}(?:success|exception|error|cancel|shutdown)", text, flags=re.IGNORECASE), (
        "shutdown guidance does not explain that resources close across normal and exceptional worker exits"
    )
