#!/usr/bin/env python3
"""Generate the deterministic fictional marketing-performance fixture."""

from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path


OUT = Path(__file__).resolve().parent
CHANNELS = ("Paid Search", "Paid Social", "Email", "Organic Search")


def noise(day_index: int, channel_index: int, scale: float = 0.035) -> float:
    return 1.0 + scale * math.sin(day_index * 1.71 + channel_index * 2.13)


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def campaign_id(channel: str, month: int) -> str:
    prefix = {
        "Paid Search": "SEA",
        "Paid Social": "SOC",
        "Email": "EML",
        "Organic Search": "ORG",
    }[channel]
    return f"{prefix}-2026-{month:02d}"


def daily_row(day: date, channel: str, day_index: int, channel_index: int) -> dict[str, object]:
    weekday_factor = 0.68 if day.weekday() >= 5 else 1.0 + (0.035 if day.weekday() in (1, 2) else 0.0)
    n = noise(day_index, channel_index)
    coverage = 1.0

    if channel == "Paid Search":
        if day.month == 7:
            impressions = 8200 * weekday_factor * n
            ctr = 0.042
            spend = 1130 * weekday_factor * noise(day_index + 2, channel_index, 0.025)
            lead_rate = 0.055
        else:
            impressions = 8500 * weekday_factor * n
            ctr = 0.043
            spend = 1210 * weekday_factor * noise(day_index + 2, channel_index, 0.025)
            lead_rate = 0.056
            if date(2026, 8, 8) <= day <= date(2026, 8, 10):
                lead_rate *= 0.45
            if day >= date(2026, 8, 12):
                ctr *= 1.06
                lead_rate *= 1.27
        clicks = round(impressions * ctr)
        leads = round(clicks * lead_rate)
        mqls = round(leads * 0.52)
        customers = round(leads * 0.17)
        revenue = customers * 5200

    elif channel == "Paid Social":
        if day.month == 7:
            impressions = 19000 * weekday_factor * n
            ctr = 0.0125
            spend = 920 * weekday_factor * noise(day_index + 3, channel_index, 0.03)
            lead_rate = 0.040
        else:
            impressions = 20500 * weekday_factor * n
            ctr = 0.0123
            spend = 1030 * weekday_factor * noise(day_index + 3, channel_index, 0.03)
            lead_rate = 0.038
            if date(2026, 8, 5) <= day <= date(2026, 8, 15):
                ctr *= 1.32
                lead_rate *= 1.12
            elif date(2026, 8, 16) <= day <= date(2026, 8, 23):
                ctr *= 1.15
                lead_rate *= 1.04
            elif day >= date(2026, 8, 24):
                ctr *= 0.78
                lead_rate *= 0.90
                spend *= 1.05
            if date(2026, 8, 14) <= day <= date(2026, 8, 18):
                coverage = 0.60
        clicks = round(impressions * ctr)
        leads = round(clicks * lead_rate)
        mqls = round(leads * 0.42)
        customers = round(leads * 0.12)
        revenue = customers * 4200 * coverage

    elif channel == "Email":
        scheduled_send = day.weekday() in (1, 3)
        webinar_send = day in (date(2026, 8, 16), date(2026, 8, 18), date(2026, 8, 20))
        if not scheduled_send and not webinar_send:
            impressions = clicks = spend = leads = mqls = customers = revenue = 0
        else:
            impressions = (11900 if day.month == 7 else 13200) * noise(day_index, channel_index, 0.02)
            ctr = 0.031 if day.month == 7 else 0.032
            lead_rate = 0.082 if day.month == 7 else 0.086
            if webinar_send:
                impressions *= 1.12
                ctr *= 1.38
                lead_rate *= 1.34
            clicks = round(impressions * ctr)
            leads = round(clicks * lead_rate)
            mqls = round(leads * 0.48)
            customers = round(leads * 0.14)
            spend = 0
            revenue = customers * 4800

    else:  # Organic Search
        month_growth = 1.0 if day.month == 7 else 1.06
        impressions = 13200 * month_growth * weekday_factor * n
        ctr = 0.022
        lead_rate = 0.037
        if day >= date(2026, 8, 21):
            impressions *= 1.15
            ctr *= 1.10
            lead_rate *= 1.12
        if day == date(2026, 8, 28):
            impressions *= 2.40
            lead_rate *= 0.55
        clicks = round(impressions * ctr)
        leads = round(clicks * lead_rate)
        mqls = round(leads * 0.46)
        customers = round(leads * 0.13)
        spend = 0
        revenue = customers * 5000

    return {
        "date": day.isoformat(),
        "channel": channel,
        "campaign_id": campaign_id(channel, day.month),
        "impressions": int(round(impressions)),
        "clicks": int(clicks),
        "spend_usd": round(float(spend), 2),
        "leads": int(leads),
        "mqls": int(mqls),
        "new_customers": int(customers),
        "attributed_revenue_usd": round(float(revenue), 2),
        "revenue_tracking_coverage": coverage,
    }


def write_csv(name: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    daily = []
    for day_index, day in enumerate(daterange(date(2026, 7, 1), date(2026, 8, 31))):
        for channel_index, channel in enumerate(CHANNELS):
            daily.append(daily_row(day, channel, day_index, channel_index))
    write_csv("daily_channel_performance.csv", list(daily[0]), daily)

    campaigns = [
        {"campaign_id": "SEA-2026-07", "channel": "Paid Search", "campaign_name": "Core Intent Search", "start_date": "2026-07-01", "end_date": "2026-07-31", "objective": "demo requests"},
        {"campaign_id": "SEA-2026-08", "channel": "Paid Search", "campaign_name": "Core Intent + Short Form", "start_date": "2026-08-01", "end_date": "2026-08-31", "objective": "demo requests"},
        {"campaign_id": "SOC-2026-07", "channel": "Paid Social", "campaign_name": "Workflow Awareness", "start_date": "2026-07-01", "end_date": "2026-07-31", "objective": "qualified leads"},
        {"campaign_id": "SOC-2026-08", "channel": "Paid Social", "campaign_name": "Workflow Proof Creative", "start_date": "2026-08-01", "end_date": "2026-08-31", "objective": "qualified leads"},
        {"campaign_id": "EML-2026-07", "channel": "Email", "campaign_name": "Product Education Nurture", "start_date": "2026-07-01", "end_date": "2026-07-31", "objective": "demo requests"},
        {"campaign_id": "EML-2026-08", "channel": "Email", "campaign_name": "Automation Webinar Nurture", "start_date": "2026-08-01", "end_date": "2026-08-31", "objective": "webinar and demo conversions"},
        {"campaign_id": "ORG-2026-07", "channel": "Organic Search", "campaign_name": "Evergreen Workflow Content", "start_date": "2026-07-01", "end_date": "2026-07-31", "objective": "inbound leads"},
        {"campaign_id": "ORG-2026-08", "channel": "Organic Search", "campaign_name": "Operations Benchmark Guide", "start_date": "2026-08-01", "end_date": "2026-08-31", "objective": "inbound leads"},
    ]
    write_csv("campaigns.csv", list(campaigns[0]), campaigns)

    events = [
        {"event_id": "EVT-01", "start_date": "2026-08-05", "end_date": "2026-08-05", "channel": "Paid Social", "campaign_id": "SOC-2026-08", "event_type": "creative_launch", "detail": "Customer-proof video and new hook launched."},
        {"event_id": "EVT-02", "start_date": "2026-08-08", "end_date": "2026-08-10", "channel": "Paid Search", "campaign_id": "SEA-2026-08", "event_type": "site_incident", "detail": "Demo form latency caused intermittent submission failures."},
        {"event_id": "EVT-03", "start_date": "2026-08-11", "end_date": "2026-08-11", "channel": "Paid Search", "campaign_id": "SEA-2026-08", "event_type": "site_fix", "detail": "Latency fix deployed; shorter form released for traffic from August 12."},
        {"event_id": "EVT-04", "start_date": "2026-08-14", "end_date": "2026-08-18", "channel": "Paid Social", "campaign_id": "SOC-2026-08", "event_type": "tracking_gap", "detail": "Server-side purchase events captured an estimated 60% of paid-social revenue; lead and customer counts are unaffected."},
        {"event_id": "EVT-05", "start_date": "2026-08-16", "end_date": "2026-08-20", "channel": "Email", "campaign_id": "EML-2026-08", "event_type": "webinar_push", "detail": "Three-message webinar invitation sequence ran."},
        {"event_id": "EVT-06", "start_date": "2026-08-21", "end_date": "2026-08-21", "channel": "Organic Search", "campaign_id": "ORG-2026-08", "event_type": "content_indexed", "detail": "Operations Benchmark Guide began ranking and receiving search traffic."},
        {"event_id": "EVT-07", "start_date": "2026-08-24", "end_date": "2026-08-31", "channel": "Paid Social", "campaign_id": "SOC-2026-08", "event_type": "creative_fatigue", "detail": "Frequency alert triggered; the existing audience saw the same creative repeatedly."},
        {"event_id": "EVT-08", "start_date": "2026-08-28", "end_date": "2026-08-28", "channel": "Organic Search", "campaign_id": "ORG-2026-08", "event_type": "syndication_spike", "detail": "A partner newsletter linked to the guide, creating a one-day traffic spike."},
    ]
    write_csv("campaign_events.csv", list(events[0]), events)

    targets = [
        {"scope": "Overall", "metric": "leads", "target": 1750, "direction": "at_least", "unit": "count"},
        {"scope": "Overall", "metric": "mqls", "target": 900, "direction": "at_least", "unit": "count"},
        {"scope": "Paid Search", "metric": "leads", "target": 650, "direction": "at_least", "unit": "count"},
        {"scope": "Paid Search", "metric": "cpa", "target": 300, "direction": "at_most", "unit": "USD per customer"},
        {"scope": "Paid Search", "metric": "roas", "target": 16.0, "direction": "at_least", "unit": "ratio"},
        {"scope": "Paid Social", "metric": "leads", "target": 330, "direction": "at_least", "unit": "count"},
        {"scope": "Paid Social", "metric": "cpa", "target": 700, "direction": "at_most", "unit": "USD per customer"},
        {"scope": "Paid Social", "metric": "roas", "target": 5.3, "direction": "at_least", "unit": "ratio"},
        {"scope": "Email", "metric": "leads", "target": 400, "direction": "at_least", "unit": "count"},
        {"scope": "Organic Search", "metric": "leads", "target": 360, "direction": "at_least", "unit": "count"},
        {"scope": "Paid total", "metric": "spend", "target": 62000, "direction": "at_most", "unit": "USD"},
    ]
    write_csv("august_targets.csv", list(targets[0]), targets)


if __name__ == "__main__":
    main()
