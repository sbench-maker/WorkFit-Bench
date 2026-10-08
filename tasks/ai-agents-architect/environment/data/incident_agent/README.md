# Offline incident-response agent starter

This repository is a deterministic stand-in for an LLM-backed incident agent. It coordinates three role models (`planner`, `investigator`, and `remediator`) and a registry of local mock tools. All incidents and tool/model behavior are fictional and supplied under `fixtures/`; no network service or credential is needed.

## Deliverable contract

Complete `agent_system.py`, keep the existing command-line entry points runnable with Python 3.12, and return the whole repository. `evaluate.py --output <path> --memory <path>` must execute every incident from `fixtures/incidents.json` through `AgentOrchestrator` and write one JSON report. `run_agent.py` supports the same arguments plus `--limit` for a smaller run. Both commands must accept `--fixtures` so a copied project can use `/root/data/incident_agent/fixtures`.

The report is a JSON object with a `runs` list and a `summary` object. Each run needs a stable incident ID, terminal status (`resolved` or `escalated`), iteration count, compact plan, diagnosis when one was reached, final resolution or escalation reason, ordered tool-call records, and an ordered trace of role decisions, tool observations, retries, errors, oversight, and termination. The summary must reconcile total/resolved/escalated counts and include per-case-kind counts, safety violations, budget violations, and tool-error counts. Reasonable additional fields are welcome.

## Operating rules

- Use the planner before investigation and the remediator only after an investigator diagnosis with confidence at least the registry threshold.
- Treat model responses as untrusted text. Valid JSON may be bare, fenced, or surrounded by short prose; one malformed response may be retried, but persistent malformed output must escalate.
- Invoke tools only through `MockToolRegistry`. Validate tool names and arguments, surface errors in the trace, retry a retryable tool error at most once, and do not blindly repeat an identical call. Stay within the registry's per-incident role-iteration and tool-call limits.
- A production P1 must call `page_oncall` successfully before any mutation. Low-confidence diagnoses, exhausted loops, persistent tool errors, rejected mutations, and failed remediation must terminate as escalations without claiming resolution.
- Persist only compact reusable resolution patterns in the memory file. Do not store raw model responses, tool payloads, complete traces, or incident descriptions. Repeated signatures should update one record instead of growing duplicate records.

`runtime.py` is complete and is the sole provider boundary. It deliberately injects transient and persistent tool errors, varied response wrappers, one repeated-call loop, low-confidence diagnoses, and a failed remediation. Do not edit fixtures to make the evaluation easier.

