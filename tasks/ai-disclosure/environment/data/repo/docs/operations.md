# Retry-budget operations

Roll out to one canary tenant before enabling the default policy. Alert when
the five-minute saturation ratio stays above 0.85 and the denied-retry counter
is rising. During an incident, disable retries for the affected tenant before
raising the global capacity; raising capacity can amplify an upstream outage.

The dashboard should pair allowed and denied retry counts with upstream error
rate so operators do not mistake a healthy low-retry period for missing data.
