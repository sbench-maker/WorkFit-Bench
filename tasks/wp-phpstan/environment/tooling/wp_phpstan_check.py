#!/usr/bin/env python3
"""Deterministic offline PHPStan fixture for the ParcelPilot project.

The fixture models the project-specific findings that the checked-in Composer
gate exposed. It intentionally accepts several equivalent PHPDoc and NEON
representations so the task is about outcomes rather than one golden patch.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if value and value[0] in "'\"" and value[-1:] == value[0]:
        value = value[1:-1]
    return value.strip()


def _list_block(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    inline_re = re.compile(
        rf"^(?P<indent>\s*){re.escape(key)}\s*:\s*\[(?P<values>.*?)\]\s*$", re.I
    )
    key_re = re.compile(rf"^(?P<indent>\s*){re.escape(key)}\s*:\s*$", re.I)
    for index, line in enumerate(lines):
        inline = inline_re.match(line)
        if inline:
            return [_clean_scalar(value) for value in inline.group("values").split(",") if value.strip()]
        match = key_re.match(line)
        if not match:
            continue
        indent = len(match.group("indent").replace("\t", "    "))
        values: list[str] = []
        for nested in lines[index + 1 :]:
            if not nested.strip() or nested.lstrip().startswith("#"):
                continue
            nested_indent = len(nested) - len(nested.lstrip(" \t"))
            if nested_indent <= indent:
                break
            stripped = nested.strip()
            if stripped.startswith("-"):
                values.append(_clean_scalar(stripped[1:].strip()))
        return values
    return []


def _ignore_patterns(text: str) -> list[str]:
    patterns = [value for value in _list_block(text, "ignoreErrors") if value]
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if re.match(r"^\s*ignoreErrors\s*:\s*$", line, re.I)),
        None,
    )
    if start is None:
        return patterns
    indent = len(lines[start]) - len(lines[start].lstrip(" \t"))
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        nested_indent = len(line) - len(line.lstrip(" \t"))
        if nested_indent <= indent:
            break
        message = re.match(r"^\s*message\s*:\s*(.*?)\s*$", line, re.I)
        if message:
            patterns.append(_clean_scalar(message.group(1)))
    return list(dict.fromkeys(patterns))


def _pattern_matches(pattern: str, message: str) -> bool:
    candidate = pattern.strip()
    if len(candidate) >= 2 and not candidate[0].isalnum():
        delimiter = candidate[0]
        closing = candidate.rfind(delimiter)
        if closing > 0:
            candidate = candidate[1:closing]
    try:
        return re.search(candidate, message, re.I) is not None
    except re.error:
        return "vendor_loyalty_card" in pattern.lower() and "vendor_loyalty_card" in message.lower()


def _norm_path(value: str) -> str:
    value = value.replace("\\", "/").strip().lstrip("./")
    value = re.sub(r"[/\\*]+$", "", value)
    return value.lower()


def _path_selected(paths: list[str], wanted: str) -> bool:
    wanted = _norm_path(wanted)
    for value in paths:
        norm = _norm_path(value)
        if norm in {"", "."} or norm == wanted or wanted.startswith(norm + "/"):
            return True
    return False


def _path_excluded(excludes: list[str], wanted: str) -> bool:
    wanted = _norm_path(wanted)
    for value in excludes:
        norm = _norm_path(value)
        if norm == wanted or wanted.startswith(norm + "/") or norm.startswith(wanted + "/"):
            return True
    return False


def check_config(project: Path) -> list[str]:
    config_path = project / "phpstan.neon"
    if not config_path.is_file():
        return ["phpstan.neon:1: PHPStan configuration is missing"]
    text = config_path.read_text(encoding="utf-8")
    paths = _list_block(text, "paths")
    excludes = _list_block(text, "excludePaths")
    includes = _list_block(text, "includes")
    scan_files = _list_block(text, "scanFiles")
    errors: list[str] = []

    include_norm = {_norm_path(value) for value in includes}
    if "phpstan-baseline.neon" not in include_norm:
        errors.append("phpstan.neon:1: The existing migration baseline is not included")

    if not paths:
        errors.append("phpstan.neon:6: No analysis paths are configured")
    for required in ("src", "includes"):
        if not _path_selected(paths, required):
            errors.append(f"phpstan.neon:6: First-party path {required}/ is not analyzed")

    for noisy in ("build", "vendor", "tests", "node_modules"):
        if _path_selected(paths, noisy) and not _path_excluded(excludes, noisy):
            errors.append(
                f"phpstan.neon:6: Generated or non-production path {noisy}/ is in the analysis scope"
            )

    scans = "\n".join(scan_files).replace("\\", "/").lower()
    if "php-stubs/wordpress-stubs" not in scans:
        errors.append("phpstan.neon:12: WordPress core stubs are not loaded")
    return errors


def _docblock_before(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    prefix = text[:index]
    match = re.search(r"/\*\*[\s\S]*?\*/\s*$", prefix)
    return match.group(0) if match else ""


def _split_shape_fields(body: str) -> dict[str, str]:
    body = re.sub(r"(?m)^\s*\*\s?", "", body)
    fields: dict[str, str] = {}
    depth = 0
    token = ""
    pieces: list[str] = []
    for char in body:
        if char in "<{[(":
            depth += 1
        elif char in ">}])":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            pieces.append(token)
            token = ""
        else:
            token += char
    if token.strip():
        pieces.append(token)
    for piece in pieces:
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:\s*(.*?)\s*$", piece, re.S)
        if match:
            name, optional, type_text = match.groups()
            fields[name] = ("?" if optional else "") + re.sub(r"\s+", "", type_text).lower()
    return fields


def _shape_for_param(doc: str, generic: str, variable: str) -> dict[str, str]:
    pattern = re.compile(
        rf"@phpstan-param\s+{re.escape(generic)}\s*<\s*(array\{{[\s\S]*?\}}|[A-Za-z_][A-Za-z0-9_]*)\s*>\s+\${re.escape(variable)}\b"
    )
    match = pattern.search(doc)
    if not match:
        return {}
    raw = match.group(1)
    if raw.startswith("array{"):
        return _split_shape_fields(raw[len("array{") : -1])
    alias = re.search(rf"@phpstan-type\s+{re.escape(raw)}\s+array\{{([\s\S]*?)\}}", doc)
    return _split_shape_fields(alias.group(1)) if alias else {}


def _has_required_fields(actual: dict[str, str], expected: dict[str, tuple[bool, set[str]]]) -> bool:
    for name, (optional, accepted_types) in expected.items():
        value = actual.get(name)
        if value is None:
            return False
        actual_optional = value.startswith("?")
        actual_type = value[1:] if actual_optional else value
        if optional != actual_optional or actual_type not in accepted_types:
            return False
    return True


def _contains_object_shape(text: str, required: dict[str, str]) -> bool:
    for match in re.finditer(r"object\{([\s\S]*?)\}", text):
        fields = _split_shape_fields(match.group(1))
        if all(fields.get(name, "").lstrip("?") == type_name for name, type_name in required.items()):
            return True
    return False


def check_wordpress_types(project: Path) -> list[str]:
    errors: list[str] = []

    rest_path = project / "src/Rest/OrdersController.php"
    rest_text = rest_path.read_text(encoding="utf-8") if rest_path.is_file() else ""
    rest_doc = _docblock_before(rest_text, "public function getItems")
    rest_shape = _shape_for_param(rest_doc, "WP_REST_Request", "request")
    expected_rest = {
        "customer_id": (True, {"int"}),
        "include_archived": (True, {"bool", "boolean"}),
        "status": (True, {"'open'|'packed'|'shipped'", "'open'|'shipped'|'packed'", "'packed'|'open'|'shipped'", "'packed'|'shipped'|'open'", "'shipped'|'open'|'packed'", "'shipped'|'packed'|'open'"}),
    }
    if not _has_required_fields(rest_shape, expected_rest):
        errors.append(
            "src/Rest/OrdersController.php:17: WP_REST_Request parameters customer_id, include_archived, and status have unresolved types"
        )

    hook_path = project / "src/Hooks/OrderStatusHooks.php"
    hook_text = hook_path.read_text(encoding="utf-8") if hook_path.is_file() else ""
    hook_doc = _docblock_before(hook_text, "public static function syncOrderStatus")
    doc_typed = bool(re.search(r"@param\s+\\?WC_Order\s+\$order\b", hook_doc))
    signature_typed = bool(
        re.search(r"syncOrderStatus\s*\([^)]*\\?WC_Order\s+\$order\b", hook_text, re.S)
    )
    if not (doc_typed or signature_typed):
        errors.append(
            "src/Hooks/OrderStatusHooks.php:18: Call to get_id() is made on an imprecisely typed hook argument"
        )

    repo_path = project / "src/Repository/PickListRepository.php"
    repo_text = repo_path.read_text(encoding="utf-8") if repo_path.is_file() else ""
    repo_doc = _docblock_before(repo_text, "public function findOpenByRoute")
    has_shape = _contains_object_shape(
        repo_doc, {"order_id": "int", "route": "string", "priority": "int"}
    )
    fallback_direct = bool(
        re.search(r"get_results\s*\([\s\S]*?\)\s*(?:\?:|\?\?)\s*\[\]", repo_text)
    )
    fallback_variable = bool(
        re.search(r"return\s+\$[A-Za-z_][A-Za-z0-9_]*\s*(?:\?:|\?\?)\s*\[\]", repo_text)
        or re.search(r"return\s+is_array\s*\([^)]*\)\s*\?[^:]+:\s*\[\]", repo_text, re.S)
    )
    if not has_shape:
        errors.append(
            "src/Repository/PickListRepository.php:13: Database rows lack the order_id/route/priority object shape"
        )
    if not (fallback_direct or fallback_variable):
        errors.append(
            "src/Repository/PickListRepository.php:23: Method may return null although array is declared"
        )

    job_path = project / "src/Jobs/CarrierSyncJob.php"
    job_text = job_path.read_text(encoding="utf-8") if job_path.is_file() else ""
    job_doc = _docblock_before(job_text, "public function __invoke")
    job_shape = {}
    inline = re.search(r"@param\s+array\{([\s\S]*?)\}\s+\$args\b", job_doc)
    if inline:
        job_shape = _split_shape_fields(inline.group(1))
    else:
        alias_param = re.search(r"@phpstan-param\s+([A-Za-z_][A-Za-z0-9_]*)\s+\$args\b", job_doc)
        if alias_param:
            alias = re.search(
                rf"@phpstan-type\s+{re.escape(alias_param.group(1))}\s+array\{{([\s\S]*?)\}}",
                job_doc,
            )
            if alias:
                job_shape = _split_shape_fields(alias.group(1))
    expected_job = {
        "order_id": (False, {"int"}),
        "carrier": (False, {"string"}),
        "attempt": (False, {"int"}),
    }
    if not _has_required_fields(job_shape, expected_job):
        errors.append(
            "src/Jobs/CarrierSyncJob.php:15: Scheduler argument shape does not establish order_id, carrier, and attempt types"
        )
    return errors


def check_third_party(project: Path) -> list[str]:
    config_path = project / "phpstan.neon"
    if not config_path.is_file():
        return ["phpstan.neon:1: PHPStan configuration is missing"]
    text = config_path.read_text(encoding="utf-8")
    scans = "\n".join(_list_block(text, "scanFiles")).replace("\\", "/").lower()
    ignores = _ignore_patterns(text)
    errors: list[str] = []
    if "php-stubs/woocommerce-stubs" not in scans:
        errors.append(
            "src/Integration/WooCommerceBridge.php:12: Class WC_Order is unresolved because the installed WooCommerce stubs are not loaded"
        )

    loyalty_messages = [
        "Instantiated class Vendor_Loyalty_Card not found",
        "Call to method rewardBalance() on an unknown class Vendor_Loyalty_Card",
    ]
    loyalty_patterns = [
        pattern for pattern in ignores if any(_pattern_matches(pattern, message) for message in loyalty_messages)
    ]
    if not loyalty_patterns:
        errors.append(
            "src/Integration/LoyaltyBridge.php:17: Instantiated class Vendor_Loyalty_Card is unavailable in the analysis environment"
        )

    unrelated_messages = [
        "Call to method run() on an unknown class ParcelPilot_Internal_Service",
        "Parameter has invalid type Other_Plugin_Model",
        "Instantiated class Unrelated_Vendor_Client not found",
    ]
    for pattern in ignores:
        if any(_pattern_matches(pattern, message) for message in unrelated_messages):
            errors.append(
                "phpstan.neon:16: An ignoreErrors pattern can suppress unrelated unknown-class findings"
            )
            break
    return errors


def all_errors(project: Path, category: str) -> list[str]:
    checks = {
        "config": check_config,
        "wordpress": check_wordpress_types,
        "third-party": check_third_party,
    }
    if category == "all":
        errors: list[str] = []
        for check in checks.values():
            errors.extend(check(project))
        return errors
    return checks[category](project)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument(
        "--category", choices=("all", "config", "wordpress", "third-party"), default="all"
    )
    parser.add_argument("--error-format", default="table")
    parser.add_argument("--version", action="store_true")
    args, _unknown = parser.parse_known_args()
    if args.version:
        print("PHPStan 1.12.9 (ParcelPilot offline fixture)")
        return 0

    project = args.project.resolve()
    errors = all_errors(project, args.category)
    if args.error_format == "json":
        print(json.dumps({"totals": {"file_errors": len(errors), "errors": 0}, "errors": errors}))
    elif errors:
        print(" ------ -----------------------------------------------------------------------")
        print("  Line   Finding")
        print(" ------ -----------------------------------------------------------------------")
        for error in errors:
            print(f"  {error}")
        print(" ------ -----------------------------------------------------------------------")
        print(f" [ERROR] Found {len(errors)} error(s)")
    else:
        print(" [OK] No errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
