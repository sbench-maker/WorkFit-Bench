# RelayForge production command reference

Commands below are approved for production. Replace angle-bracket placeholders; do not copy literal placeholder text into the shell. Commands are read-only unless marked **mutating**.

## Establish context and inspect

```bash
pagerctl ack <INCIDENT_ID> --service webhook-delivery
opsctl queue status --service webhook-delivery --env prod --region <REGION>
opsctl workers status --service webhook-delivery --env prod --region <REGION> --pool async
opsctl downstream status --service webhook-delivery --env prod --region <REGION>
opsctl state-store status --service webhook-delivery --env prod --region <REGION>
opsctl deploy history --service webhook-delivery --env prod --region <REGION> --limit 5
```

`queue status` returns oldest age, depth, head event ID, and head error. `workers status` returns desired/ready/crash-loop counts. `downstream status` returns provider and five-minute 429/5xx rates. All read commands should return exit code 0 and a timestamp no older than two minutes.

## Approved mitigations

- Worker saturation, **mutating** (cap without Incident Commander approval is 18 replicas):
  `opsctl workers scale --service webhook-delivery --env prod --region <REGION> --pool async --replicas 18 --change <CHANGE_ID>`
- Downstream rate limiting, **mutating**:
  `opsctl throttle set --service webhook-delivery --env prod --region <REGION> --provider <PROVIDER> --rps 120 --ttl 30m --change <CHANGE_ID>`
- One identified poison event, **mutating** and reversible only with owner approval:
  `opsctl queue quarantine --service webhook-delivery --env prod --region <REGION> --event <EVENT_ID> --reason <INCIDENT_ID> --change <CHANGE_ID>`
- Confirmed release regression, **mutating** and Incident Commander approval required:
  `opsctl deploy rollback --service webhook-delivery --env prod --region <REGION> --to <LAST_GOOD_VERSION> --change <CHANGE_ID>`

## Verification and reversal

Use the same `queue status`, `workers status`, and `downstream status` commands for each recovery sample. Reverse temporary capacity with:
`opsctl workers scale --service webhook-delivery --env prod --region <REGION> --pool async --replicas 12 --change <CHANGE_ID>`

Clear a throttle early only after the provider has recovered:
`opsctl throttle clear --service webhook-delivery --env prod --region <REGION> --provider <PROVIDER> --change <CHANGE_ID>`

Never auto-release a quarantined event. Integration Runtime must validate the corrected payload and approve:
`opsctl queue release --service webhook-delivery --env prod --region <REGION> --event <EVENT_ID> --change <CHANGE_ID>`
