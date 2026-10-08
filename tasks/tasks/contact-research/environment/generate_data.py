#!/usr/bin/env python3
"""Generate the deterministic fictional Common Room export used by this task."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path


OUT = Path(__file__).resolve().parent / "data"
AS_OF = date(2026, 9, 1)


def write_csv(name: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def iso(days_ago: int) -> str:
    return (AS_OF - timedelta(days=days_ago)).isoformat()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    company_roots = [
        "Juniper Metric", "Cinder Works", "Aster Cloud", "Harborline", "Mosaic Forge",
        "Lattice Harbor", "Northstar Grid", "Copper Peak", "Quarry Labs", "Sable Systems",
        "Orbit Foundry", "Maple Circuit", "Summit Ledger", "Blue Meridian", "Pine Signal",
        "Cobalt Thread", "Driftline", "Elm Robotics", "Fable Stack", "Granite Loop",
        "Helix Harbor", "Ivory Relay", "Kiteframe", "Lucent Field", "Nimble Current",
        "Opal Network", "Prairie Logic", "Quartz Run", "Riverglass", "Tandem Arc",
    ]
    accounts: list[dict[str, object]] = []
    for idx, company in enumerate(company_roots, 1):
        accounts.append({
            "account_id": f"A-{idx:03d}",
            "company": company,
            "domain": f"{company.lower().replace(' ', '')}.example",
            "lifecycle_stage": ["Prospect", "Customer", "Customer", "Trial"][idx % 4],
            "employee_band": ["51-200", "201-500", "501-1000", "1001-5000"][idx % 4],
            "expansion_signal": ["None", "Usage growth", "New engineering hires", "Multiple active teams"][idx % 4],
            "churn_risk": ["Low", "Low", "Medium", "Low", "High"][idx % 5],
        })
    accounts[6].update({
        "lifecycle_stage": "Customer",
        "employee_band": "501-1000",
        "expansion_signal": "Identity rollout across three teams",
        "churn_risk": "Low",
    })
    write_csv("accounts.csv", list(accounts[0]), accounts)

    first_names = ["Avery", "Casey", "Drew", "Emery", "Finley", "Harper", "Jordan", "Kai", "Morgan", "Quinn", "Riley", "Sasha"]
    last_names = ["Bennett", "Duarte", "Ellis", "Foster", "Garcia", "Hart", "Ibrahim", "Kowalski", "Lopez", "Nguyen", "Okafor", "Singh"]
    titles = [
        "Platform Engineer", "Engineering Manager", "Security Architect", "VP of Engineering",
        "Developer Advocate", "IT Director", "Product Manager", "Customer Success Director",
    ]
    contacts: list[dict[str, object]] = []
    for idx in range(1, 241):
        account_idx = (idx - 1) % len(accounts)
        account = accounts[account_idx]
        first = first_names[(idx * 5) % len(first_names)]
        last = last_names[(idx * 7) % len(last_names)]
        full_name = f"{first} {last}"
        local = f"{first}.{last}.{idx}".lower()
        contacts.append({
            "contact_id": f"C-{idx:04d}",
            "full_name": full_name,
            "email": f"{local}@{account['domain']}",
            "title": titles[idx % len(titles)],
            "account_id": account["account_id"],
            "company": account["company"],
            "linkedin_handle": f"{first.lower()}-{last.lower()}-{idx}",
            "x_handle": f"@{first.lower()}{last.lower()}{idx}" if idx % 4 == 0 else "",
            "github_handle": f"{first.lower()}{last.lower()}-{idx}" if idx % 5 == 0 else "",
            "crm_contact_ref": f"CRM-C-{idx:04d}",
            "relationship_status": ["New", "Known", "Engaged", "Dormant"][idx % 4],
        })

    replacements = {
        "C-0007": ("Rina Patel", "rina.patel@northstargrid.example", "VP of Security", "A-007", "Northstar Grid", "rina-patel", "@rinapatel", "", "Known"),
        "C-0037": ("Theo Barnes", "theo.barnes@northstargrid.example", "Enterprise Architect", "A-007", "Northstar Grid", "theo-barnes", "", "theobarnes", "Known"),
        "C-0043": ("Maya Chen", "maya.chen@northstargrid.example", "Director of Platform Engineering", "A-007", "Northstar Grid", "maya-chen-ng", "@mayacodes", "maya-chen", "Engaged"),
        "C-0067": ("Luca Owens", "luca.owens@northstargrid.example", "Procurement Manager", "A-007", "Northstar Grid", "luca-owens", "", "", "Known"),
        "C-0101": ("Maya Chen", "maya.chen@astercloud.example", "Data Platform Manager", "A-003", "Aster Cloud", "maya-chen-ac", "", "", "New"),
        "C-0174": ("Maya Chen", "maya.chen@bluemeridian.example", "Engineering Manager", "A-014", "Blue Meridian", "maya-chen-bm", "@mayacbuilds", "", "Dormant"),
    }
    for row in contacts:
        if row["contact_id"] in replacements:
            name, email, title, account_id, company, linkedin, x_handle, github, status = replacements[row["contact_id"]]
            row.update({
                "full_name": name,
                "email": email,
                "title": title,
                "account_id": account_id,
                "company": company,
                "linkedin_handle": linkedin,
                "x_handle": x_handle,
                "github_handle": github,
                "relationship_status": status,
            })
    write_csv("contacts.csv", list(contacts[0]), contacts)

    activities: list[dict[str, object]] = []
    activity_types = ["Product event", "Community post", "Support ticket", "Documentation feedback", "Event attended"]
    generic_details = [
        "Joined a product onboarding session.",
        "Asked about deployment controls in the community.",
        "Opened a support request about workspace permissions.",
        "Commented on an integration guide.",
        "Attended the platform reliability briefing.",
    ]
    special_activity_ids = {
        str(row["contact_id"]) for row in contacts if row["account_id"] == "A-007"
    } | {"C-0101", "C-0174"}
    activity_no = 1
    for idx in range(1, 241):
        cid = f"C-{idx:04d}"
        if cid in special_activity_ids:
            continue
        for offset in range(1 + idx % 3):
            days = (idx * 11 + offset * 37) % 150
            initiated = "Team Initiated" if (idx + offset) % 6 == 0 else "Contact Initiated"
            kind_idx = (idx + offset) % len(activity_types)
            activities.append({
                "activity_id": f"ACT-{activity_no:05d}",
                "contact_id": cid,
                "occurred_at": iso(days),
                "activity_type": activity_types[kind_idx],
                "initiated_by": initiated,
                "channel": ["Product", "Community", "Support", "Docs", "Event"][kind_idx],
                "detail": generic_details[kind_idx],
            })
            activity_no += 1

    special_activities = [
        ("C-0043", 32, "Community post", "Contact Initiated", "Community", "Asked how SCIM group mapping handles nested groups during an identity rollout."),
        ("C-0043", 39, "Event attended", "Contact Initiated", "Event", "Attended identity governance office hours and asked about exporting audit evidence."),
        ("C-0043", 60, "Support ticket", "Contact Initiated", "Support", "Requested guidance on SSO rollout sequencing across three subsidiaries."),
        ("C-0043", 63, "Documentation feedback", "Contact Initiated", "Docs", "Suggested a clearer example for custom role mappings."),
        ("C-0043", 2, "Sales follow-up", "Team Initiated", "Email", "Account executive sent a technical validation recap."),
        ("C-0043", 1, "Meeting outreach", "Team Initiated", "CRM", "Solutions engineer proposed times for an architecture review."),
        ("C-0007", 5, "Community reply", "Contact Initiated", "Community", "Replied to a thread about audit retention policy."),
        ("C-0007", 18, "Event attended", "Contact Initiated", "Event", "Joined the enterprise security roundtable."),
        ("C-0037", 45, "Product event", "Contact Initiated", "Product", "Completed an identity provider sandbox connection."),
        ("C-0037", 70, "Support ticket", "Contact Initiated", "Support", "Asked about regional data residency."),
        ("C-0067", 0, "Sales email", "Team Initiated", "Email", "Account executive sent procurement documentation."),
        ("C-0067", 112, "Email reply", "Contact Initiated", "Email", "Acknowledged receipt of the master services agreement."),
        ("C-0101", 4, "Community post", "Contact Initiated", "Community", "Asked about streaming ingestion throughput."),
        ("C-0174", 14, "Support ticket", "Contact Initiated", "Support", "Asked about build cache configuration."),
    ]
    for row in contacts:
        cid = str(row["contact_id"])
        if row["account_id"] == "A-007" and cid not in {"C-0007", "C-0037", "C-0043", "C-0067"}:
            special_activities.append(
                (cid, 95, "Product event", "Contact Initiated", "Product", "Viewed a workspace administration walkthrough.")
            )
    for cid, days, kind, initiated, channel, detail in special_activities:
        activities.append({
            "activity_id": f"ACT-{activity_no:05d}", "contact_id": cid, "occurred_at": iso(days),
            "activity_type": kind, "initiated_by": initiated, "channel": channel, "detail": detail,
        })
        activity_no += 1
    activities.sort(key=lambda row: (str(row["contact_id"]), str(row["occurred_at"]), str(row["activity_id"])))
    write_csv("activities.csv", list(activities[0]), activities)

    visits: list[dict[str, object]] = []
    pages = ["/docs/sso", "/pricing", "/security", "/integrations", "/customers/platform", "/docs/api"]
    visit_no = 1
    for idx in range(1, 241):
        cid = f"C-{idx:04d}"
        if cid == "C-0043":
            continue
        for offset in range(idx % 5):
            days = (idx * 7 + offset * 23) % 130
            visits.append({
                "visit_id": f"VIS-{visit_no:05d}", "contact_id": cid, "visited_at": iso(days),
                "page_path": pages[(idx + offset) % len(pages)], "session_id": f"S-{idx:04d}-{offset + 1}",
            })
            visit_no += 1
    target_visits = [
        (3, "/pricing/enterprise", "S-MC-01"),
        (3, "/security/compliance", "S-MC-01"),
        (12, "/docs/sso/scim", "S-MC-02"),
        (53, "/integrations/idp", "S-MC-03"),
        (78, "/customers/finops", "S-MC-04"),
        (84, "/pricing/enterprise", "S-MC-05"),
        (85, "/legal/dpa", "S-MC-06"),
    ]
    for days, page, session in target_visits:
        visits.append({
            "visit_id": f"VIS-{visit_no:05d}", "contact_id": "C-0043", "visited_at": iso(days),
            "page_path": page, "session_id": session,
        })
        visit_no += 1
    visits.sort(key=lambda row: (str(row["contact_id"]), str(row["visited_at"]), str(row["visit_id"])))
    write_csv("website_visits.csv", list(visits[0]), visits)

    sparks: list[dict[str, object]] = []
    spark_no = 1
    personas = ["End User", "Technical Evaluator", "Champion", "Gatekeeper", "Economic Buyer"]
    for idx in range(2, 241, 3):
        cid = f"C-{idx:04d}"
        if cid == "C-0043":
            continue
        sparks.append({
            "spark_id": f"SPK-{spark_no:04d}", "contact_id": cid, "generated_at": iso((idx * 3) % 120),
            "persona": personas[idx % len(personas)],
            "background_summary": "Fictional enrichment snapshot describing platform and cross-team delivery experience.",
            "influence_signals": "Participates in technical evaluation and peer discussions.",
            "job_change": "",
        })
        spark_no += 1
    target_sparks = [
        ("2026-03-15", "End User", "Senior Platform Engineer owning identity automation.", "Hands-on administrator for SSO and provisioning.", ""),
        ("2026-06-20", "Technical Evaluator", "Promoted to Director of Platform Engineering.", "Joined the security architecture committee and led vendor validation.", "Promotion from Senior Platform Engineer"),
        ("2026-08-22", "Champion", "Director coordinating the identity rollout across Platform, Security, and Finance IT.", "Organizes the pilot and shares evaluation notes with the buying group.", ""),
    ]
    for generated_at, persona, background, influence, job_change in target_sparks:
        sparks.append({
            "spark_id": f"SPK-{spark_no:04d}", "contact_id": "C-0043", "generated_at": generated_at,
            "persona": persona, "background_summary": background, "influence_signals": influence,
            "job_change": job_change,
        })
        spark_no += 1
    sparks.sort(key=lambda row: (str(row["contact_id"]), str(row["generated_at"])))
    write_csv("sparks.csv", list(sparks[0]), sparks)

    scores: list[dict[str, object]] = []
    for idx in range(1, 241):
        scores.append({
            "contact_id": f"C-{idx:04d}",
            "product_engagement_score": round(18 + (idx * 7.3) % 76, 1),
            "community_score": int(10 + (idx * 13) % 88),
            "fit_percentile": int(20 + (idx * 17) % 80),
            "score_as_of": AS_OF.isoformat(),
        })
    next(row for row in scores if row["contact_id"] == "C-0043").update({
        "product_engagement_score": 73.5, "community_score": 41, "fit_percentile": 92,
    })
    write_csv("scores.csv", list(scores[0]), scores)

    segments: list[dict[str, object]] = []
    segment_names = ["Newsletter", "Developer Community", "Product-led", "Enterprise", "Security Interest"]
    for idx in range(1, 241):
        cid = f"C-{idx:04d}"
        segments.append({"contact_id": cid, "segment_name": segment_names[idx % len(segment_names)]})
        if idx % 4 == 0:
            segments.append({"contact_id": cid, "segment_name": "Event Attendee"})
    segments = [row for row in segments if row["contact_id"] != "C-0043"]
    segments.extend([
        {"contact_id": "C-0043", "segment_name": "Enterprise Evaluation"},
        {"contact_id": "C-0043", "segment_name": "Identity & Security"},
        {"contact_id": "C-0043", "segment_name": "Existing Customer"},
    ])
    segments.sort(key=lambda row: (str(row["contact_id"]), str(row["segment_name"])))
    write_csv("segments.csv", ["contact_id", "segment_name"], segments)

    opportunities: list[dict[str, object]] = []
    opp_no = 1
    for idx in range(1, 31):
        opportunities.append({
            "opportunity_id": f"OPP-{opp_no:04d}", "account_id": f"A-{idx:03d}",
            "opportunity_type": "New Business" if idx % 3 else "Renewal",
            "status": "Open" if idx % 4 else "Closed Won",
            "stage": ["Discovery", "Business Case", "Technical Validation", "Contracting"][idx % 4],
            "amount_usd": 40000 + idx * 3500,
            "target_close_date": (AS_OF + timedelta(days=30 + idx * 3)).isoformat(),
        })
        opp_no += 1
    opportunities = [row for row in opportunities if row["account_id"] != "A-007"]
    opportunities.extend([
        {"opportunity_id": "OPP-0101", "account_id": "A-007", "opportunity_type": "New Business", "status": "Closed Won", "stage": "Closed Won", "amount_usd": 120000, "target_close_date": "2025-11-30"},
        {"opportunity_id": "OPP-0208", "account_id": "A-007", "opportunity_type": "Expansion", "status": "Open", "stage": "Technical Validation", "amount_usd": 180000, "target_close_date": "2026-12-15"},
    ])
    opportunities.sort(key=lambda row: str(row["opportunity_id"]))
    write_csv("opportunities.csv", list(opportunities[0]), opportunities)

    snapshot = {
        "as_of": AS_OF.isoformat(),
        "source_type": "fictional offline Common Room export",
        "notes": "All entities and signals are synthetic fixtures for local analysis; no live service is required.",
        "windows": {"contact_initiated_activity_days": 60, "website_visit_days": 84},
        "row_counts": {
            "accounts": len(accounts), "contacts": len(contacts), "activities": len(activities),
            "website_visits": len(visits), "sparks": len(sparks), "scores": len(scores),
            "segments": len(segments), "opportunities": len(opportunities),
        },
    }
    (OUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
