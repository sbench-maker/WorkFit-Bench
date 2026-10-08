# Driftline Replay campaign brief

Audience: engineering leaders and platform teams already using Driftline.

Launch date: September 15, 2026.

Product: Driftline Replay.

What it does: automatically replays recorded API workflows against a candidate build so teams can catch regressions before staging.

Mechanism: Driftline records a sanitized request-and-response shape, replays it against the candidate build, then compares status codes, schemas, and latency budgets.

Measured result from the frozen internal benchmark: Driftline Replay flagged 37 of 41 breaking behavior changes before staging. Median replay time was 84 seconds across 620 workflows.

Availability: included with Team and Scale plans at launch. No separate add-on is required.

Important limitation: Replay does not verify third-party side effects. A human must approve any workflow connected to production systems.

CTA options:

- X: say that it is available today for Team and Scale plans.
- Customer email: ask the recipient to reply with “replay” for a setup walkthrough.

Do not claim that Replay replaces staging, verifies third-party side effects, or runs production-connected workflows without human approval.
