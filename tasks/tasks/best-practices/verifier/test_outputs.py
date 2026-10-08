from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
SOURCE = DATA_ROOT / "site"
SITE = RESULTS_ROOT / "hardened_site"
REPORT_PATH = RESULTS_ROOT / "security_audit.json"
ROUTES = ("index.html", "activity.html", "settings.html")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def report_payload():
    return json.loads(read(REPORT_PATH))


def scalar_text(value) -> str:
    parts: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                parts.append(str(key))
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif node is not None:
            parts.append(str(node))

    walk(value)
    return " ".join(parts).lower()


FINDING_KEYS = {"finding", "findings", "issue", "issues", "vulnerability", "vulnerabilities", "results", "items"}


def extract_findings(payload) -> list[dict]:
    candidates: list[list[dict]] = []

    def walk(node, parent_key="") -> None:
        if isinstance(node, list):
            dict_rows = [item for item in node if isinstance(item, dict)]
            if dict_rows and (parent_key.lower() in FINDING_KEYS or len(dict_rows) >= 3):
                candidates.append(dict_rows)
            for item in node:
                walk(item, parent_key)
        elif isinstance(node, dict):
            for key, item in node.items():
                walk(item, str(key))

    walk(payload)
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        candidates.append(payload)
    if not candidates:
        return []
    return max(candidates, key=len)


class PageInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.ids: list[str] = []
        self.text: list[str] = []
        self.lang = ""
        self.head_first_element = ""
        self.in_head = False
        self.viewport = False
        self.charset = False
        self.invalid: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        values = {str(key).lower(): (value or "") for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "head":
            self.in_head = True
        elif self.in_head and not self.head_first_element:
            self.head_first_element = tag
        if tag == "meta":
            self.charset = self.charset or values.get("charset", "").lower().replace("-", "") == "utf8"
            self.viewport = self.viewport or values.get("name", "").lower() == "viewport"
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "button" and "a" in self.stack:
            self.invalid.append("button nested in link")
        if self.stack and self.stack[-1] in {"ul", "ol"} and tag != "li":
            self.invalid.append(f"{tag} is a direct child of {self.stack[-1]}")
        if tag not in {"meta", "link", "img", "input", "br", "hr", "source"}:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "head":
            self.in_head = False
        if tag in self.stack:
            while self.stack:
                current = self.stack.pop()
                if current == tag:
                    break

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.text.append(value)


def inspect_page(path: Path) -> PageInspector:
    parser = PageInspector()
    parser.feed(read(path))
    return parser


def all_code(suffixes=(".html", ".js", ".css", ".conf")) -> str:
    return "\n".join(read(path) for path in sorted(SITE.rglob("*")) if path.suffix.lower() in suffixes)


def js_code() -> str:
    return "\n".join(read(path) for path in sorted(SITE.rglob("*.js")))


def test_artifacts_are_readable():
    assert SITE.is_dir(), "the requested hardened_site directory is missing"
    assert REPORT_PATH.is_file(), "the requested security_audit.json is missing"
    try:
        payload = report_payload()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"security_audit.json is not readable JSON: {exc}")
    findings = extract_findings(payload)
    assert findings, "the audit has no recognizable collection of material findings"
    for route in ROUTES:
        assert (SITE / route).is_file(), f"the hardened copy dropped route {route}"


def test_user_visible_contract_is_preserved():
    required = [
        "data/activity.json",
        "deploy/headers.conf",
        "deploy/edge_snapshot.json",
        "js/app.js",
        "js/activity.js",
        "js/settings.js",
        "styles/base.css",
        "assets/harbor-mark.svg",
        "js/vendor/chartlite-1.4.2.js",
    ]
    missing = [relative for relative in required if not (SITE / relative).is_file()]
    assert not missing, f"the hardened site dropped contract files: {missing}"
    assert json.loads(read(SITE / "data/activity.json")) == json.loads(read(SOURCE / "data/activity.json")), (
        "the 240-record activity feed was changed or truncated"
    )
    expected_text = {
        "index.html": ("Harborlight Partner Console", "Open activity", "Account settings"),
        "activity.html": ("Recent activity", "Filter activity", "Console home"),
        "settings.html": ("Location-aware timezone", "Use my location", "Account settings"),
    }
    for route, phrases in expected_text.items():
        visible = " ".join(inspect_page(SITE / route).text).lower()
        for phrase in phrases:
            assert phrase.lower() in visible, f"{route} no longer exposes user-visible behavior text {phrase!r}"
    app = read(SITE / "js/app.js").lower()
    activity = read(SITE / "js/activity.js").lower()
    settings = read(SITE / "js/settings.js").lower()
    assert "name" in app and "summary-chart" in app and "activity.json" in app, "home greeting or chart behavior was dropped"
    assert "activity.json" in activity and "filter" in activity and "input" in activity and "q" in activity, "activity loading or filtering was dropped"
    assert "geolocation" in settings and "use-location" in settings and "click" in settings, "user-triggered timezone detection was dropped"


def test_content_injection_defenses():
    code = js_code()
    assert not re.search(r"\beval\s*\(|\bnew\s+Function\s*\(", code), "dynamic code execution remains in the hardened JavaScript"
    raw_sinks = re.findall(r"(?:\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML\s*\()", code, re.I)
    if raw_sinks:
        sanitized = re.search(r"DOMPurify\.sanitize|sanitizeHTML|escapeHTML|createHTML\s*\(", code, re.I)
        assert sanitized, (
            "HTML execution sinks remain without an observable sanitizer or Trusted Types policy"
        )
    adversarial = json.loads(read(SITE / "data/activity.json"))
    assert any("<script>" in row["detail"] for row in adversarial), "the security edge-case records were removed instead of handled"


def test_active_resources_transport_and_integrity():
    violations: list[str] = []
    tag_pattern = re.compile(r"<(script|link)\b([^>]*)>", re.I)
    attr_pattern = re.compile(r"([\w-]+)\s*=\s*(['\"])(.*?)\2", re.S)
    for page_path in sorted(SITE.rglob("*.html")):
        for tag, body in tag_pattern.findall(read(page_path)):
            attrs = {name.lower(): value.strip() for name, _, value in attr_pattern.findall(body)}
            url = attrs.get("src") or attrs.get("href")
            if not url or url.startswith(("data:", "#")):
                continue
            if url.startswith("//") or url.lower().startswith("http://"):
                violations.append(f"{page_path.name}: insecure {url}")
                continue
            if url.lower().startswith("https://"):
                parsed = urlparse(url)
                pinned = bool(re.search(r"(?:@|/|[-_.])v?\d+\.\d+(?:\.\d+)?(?:/|[-_.])", parsed.path))
                if not (attrs.get("integrity", "").startswith(("sha256-", "sha384-", "sha512-")) and attrs.get("crossorigin") and pinned):
                    violations.append(f"{page_path.name}: remote active resource is not pinned with SRI: {url}")
    css_js = all_code((".css", ".js"))
    insecure_literals = re.findall(r"(?<!:)//[a-z0-9.-]+|http://[^\s'\")]+", css_js, re.I)
    assert not violations and not insecure_literals, f"insecure or mutable active resources remain: {violations + insecure_literals}"


def test_response_security_policy():
    config_files = [path for path in SITE.rglob("*") if path.suffix.lower() in {".conf", ".toml", ".json"}]
    policy = "\n".join(read(path) for path in config_files).lower()
    csp_matches = re.findall(r"content-security-policy(?!-report-only)[^\n]*", policy)
    assert csp_matches, "no enforced Content-Security-Policy is configured"
    csp = " ".join(csp_matches)
    for directive in ("default-src", "script-src", "frame-ancestors", "base-uri", "form-action"):
        assert directive in csp, f"the enforced CSP lacks {directive}"
    assert "'unsafe-eval'" not in csp and "'unsafe-inline'" not in csp, "the enforced CSP still permits unsafe script/style execution"
    assert re.search(r"strict-transport-security[^\n]*max-age\s*=\s*(?:31536000|[4-9]\d{7,}|\d{9,})", policy), "HSTS is missing or shorter than one year"
    assert "includesubdomains" in policy, "HSTS does not cover subdomains"
    assert re.search(r"x-content-type-options[^\n]*nosniff", policy), "MIME-sniffing protection is missing"
    assert re.search(r"referrer-policy[^\n]*strict-origin-when-cross-origin", policy), "the referrer policy is not privacy-preserving"
    assert "permissions-policy" in policy and "camera=()" in policy and "microphone=()" in policy, "powerful unused browser features are not denied"
    assert "x-xss-protection" not in policy, "the deprecated X-XSS-Protection header is still sent"


def test_location_permission_is_contextual():
    code = read(SITE / "js/settings.js")
    geo = code.find("getCurrentPosition")
    assert geo >= 0, "location-aware timezone behavior was removed"
    direct_callback = re.search(r"addEventListener\s*\(\s*['\"]click['\"][\s\S]{0,1800}getCurrentPosition", code, re.I)
    named = re.search(r"addEventListener\s*\(\s*['\"]click['\"]\s*,\s*([A-Za-z_$][\w$]*)", code)
    named_callback = False
    if named:
        handler = re.escape(named.group(1))
        named_callback = bool(re.search(rf"(?:function\s+{handler}|(?:const|let|var)\s+{handler}\s*=)[\s\S]{{0,1200}}getCurrentPosition", code))
    assert direct_callback or named_callback, "geolocation is not gated by the user's click"
    assert re.search(r"confirm\s*\(|permission|explain|consent|allow location", code, re.I), "the location request has no contextual explanation or confirmation"


@pytest.mark.parametrize("route", ROUTES)
def test_html5_documents_are_modern_and_valid(route):
    path = SITE / route
    raw = read(path)
    page = inspect_page(path)
    assert re.match(r"\s*<!doctype\s+html\s*>", raw, re.I), f"{route} lacks an HTML5 doctype"
    assert page.lang, f"{route} lacks a document language"
    assert page.head_first_element == "meta" and page.charset, f"{route} does not declare UTF-8 first in head"
    assert page.viewport, f"{route} lacks a responsive viewport"
    duplicates = {item for item in page.ids if page.ids.count(item) > 1}
    assert not duplicates, f"{route} has duplicate IDs: {sorted(duplicates)}"
    assert not page.invalid, f"{route} has invalid interactive or list nesting: {page.invalid}"


def test_modern_runtime_and_production_output():
    code = js_code()
    assert not re.search(r"navigator\.(?:userAgent|vendor|appVersion)", code, re.I), "browser-name sniffing remains"
    assert not re.search(r"document\.write\s*\(", code, re.I), "parser-blocking document.write remains"
    assert not re.search(r"\.open\s*\([^\n]*,\s*false\s*\)", code), "synchronous XHR remains"
    assert not re.search(r"console\.(?:log|debug|info|warn|error)\s*\(", code), "production console logging remains"
    config = read(SITE / "vite.config.js").lower()
    assert re.search(r"sourcemap\s*:\s*(?:false|['\"]hidden['\"])", config), "production source maps remain publicly exposed"
    for match in re.finditer(r"addEventListener\s*\(\s*['\"](?:wheel|touchstart|touchmove)['\"]([^;]*)", code, re.I):
        assert re.search(r"passive\s*:\s*true", match.group(0), re.I), "a scroll/touch listener is not explicitly passive"


ISSUE_FAMILIES = [
    ("dom_xss", (r"dom.?xss|cross.site scripting|untrusted", r"innerhtml|html sink|textcontent|dom")),
    ("csp", (r"content.security.policy|\bcsp\b", r"unsafe.inline|unsafe.eval|trusted types|frame.ancestors")),
    ("mixed_content", (r"mixed content|http resource|non.https|scheme.relative",)),
    ("third_party_integrity", (r"subresource integrity|\bsri\b|supply.chain|unpinned third.party|remote script",)),
    ("security_headers", (r"security header|strict.transport.security|\bhsts\b|nosniff|referrer.policy",)),
    ("document_metadata", (r"doctype|charset|viewport|document metadata",)),
    ("invalid_html", (r"duplicate id|invalid (?:html|nesting)|semantic html|list nesting",)),
    ("document_write", (r"document\.write|parser.blocking",)),
    ("browser_detection", (r"user.agent|browser (?:sniff|detect)|feature detect",)),
    ("permission_timing", (r"geolocation|location permission|permission.*page load",)),
    ("errors_console", (r"console log|console logging|error handling|fetch failure|silent.*fail",)),
    ("source_maps", (r"source map|sourcemap|sourcescontent",)),
    ("cookie_policy", (r"httponly|session cookie|cookie.*script",)),
]


def matching_finding(family_patterns: tuple[str, ...], findings: list[dict]) -> dict | None:
    for item in findings:
        text = scalar_text(item)
        if all(re.search(pattern, text, re.I) for pattern in family_patterns):
            return item
    return None


@pytest.mark.parametrize("family,patterns", ISSUE_FAMILIES, ids=[row[0] for row in ISSUE_FAMILIES])
def test_audit_material_findings_coverage(family, patterns):
    findings = extract_findings(report_payload())
    assert matching_finding(patterns, findings) is not None, f"the audit omits the material {family} issue evidenced by the snapshot"


def test_audit_evidence_and_dispositions():
    payload = report_payload()
    findings = extract_findings(payload)
    matched = [matching_finding(patterns, findings) for _, patterns in ISSUE_FAMILIES]
    assert all(matched), "material findings must be present before their evidence and disposition can be checked"
    for item in matched:
        assert item is not None
        text = scalar_text(item)
        keys = {str(key).lower() for key in item}
        assert re.search(r"(?:[\w-]+/)*[\w-]+\.(?:html|js|css|conf|json)", text), f"finding lacks file evidence: {item}"
        assert "location" in keys or re.search(r"\bline(?:s)?\s*\d|:\d+|\bhead\b|\bblock\b|\bconfig", text), f"finding lacks a usable location: {item}"
        assert keys.intersection({"status", "state", "disposition", "resolution"}) or re.search(r"\bfixed\b|\bresolved\b|\bopen\b|operational|pending", text), f"finding does not say whether it was fixed or remains open: {item}"
    cookie = matching_finding(ISSUE_FAMILIES[-1][1], findings)
    cookie_text = scalar_text(cookie)
    assert re.search(r"operational|open|pending|unresolved|external|decision", cookie_text), "the externally owned HttpOnly gap is incorrectly presented as a repository fix"
    full = scalar_text(payload)
    assert re.search(r"fixed|resolved|remediated", full) and re.search(r"operational|open|pending|decision", full), "the report does not distinguish fixed work from the operational decision"
