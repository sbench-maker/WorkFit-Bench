# Breakwater v0.9 deployment review

This is a fictional, locally constructed pre-deployment snapshot. Review the Solidity sources in `contracts/`, the scoped entrypoint inventory, deployment configuration, token profiles, and threat scenarios. No chain access or external dependency is needed.

## Intended security boundaries

- `governor` alone may change protocol economics, replace the oracle pool, unpause components, or sweep surplus balances.
- `guardian` may pause but may not change fees or accounting.
- `keeper` alone may harvest vault yield.
- Administrative ownership transfer must require an explicit second-party acceptance.
- Swappers choose both their minimum acceptable output and transaction expiry.
- Vault shares are based on internally accounted assets actually received. Unsolicited transfers must not change a depositor's share price or become accounted assets through a public synchronization call.
- Listed assets can charge transfer fees, return `false`, omit return values, or invoke a receiver callback. Token interactions must not silently corrupt accounting.
- The stored collateral price must represent a manipulation-resistant 30-minute observation, not one reserve snapshot.
- A single high or critical exploit reachable in the deployment configuration blocks release. Medium findings require a documented fix plan before launch.

## Report contract

Return one JSON object. It should expose:

- the overall deployment gate decision and a short rationale;
- a findings collection in which each item has a stable identifier, severity, vulnerability category/title, affected source file and function, source evidence, exploit impact or preconditions, and remediation;
- a reviewed-entrypoints collection covering every `entrypoint_id` in `scope_inventory.json`, with either related finding identifiers or an explicit no-material-issue outcome;
- confirmed controls that distinguish defensive code from vulnerable paths.

Line ranges may be approximate when the function name and code evidence unambiguously locate the issue. Finding order and wording are not prescribed.
