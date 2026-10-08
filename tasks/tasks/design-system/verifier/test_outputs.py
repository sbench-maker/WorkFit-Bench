from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data/aurora-ui"))
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/design_system_audit.md"))
if not DATA.is_absolute() or not OUTPUT.is_absolute():
    raise ValueError("Verifier data and output paths must be absolute")


def load_json(relative: str) -> dict:
    return json.loads((DATA / relative).read_text(encoding="utf-8"))


def norm(value: str) -> str:
    value = value.casefold().replace("_", " ").replace("–", " ").replace("—", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value).strip()


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def contract(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    result = {}
    for key in ("variants", "sizes", "states", "accessibility"):
        match = re.search(rf"\b{key}:\s*(\[[^\n]*\])", text)
        if not match:
            raise ValueError(f"missing {key} contract in {path}")
        result[key] = json.loads(match.group(1))
    return result


def documented_terms(path: Path, heading: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"(?ims)^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)", text)
    return set() if not match else set(re.findall(r"`([^`]+)`", match.group(1)))


def literal_candidates(category: str, value: str) -> list[str]:
    if category == "color":
        return re.findall(r"#[0-9A-Fa-f]{6}\b|rgba?\([^)]*\)", value)
    if category == "shadow":
        return [value.strip()]
    if category == "fontWeight":
        return re.findall(r"(?<![\w.-])\d{3}(?![\w.-])", value)
    return re.findall(r"(?<![\w.-])-?\d+(?:\.\d+)?(?:ms|px|rem|em|%)(?![\w.-])", value)


def derive_truth() -> dict:
    tokens = load_json("tokens/design-tokens.json")["tokens"]
    policy = load_json("policies/audit-policy.json")
    registry = load_json("registry/components.json")["components"]
    property_category = {
        prop: category
        for category, properties in policy["audited_properties"].items()
        for prop in properties
    }
    reverse_tokens = {
        category: {compact(value): f"{category}.{name}" for name, value in values.items()}
        for category, values in tokens.items()
    }
    exceptions = {
        (item["file"], item["property"], compact(item["value"]))
        for item in policy["registered_literal_exceptions"]
    }
    token_issues = []
    for path in sorted((DATA / "src" / "components").glob("*/*.css")):
        relative = path.relative_to(DATA).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.match(r"\s*([\w-]+)\s*:\s*(.*?)\s*;\s*$", line)
            if not match or match.group(1) not in property_category:
                continue
            prop, raw_value = match.groups()
            if "var(" in raw_value:
                continue
            category = property_category[prop]
            for literal in literal_candidates(category, raw_value):
                if (relative, prop, compact(literal)) in exceptions:
                    continue
                token_issues.append({
                    "component": path.parent.name,
                    "file": relative,
                    "line": line_number,
                    "property": prop,
                    "literal": literal,
                    "token": reverse_tokens.get(category, {}).get(compact(literal)),
                })

    naming = []
    implementation = []
    docs = []
    for item in registry:
        actual = contract(DATA / item["source"])
        kind_policy = policy["component_kind_policies"][item["kind"]]
        for api, allowed_key in (("variant", "allowed_variants"), ("size", "allowed_sizes")):
            for current in actual[api + "s"]:
                if current not in kind_policy[allowed_key]:
                    naming.append({
                        "component": item["name"], "api": api, "current": current,
                        "replacement": policy["public_name_aliases"].get(current), "file": item["source"],
                    })
        for dimension, required_key, actual_key in (
            ("state", "required_states", "states"),
            ("accessibility", "required_accessibility", "accessibility"),
        ):
            for missing in sorted(set(kind_policy[required_key]) - set(actual[actual_key])):
                implementation.append({
                    "component": item["name"], "dimension": dimension,
                    "missing": missing, "file": item["source"],
                })
        documented = {
            "variants": documented_terms(DATA / item["documentation"], "Variants"),
            "sizes": documented_terms(DATA / item["documentation"], "Sizes"),
            "states": documented_terms(DATA / item["documentation"], "States"),
            "accessibility": documented_terms(DATA / item["documentation"], "Accessibility"),
        }
        for dimension in ("variants", "sizes", "states", "accessibility"):
            for missing in sorted(set(actual[dimension]) - documented[dimension]):
                docs.append({
                    "component": item["name"], "dimension": dimension,
                    "missing": missing, "file": item["documentation"],
                })
    return {
        "registry": registry,
        "policy": policy,
        "token_issues": token_issues,
        "naming": naming,
        "implementation": implementation,
        "docs": docs,
    }


TRUTH = derive_truth()


def readable_report() -> str | None:
    if not OUTPUT.is_file():
        return None
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


@pytest.fixture(scope="session")
def report_text() -> str:
    text = readable_report()
    if not text:
        pytest.skip("The requested Markdown artifact is missing or unreadable; root failure is scored once under artifact scope.")
    return text


def windows(text: str, *terms: str, radius: int = 2) -> list[str]:
    lines = text.splitlines()
    found = []
    for index in range(len(lines)):
        fragment = "\n".join(lines[max(0, index - radius): min(len(lines), index + radius + 1)])
        flattened = norm(fragment)
        compacted = compact(fragment)
        if all(norm(term) in flattened or compact(term) in compacted for term in terms):
            found.append(fragment)
    return found


def has_labeled_count(text: str, expected: int, aliases: tuple[str, ...]) -> bool:
    for line in text.splitlines():
        flat = norm(line)
        if re.search(rf"(?<!\d){expected}(?!\d)", flat) and any(alias in flat for alias in aliases):
            return True
    return False


def token_forms(token: str) -> tuple[str, ...]:
    css_name = "--" + re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", token).replace(".", "-").casefold()
    return token.casefold(), css_name, f"var({css_name})"


def test_artifact_readability_scope_and_summary():
    text = readable_report()
    assert text, "The requested design_system_audit.md is missing, empty, or not readable UTF-8."
    assert len(text.split()) >= 180, "The artifact is too thin to contain a system-wide audit and actionable evidence."
    missing_components = [
        item["name"] for item in TRUTH["registry"]
        if re.search(rf"\b{re.escape(item['name'])}\b", text, flags=re.I) is None
    ]
    assert not missing_components, f"The report does not demonstrate coverage of catalogued components: {missing_components}."
    expected_counts = (
        (len(TRUTH["registry"]), ("component", "reviewed", "catalog")),
        (len(TRUTH["token_issues"]), ("literal", "hardcoded", "token")),
        (len(TRUTH["naming"]), ("naming", "name drift", "public name")),
        (len(TRUTH["implementation"]), ("implementation gap", "required behavior", "implementation")),
        (len(TRUTH["docs"]), ("documentation gap", "docs gap", "documentation")),
    )
    missing_counts = [(count, aliases) for count, aliases in expected_counts if not has_labeled_count(text, count, aliases)]
    assert not missing_counts, f"The inventory summary omits or misstates objective category counts: {missing_counts}."


TOKEN_CASES = [
    pytest.param(issue, id=f"{issue['component']}-{issue['line']}-{index}")
    for index, issue in enumerate(TRUTH["token_issues"], 1)
]


@pytest.mark.parametrize("issue", TOKEN_CASES)
def test_hardcoded_visual_value_findings(report_text: str, issue: dict):
    file_hint = Path(issue["file"]).name
    candidates = windows(report_text, file_hint, issue["literal"], radius=2)
    assert candidates, (
        f"The unauthorized {issue['property']} literal {issue['literal']} in {issue['file']} is missing from the audit evidence."
    )
    joined = "\n".join(candidates)
    if issue["token"]:
        assert any(form in compact(joined) for form in map(compact, token_forms(issue["token"]))), (
            f"{issue['file']} {issue['literal']} is not mapped to approved token {issue['token']}."
        )
    else:
        phrases = ("no exact token", "new token", "add a semantic", "design review")
        assert any(phrase in norm(joined) for phrase in phrases), (
            f"{issue['file']} {issue['literal']} has no exact token, but the report presents no honest review/new-token disposition."
        )


def test_registered_literal_exception_is_not_a_violation(report_text: str):
    exception = TRUTH["policy"]["registered_literal_exceptions"][0]
    candidates = windows(report_text, Path(exception["file"]).name, exception["value"], radius=2)
    if not candidates:
        return
    context = norm("\n".join(candidates))
    accepted = ("exception", "approved", "allowed", "not a violation", "excluded")
    assert any(word in context for word in accepted), (
        "The registered Avatar 50% crop radius is mentioned as a defect rather than preserved as an approved exception."
    )


NAMING_CASES = [pytest.param(issue, id=f"{issue['component']}-{issue['api']}") for issue in TRUTH["naming"]]


@pytest.mark.parametrize("issue", NAMING_CASES)
def test_public_name_drift_and_safe_replacement(report_text: str, issue: dict):
    candidates = windows(
        report_text,
        issue["component"],
        Path(issue["file"]).name,
        issue["current"],
        issue["replacement"],
        radius=3,
    )
    assert candidates, (
        f"The public {issue['api']} drift {issue['component']}.{issue['current']} -> {issue['replacement']} "
        "is missing or lacks source evidence."
    )
    full = norm(report_text)
    assert "deprecat" in full and "alias" in full and re.search(r"\bone minor(?: release)?\b", full), (
        "The naming fixes omit the policy-required deprecated alias for one minor release, creating avoidable API breakage."
    )


IMPLEMENTATION_CASES = [
    pytest.param(issue, id=f"{issue['component']}-{issue['dimension']}-{issue['missing']}")
    for issue in TRUTH["implementation"]
]


@pytest.mark.parametrize("issue", IMPLEMENTATION_CASES)
def test_required_state_and_accessibility_gaps(report_text: str, issue: dict):
    candidates = windows(
        report_text, issue["component"], Path(issue["file"]).name, issue["missing"], radius=3
    )
    assert candidates, (
        f"The audit misses required {issue['dimension']} gap {issue['component']}.{issue['missing']} "
        f"from {issue['file']}."
    )


DOCUMENTATION_CASES = [
    pytest.param(issue, id=f"{issue['component']}-{issue['dimension']}-{issue['missing']}")
    for issue in TRUTH["docs"]
]


@pytest.mark.parametrize("issue", DOCUMENTATION_CASES)
def test_documentation_contract_gaps(report_text: str, issue: dict):
    candidates = windows(
        report_text, issue["component"], Path(issue["file"]).name, issue["missing"], radius=3
    )
    assert candidates, (
        f"The public {issue['dimension']} item {issue['component']}.{issue['missing']} is absent from its docs, "
        "but the documentation drift is not evidenced in the audit."
    )
