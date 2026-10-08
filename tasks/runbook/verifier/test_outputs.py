from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "webhook_backlog_runbook.md"


def artifact_text() -> str:
    assert OUTPUT.is_file(), (
        "The requested /root/results/webhook_backlog_runbook.md is missing; "
        "the on-call rotation has no runbook to use."
    )
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"The runbook is not readable UTF-8 Markdown: {exc}")


def normalize(text: str) -> str:
    value = text.lower().replace("–", "-").replace("—", "-").replace("≥", ">=").replace("≤", "<=")
    value = re.sub(r"\bseconds?\b", "sec", value)
    value = re.sub(r"\bminutes?\b", "min", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized_placeholders(text: str) -> str:
    value = normalize(text)
    for name in ("incident_id", "region", "change_id", "provider", "event_id", "last_good_version"):
        patterns = (
            rf"<\s*{name}\s*>",
            rf"\$\{{\s*{name}\s*\}}",
            rf"\${name}\b",
        )
        for pattern in patterns:
            value = re.sub(pattern, "{" + name + "}", value, flags=re.IGNORECASE)
    return value


def command_lines(text: str) -> list[str]:
    # Join conventional shell continuations, then accept fenced, inline-code, table,
    # and bullet representations. Option ordering is deliberately not significant.
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    lines = []
    for raw in joined.splitlines():
        lowered = raw.lower()
        if re.search(r"\b(?:do not|don't|never|must not|forbidden|superseded|archived|rejected|not approved)\b", lowered):
            continue
        starts = [pos for name in ("pagerctl", "opsctl") if (pos := lowered.find(name)) >= 0]
        if starts:
            lines.append(normalized_placeholders(raw[min(starts) :]))
    return lines


def has_command(text: str, command_words: tuple[str, ...], required: tuple[str, ...] = ()) -> bool:
    for line in command_lines(text):
        tokens = set(re.findall(r"--[a-z0-9-]+|\{[a-z0-9_]+\}|[a-z0-9][a-z0-9._:/-]*", line))
        if all(word in tokens for word in command_words) and all(item in tokens for item in required):
            return True
    return False


def contexts(text: str, aliases: tuple[str, ...], radius: int = 7) -> str:
    lines = text.splitlines()
    selected: list[str] = []
    for index, line in enumerate(lines):
        current = normalize(line)
        if any(alias in current for alias in aliases):
            selected.extend(lines[max(0, index - 2) : min(len(lines), index + radius + 1)])
    return normalize("\n".join(selected))


def has_all(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    value = normalize(text)
    return all(any(term in value for term in group) for group in groups)


def test_artifact_usability():
    """The exact requested Markdown is readable and addresses the frozen service scope."""
    text = artifact_text()
    value = normalize(text)
    assert len(text.strip()) >= 900, (
        "The runbook is too sparse to contain an executable multi-branch response; "
        "the responder would have to reconstruct the procedure from source notes."
    )
    assert "\x00" not in text, "The runbook contains binary/NUL content and is not usable Markdown."
    assert "relayforge" in value and "webhookqueueagehigh" in value, (
        "The artifact does not identify RelayForge's WebhookQueueAgeHigh page; "
        "an operator could apply it to the wrong incident."
    )
    assert "production" in value or "--env prod" in value, "The production scope is not clear."
    assert "us-east" in value and "eu-west" in value, (
        "Both production regions must be in scope so the page's region is not guessed."
    )


def test_diagnostic_sequence():
    """All frozen evidence reads are present and precede the first mitigation."""
    text = artifact_text()
    required_reads = [
        (("pagerctl", "ack"), ("{incident_id}", "--service", "webhook-delivery")),
        (("opsctl", "queue", "status"), ("--service", "webhook-delivery", "--env", "prod", "--region", "{region}")),
        (("opsctl", "workers", "status"), ("--pool", "async", "--region", "{region}")),
        (("opsctl", "downstream", "status"), ("--region", "{region}")),
        (("opsctl", "state-store", "status"), ("--region", "{region}")),
        (("opsctl", "deploy", "history"), ("--region", "{region}", "--limit", "5")),
    ]
    missing = [" ".join(words) for words, tokens in required_reads if not has_command(text, words, tokens)]
    assert not missing, (
        f"Missing approved acknowledgement/evidence commands: {missing}; without the full snapshot, "
        "overlapping failures can be misclassified."
    )
    value = normalized_placeholders(text)
    read_positions = [value.find("opsctl " + " ".join(words[1:])) for words, _ in required_reads[1:]]
    mutation_markers = ("opsctl workers scale", "opsctl throttle set", "opsctl queue quarantine", "opsctl deploy rollback")
    mutation_positions = [value.find(marker) for marker in mutation_markers if value.find(marker) >= 0]
    assert mutation_positions and all(position >= 0 for position in read_positions), "Could not locate the diagnostic or mitigation sequence."
    assert max(read_positions) < min(mutation_positions), (
        "A mutating mitigation appears before the complete queue/worker/downstream/state-store/deploy evidence set; "
        "the responder could act on the wrong cause."
    )


def test_approved_mitigation_commands_and_boundaries():
    """Every recurring failure mode maps to its approved mutation and discriminator."""
    text = artifact_text()
    expected_commands = [
        (("opsctl", "workers", "scale"), ("--pool", "async", "--replicas", "18", "--change", "{change_id}")),
        (("opsctl", "throttle", "set"), ("--provider", "{provider}", "--rps", "120", "--ttl", "30m", "--change", "{change_id}")),
        (("opsctl", "queue", "quarantine"), ("--event", "{event_id}", "--reason", "{incident_id}", "--change", "{change_id}")),
        (("opsctl", "deploy", "rollback"), ("--to", "{last_good_version}", "--change", "{change_id}")),
    ]
    missing = [" ".join(words) for words, tokens in expected_commands if not has_command(text, words, tokens)]
    assert not missing, f"Approved mitigation command coverage is incomplete: {missing}."

    state = contexts(text, ("state-store lag", "state store lag"))
    downstream = contexts(text, ("provider 429", "downstream rate"))
    deploy = contexts(text, ("crash-loop", "crash loop", "release regression"))
    poison = contexts(text, ("poison event", "schema_rejected", "schema rejected"))
    saturation = contexts(text, ("worker saturation", "ready workers", "ready < desired"), radius=20)
    defects = []
    if not has_all(state, (("200",), ("do not scale", "no scaling", "not scale"))):
        defects.append("state-store >=200 ms must block scaling while telemetry is unreliable")
    if not has_all(downstream, (("429",), ("10%", "10 %"), ("do not add workers", "do not scale", "never scale", "not add workers"))):
        defects.append("provider 429 >=10% must select throttle rather than capacity")
    if not has_all(deploy, (("30 min", "30-min"), ("3", "three"), ("last-good", "last good", "last_good_version"), ("incident commander",))):
        defects.append("a <30-minute deploy with >=3 crash loops needs an IC-approved history-derived rollback")
    if not has_all(poison, (("two", "twice", "2 read"), ("same", "stable", "matching"), ("one", "only that", "single"))):
        defects.append("poison isolation requires the same event on two reads and only that event")
    if not has_all(saturation, (("ready",), ("desired",), ("below 2%", "<2%", "under 2%", "low 429"), ("18",))):
        defects.append("worker saturation requires ready<desired, healthy downstream, and the 18-replica cap")
    assert not defects, "Incomplete or unsafe decision boundaries: " + "; ".join(defects)


def test_verification_and_reversal():
    """Recovery is sustained and each temporary mutation has a safe exit path."""
    text = artifact_text()
    verify = contexts(text, ("verification", "recovery requires", "healthy sample"), radius=12)
    required_gates = (
        ("three consecutive", "3 consecutive"),
        ("five-min", "5 min", "5-min"),
        ("below 120", "<120"),
        ("15%", "15 %"),
        ("below 1%", "<1%"),
        ("below 2%", "<2%"),
        ("tenant delivery probe", "delivery probe"),
    )
    assert has_all(verify, required_gates), (
        "The recovery gate must require three five-minute samples, age <120 sec, depth falling 15% each sample, "
        "5xx <1%, 429 <2%, and a tenant delivery probe; premature closure can hide a recurring backlog."
    )
    assert has_command(
        text,
        ("opsctl", "workers", "scale"),
        ("--pool", "async", "--replicas", "12", "--change", "{change_id}"),
    ), "Temporary scale-up is missing the approved return to the normal 12 replicas."
    assert has_command(
        text,
        ("opsctl", "throttle", "clear"),
        ("--provider", "{provider}", "--change", "{change_id}"),
    ), "The throttle lacks its approved early-clear reversal."
    release = contexts(text, ("queue release", "quarantine", "auto-release", "auto release"), radius=9)
    assert has_all(release, (("never auto", "do not auto", "not auto"), ("integration runtime",), ("approve", "approval"), ("corrected payload", "validate"))), (
        "A quarantined event must not be auto-released; Integration Runtime must validate the corrected payload and approve."
    )


def test_escalation_and_conflict_safety():
    """Material conditions route correctly and superseded destructive advice is rejected."""
    text = artifact_text()
    value = normalize(text)
    ic = contexts(text, ("incident commander", "#incident-command"), radius=10)
    provider = contexts(text, ("integration reliability", "#integration-reliability"), radius=8)
    state = contexts(text, ("platform state", "#platform-state"), radius=8)
    assert has_all(ic, (("900",), ("three tenant", "3 tenant"), ("10 min", "10-min"), ("15%", "15 %"))), (
        "Incident Commander routing must cover age >=900 sec, >=3 tenants, and failure to reduce depth 15% within 10 minutes."
    )
    assert "#incident-command" in value
    assert has_all(provider, (("429",), ("10%", "10 %"), ("#integration-reliability",))), (
        "Provider 429 >=10% must route to Integration Reliability."
    )
    assert has_all(state, (("200",), ("#platform-state",))), "State-store lag >=200 ms must route to Platform State."

    assert not has_command(text, ("opsctl", "queue", "purge")), (
        "The archived queue-purge command is destructive and superseded; it must not appear as executable guidance."
    )
    active_24 = any("--replicas" in line and re.search(r"(?:^| )24(?: |$)", line) for line in command_lines(text))
    assert not active_24, "The superseded 24-replica command must not appear as executable guidance."
    conflict = contexts(text, ("conflict", "superseded", "archived note", "old note"), radius=8)
    assert has_all(conflict, (("purge",), ("24",), ("18",), ("supersed", "reject", "never", "do not"))), (
        "The runbook does not explicitly resolve the archived purge/24-replica note against current policy; "
        "leaving the conflict implicit is unsafe for a new responder."
    )
