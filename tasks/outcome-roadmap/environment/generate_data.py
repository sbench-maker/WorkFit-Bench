#!/usr/bin/env python3
"""Generate the deterministic, fictional FieldNest planning fixture."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"


ROADMAP = [
    ("FN-101", "Q1 2027", "Guided workspace setup wizard", "feature", "committed", "SMB admins", "New admins do not know which setup steps matter first.", "14-day activation rate; setup time", "setup_friction"),
    ("FN-102", "Q1 2027", "CSV customer import validator", "feature", "committed", "SMB admins", "Import errors stall initial configuration and force support contact.", "14-day activation rate; setup time", "setup_friction"),
    ("FN-103", "Q1 2027", "Sample job templates", "feature", "committed", "SMB admins", "Blank-state workspaces make the first workflow hard to understand.", "14-day activation rate", "setup_friction"),
    ("FN-104", "Q1 2027", "Admin launch checklist", "feature", "committed", "SMB admins", "Admins cannot tell whether a workspace is ready for technicians.", "14-day activation rate; setup time", "setup_friction"),
    ("FN-105", "Q1 2027", "Role permission presets", "feature", "committed", "Enterprise admins", "Security setup is repeatedly rebuilt during pilots.", "enterprise pilot-to-paid conversion", "permissions_and_audit"),
    ("FN-106", "Q1 2027", "Downloadable audit log", "feature", "committed", "Enterprise admins", "Security reviews pause while admins assemble activity evidence.", "enterprise pilot-to-paid conversion", "permissions_and_audit"),
    ("FN-107", "Q1 2027", "Self-service SSO configuration", "feature", "planned", "Enterprise admins", "SSO setup currently requires FieldNest support and lengthens pilots.", "enterprise pilot-to-paid conversion", "permissions_and_audit"),
    ("FN-108", "Q1 2027", "Redesigned billing settings", "redesign", "planned", "SMB admins", "Admins contact support to understand seats, plans, and invoice contacts.", "billing-settings tickets", "billing_self_service"),
    ("FN-201", "Q2 2027", "Drag-and-drop dispatch board", "feature", "committed", "Dispatchers", "Moving jobs between technicians requires several screens.", "time to schedule 20 jobs; dispatcher WAU", "dispatch_speed"),
    ("FN-202", "Q2 2027", "Bulk technician assignment", "feature", "committed", "Dispatchers", "High-volume dispatchers repeat the same assignment action job by job.", "time to schedule 20 jobs", "dispatch_speed"),
    ("FN-203", "Q2 2027", "Scheduling conflict alerts", "feature", "committed", "Dispatchers", "Overlaps are noticed after customers or technicians complain.", "reschedule conflicts; dispatcher WAU", "dispatch_speed"),
    ("FN-204", "Q2 2027", "Saved dispatcher views", "feature", "planned", "Dispatchers", "Dispatchers rebuild filters for territories and shifts every day.", "time to schedule 20 jobs; dispatcher WAU", "dispatch_speed"),
    ("FN-205", "Q2 2027", "Offline mobile job cards", "feature", "committed", "Technicians", "Technicians in weak coverage lose job details and defer completion.", "retry-free mobile completion", "mobile_reliability"),
    ("FN-206", "Q2 2027", "Resumable photo uploads", "feature", "committed", "Technicians", "Failed evidence uploads force technicians to repeat work.", "photo upload failure rate", "mobile_reliability"),
    ("FN-207", "Q2 2027", "Background sync status screen", "feature", "planned", "Technicians", "Technicians cannot tell whether offline changes reached dispatch.", "retry-free mobile completion", "mobile_reliability"),
    ("FN-208", "Q2 2027", "Partner calendar two-way sync", "integration", "planned", "Mid-market teams", "External appointments drift from the dispatch schedule.", "active integrations at 90 days", "calendar_coordination"),
    ("FN-301", "Q3 2027", "Route suggestion engine", "feature", "planned", "Dispatchers", "Manual route choices create avoidable travel and late arrivals.", "on-time arrival rate", "route_efficiency"),
    ("FN-302", "Q3 2027", "Map job clustering", "feature", "planned", "Dispatchers", "Dense job areas are hard to group into efficient runs.", "on-time arrival rate", "route_efficiency"),
    ("FN-303", "Q3 2027", "Live traffic overlay", "feature", "candidate", "Dispatchers", "Schedules do not reflect changing travel conditions.", "on-time arrival rate", "route_efficiency"),
    ("FN-304", "Q3 2027", "Customer SMS ETA", "feature", "committed", "Service customers", "Customers call dispatch because arrival timing is unclear.", "where-is-technician contacts; missed appointments", "appointment_reliability"),
    ("FN-305", "Q3 2027", "Appointment confirmation portal", "feature", "planned", "Service customers", "Teams discover unavailable customers only at arrival.", "missed appointment rate", "appointment_reliability"),
    ("FN-306", "Q3 2027", "Customer self-service rescheduling", "feature", "planned", "Service customers", "Changing an appointment requires a phone exchange with dispatch.", "missed appointments; support contacts", "appointment_reliability"),
    ("FN-307", "Q3 2027", "Public API and webhook registry", "platform", "committed", "Integration admins", "Partners cannot build stable, supportable connections.", "active integrations at 90 days", "integration_demand"),
    ("FN-308", "Q3 2027", "Manager analytics dashboard", "redesign", "candidate", "Operations managers", "Weekly performance reviews require manual spreadsheet assembly.", "manager report preparation time", "manager_visibility"),
    ("FN-401", "Q4 2027", "Accounting-system invoice export", "integration", "planned", "Finance teams", "Completed work is re-keyed before invoices can be prepared.", "invoice-ready lag", "invoice_cycle"),
    ("FN-402", "Q4 2027", "Batch invoice review", "feature", "planned", "Finance teams", "Finance reviews completed jobs one at a time.", "invoice-ready lag", "invoice_cycle"),
    ("FN-403", "Q4 2027", "Payment status reconciliation", "feature", "candidate", "Finance teams", "Payment status is manually matched back to field work.", "invoice-ready lag", "invoice_cycle"),
    ("FN-404", "Q4 2027", "Multi-region admin console", "feature", "planned", "Enterprise admins", "Regional rollouts require separate workspaces and duplicated governance.", "enterprise pilot-to-paid conversion", "regional_governance"),
    ("FN-405", "Q4 2027", "Custom data-retention controls", "feature", "planned", "Enterprise admins", "Fixed retention settings fail some enterprise governance reviews.", "enterprise pilot-to-paid conversion; gross retention", "regional_governance"),
    ("FN-406", "Q4 2027", "Data-residency selector", "feature", "candidate", "Enterprise admins", "Some prospects ask where operational data is stored, but the affected pipeline is not quantified.", "enterprise pilot-to-paid conversion", "data_residency"),
    ("FN-407", "Q4 2027", "Partner integration marketplace", "feature", "planned", "Integration admins", "Customers struggle to discover supported partner workflows.", "active integrations at 90 days", "integration_demand"),
    ("FN-408", "Q4 2027", "AI voice dispatch assistant prototype", "experiment", "validation", "Dispatchers", "Two discovery calls suggested hands-free dispatch might help during peaks; no workflow study exists.", "no validated KPI yet", "voice_dispatch"),
]


KPI_ROWS = [
    ("KPI-01", "New workspaces active within 14 days", "SMB admins", "42", "percent", "2026 H2 cohort", "60", "percent", "H1 2027", "Activation means first technician invited and five jobs completed."),
    ("KPI-02", "Median admin setup time", "SMB admins", "118", "minutes", "2026 Q4 onboarding study", "70", "minutes", "H1 2027", "Measured from workspace creation to technician-ready configuration."),
    ("KPI-03", "Median time to schedule 20 jobs", "Dispatchers", "31", "minutes", "2026 Q4 workflow study", "18", "minutes", "Q3 2027", "Study excludes initial data import."),
    ("KPI-04", "Conflicts caused by rescheduling", "Dispatchers", "9.4", "per 100 rescheduled jobs", "2026 H2", "5.0", "per 100 rescheduled jobs", "Q3 2027", "Lower is better."),
    ("KPI-05", "Mobile jobs completed without a sync retry", "Technicians", "86", "percent", "2026 H2", "95", "percent", "Q3 2027", "Only jobs with at least one mobile update are included."),
    ("KPI-06", "Technician photo upload failure rate", "Technicians", "7.6", "percent", "2026 Q4", "2.5", "percent", "Q3 2027", "Lower is better; retry attempts count once per job."),
    ("KPI-07", "On-time arrival rate", "Service customers", "71", "percent", "2026 H2", "82", "percent", "Q4 2027", "On time means within the promised 30-minute window."),
    ("KPI-08", "Missed appointment rate", "Service customers", "8.8", "percent", "2026 H2", "6.0", "percent", "Q4 2027", "Lower is better; customer-cancelled visits are excluded."),
    ("KPI-09", "Where-is-my-technician contacts", "Service customers", "14.2", "per 100 appointments", "2026 Q4", "8.0", "per 100 appointments", "Q4 2027", "Lower is better."),
    ("KPI-10", "Customers with an active integration at day 90", "Integration admins", "18", "percent", "2026 H2 cohort", "32", "percent", "Q4 2027", "Active means at least 20 successful sync events in the prior 30 days."),
    ("KPI-11", "Median invoice-ready lag", "Finance teams", "4.8", "days", "2026 H2", "2.5", "days", "Q1 2028", "From job completion to approved invoice batch; lower is better."),
    ("KPI-12", "Enterprise pilot-to-paid conversion", "Enterprise admins", "36", "percent", "2026 full year", "50", "percent", "Q1 2028", "Pilots with fewer than 25 technicians are excluded."),
    ("KPI-13", "Gross revenue retention", "Business", "87", "percent", "2026 full year", "91", "percent", "Q1 2028", "Company-level lagging indicator, not attributable to one feature."),
    ("KPI-14", "Weekly active dispatcher rate", "Dispatchers", "64", "percent", "2026 H2", "72", "percent", "Q4 2027", "Among licensed dispatchers."),
    ("KPI-15", "Median manager report preparation time", "Operations managers", "96", "minutes per week", "2026 Q4 interviews", "45", "minutes per week", "Q4 2027", "Self-reported sample of 18 managers."),
    ("KPI-16", "Billing-settings support tickets", "SMB admins", "6.2", "per 100 accounts per month", "2026 H2", "3.5", "per 100 accounts per month", "Q3 2027", "Lower is better."),
]


DEPENDENCIES = [
    ("FN-101", "FN-104", "The launch checklist should deep-link into the setup wizard.", "normal"),
    ("FN-105", "FN-107", "SSO self-service must inherit tested permission presets.", "normal"),
    ("FN-205", "FN-207", "Sync status needs the offline queue introduced with job cards.", "critical"),
    ("FN-207", "FN-301", "Route suggestions need reliable fresh technician state.", "critical"),
    ("FN-307", "FN-208", "Calendar sync needs the public event and webhook contracts.", "critical"),
    ("FN-304", "FN-305", "The confirmation link is delivered through the messaging service.", "normal"),
    ("FN-305", "FN-306", "Self-service rescheduling reuses confirmation identity and availability rules.", "critical"),
    ("FN-307", "FN-401", "Accounting export should use the supported public integration contract.", "critical"),
    ("FN-401", "FN-402", "Batch review consumes normalized invoice-export records.", "normal"),
    ("FN-401", "FN-403", "Reconciliation needs external invoice identifiers from export.", "normal"),
    ("FN-307", "FN-407", "Marketplace listings require stable APIs and webhooks.", "critical"),
    ("FN-105", "FN-404", "Multi-region administration relies on the common role model.", "normal"),
]


THEMES = {
    "setup_friction": (30, "SMB", "admin", ["Setup stalled before the first technician could be invited", "Import errors made the team ask support what to fix", "The blank workspace did not show a clear path to first value"]),
    "permissions_and_audit": (24, "enterprise", "admin", ["The pilot paused while security roles were rebuilt", "Audit evidence took several days to assemble", "SSO configuration needed repeated support handoffs"]),
    "billing_self_service": (12, "SMB", "admin", ["The account owner could not explain the next invoice", "Changing billing contacts required a support ticket", "Seat and plan details were hard to reconcile"]),
    "dispatch_speed": (34, "mid-market", "dispatcher", ["Reassigning a busy day took too many repeated clicks", "A schedule overlap was found only after a customer called", "Daily territory filters had to be rebuilt from scratch"]),
    "mobile_reliability": (32, "mid-market", "technician", ["Weak coverage hid the job details needed on site", "A failed photo upload forced the visit evidence to be repeated", "The technician could not tell whether an offline update synced"]),
    "calendar_coordination": (8, "mid-market", "dispatcher", ["Partner appointments drifted from the dispatch board", "Calendar changes had to be copied into FieldNest", "The external booking time and field schedule disagreed"]),
    "route_efficiency": (22, "mid-market", "dispatcher", ["Manual routing left avoidable gaps between nearby jobs", "Changing traffic made the morning route obsolete", "Dense jobs were difficult to group into efficient runs"]),
    "appointment_reliability": (20, "SMB", "customer", ["The customer called because the arrival window was unclear", "The team learned nobody was available only after arrival", "Rescheduling required several phone exchanges"]),
    "integration_demand": (18, "enterprise", "integration_admin", ["A partner connection broke after an undocumented change", "The team could not discover which workflows were supported", "The prospect wanted a stable event contract before rollout"]),
    "manager_visibility": (10, "mid-market", "manager", ["The weekly review required a manually assembled spreadsheet", "Managers lacked one view of schedule and completion health", "Reporting work crowded out operational follow-up"]),
    "invoice_cycle": (16, "mid-market", "finance", ["Completed work was re-keyed before invoicing", "Invoice batches were checked one job at a time", "Payment status was manually matched back to jobs"]),
    "regional_governance": (8, "enterprise", "admin", ["Regional rollout duplicated roles across workspaces", "A fixed retention policy blocked governance approval", "Central admins lacked a safe regional control model"]),
    "data_residency": (4, "enterprise", "admin", ["A prospect asked where operational data would be stored", "Residency came up in review but affected pipeline was unclear", "Procurement asked for a regional storage choice"]),
    "voice_dispatch": (2, "mid-market", "dispatcher", ["One dispatcher wondered if voice entry could help during peaks", "A discovery caller suggested hands-free reassignment"]),
}


def write_csv(name: str, header: list[str], rows: list[tuple | list]) -> None:
    with (DATA_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        "roadmap_items.csv",
        ["initiative_id", "quarter", "initiative", "work_type", "commitment", "primary_segment", "problem_hypothesis", "metric_hint", "evidence_theme"],
        ROADMAP,
    )
    write_csv(
        "kpi_baselines.csv",
        ["metric_id", "metric_name", "audience", "baseline", "baseline_unit", "observation_window", "strategic_target", "target_unit", "target_window", "caveat"],
        KPI_ROWS,
    )
    write_csv(
        "dependency_edges.csv",
        ["prerequisite_id", "dependent_id", "reason", "criticality"],
        DEPENDENCIES,
    )

    start = date(2026, 1, 8)
    signals: list[list[str]] = []
    index = 0
    segment_jobs = {"SMB": 180, "mid-market": 920, "enterprise": 3100}
    channels = ["interview", "support_summary", "win_loss", "workflow_observation"]
    for theme, (count, segment, role, summaries) in THEMES.items():
        for offset in range(count):
            index += 1
            signal_date = start + timedelta(days=(index * 7 + offset * 3) % 330)
            account_no = ((index * 11) % 72) + 1
            jobs = segment_jobs[segment] + ((account_no * 37 + offset * 19) % max(80, segment_jobs[segment] // 2))
            impact = ["medium", "high", "high", "critical"][((index + offset) * 5) % 4]
            sentiment = "mixed" if offset % 9 == 0 else "negative"
            summary = summaries[offset % len(summaries)] + f"; account reported roughly {jobs} monthly jobs."
            signals.append([
                f"SIG-{index:03d}",
                signal_date.isoformat(),
                f"ACCT-{account_no:03d}",
                segment,
                role,
                channels[(index + offset) % len(channels)],
                theme,
                sentiment,
                impact,
                str(jobs),
                summary,
            ])
    write_csv(
        "customer_signals.csv",
        ["signal_id", "signal_date", "account_id", "segment", "role", "channel", "theme", "sentiment", "impact_level", "monthly_jobs", "summary"],
        signals,
    )

    (DATA_DIR / "company_strategy.md").write_text(
        """# FieldNest 2027 strategy snapshot

FieldNest is a fictional B2B platform used to schedule and complete field-service work. The 2027 strategy is to win durable adoption before expanding the product surface.

## Company outcomes

1. **Reach first value faster for small teams.** Raise 14-day workspace activation from 42% to 60% by the end of H1 2027 without increasing onboarding headcount.
2. **Make daily coordination dependable.** Improve dispatcher and technician adoption by removing avoidable scheduling work and failed mobile updates; weekly active dispatcher rate should move from 64% to 72% by Q4 2027.
3. **Make service more predictable for customers.** Lift on-time arrival from 71% to 82% and reduce missed appointments from 8.8% to 6.0% by Q4 2027.
4. **Earn expansion readiness.** Raise enterprise pilot-to-paid conversion from 36% to 50% and gross revenue retention from 87% to 91% by Q1 2028 through trustworthy governance and supportable integrations.

## Planning principles

- Quarters are planning windows, not promised ship dates. Committed, planned, candidate, and validation work must not be presented as equally certain.
- The roadmap may group or swap outputs when they pursue the same measured result.
- Customer evidence is directional and may include repeated accounts; signal counts are not market prevalence.
- Lagging business metrics should be paired with a nearer customer or workflow indicator when possible.
- No 2027 headcount increase is assumed. Platform work that unlocks later initiatives must be made visible.
""",
        encoding="utf-8",
    )
    (DATA_DIR / "planning_notes.md").write_text(
        """# Planning notes

- The current roadmap was assembled from team feature proposals. Initiative IDs are the stable review references and should survive any regrouping.
- Leadership wants an outcome roadmap for the annual review, not a delivery contract. Keep the four quarter windows so capacity and dependency conversations remain possible.
- FN-208 is currently placed before its prerequisite FN-307. Teams have not agreed whether to pull the platform work forward or move calendar sync later.
- FN-406 has only four directional signals and no quantified affected pipeline. Treat the need as an assumption to validate, not a proven conversion lever.
- FN-408 has two exploratory comments and no baseline KPI. Its useful 2027 result may be learning or a go/no-go decision rather than adoption.
- KPI-15 comes from a small self-reported sample. It can guide a hypothesis, but claims of company-wide prevalence would be too strong.
- Product operations will review baselines quarterly; success measures should retain units and direction so changes remain interpretable.
""",
        encoding="utf-8",
    )
    notes = {
        "method": "deterministic fictional fixture construction",
        "files": {
            "roadmap_items.csv": len(ROADMAP),
            "customer_signals.csv": len(signals),
            "kpi_baselines.csv": len(KPI_ROWS),
            "dependency_edges.csv": len(DEPENDENCIES),
        },
        "relationships": [
            "roadmap_items.evidence_theme joins customer_signals.theme",
            "dependency_edges initiative IDs join roadmap_items.initiative_id",
            "roadmap metric hints correspond to kpi_baselines metric names",
        ],
        "notes": "All entities and observations are fictional; signal counts are evidence volume, not market prevalence.",
    }
    (DATA_DIR / "generation_notes.json").write_text(json.dumps(notes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
