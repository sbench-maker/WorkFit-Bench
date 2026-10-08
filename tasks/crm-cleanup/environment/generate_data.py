#!/usr/bin/env python3
"""Generate the deterministic fictional CRM export used by this task."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


OUT = Path(__file__).resolve().parent / "data"
AS_OF = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    first_names = [
        "Avery", "Blake", "Casey", "Drew", "Elliot", "Finley", "Gray", "Harper",
        "Indigo", "Jordan", "Kai", "Logan", "Morgan", "Noel", "Oakley", "Parker",
        "Quinn", "Reese", "Sage", "Taylor", "Uma", "Val", "Winter", "Zion",
    ]
    last_names = [
        "Arden", "Bennett", "Calder", "Dalton", "Ellis", "Foster", "Gibson", "Hale",
        "Ibarra", "Jensen",
    ]
    company_leads = [
        "Amber", "Blue", "Cedar", "Delta", "Ember", "Fox", "Granite", "Harbor", "Ivory", "Juniper",
    ]
    company_tails = ["Works", "Labs", "Supply", "Systems", "Studio"]
    companies = [f"{lead} {tail}" for lead in company_leads for tail in company_tails]

    contacts: list[dict] = []
    for i in range(1, 241):
        first = first_names[(i - 1) % len(first_names)]
        last = last_names[(i - 1) // len(first_names)]
        company = companies[(i * 17) % len(companies)]
        contacts.append(
            {
                "contact_id": f"C{i:04d}",
                "first_name": first,
                "last_name": last,
                "email": "" if i % 37 == 0 else f"{first.lower()}.{last.lower()}{i}@example.test",
                "company": "" if i % 41 == 0 else company,
                "phone": "" if i % 13 == 0 else f"+1-555-{100 + i // 100:03d}-{i % 10000:04d}",
                "owner_id": f"U{1 + (i % 7):03d}",
                "created_at": iso(AS_OF - timedelta(days=540 - (i % 400))),
                "updated_at": iso(AS_OF - timedelta(days=i % 63, hours=i % 20)),
            }
        )

    by_contact = {row["contact_id"]: row for row in contacts}
    duplicate_overrides = {
        "C0011": ("Nora", "Voss", "nora.voss@sample.test", "Cobalt Grid", "+1-555-210-1011"),
        "C0211": ("Nora", "Voss", " NORA.VOSS@sample.test ", "Cobalt Grid", ""),
        "C0024": ("Imani", "Pike", "imani.pike@sample.test", "Northstar Fabrication", ""),
        "C0224": ("Imani", "Pike", "IMANI.PIKE@sample.test", "Northstar Fabrication", "+1-555-210-2224"),
        "C0037": ("Alex", "Rivera", "alex.r37@sample.test", "Orchid Signal", "+1-555-210-0037"),
        "C0237": ("Alexander", "Rivera", "alexander.r@sample.test", "Orchid Signal", ""),
        "C0052": ("Mia", "Chen", "mia.chen52@sample.test", "Pioneer Harbor", ""),
        "C0202": ("Mia ", " Chen", "mia.c202@sample.test", "Pioneer Harbor", "+1-555-210-0202"),
        "C0079": ("Leila", "Stone", "leila.stone@sample.test", "Quartz Grove", "+1-555-210-0079"),
        "C0179": ("Leila", "Stone", "LEILA.STONE@sample.test", "Quartz Grove", "+1-555-210-0179"),
        "C0105": ("Robert", "O'Neil", "robert.oneil@sample.test", "Redwood Transit", "+1-555-210-0105"),
        "C0155": ("Bob", "O’Neil", "bob.oneil@sample.test", "Redwood Transit", ""),
        "C0064": ("Priya", "Nolan", "priya.nolan@sample.test", "Silverline Foods", "+1-555-210-0064"),
        "C0164": ("Priya", "Nolan", "PRIYA.NOLAN@sample.test", "Silverline Foods", ""),
        "C0234": ("P.", "Nolan", "priya.nolan@sample.test", "Silverline Foods", "+1-555-210-0234"),
    }
    for contact_id, values in duplicate_overrides.items():
        row = by_contact[contact_id]
        row.update(dict(zip(("first_name", "last_name", "email", "company", "phone"), values)))

    # Deliberate near-matches that must not be treated as duplicates.
    by_contact["C0090"].update(
        {"first_name": "Sam", "last_name": "Lee", "email": "sam.lee90@sample.test", "company": "Atlas Forge"}
    )
    by_contact["C0190"].update(
        {"first_name": "Sam", "last_name": "Lee", "email": "sam.lee190@sample.test", "company": "Birch Medical"}
    )
    by_contact["C0091"].update(
        {"first_name": "Dana", "last_name": "Mills", "email": "dana.mills@sample.test", "company": "Atlas Forge"}
    )
    by_contact["C0191"].update(
        {"first_name": "Dana", "last_name": "Miles", "email": "dana.miles@sample.test", "company": "Atlas Forge"}
    )

    stages = ["qualification", "discovery", "proposal", "negotiation"]
    deals: list[dict] = []
    for i in range(1, 121):
        status = "open" if i <= 90 else ("won" if i % 2 else "lost")
        stage = stages[(i - 1) % len(stages)]
        if status == "open" and i % 29 == 0:
            stage = ""
        amount = "" if status == "open" and i % 17 == 0 else str(3500 + (i * 1375) % 92000)
        if i == 34:
            amount = "0"
        close_date = "" if status == "open" and i % 19 == 0 else (AS_OF.date() + timedelta(days=7 + i % 70)).isoformat()
        next_step = "" if i % 11 == 0 else [
            "Confirm evaluation team", "Send pricing revision", "Book technical review", "Validate procurement path"
        ][i % 4]
        notes = "" if i % 11 == 0 or i % 5 == 0 else f"Owner note for account cycle {i % 9}."
        deals.append(
            {
                "deal_id": f"D{i:04d}",
                "deal_name": f"{companies[(i * 11) % len(companies)]} - Expansion {i:03d}",
                "pipeline_status": status,
                "deal_stage": stage,
                "amount": amount,
                "currency": "USD",
                "close_date": close_date,
                "next_step": next_step,
                "notes": notes,
                "owner_id": f"U{1 + (i % 7):03d}",
                "created_at": iso(AS_OF - timedelta(days=120 + i)),
            }
        )

    associations: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    def associate(deal_num: int, contact_num: int, role: str = "decision_maker") -> None:
        pair = (f"D{deal_num:04d}", f"C{contact_num:04d}")
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            associations.append({"deal_id": pair[0], "contact_id": pair[1], "role": role})

    for i in range(1, 121):
        if not (i <= 90 and i % 23 == 0):
            associate(i, ((i * 19) % 240) + 1)
        if i % 3 == 0:
            associate(i, ((i * 23 + 7) % 240) + 1, "influencer")
        if i % 10 == 0:
            associate(i, ((i * 29 + 13) % 240) + 1, "billing_contact")
        if i % 7 == 0:
            associate(i, ((i * 31 + 17) % 240) + 1, "technical_contact")

    # Put every duplicate candidate into live pipeline context, with uneven deal histories.
    for deal_num, contact_num in [
        (1, 11), (2, 211), (3, 24), (4, 224), (5, 37), (6, 237), (7, 52), (8, 202),
        (9, 79), (10, 179), (11, 105), (12, 155), (13, 64), (14, 164), (15, 234),
        (16, 11), (17, 24), (18, 37), (19, 52), (20, 79), (21, 105), (22, 64),
    ]:
        associate(deal_num, contact_num)

    assoc_by_deal: dict[str, list[str]] = {}
    for row in associations:
        assoc_by_deal.setdefault(row["deal_id"], []).append(row["contact_id"])

    activities: list[dict] = []
    qualifying_types = ["email", "call", "meeting", "note"]
    for i in range(1, 121):
        deal_id = f"D{i:04d}"
        contact_ids = assoc_by_deal.get(deal_id, [])
        primary_contact = contact_ids[0] if contact_ids else ""
        if i <= 90:
            latest_offset = 20 + (i % 10) if i % 4 == 0 else i % 14
        else:
            latest_offset = 35 + i % 80
        event_specs = [
            (qualifying_types[i % 4], "completed", latest_offset),
            (qualifying_types[(i + 1) % 4], "completed", latest_offset + 18),
            (qualifying_types[(i + 2) % 4], "completed", latest_offset + 43),
            ("task", "completed", max(0, latest_offset - 2)),
        ]
        if i == 40:
            event_specs = [("meeting", "scheduled", -5), ("note", "completed", 27), ("call", "completed", 55), ("task", "completed", 0)]
        elif i == 44:
            event_specs = [("meeting", "canceled", 1), ("note", "completed", 25), ("email", "completed", 61), ("task", "completed", 0)]
        elif i == 48:
            event_specs = [("task", "completed", 0), ("call", "completed", 23), ("email", "completed", 49), ("meeting", "scheduled", -8)]
        elif i == 89:
            event_specs = [("meeting", "scheduled", -2), ("meeting", "canceled", 3), ("task", "completed", 0), ("task", "completed", 45)]
        elif i == 88:
            event_specs[0] = (event_specs[0][0], "completed", 14)
        for j, (kind, status, day_offset) in enumerate(event_specs, start=1):
            moment = AS_OF - timedelta(days=day_offset, hours=(i + j) % 17)
            activities.append(
                {
                    "activity_id": f"A{i:04d}-{j}",
                    "deal_id": deal_id,
                    "contact_id": primary_contact,
                    "activity_type": kind,
                    "status": status,
                    "occurred_at": iso(moment),
                    "subject": f"{kind.title()} touchpoint {i:03d}-{j}",
                }
            )

    write_csv(
        "contacts.csv",
        ["contact_id", "first_name", "last_name", "email", "company", "phone", "owner_id", "created_at", "updated_at"],
        contacts,
    )
    write_csv(
        "deals.csv",
        ["deal_id", "deal_name", "pipeline_status", "deal_stage", "amount", "currency", "close_date", "next_step", "notes", "owner_id", "created_at"],
        deals,
    )
    write_csv("deal_contacts.csv", ["deal_id", "contact_id", "role"], associations)
    write_csv(
        "activities.csv",
        ["activity_id", "deal_id", "contact_id", "activity_type", "status", "occurred_at", "subject"],
        activities,
    )

    snapshot = {
        "snapshot_type": "fictional_offline_crm_export",
        "as_of": iso(AS_OF),
        "row_counts": {
            "contacts.csv": len(contacts),
            "deals.csv": len(deals),
            "deal_contacts.csv": len(associations),
            "activities.csv": len(activities),
        },
    }
    (OUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    policy = {
        "open_deal_status": "open",
        "stale_after_days": 14,
        "qualifying_activity_status_by_type": {
            "email": ["completed", "sent"],
            "call": ["completed"],
            "meeting": ["completed", "held"],
            "note": ["completed", "logged"],
        },
        "required_deal_fields": ["close_date", "amount", "deal_stage", "associated_contact", "next_step_or_notes"],
        "required_contact_fields_for_open_deals": ["email", "company", "phone"],
        "missing_value_rule": "null, an empty string, or whitespace-only text is missing; numeric zero is present",
        "duplicate_candidate_rules": {
            "email": "same non-empty email after trimming whitespace and case-folding",
            "identity": "same company after punctuation/whitespace normalization plus the same normalized first and last name",
            "first_name_aliases": {"alexander": "alex", "bob": "robert"},
            "initial_rule": "a one-letter first-name initial matches the same initial only when normalized company, last name, and a non-empty email also match",
        },
        "change_policy": "This snapshot is review-only. All merge, stage-change, close-lost, and field-fill proposals require explicit owner approval and no records may be deleted.",
    }
    (OUT / "cleanup_policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
