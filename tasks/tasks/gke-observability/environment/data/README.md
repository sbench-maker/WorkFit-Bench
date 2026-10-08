# Orion fleet observability export

This directory is a deterministic, fictional control-plane export captured at
`2026-08-17T09:00:00Z`. It does not contain live cloud data.

- `clusters.json` is the fleet inventory and current GKE observability state.
- `fleet_policy.json` is the approved target profile, dashboard/alert contract,
  component aliases, and rollout guardrails.
- `metric_inventory.csv` records whether each signal is present in the current
  snapshot. Absence can be caused by a disabled collection component and should
  be addressed before dependent dashboards or alerts are activated.

For update commands, use `--region` for regional clusters and `--zone` for zonal
clusters (or the equivalent `--location` form), and always name the project.
Clusters already at policy state should remain explicit no-ops, not receive a
gratuitous update command.
