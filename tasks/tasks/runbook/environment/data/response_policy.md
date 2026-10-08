# Production incident response policy — revision 7

Effective 2026-08-25. This policy overrides earlier shift notes and resolved-ticket suggestions.

1. Acknowledge the page and open or attach a change ID before a mutating command.
2. Collect queue, worker, downstream, state-store, and deployment evidence before choosing a mitigation.
3. One responder announces the hypothesis and command in `#relayforge-ops`; a second responder confirms region and placeholders for production mutations.
4. Do not purge the queue, delete worker pods, retry the entire backlog, or raise workers above 18 without Incident Commander approval.
5. When a poison event ID is absent or not stable across two reads, do not quarantine by tenant or queue range; escalate to Integration Runtime.
6. Escalate to the Incident Commander if queue age reaches 900 seconds, three tenants are delayed, or no 15% depth reduction is seen within 10 minutes after mitigation.
7. Escalate provider 429 of 10% or more to Integration Reliability. Escalate state-store lag of 200 ms or more to Platform State; do not scale while queue telemetry is unreliable.
8. Record every mutation and its result in the incident ticket. Close only after three healthy five-minute samples and a tenant delivery probe succeeds.
