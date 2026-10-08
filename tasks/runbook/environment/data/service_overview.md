# RelayForge webhook delivery: service overview

This is a fictional internal service snapshot dated 2026-09-09. RelayForge accepts tenant webhooks, stores them in `relay-queue`, and dispatches them through the `async` worker pool. Production runs in `us-east` and `eu-west`. Times and alert windows are UTC.

## Alert and normal state

- Alert name: `WebhookQueueAgeHigh`.
- Warning: oldest queued event is above 300 seconds for 10 minutes. Critical: 900 seconds for 5 minutes.
- Normal worker count is 12 per region. A change ticket is required for any scaling action.
- Healthy recovery means oldest age below 120 seconds, queue depth falling at least 15% between each five-minute sample, delivery 5xx below 1%, and provider 429 below 2% for three consecutive samples.

## Signal interpretation

- `ready < desired` with downstream 429 below 2% points to worker saturation.
- A stable event ID at the head of the queue with repeated `schema_rejected` points to one poison event.
- Provider 429 at or above 10% points to downstream rate limiting; adding workers amplifies it.
- State-store lag at or above 200 ms, especially when queue age and depth disagree, makes queue telemetry unreliable.
- A deployment in the prior 30 minutes plus three or more crash-looping workers points to a release regression. The last known-good build is recorded by `opsctl deploy history`, not guessed from a ticket.

## Impact classification

Page the Incident Commander immediately when queue age reaches 900 seconds or three or more tenants are confirmed delayed. Otherwise treat the page as P2 while investigation continues.
