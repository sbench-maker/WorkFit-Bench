# First-response SLA training policy

This fictional exercise uses a fixed reporting snapshot of **2026-08-31 12:00 UTC**. The weekly cohort is every row in `tickets.csv`; all tickets opened during the supplied week are present.

## Eligibility

- Include production requests from `customer` and `partner` requesters.
- Exclude a row when `is_test` is `true` or `requester_type` is `employee`.
- Excluded rows must not contribute to any SLA count or rate.

## Targets

| Priority | First-response target |
|---|---:|
| urgent | 30 minutes |
| high | 120 minutes |
| normal | 480 minutes |
| low | 1,440 minutes |

Elapsed minutes are measured from `opened_at`. A response exactly at the target is **met**, not breached.

For an eligible row with a recorded `first_response_at`, classify it as `met` when elapsed minutes are at or below its target and `breached` otherwise. For an eligible row without a response, compare the snapshot with `opened_at`: it is `pending` while still within target and `breached` once the target has passed. Do not treat a blank response as zero minutes.

## Summaries

The worked section should summarize eligible tickets by priority with `eligible`, `met`, `breached`, `pending`, and `compliance_rate`. Compute compliance as `met / (met + breached)` and omit pending tickets from the rate denominator. Show the rate as a percentage rounded to one decimal place.

The practice section repeats the same summary by channel. All groups should be present, and group counts should reconcile to the eligible overall total.
