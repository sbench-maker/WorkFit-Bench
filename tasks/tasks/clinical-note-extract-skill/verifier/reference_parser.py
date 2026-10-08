#!/usr/bin/env python3
"""Reference abstraction for the deterministic fictional PFT note fixture."""

from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
import re
from typing import Any


DATA = Path("/root/data")
OUTPUT = Path("/root/results/output.json")


def section_for(text: str, span: str) -> str:
    pos = text.index(span)
    section = "header"
    for line in text[:pos].splitlines():
        if line in {"HISTORY", "PFT LAB", "INTERPRETATION", "ASSESSMENT"}:
            section = line
    return section


def date_ok(value: str) -> bool:
    try:
        if re.fullmatch(r"\d{4}", value):
            return True
        if re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = map(int, value.split("-"))
            return 1 <= month <= 12 and year > 0
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def range_flag(value: float, unit: str | None, check: dict[str, Any]) -> str | None:
    if check.get("unit") and unit != check["unit"]:
        return "unit_mismatch"
    if value < check["min"]:
        return "below_min"
    if value > check["max"]:
        return "above_max"
    return None


def populated(
    text: str,
    value: Any,
    span: str,
    *,
    unit: str | None = None,
    axes: dict[str, str] | None = None,
    check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "value": value,
        "span": span,
        "location": section_for(text, span),
        "span_verified": span in text,
    }
    if unit is not None:
        row["unit"] = unit
    if axes:
        row.update(axes)
    if check:
        if check["kind"] == "range":
            row["range_flag"] = range_flag(float(value), unit, check)
        elif check["kind"] == "date":
            row["date_ok"] = date_ok(str(value))
        elif check["kind"] == "terminology":
            row["code_status"] = "unvalidated"
    return row


def null_field(reason: str, text: str, span: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"value": None, "null_reason": reason}
    if span is not None:
        row.update({"span": span, "location": section_for(text, span)})
    return row


def line_starting(text: str, prefix: str) -> str | None:
    return next((line for line in text.splitlines() if line.startswith(prefix)), None)


def extract_note(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}

    date_line = line_starting(text, "Date of Service:")
    assert date_line
    date_value = date_line.split(":", 1)[1].strip()
    fields["test_date"] = populated(text, date_value, date_line, check=schema["test_date"]["check"])

    fev1_line = line_starting(text, "FEV1:")
    assert fev1_line
    fev1_match = re.search(r"post ([0-9.]+) (L|mL); post ([0-9.]+) % predicted", fev1_line)
    assert fev1_match
    fields["fev1_liters"] = populated(
        text,
        float(fev1_match.group(1)),
        fev1_line,
        unit=fev1_match.group(2),
        check=schema["fev1_liters"]["check"],
    )
    fields["fev1_percent_predicted"] = populated(
        text,
        float(fev1_match.group(3)),
        fev1_line,
        unit="%",
        check=schema["fev1_percent_predicted"]["check"],
    )

    fvc_line = line_starting(text, "FVC:")
    assert fvc_line
    fvc_match = re.search(r"post ([0-9.]+) (L|mL); post ([0-9.]+) % predicted", fvc_line)
    assert fvc_match
    fields["fvc_liters"] = populated(
        text,
        float(fvc_match.group(1)),
        fvc_line,
        unit=fvc_match.group(2),
        check=schema["fvc_liters"]["check"],
    )
    fields["fvc_percent_predicted"] = populated(
        text,
        float(fvc_match.group(3)),
        fvc_line,
        unit="%",
        check=schema["fvc_percent_predicted"]["check"],
    )

    ratio_line = line_starting(text, "FEV1/FVC:")
    assert ratio_line
    ratio_value = float(re.search(r"post ([0-9]+(?:\.[0-9]+)?)", ratio_line).group(1))
    fields["fev1_fvc_ratio"] = populated(
        text, ratio_value, ratio_line, check=schema["fev1_fvc_ratio"]["check"]
    )

    dlco_line = line_starting(text, "DLCO:")
    if dlco_line is None:
        fields["dlco_percent_predicted"] = null_field("not_mentioned", text)
    elif "[REDACTED]" in dlco_line:
        fields["dlco_percent_predicted"] = null_field("redacted", text, dlco_line)
    elif "not measured" in dlco_line:
        fields["dlco_percent_predicted"] = null_field("mentioned_unclear", text, dlco_line)
    else:
        dlco_value = float(re.search(r"DLCO: ([0-9.]+)", dlco_line).group(1))
        fields["dlco_percent_predicted"] = populated(
            text,
            dlco_value,
            dlco_line,
            unit="%",
            check=schema["dlco_percent_predicted"]["check"],
        )

    response_line = line_starting(text, "Bronchodilator response:")
    assert response_line
    response_axes: dict[str, str] = {}
    if "no significant" in response_line:
        response_axes["presence"] = "absent"
    elif "possible significant" in response_line:
        response_axes["presence"] = "possible"
    fields["bronchodilator_response"] = populated(
        text, "significant bronchodilator response", response_line, axes=response_axes
    )

    interpretation_line = line_starting(text, "Interpretation:")
    assert interpretation_line
    lower_interp = interpretation_line.lower()
    pattern = next(item for item in ("obstructive", "restrictive", "mixed", "normal") if item in lower_interp)
    severity = next(
        item
        for item in ("moderately severe", "severe", "moderate", "mild", "normal")
        if item in lower_interp
    )
    fields["interpretation_pattern"] = populated(text, pattern, interpretation_line)
    fields["interpretation_severity"] = populated(text, severity, interpretation_line)

    oxygen_line = line_starting(text, "Home oxygen:")
    if oxygen_line is None:
        fields["home_oxygen"] = null_field("not_mentioned", text)
    else:
        oxygen_axes: dict[str, str] = {}
        if "not in use" in oxygen_line or "no longer in use" in oxygen_line:
            oxygen_axes["presence"] = "absent"
        elif "consider if" in oxygen_line:
            oxygen_axes["temporality"] = "hypothetical"
        fields["home_oxygen"] = populated(text, "home oxygen", oxygen_line, axes=oxygen_axes)

    chest_line = line_starting(text, "Chest pain:")
    if chest_line is None:
        fields["current_chest_pain"] = null_field("not_mentioned", text)
    else:
        chest_axes: dict[str, str] = {}
        if "denies" in chest_line:
            chest_axes["presence"] = "absent"
        elif "possible" in chest_line:
            chest_axes["presence"] = "possible"
        elif "monitor for" in chest_line:
            chest_axes["temporality"] = "hypothetical"
        fields["current_chest_pain"] = populated(text, "chest pain", chest_line, axes=chest_axes)

    family_line = line_starting(text, "Family history:")
    if family_line is None:
        fields["family_emphysema"] = null_field("not_mentioned", text)
    else:
        family_axes = {"experiencer": "family_member"}
        if "no family history" in family_line or "denied" in family_line:
            family_axes["presence"] = "absent"
        if "may have had" in family_line:
            family_axes["presence"] = "possible"
            family_axes["temporality"] = "historical"
        if "prior" in family_line:
            family_axes["temporality"] = "historical"
        fields["family_emphysema"] = populated(text, "emphysema", family_line, axes=family_axes)

    diagnosis_line = line_starting(text, "Primary pulmonary diagnosis:")
    if diagnosis_line is None:
        fields["primary_pulmonary_diagnosis"] = null_field("not_mentioned", text)
    elif "[REDACTED]" in diagnosis_line:
        fields["primary_pulmonary_diagnosis"] = null_field("redacted", text, diagnosis_line)
    else:
        diagnosis = diagnosis_line.split(":", 1)[1].strip().rsplit(" (", 1)[0]
        fields["primary_pulmonary_diagnosis"] = populated(
            text,
            diagnosis,
            diagnosis_line,
            check=schema["primary_pulmonary_diagnosis"]["check"],
        )

    smoking_line = line_starting(text, "Smoking:")
    if smoking_line is None:
        fields["smoking_cessation_date"] = null_field("not_mentioned", text)
    elif "[REDACTED]" in smoking_line:
        fields["smoking_cessation_date"] = null_field("redacted", text, smoking_line)
    else:
        raw_value = smoking_line.removeprefix("Smoking: quit ").removesuffix(".")
        month_match = re.fullmatch(r"June (\d{4})", raw_value)
        value = f"{month_match.group(1)}-06" if month_match else raw_value
        fields["smoking_cessation_date"] = populated(
            text, value, smoking_line, check=schema["smoking_cessation_date"]["check"]
        )
    return fields


def build_output(data_dir: Path = DATA) -> dict[str, Any]:
    readme = (data_dir / "README.md").read_text(encoding="utf-8")
    generation = json.loads((data_dir / "generation_notes.json").read_text(encoding="utf-8"))
    assert "fictional" in readme.lower() and generation.get("fictional") is True
    schema = json.loads((data_dir / "extraction_schema.json").read_text(encoding="utf-8"))
    with (data_dir / "note_index.csv").open(encoding="utf-8", newline="") as handle:
        inventory = list(csv.DictReader(handle))
    assert generation["note_files"] == len(inventory)
    assert generation["schema_fields"] == len(schema)

    records: list[dict[str, Any]] = []
    for item in inventory:
        text = (data_dir / "notes" / item["filename"]).read_text(encoding="utf-8")
        if text.count("PULMONARY FOLLOW-UP NOTE") != 1:
            records.append(
                {
                    "note_id": item["note_id"],
                    "refusal": True,
                    "reason": "source file contains multiple clinical notes",
                }
            )
            continue
        records.append({"note_id": item["note_id"], "fields": extract_note(text, schema)})

    valid_records = [row for row in records if not row.get("refusal")]
    all_fields = [field for row in valid_records for field in row["fields"].values()]
    nulls = [field for field in all_fields if field.get("value") is None]
    populated_fields = [field for field in all_fields if field.get("value") is not None]
    reason_counts: dict[str, int] = {}
    for field in nulls:
        reason = field["null_reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    flags: list[dict[str, Any]] = []
    for record in valid_records:
        for field_name, field in record["fields"].items():
            if field.get("range_flag"):
                flags.append(
                    {
                        "note_id": record["note_id"],
                        "field": field_name,
                        "kind": "range",
                        "detail": field["range_flag"],
                    }
                )
            if field.get("date_ok") is False:
                flags.append(
                    {
                        "note_id": record["note_id"],
                        "field": field_name,
                        "kind": "date",
                        "detail": "invalid",
                    }
                )
    flags.append(
        {
            "note_id": "PN-024",
            "kind": "refusal",
            "detail": "multiple clinical notes in one source file",
        }
    )
    terminology_unvalidated = sum(
        field.get("code_status") == "unvalidated" for field in populated_fields
    )
    if terminology_unvalidated:
        flags.append(
            {
                "kind": "terminology_unvalidated",
                "system": "icd10cm",
                "count": terminology_unvalidated,
            }
        )

    validation = {
        "span_passed": sum(field.get("span_verified") is True for field in populated_fields),
        "span_failed": sum(field.get("span_verified") is False for field in populated_fields),
        "range_passed": sum("range_flag" in field and field["range_flag"] is None for field in populated_fields),
        "range_flagged": sum(bool(field.get("range_flag")) for field in populated_fields),
        "date_passed": sum(field.get("date_ok") is True for field in populated_fields),
        "date_flagged": sum(field.get("date_ok") is False for field in populated_fields),
        "terminology_unvalidated": terminology_unvalidated,
    }
    summary = {
        "notes_requested": len(inventory),
        "notes_completed": len(valid_records),
        "notes_refused": len(records) - len(valid_records),
        "fields_requested": len(inventory) * len(schema),
        "field_slots_processed": len(all_fields),
        "populated": len(populated_fields),
        "null": len(nulls),
        "null_reasons": reason_counts,
        "validation": validation,
        "flags": flags,
    }
    return {"records": records, "reviewer_summary": summary}


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_output(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
