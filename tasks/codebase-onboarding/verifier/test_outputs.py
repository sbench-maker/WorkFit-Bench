from pathlib import Path
import os
import re


RESULTS = Path(os.environ.get("TASK_ROOT", "/root")) / "results"
GUIDE = RESULTS / "onboarding-guide.md"
CLAUDE = RESULTS / "CLAUDE.md"


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssertionError(f"{path.name} is missing or not readable UTF-8 text: {exc}") from exc


def normalized(value: str) -> str:
    value = value.casefold().replace("`", "").replace("\\", "/")
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    return re.sub(r"\s+", " ", value)


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalized(value))


def mentions_path(text: str, path: str) -> bool:
    plain = normalized(text)
    clean_path = path.rstrip("/")
    module = clean_path.removesuffix(".py").replace("/", ".")
    return path.casefold() in plain or module.casefold() in plain


def test_guide_identifies_current_stack_and_key_areas():
    guide = read_utf8(GUIDE)
    tokens = compact(guide)
    for technology in (
        "python3.12",
        "fastapi",
        "sqlalchemy",
        "postgresql",
        "alembic",
        "react",
        "typescript",
        "vite",
        "pytest",
    ):
        assert compact(technology) in tokens, f"guide omits current technology: {technology}"

    for path in (
        "rosterly/main.py",
        "rosterly/api/routes.py",
        "rosterly/services/approvals.py",
        "rosterly/db/",
        "rosterly/worker.py",
        "web/src/",
        "migrations/",
        "tests/",
    ):
        assert mentions_path(guide, path), f"guide omits a key current repository area: {path}"


def test_guide_uses_current_day_one_commands():
    guide = normalized(read_utf8(GUIDE))
    for command in ("make bootstrap", "make dev", "make test", "make lint"):
        assert command in guide, f"guide omits a day-one command present in the Makefile: {command}"
    if "python app.py" in guide:
        position = guide.index("python app.py")
        context = guide[max(0, position - 100): position + 160]
        assert any(word in context for word in ("stale", "obsolete", "old", "do not", "don't", "not use")), (
            "guide presents the README's obsolete prototype command without warning"
        )


def test_claude_preserves_existing_project_rules():
    claude = normalized(read_utf8(CLAUDE))
    flattened = compact(claude)
    provision_rule = re.search(
        r"(?:never|do not|don't|must not|avoid).{0,120}provision.{0,120}(?:http|request|handler)",
        claude,
    ) or re.search(
        r"provision.{0,120}(?:http|request|handler).{0,120}(?:never|do not|don't|must not|avoid)",
        claude,
    )
    assert provision_rule and "outbox" in claude, (
        "CLAUDE.md lost the rule that provisioning stays out of handlers and behind the outbox boundary"
    )
    private_rule = re.search(
        r"(?:never|do not|don't|must not|avoid).{0,100}log.{0,100}private[ _-]?note",
        claude,
    ) or re.search(
        r"private[ _-]?note.{0,100}(?:never|do not|don't|must not|avoid).{0,100}log",
        claude,
    )
    assert private_rule, (
        "CLAUDE.md lost the prohibition on logging private_note"
    )
    negative_actor = any(compact(term) in flattened for term in ("non-manager", "employee actor", "unauthorized actor", "other roles"))
    assert "approval" in claude and "manager" in claude and negative_actor and "test" in claude, (
        "CLAUDE.md lost the requirement to test approval policy for manager and non-manager actors"
    )


def test_claude_adds_current_repository_guidance():
    claude = read_utf8(CLAUDE)
    flat = normalized(claude)
    for command in ("make dev", "make test", "make lint"):
        assert command in flat, f"refreshed CLAUDE.md omits current command: {command}"
    for path in ("rosterly/api/", "rosterly/services/", "rosterly/db/", "web/"):
        assert mentions_path(claude, path), f"refreshed CLAUDE.md omits current project area: {path}"
    if "flask" in flat or "python app.py" in flat:
        stale_terms = ("stale", "obsolete", "old", "prototype", "do not", "don't", "not current")
        assert any(term in flat for term in stale_terms), "CLAUDE.md adopts the obsolete Flask prototype instead of current code"
