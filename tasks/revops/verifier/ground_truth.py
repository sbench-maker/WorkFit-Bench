#!/usr/bin/env python3
"""Deterministic handoff decision engine for the frozen CRM snapshot."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


def parse_dt(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def truthy(raw: object) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes"}


def load_rows(data_dir: Path, filename: str) -> list[dict[str, str]]:
    with (data_dir / filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def next_business_start(moment: datetime, calendar: dict, holidays: set[date]) -> datetime:
    start_hour = int(calendar["start_hour"])
    end_hour = int(calendar["end_hour"])
    valid_weekdays = {int(item) for item in calendar["weekdays"]}
    current = moment.astimezone(timezone.utc)
    while True:
        day_start = datetime.combine(current.date(), time(start_hour), tzinfo=timezone.utc)
        day_end = datetime.combine(current.date(), time(end_hour), tzinfo=timezone.utc)
        if current.weekday() not in valid_weekdays or current.date() in holidays:
            current = datetime.combine(current.date() + timedelta(days=1), time(start_hour), tzinfo=timezone.utc)
            continue
        if current < day_start:
            return day_start
        if current >= day_end:
            current = datetime.combine(current.date() + timedelta(days=1), time(start_hour), tzinfo=timezone.utc)
            continue
        return current


def add_business_hours(moment: datetime, hours: float, calendar: dict, holidays: set[date]) -> datetime:
    current = next_business_start(moment, calendar, holidays)
    remaining = float(hours)
    end_hour = int(calendar["end_hour"])
    while remaining > 1e-9:
        day_end = datetime.combine(current.date(), time(end_hour), tzinfo=timezone.utc)
        available = (day_end - current).total_seconds() / 3600
        if remaining <= available:
            return current + timedelta(hours=remaining)
        remaining -= available
        current = next_business_start(day_end + timedelta(seconds=1), calendar, holidays)
    return current


def score_contact(contact: dict, account: dict | None, events: list[dict], policy: dict, now: datetime) -> dict:
    fit = 0
    if account is not None:
        employees = int(account["employee_count"])
        for band in policy["fit_scoring"]["employee_count"]:
            upper = band["max"]
            if employees >= int(band["min"]) and (upper is None or employees <= int(upper)):
                fit += int(band["points"])
                break
        fit += int(policy["fit_scoring"]["industry"].get(account["industry"], 0))
        fit += int(policy["fit_scoring"]["target_country"].get(account["country"], 0))
        if truthy(account["uses_complementary_tool"]):
            fit += int(policy["fit_scoring"]["uses_complementary_tool"])
    fit += int(policy["fit_scoring"]["title_level"].get(contact["title_level"], 0))

    engagement_rules = policy["engagement_scoring"]
    cutoff = now - timedelta(days=int(engagement_rules["lookback_days"]))
    scoring_events = [event for event in events if cutoff <= parse_dt(event["occurred_at"]) <= now and event["activity_type"] in engagement_rules]
    counts = Counter(event["activity_type"] for event in scoring_events)
    engagement = 0
    for activity_type, count in counts.items():
        rule = engagement_rules[activity_type]
        engagement += min(count * int(rule["points_each"]), int(rule["cap"]))

    domain = contact["email"].rsplit("@", 1)[-1].lower()
    negative = 0
    negative_rules = policy["negative_scoring"]
    if domain in {item.lower() for item in negative_rules["personal_email_domains"]}:
        negative += int(negative_rules["personal_email_points"])
    if truthy(contact["unsubscribed"]):
        negative += int(negative_rules["unsubscribed_points"])
    if contact["title_level"] == "Intern":
        negative += int(negative_rules["intern_points"])
    active_cutoff = now - timedelta(days=30)
    if not any(parse_dt(event["occurred_at"]) >= active_cutoff for event in scoring_events):
        negative += int(negative_rules["inactive_30_days_points"])

    disqualifiers: list[str] = []
    if domain in {item.lower() for item in policy["disqualifiers"]["email_domains"]}:
        disqualifiers.append("blocked_domain")
    for field in policy["disqualifiers"]["boolean_fields"]:
        if truthy(contact[field]):
            disqualifiers.append(field)
    return {
        "fit_score": fit,
        "engagement_score": engagement,
        "negative_score": negative,
        "total_score": fit + engagement + negative,
        "disqualifiers": disqualifiers,
        "scoring_events": scoring_events,
    }


def build_decisions(data_dir: Path) -> dict:
    policy = json.loads((data_dir / "handoff_policy.json").read_text(encoding="utf-8"))
    now = parse_dt(policy["reporting_at"])
    contacts = load_rows(data_dir, "contacts.csv")
    accounts = load_rows(data_dir, "accounts.csv")
    reps = load_rows(data_dir, "sales_reps.csv")
    activities = load_rows(data_dir, "activities.csv")
    holidays = {date.fromisoformat(row["date"]) for row in load_rows(data_dir, "holidays.csv")}
    calendar = policy["business_calendar"]

    accounts_by_id = {row["account_id"]: row for row in accounts}
    accounts_by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in accounts:
        accounts_by_domain[row["domain"].lower()].append(row)
    events_by_lead: dict[str, list[dict]] = defaultdict(list)
    for row in activities:
        events_by_lead[row["lead_id"]].append(row)
    reps_by_id = {row["rep_id"]: row for row in reps}
    projected = {row["rep_id"]: int(row["open_mqls"]) for row in reps}

    prepared: list[dict] = []
    mql_rule = policy["mql_rule"]
    for contact in contacts:
        review_reasons: list[str] = []
        account = None
        resolution = "unresolved"
        if contact["account_id"] and contact["account_id"] in accounts_by_id:
            account = accounts_by_id[contact["account_id"]]
            resolution = "account_id"
        else:
            domain = contact["email"].rsplit("@", 1)[-1].lower()
            matches = accounts_by_domain.get(domain, [])
            if len(matches) == 1:
                account = matches[0]
                resolution = "unique_email_domain"
            else:
                review_reasons.append("ambiguous_account_domain" if len(matches) > 1 else "unmatched_account")

        scored = score_contact(contact, account, events_by_lead[contact["lead_id"]], policy, now)
        if contact["current_stage"] == "Customer" or (account is not None and truthy(account["is_customer"])):
            stage = "Customer"
        elif scored["disqualifiers"]:
            stage = "Disqualified"
        elif account is None:
            stage = contact["current_stage"] if contact["current_stage"] == "MQL" else "Lead"
        elif contact["current_stage"] == "MQL":
            stage = "MQL"
        elif (
            scored["fit_score"] >= int(mql_rule["minimum_fit"])
            and scored["engagement_score"] >= int(mql_rule["minimum_engagement"])
            and scored["total_score"] >= int(mql_rule["minimum_total"])
        ):
            stage = "MQL"
        else:
            stage = contact["current_stage"]

        handoff_at = None
        if stage == "MQL":
            if contact["current_stage"] == "MQL" and contact["mql_at"]:
                handoff_at = parse_dt(contact["mql_at"])
            elif scored["scoring_events"]:
                handoff_at = max(parse_dt(event["occurred_at"]) for event in scored["scoring_events"])
            else:
                handoff_at = parse_dt(contact["created_at"])
        prepared.append(
            {
                "contact": contact,
                "account": account,
                "account_resolution": resolution,
                "scores": scored,
                "lifecycle_stage": stage,
                "handoff_at": handoff_at,
                "review_reasons": review_reasons,
            }
        )

    def rep_eligible(rep_id: str, excluded: set[str]) -> bool:
        rep = reps_by_id.get(rep_id)
        return bool(rep and rep_id not in excluded and truthy(rep["available"]) and projected[rep_id] < int(rep["capacity"]))

    def choose(rep_ids: list[str], excluded: set[str]) -> str | None:
        eligible = [rep_id for rep_id in rep_ids if rep_eligible(rep_id, excluded)]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda rep_id: (
                projected[rep_id] / int(reps_by_id[rep_id]["capacity"]),
                parse_dt(reps_by_id[rep_id]["last_assigned_at"]),
                rep_id,
            ),
        )

    def route(item: dict, *, excluded: set[str]) -> tuple[str, str, list[str]]:
        contact = item["contact"]
        account = item["account"]
        exceptions: list[str] = []
        current = contact["current_owner_id"]
        if current and current not in excluded:
            current_rep = reps_by_id.get(current)
            if contact["current_stage"] == "MQL" and current_rep and truthy(current_rep["available"]):
                return current, "current_owner", exceptions
            if rep_eligible(current, excluded):
                return current, "current_owner", exceptions
            exceptions.append("current_owner_unavailable_or_at_capacity")
        named = account["named_owner_id"] if account is not None else ""
        if named and named not in excluded:
            if rep_eligible(named, excluded):
                return named, "named_account_owner", exceptions
            exceptions.append("named_owner_unavailable_or_at_capacity")

        if account is not None and account["industry"] == "Healthcare":
            selected = choose([row["rep_id"] for row in reps if row["team"] == "healthcare"], excluded)
            if selected:
                return selected, "healthcare_specialist", exceptions
        if account is not None and int(account["employee_count"]) >= int(policy["routing"]["enterprise_employee_min"]):
            region = "us" if account["country"] == "US" else "international"
            selected = choose([row["rep_id"] for row in reps if row["team"] == "enterprise" and row["region"] == region], excluded)
            if selected:
                return selected, f"enterprise_{region}", exceptions
        if account is not None:
            if account["country"] == "US":
                suffix = int(account["account_id"][1:]) % 3
                region = policy["routing"]["us_region_by_account_id_modulo"][str(suffix)]
            else:
                region = "international"
            selected = choose([row["rep_id"] for row in reps if row["team"] == "midmarket" and row["region"] == region], excluded)
            if selected:
                return selected, f"territory_{region}", exceptions
        selected = choose([row["rep_id"] for row in reps if row["team"] == "general"], excluded)
        if selected:
            return selected, "general_pool", exceptions
        return policy["routing"]["queue_owner_id"], "capacity_queue", exceptions

    decisions: list[dict] = []
    prepared.sort(key=lambda item: (item["handoff_at"] or now + timedelta(days=1), item["contact"]["lead_id"]))
    sales_types = set(policy["sla"]["sales_contact_activity_types"])
    for item in prepared:
        contact = item["contact"]
        scores = item["scores"]
        stage = item["lifecycle_stage"]
        handoff_at = item["handoff_at"]
        review_reasons = list(item["review_reasons"])
        assigned_owner = None
        routing_reason = "not_applicable"
        due_at = None
        sla_status = "not_applicable"
        next_action = "none"
        first_contact_at = None

        if stage == "MQL" and handoff_at is not None:
            due_at = add_business_hours(handoff_at, policy["sla"]["first_contact_business_hours"], calendar, holidays)
            reassign_at = add_business_hours(handoff_at, policy["sla"]["reassign_after_business_hours"], calendar, holidays)
            contacts_after = [
                parse_dt(event["occurred_at"])
                for event in events_by_lead[contact["lead_id"]]
                if event["activity_type"] in sales_types and parse_dt(event["occurred_at"]) >= handoff_at
            ]
            first_contact_at = min(contacts_after) if contacts_after else None
            if first_contact_at is not None:
                sla_status = "contacted_on_time" if first_contact_at <= due_at else "contacted_late"
                assigned_owner = contact["current_owner_id"] or None
                routing_reason = "engaged_existing_owner" if assigned_owner else "missing_contact_owner"
                if not assigned_owner:
                    assigned_owner, routing_reason, exceptions = route(item, excluded=set())
                    review_reasons.extend(exceptions)
                    review_reasons.append("sales_contact_without_owner")
                    if assigned_owner != policy["routing"]["queue_owner_id"]:
                        projected[assigned_owner] += 1
                next_action = "none" if sla_status == "contacted_on_time" else "record_sla_breach"
            else:
                excluded: set[str] = set()
                if now > reassign_at and contact["current_owner_id"]:
                    excluded.add(contact["current_owner_id"])
                    old_owner = contact["current_owner_id"]
                    if old_owner in projected:
                        projected[old_owner] = max(0, projected[old_owner] - 1)
                    review_reasons.append("sla_reassignment")
                assigned_owner, routing_reason, exceptions = route(item, excluded=excluded)
                review_reasons.extend(exceptions)
                changed_owner = bool(contact["current_owner_id"] and assigned_owner != contact["current_owner_id"])
                if assigned_owner == policy["routing"]["queue_owner_id"]:
                    review_reasons.append("no_rep_capacity")
                    next_action = "manual_assignment_required"
                else:
                    if assigned_owner != contact["current_owner_id"]:
                        projected[assigned_owner] += 1
                    if now > reassign_at:
                        next_action = "reassign_and_create_urgent_task"
                    elif now > due_at:
                        next_action = "reassign_and_alert_manager" if changed_owner else "alert_manager_and_keep_task_open"
                    else:
                        next_action = "reassign_and_create_followup_task" if changed_owner else "create_followup_task"
                if now > reassign_at:
                    sla_status = "breached_48h"
                elif now > due_at:
                    sla_status = "breached_4h"
                else:
                    sla_status = "within_sla"

        review_reasons = list(dict.fromkeys(review_reasons))
        decisions.append(
            {
                "lead_id": contact["lead_id"],
                "resolved_account_id": item["account"]["account_id"] if item["account"] else None,
                "account_resolution": item["account_resolution"],
                "fit_score": scores["fit_score"],
                "engagement_score": scores["engagement_score"],
                "negative_score": scores["negative_score"],
                "total_score": scores["total_score"],
                "disqualifiers": scores["disqualifiers"],
                "lifecycle_stage": stage,
                "assigned_owner_id": assigned_owner,
                "routing_reason": routing_reason,
                "handoff_at": iso(handoff_at),
                "first_contact_due_at": iso(due_at),
                "first_contact_at": iso(first_contact_at),
                "sla_status": sla_status,
                "next_action": next_action,
                "human_review_required": bool(review_reasons),
                "human_review_reasons": review_reasons,
            }
        )

    decisions.sort(key=lambda row: row["lead_id"])
    return {
        "reporting_at": policy["reporting_at"],
        "summary": {
            "contact_count": len(decisions),
            "lifecycle_counts": dict(sorted(Counter(row["lifecycle_stage"] for row in decisions).items())),
            "sla_counts": dict(sorted(Counter(row["sla_status"] for row in decisions).items())),
            "owner_counts": dict(sorted(Counter(row["assigned_owner_id"] or "unassigned" for row in decisions).items())),
            "human_review_count": sum(row["human_review_required"] for row in decisions),
        },
        "decisions": decisions,
    }
