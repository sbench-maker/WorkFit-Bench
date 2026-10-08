# ParcelPilot reservation service

This repository contains a small inventory-reservation library and an xUnit test project. The behavior to preserve is documented in `contracts/reservation_contract.md`; deterministic examples are in `contracts/reservation_cases.json`.

Run the suite offline from this directory:

```bash
dotnet test --no-restore
```

The existing test is only a smoke test. Expand the test project without changing production behavior or adding packages.
