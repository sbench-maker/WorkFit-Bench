# Selected on-call shift notes

## 2026-08-03 — old note, superseded

When queue age spikes, I used `opsctl queue purge --region us-east` and then scaled to 24. It cleared quickly. — archived note from before policy revision 7

## 2026-08-29 — current handoff

Never use the purge line above. Policy revision 7 removed it after dropped deliveries. Check downstream and state-store before touching capacity. Eighteen is the no-IC ceiling.

## 2026-09-04 — current handoff

For a poison event, confirm the same head event twice. Quarantine only that event and retain its ID in the ticket. A tenant-wide quarantine hid unrelated healthy traffic in INC-2026-082.

## 2026-09-08 — current handoff

Throttle is safer than scale when the provider is returning 429s. The 30-minute TTL is deliberate; if the provider recovers early, clear it through a change. If the TTL expires while 429 remains high, contact Integration Reliability rather than repeatedly extending it.
