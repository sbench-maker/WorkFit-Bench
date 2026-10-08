#!/usr/bin/env python3
"""Deterministic offline review responses for the SkillsBench fixture."""

from __future__ import annotations


REQUIRED_DIFF_MARKERS = (
    "diff --git a/src/gateway/auth.py",
    "diff --git a/src/gateway/batching.py",
    "diff --git a/src/gateway/quota.py",
    "diff --git a/src/gateway/router.py",
)


def has_complete_branch_diff(prompt: str) -> bool:
    return all(marker in prompt for marker in REQUIRED_DIFF_MARKERS)


def has_project_context(prompt: str) -> bool:
    return "Tenant boundaries are authorization boundaries" in prompt and "Only `TimeoutError` is retryable" in prompt


def security_focused(prompt: str) -> bool:
    lowered = prompt.lower()
    return "security" in lowered and ("auth" in lowered or "authorization" in lowered)


def codex_response(prompt: str) -> dict:
    if not has_complete_branch_diff(prompt):
        return {
            "findings": [],
            "overall_correctness": "patch is correct",
            "overall_explanation": "No proposed branch changes were present in the supplied diff.",
            "overall_confidence_score": 0.98,
        }

    findings = [
        {
            "title": "[Q001] Preserve tenant scope in the quota cache key",
            "body": "Keying the process-wide cache only by model lets the first tenant's remaining quota be returned to another tenant using the same model. Keep `(tenant_id, model)` in the key and add a two-tenant regression test.",
            "confidence_score": 0.99,
            "priority": 3,
            "code_location": {"file_path": "src/gateway/quota.py", "line_range": {"start": 7, "end": 7}},
        },
        {
            "title": "[B001] Reject a request larger than the batch budget",
            "body": "After this guard is removed, a request with `token_count > max_tokens` is appended to an empty batch and emitted over budget. Restore explicit rejection before appending; fixture request req-0038 exercises this path.",
            "confidence_score": 0.97,
            "priority": 2,
            "code_location": {"file_path": "src/gateway/batching.py", "line_range": {"start": 9, "end": 10}},
        },
    ]
    if has_project_context(prompt):
        findings.append(
            {
                "title": "[R001] Do not retry policy failures on a fallback model",
                "body": "Catching every Exception also catches authentication, authorization, validation, and policy errors. Those failures will be sent to `fallback_model`, masking the real denial and potentially invoking a model the caller may not use. Catch `TimeoutError` only.",
                "confidence_score": 0.98,
                "priority": 3,
                "code_location": {"file_path": "src/gateway/router.py", "line_range": {"start": 7, "end": 8}},
            }
        )
    return {
        "findings": findings,
        "overall_correctness": "patch is incorrect",
        "overall_explanation": "The branch introduces tenant-isolation, batching, and failure-routing regressions that should block merge.",
        "overall_confidence_score": 0.99,
    }


def gemini_response(prompt: str) -> dict:
    if not has_complete_branch_diff(prompt):
        return {
            "reviewer": "gemini",
            "verdict": "no changes found",
            "findings": [],
            "summary": "The supplied input did not include the proposed branch diff.",
        }

    findings = [
        {
            "issue_id": "Q001",
            "severity": "critical",
            "file": "src/gateway/quota.py",
            "line": 7,
            "title": "Quota cache crosses tenant boundaries",
            "explanation": "The shared cache now ignores tenant_id, so tenants that choose the same model reuse another tenant's quota result.",
            "remediation": "Restore a composite `(tenant_id, model)` key and test two tenants using one model.",
        }
    ]
    if security_focused(prompt):
        findings.append(
            {
                "issue_id": "A001",
                "severity": "critical",
                "file": "src/gateway/auth.py",
                "line": 5,
                "title": "Caller-controlled metadata bypasses model scope",
                "explanation": "A request can set metadata.x_internal to true and return before verified claims.scopes is checked, granting routing without the required route:model scope.",
                "remediation": "Remove the metadata bypass and derive any internal identity from verified middleware claims.",
            }
        )
    if has_project_context(prompt):
        findings.append(
            {
                "issue_id": "R001",
                "severity": "high",
                "file": "src/gateway/router.py",
                "line": 7,
                "title": "Broad exception fallback converts denials into retries",
                "explanation": "Exception includes policy and authorization failures, which must be returned rather than retried on another model.",
                "remediation": "Limit fallback handling to TimeoutError and preserve all other exceptions.",
            }
        )
    return {
        "reviewer": "gemini",
        "verdict": "changes requested",
        "findings": findings,
        "summary": "Tenant isolation and authorization regressions make the branch unsafe to merge.",
    }
