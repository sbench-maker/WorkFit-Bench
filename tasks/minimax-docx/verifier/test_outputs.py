from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


OUTPUT = Path(os.environ.get("SKILLSBENCH_RESULTS_DIR", "/root/results")).resolve() / "orion_4_8_release_packet.docx"
DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data")).resolve()
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R, "pr": REL}


def qn(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def element_text(node: ET.Element) -> str:
    return "".join(
        child.text or ""
        for child in node.iter()
        if child.tag in {qn(W, "t"), qn(W, "delText"), qn(W, "instrText")}
    )


@dataclass
class ParagraphView:
    text: str
    style_id: str | None


@dataclass
class DocxView:
    parts: dict[str, bytes]
    document: ET.Element
    styles: ET.Element
    settings: ET.Element
    paragraphs: list[ParagraphView]
    visible_text: str


def load_docx(path: Path) -> DocxView:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt ZIP member: {bad}")
        parts = {name: archive.read(name) for name in archive.namelist()}
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/styles.xml",
        "word/settings.xml",
        "word/_rels/document.xml.rels",
    }
    missing = required - set(parts)
    if missing:
        raise ValueError(f"missing required DOCX parts: {sorted(missing)}")
    for name, payload in parts.items():
        if name.endswith(".xml") or name.endswith(".rels"):
            ET.fromstring(payload)
    document = ET.fromstring(parts["word/document.xml"])
    styles = ET.fromstring(parts["word/styles.xml"])
    settings = ET.fromstring(parts["word/settings.xml"])
    paragraphs = []
    for para in document.iter(qn(W, "p")):
        pstyle = para.find("./w:pPr/w:pStyle", NS)
        paragraphs.append(
            ParagraphView(
                text="".join(item.text or "" for item in para.iter(qn(W, "t"))),
                style_id=pstyle.get(qn(W, "val")) if pstyle is not None else None,
            )
        )
    visible_parts = [p.text for p in paragraphs]
    for name, payload in parts.items():
        if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name):
            visible_parts.append(element_text(ET.fromstring(payload)))
    return DocxView(parts, document, styles, settings, paragraphs, "\n".join(visible_parts))


@pytest.fixture(scope="session")
def submission() -> DocxView:
    if not OUTPUT.is_file():
        pytest.skip(f"submitted DOCX is missing: {OUTPUT}")
    try:
        return load_docx(OUTPUT)
    except Exception as exc:
        pytest.skip(f"submitted DOCX cannot be normalized: {exc}")


@pytest.fixture(scope="session")
def facts() -> dict:
    return json.loads((DATA / "release_facts.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def draft() -> DocxView:
    return load_docx(DATA / "draft_change_packet.docx")


@pytest.fixture(scope="session")
def template() -> DocxView:
    return load_docx(DATA / "corporate_release_template.docx")


def style_map(view: DocxView) -> dict[str, dict]:
    result = {}
    for style in view.styles.findall("w:style", NS):
        style_id = style.get(qn(W, "styleId"))
        name_node = style.find("w:name", NS)
        if not style_id or name_node is None:
            continue
        name = name_node.get(qn(W, "val"), "")
        outline = style.find("w:pPr/w:outlineLvl", NS)
        size = style.find("w:rPr/w:sz", NS)
        color = style.find("w:rPr/w:color", NS)
        bold = style.find("w:rPr/w:b", NS)
        borders = sorted(
            (node.tag.rsplit("}", 1)[-1], node.get(qn(W, "val")), node.get(qn(W, "color")))
            for node in style.findall(".//w:tblBorders/*", NS)
        )
        fills = sorted(
            node.get(qn(W, "fill"), "").upper()
            for node in style.findall(".//w:shd", NS)
        )
        result[style_id] = {
            "name": norm(name),
            "type": style.get(qn(W, "type")),
            "outline": outline.get(qn(W, "val")) if outline is not None else None,
            "size": size.get(qn(W, "val")) if size is not None else None,
            "color": color.get(qn(W, "val"), "").upper() if color is not None else None,
            "bold": bold is not None,
            "borders": borders,
            "fills": fills,
        }
    return result


def paragraph_styles_by_text(view: DocxView) -> dict[str, str | None]:
    return {norm(item.text): item.style_id for item in view.paragraphs if item.text.strip()}


def style_semantics(value: dict) -> tuple:
    return (
        value["type"],
        value["outline"],
        value["size"],
        value["color"],
        value["bold"],
        tuple(value["borders"]),
        tuple(value["fills"]),
    )


def tagged_lines(view: DocxView, prefix: str) -> set[str]:
    pattern = re.compile(rf"^{re.escape(prefix)}-\d{{2}}\s+-\s+.+$", re.I)
    return {norm(item.text) for item in view.paragraphs if pattern.match(item.text.strip())}


def section_layouts(view: DocxView) -> list[dict[str, str | None]]:
    layouts = []
    for sect in view.document.iter(qn(W, "sectPr")):
        size = sect.find("w:pgSz", NS)
        mar = sect.find("w:pgMar", NS)
        layouts.append({
            "w": size.get(qn(W, "w")) if size is not None else None,
            "h": size.get(qn(W, "h")) if size is not None else None,
            "orient": size.get(qn(W, "orient")) if size is not None else None,
            "top": mar.get(qn(W, "top")) if mar is not None else None,
            "right": mar.get(qn(W, "right")) if mar is not None else None,
            "bottom": mar.get(qn(W, "bottom")) if mar is not None else None,
            "left": mar.get(qn(W, "left")) if mar is not None else None,
            "header": mar.get(qn(W, "header")) if mar is not None else None,
            "footer": mar.get(qn(W, "footer")) if mar is not None else None,
        })
    return layouts


def header_footer_semantics(view: DocxView) -> tuple[str, str]:
    headers = []
    footers = []
    for name, payload in view.parts.items():
        if re.fullmatch(r"word/header\d+\.xml", name):
            headers.append(element_text(ET.fromstring(payload)))
        elif re.fullmatch(r"word/footer\d+\.xml", name):
            footers.append(element_text(ET.fromstring(payload)))
    return norm(" ".join(headers)), norm(" ".join(footers))


def test_artifact_integrity() -> None:
    assert OUTPUT.is_file(), (
        "the requested Word packet is missing, so release reviewers have no deliverable"
    )
    assert OUTPUT.stat().st_size > 5000, (
        "the submitted file is too small to contain the requested packet and template assets"
    )
    view = load_docx(OUTPUT)
    has_header = any(re.fullmatch(r"word/header\d+\.xml", name) for name in view.parts)
    has_footer = any(re.fullmatch(r"word/footer\d+\.xml", name) for name in view.parts)
    has_theme = any(re.fullmatch(r"word/theme/theme\d+\.xml", name) for name in view.parts)
    assert has_header and has_footer and has_theme, (
        "the DOCX omits header, footer, or theme parts needed for a usable corporate packet"
    )
    assert len(norm(view.visible_text)) > 1500, (
        "the readable document content is too sparse to contain the release procedure"
    )


@pytest.mark.parametrize("group", ["identity", "components", "monitoring", "artifact"])
def test_release_fact_accuracy(submission: DocxView, facts: dict, group: str) -> None:
    text = norm(submission.visible_text)
    release = facts["release"]
    if group == "identity":
        expected = [
            release["release_id"],
            release["version"],
            release["change_ticket"],
            release["environment"],
            release["deployment_window_utc"],
            release["change_freeze_cutoff_utc"],
        ]
        missing = [item for item in expected if norm(item) not in text]
        assert not missing, f"authoritative release identity/timing values are missing: {missing}"
        forbidden = ["4.7.9", "CHG-1981", "2026-09-12 21:00-22:00 UTC", "{{", "[INSERT TABLE OF CONTENTS]", "DRAFT NOTE"]
        present = [item for item in forbidden if norm(item) in text]
        assert not present, f"obsolete or draft-only values remain in the approval packet: {present}"
    elif group == "components":
        for item in facts["components"]:
            for value in (item["service"], item["version"], item["region"]):
                assert norm(value) in text, f"component fact is missing: {value}"
        for obsolete in ("2.13.8", "7.5.0"):
            assert norm(obsolete) not in text, f"obsolete component version remains: {obsolete}"
    elif group == "monitoring":
        monitoring = facts["monitoring"]
        assert norm(monitoring["readiness_endpoint"]) in text, (
            "the exact readiness endpoint, including its query parameters, is missing"
        )
        assert norm(monitoring["observation_period"]) in text, "the authoritative observation period is missing"
        for trigger in monitoring["rollback_triggers"]:
            assert norm(trigger) in text, f"authoritative rollback trigger is missing: {trigger}"
        assert "500 ms for 15 minutes" not in text and "3% for 10 minutes" not in text, (
            "obsolete rollback thresholds remain and could delay a necessary rollback"
        )
    else:
        assert norm(release["artifact_digest"]) in text, (
            "the signed artifact digest is missing or altered, preventing promotion verification"
        )


@pytest.mark.parametrize("group", ["deployment", "verification_rollback", "approvals"])
def test_scope_preservation(submission: DocxView, draft: DocxView, facts: dict, group: str) -> None:
    if group == "deployment":
        expected = tagged_lines(draft, "DEP")
        actual = tagged_lines(submission, "DEP")
        assert actual == expected, (
            f"deployment scope changed; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}"
        )
    elif group == "verification_rollback":
        for prefix in ("VAL", "RB"):
            expected = tagged_lines(draft, prefix)
            actual = tagged_lines(submission, prefix)
            assert actual == expected, (
                f"{prefix} scope changed; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}"
            )
    else:
        text = norm(submission.visible_text)
        for approval in facts["approvals"]:
            required = [approval["role"], approval["name"], approval["status"]]
            if approval["decision_date"]:
                required.append(approval["decision_date"])
            missing = [value for value in required if norm(value) not in text]
            assert not missing, (
                f"approval row for {approval['role']} is incomplete; missing values={missing}"
            )
        assert "site reliability engineering approval remains pending" in text, (
            "the pending SRE decision is not surfaced as a release-blocking approval state"
        )


@pytest.mark.parametrize("group", ["layout", "header_footer", "styles", "navigation"])
def test_template_and_navigation(submission: DocxView, template: DocxView, group: str) -> None:
    if group == "layout":
        expected = section_layouts(template)
        actual = section_layouts(submission)
        assert expected and actual, "page layout properties are missing"
        assert all(layout == expected[-1] for layout in actual), (
            f"one or more output sections do not match the template page setup: expected {expected[-1]}, got {actual}"
        )
    elif group == "header_footer":
        expected_header, expected_footer = header_footer_semantics(template)
        actual_header, actual_footer = header_footer_semantics(submission)
        assert expected_header and expected_header in actual_header, (
            "the corporate production-change header is missing or altered"
        )
        assert "internal - change control" in actual_footer, "the corporate confidentiality footer is missing"
        field_codes = " ".join(
            element_text(ET.fromstring(payload))
            for name, payload in submission.parts.items()
            if re.fullmatch(r"word/footer\d+\.xml", name)
        )
        assert re.search(r"\bPAGE\b", field_codes, re.I), (
            "the footer uses no live PAGE field, so pagination cannot update"
        )
    elif group == "styles":
        expected_styles = {value["name"]: value for value in style_map(template).values()}
        actual_styles_by_id = style_map(submission)
        actual_signatures = {style_semantics(value) for value in actual_styles_by_id.values()}
        for name in (
            "corporate title",
            "corporate heading 1",
            "corporate heading 2",
            "corporate body",
            "corporate risk",
            "corporate table",
        ):
            expected = expected_styles[name]
            assert style_semantics(expected) in actual_signatures, (
                f"no output style is semantically equivalent to the template's {name} style"
            )
        used = paragraph_styles_by_text(submission)
        expected_h1 = style_semantics(expected_styles["corporate heading 1"])
        for heading in ("Change Scope", "Deployment Procedure", "Verification", "Rollback Plan", "Approvals"):
            style_id = used.get(norm(heading))
            assert style_id in actual_styles_by_id, f"heading has no defined paragraph style: {heading}"
            assert style_semantics(actual_styles_by_id[style_id]) == expected_h1, (
                f"heading does not use the template-equivalent level-1 style: {heading}"
            )
        expected_title = style_semantics(expected_styles["corporate title"])
        title_style = used.get(norm("Orion 4.8 Production Change Packet"))
        assert title_style in actual_styles_by_id and style_semantics(actual_styles_by_id[title_style]) == expected_title, (
            "the document title does not use a template-equivalent title style"
        )
        expected_h2 = style_semantics(expected_styles["corporate heading 2"])
        h2_style = used.get(norm("Release Components"))
        assert h2_style in actual_styles_by_id and style_semantics(actual_styles_by_id[h2_style]) == expected_h2, (
            "the component subsection does not use a template-equivalent level-2 style"
        )
        expected_risk = style_semantics(expected_styles["corporate risk"])
        risk_paragraphs = [
            item for item in submission.paragraphs
            if norm(item.text).startswith("rollback warning:")
            or norm(item.text).startswith("the site reliability engineering approval remains pending")
        ]
        assert len(risk_paragraphs) == 2, "the two decision-critical warning paragraphs are not identifiable"
        assert all(
            item.style_id in actual_styles_by_id
            and style_semantics(actual_styles_by_id[item.style_id]) == expected_risk
            for item in risk_paragraphs
        ), "a decision-critical warning does not use the template-equivalent risk style"
        expected_table = style_semantics(expected_styles["corporate table"])
        table_style_ids = [
            node.get(qn(W, "val"))
            for node in submission.document.findall(".//w:tbl/w:tblPr/w:tblStyle", NS)
        ]
        assert table_style_ids and all(
            style_id in actual_styles_by_id
            and style_semantics(actual_styles_by_id[style_id]) == expected_table
            for style_id in table_style_ids
        ), "one or more output tables do not use a template-equivalent table style"
    else:
        instruction_text = " ".join(
            node.text or "" for node in submission.document.iter(qn(W, "instrText"))
        )
        assert re.search(r"\bTOC\b", instruction_text, re.I), (
            "the contents area is static text rather than an updateable Word TOC field"
        )
        update = submission.settings.find("w:updateFields", NS)
        assert update is not None and update.get(qn(W, "val"), "true").casefold() not in {"false", "0", "off"}, (
            "Word is not instructed to update the table of contents when the packet opens"
        )
        styles = style_map(submission)
        outline_levels = {
            styles[item.style_id]["outline"]
            for item in submission.paragraphs
            if item.style_id in styles and styles[item.style_id]["outline"] is not None
        }
        assert {"0", "1"}.issubset(outline_levels), (
            "the packet lacks a usable level-1/level-2 heading hierarchy for navigation"
        )
