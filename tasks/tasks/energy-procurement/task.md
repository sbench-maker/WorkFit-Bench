---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 600.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
---

Finance needs an award recommendation for the 2027 multi-site electricity RFP. Analyze the interval loads, tariffs, market scenarios, supplier bids, credit data, contract exceptions, and procurement policy in `/root/data/`; compare every eligible offer on total delivered cost, profile each facility, and propose a compliant award/hedge mix with base and stress-case budget exposure. Flag the credit or contract items that need finance or legal review and explain the trade-offs. Save the complete decision package as `/root/results/output.json`.

Report facility load factor as the dimensionless fraction `annual_kWh / (peak_kW * 8,760)`. Keep full-offer scenario costs separate from share-weighted award costs, and for base/high/low expose both total portfolio cost and signed variance versus the approved portfolio budget.
