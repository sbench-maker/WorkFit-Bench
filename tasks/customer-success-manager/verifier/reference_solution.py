#!/usr/bin/env python3
"""Build the reference weekly customer-success triage artifact."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime as RealDateTime
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "reference_models"))

import churn_risk_analyzer as churn  # noqa: E402
import expansion_opportunity_scorer as expansion  # noqa: E402
import health_score_calculator as health  # noqa: E402


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))


class FrozenDateTime(RealDateTime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 9, 9)
        return value if tz is None else value.replace(tzinfo=tz)


churn.datetime = FrozenDateTime


def validate_customer(customer: dict, policy: dict) -> list[str]:
    issues: list[str] = []
    customer_id = customer.get("customer_id")
    if not isinstance(customer_id, str) or not customer_id.strip():
        issues.append("missing_customer_id")
    if customer.get("segment") not in policy["data_quality"]["allowed_segments"]:
        issues.append(f"unsupported_segment:{customer.get('segment')}")
    arr = customer.get("arr")
    if not isinstance(arr, (int, float)) or isinstance(arr, bool) or arr <= 0:
        issues.append("nonpositive_arr")
    date_value = customer.get("contract_end_date")
    try:
        RealDateTime.strptime(date_value, "%Y-%m-%d")
    except (TypeError, ValueError):
        issues.append("missing_or_invalid_contract_end_date")

    missing_groups = [name for name in policy["data_quality"]["required_groups"] if not isinstance(customer.get(name), dict)]
    if missing_groups:
        issues.append("missing_groups:" + ",".join(sorted(missing_groups)))

    contract = customer.get("contract") if isinstance(customer.get("contract"), dict) else {}
    licensed = contract.get("licensed_seats")
    active = contract.get("active_seats")
    if not isinstance(licensed, int) or licensed <= 0:
        issues.append("invalid_licensed_seats")
    elif not isinstance(active, int) or not 0 <= active <= licensed:
        issues.append("active_seats_outside_license_range")

    product_usage = customer.get("product_usage") if isinstance(customer.get("product_usage"), dict) else {}
    for module, values in product_usage.items():
        if not isinstance(values, dict):
            issues.append(f"invalid_module_record:{module}")
            continue
        usage_pct = values.get("usage_pct")
        if not isinstance(usage_pct, (int, float)) or isinstance(usage_pct, bool) or not 0 <= usage_pct <= 100:
            issues.append(f"invalid_module_usage:{module}")
        elif values.get("adopted") is False and usage_pct != 0:
            issues.append(f"unadopted_module_has_usage:{module}")

    previous = customer.get("previous_period") if isinstance(customer.get("previous_period"), dict) else {}
    required_previous = {"usage_score", "engagement_score", "support_score", "relationship_score", "overall_score"}
    missing_previous = sorted(required_previous - set(previous))
    if missing_previous:
        issues.append("missing_previous_period_fields:" + ",".join(missing_previous))
    return issues


def days_to_renewal(date_value: str, snapshot_date: str) -> int:
    target = RealDateTime.strptime(date_value, "%Y-%m-%d")
    snapshot = RealDateTime.strptime(snapshot_date, "%Y-%m-%d")
    return max((target - snapshot).days, 0)


def evidence_for(health_row: dict, risk_row: dict) -> list[str]:
    evidence = [item["signal"] for item in risk_row.get("warning_signals", [])[:3]]
    declining = [name for name, direction in health_row.get("trends", {}).items() if name != "overall" and direction == "declining"]
    if declining:
        evidence.append("Declining health dimensions: " + ", ".join(declining))
    if health_row.get("classification") == "red":
        evidence.append(f"Health score {health_row['overall_score']} is red for the {health_row['segment']} segment")
    if not evidence:
        evidence.append(f"Churn risk score {risk_row['risk_score']} ({risk_row['risk_tier']})")
    return evidence[:4]


def next_intervention(health_row: dict, risk_row: dict) -> str:
    actions = risk_row.get("recommended_actions", [])
    if any(item.get("severity") == "critical" for item in risk_row.get("warning_signals", [])):
        return "Schedule executive-to-executive call within 48 hours"
    if risk_row.get("risk_tier") in {"critical", "high"} and actions:
        return actions[0]
    recommendations = health_row.get("recommendations", [])
    if recommendations:
        return recommendations[0]
    return "Schedule an immediate health recovery review with the account team"


def next_growth_action(expansion_row: dict) -> str:
    opportunity = expansion_row["opportunities"][0]
    category = opportunity.get("category")
    if category == "seat_expansion":
        return "Validate the hiring and seat-demand forecast before involving the account executive"
    if category == "tier_upgrade":
        return f"Confirm need for {opportunity.get('target_tier', 'the next tier')} capabilities with the economic buyer"
    if category == "module_cross_sell":
        return f"Run discovery on the {opportunity.get('module', 'recommended')} use case before a commercial proposal"
    return f"Validate the {opportunity.get('department', 'new department')} rollout sponsor and success outcome"


def solve(portfolio: dict, policy: dict) -> dict:
    valid: list[dict] = []
    human_review: list[dict] = []
    seen_ids: set[str] = set()
    for customer in portfolio["customers"]:
        issues = validate_customer(customer, policy)
        customer_id = customer.get("customer_id", "unknown")
        if customer_id in seen_ids:
            issues.append("duplicate_customer_id")
        seen_ids.add(customer_id)
        if issues:
            human_review.append({
                "customer_id": customer_id,
                "name": customer.get("name", "Unknown"),
                "issues": issues,
                "disposition": "Excluded from scoring and action queues pending CRM correction",
            })
        else:
            valid.append(customer)

    health_rows = {row["customer_id"]: health.calculate_health_score(row) for row in valid}
    risk_rows = {row["customer_id"]: churn.analyse_churn_risk(row) for row in valid}
    expansion_rows = {row["customer_id"]: expansion.analyse_expansion(row) for row in valid}

    # Replace wall-clock-derived presentation fields with the frozen review date.
    for customer in valid:
        customer_id = customer["customer_id"]
        days = days_to_renewal(customer["contract_end_date"], policy["snapshot_date"])
        risk_rows[customer_id]["days_to_renewal"] = days

    tier_severity = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    valid_by_id = {row["customer_id"]: row for row in valid}
    intervention_ids = [
        customer_id for customer_id in valid_by_id
        if health_rows[customer_id]["classification"] == "red"
        or risk_rows[customer_id]["risk_tier"] in {"high", "critical"}
        or any(item.get("severity") == "critical" for item in risk_rows[customer_id].get("warning_signals", []))
    ]
    intervention_ids.sort(key=lambda customer_id: (
        -max(
            tier_severity[risk_rows[customer_id]["risk_tier"]],
            4 if any(item.get("severity") == "critical" for item in risk_rows[customer_id].get("warning_signals", [])) else 0,
        ),
        -(risk_rows[customer_id]["days_to_renewal"] <= 30),
        -(health_rows[customer_id]["trends"]["overall"] == "declining"),
        -valid_by_id[customer_id]["arr"],
        customer_id,
    ))
    intervention_queue = []
    for rank, customer_id in enumerate(intervention_ids, 1):
        source = valid_by_id[customer_id]
        hrow = health_rows[customer_id]
        rrow = risk_rows[customer_id]
        intervention_queue.append({
            "rank": rank,
            "customer_id": customer_id,
            "name": source["name"],
            "segment": source["segment"],
            "arr": source["arr"],
            "health_score": hrow["overall_score"],
            "health_classification": hrow["classification"],
            "health_trend": hrow["trends"]["overall"],
            "churn_risk_score": rrow["risk_score"],
            "churn_risk_tier": rrow["risk_tier"],
            "days_to_renewal": rrow["days_to_renewal"],
            "evidence": evidence_for(hrow, rrow),
            "next_action": next_intervention(hrow, rrow),
        })

    expansion_ids = [
        customer_id for customer_id in valid_by_id
        if health_rows[customer_id]["classification"] == "green"
        and risk_rows[customer_id]["risk_tier"] == "low"
        and not any(item.get("severity") in {"high", "critical"} for item in risk_rows[customer_id].get("warning_signals", []))
        and expansion_rows[customer_id]["opportunity_count"] > 0
    ]
    expansion_ids.sort(key=lambda customer_id: (-expansion_rows[customer_id]["total_estimated_revenue"], customer_id))
    expansion_queue = []
    for rank, customer_id in enumerate(expansion_ids, 1):
        source = valid_by_id[customer_id]
        hrow = health_rows[customer_id]
        rrow = risk_rows[customer_id]
        erow = expansion_rows[customer_id]
        expansion_queue.append({
            "rank": rank,
            "customer_id": customer_id,
            "name": source["name"],
            "segment": source["segment"],
            "arr": source["arr"],
            "health_score": hrow["overall_score"],
            "health_classification": hrow["classification"],
            "churn_risk_score": rrow["risk_score"],
            "churn_risk_tier": rrow["risk_tier"],
            "total_estimated_revenue": erow["total_estimated_revenue"],
            "opportunity_count": erow["opportunity_count"],
            "top_opportunities": erow["opportunities"][:3],
            "next_action": next_growth_action(erow),
        })

    health_counts = {label: sum(row["classification"] == label for row in health_rows.values()) for label in ("green", "yellow", "red")}
    churn_counts = {tier: sum(row["risk_tier"] == tier for row in risk_rows.values()) for tier in ("critical", "high", "medium", "low")}
    arr_at_risk = sum(valid_by_id[cid]["arr"] for cid, row in risk_rows.items() if row["risk_tier"] in {"critical", "high"})
    modeled_revenue = sum(row["total_estimated_revenue"] for row in expansion_rows.values())
    modeled_opportunities = sum(row["opportunity_count"] for row in expansion_rows.values())
    eligible_revenue = sum(expansion_rows[cid]["total_estimated_revenue"] for cid in expansion_ids)

    return {
        "review_date": policy["snapshot_date"],
        "executive_summary": (
            f"Scored {len(valid)} of {len(portfolio['customers'])} accounts. "
            f"Intervene on {len(intervention_ids)} accounts representing ${sum(valid_by_id[cid]['arr'] for cid in intervention_ids):,.0f} ARR; "
            f"hold {len(human_review)} records for CRM correction. "
            f"There are {len(expansion_ids)} healthy, low-risk expansion candidates worth an estimated ${eligible_revenue:,.0f} ARR."
        ),
        "portfolio_summary": {
            "input_customers": len(portfolio["customers"]),
            "scored_customers": len(valid),
            "review_required": len(human_review),
            "health": {
                "average_score": round(sum(row["overall_score"] for row in health_rows.values()) / len(health_rows), 1),
                **{f"{label}_count": count for label, count in health_counts.items()},
            },
            "churn": {
                **{f"{tier}_count": count for tier, count in churn_counts.items()},
                "arr_at_risk": arr_at_risk,
            },
            "expansion": {
                "modeled_opportunities": modeled_opportunities,
                "modeled_estimated_revenue": modeled_revenue,
                "eligible_customers": len(expansion_ids),
                "eligible_estimated_revenue": eligible_revenue,
            },
        },
        "intervention_queue": intervention_queue,
        "expansion_queue": expansion_queue,
        "human_review": human_review,
        "caveats": [
            "Expansion revenue is a directional model estimate and requires discovery before a commercial proposal.",
            "Quarantined records are excluded from every score, rollup, and action queue until corrected.",
        ],
    }


def main() -> None:
    portfolio = json.loads((DATA_DIR / "customer_portfolio.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA_DIR / "scoring_policy.json").read_text(encoding="utf-8"))
    output = solve(portfolio, policy)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "output.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
