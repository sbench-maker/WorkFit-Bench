# Operations analysis brief

This directory is a frozen, fictional export from the `OperationsTelemetry` ADX database. The CSV files represent the tables named in `table_schemas.json`; all timestamps are UTC.

For this review, a failed request is `Success == false`. Examine complete one-hour UTC bins by service and region. Treat a deployment regression as two or more consecutive bins after a deployment where both the service p95 target and maximum error rate in `ServiceObjectives` are breached. The incident ends at the first complete hour in which both measures recover. Use the equal-length window immediately before the incident as its baseline. Name the top affected endpoint by failed-request count during the incident, breaking a tie with higher p95 latency. Isolated or single-metric breaches are background noise, not the primary incident.
