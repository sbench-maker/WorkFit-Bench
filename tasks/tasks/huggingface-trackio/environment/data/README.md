# Offline experiment fixture

`train_sweep.py` replays frozen observations from `telemetry.csv` for the runs in
`run_specs.json`. `monitoring_policy.json` defines the diagnostics and decisions
used by the team. The files are fictional and locally constructed.

The image exposes an offline-compatible `trackio` Python module and `trackio`
command. It supports `init`, `log`, `alert`, and `finish`, plus JSON forms of
the project/run/metric/snapshot/alert queries documented by the injected skill.
Set `TRACKIO_DB_PATH` to choose the local store path. Set `SWEEP_DATA_DIR` to
replay a compatible fixture from another directory. Remote syncing and
webhooks are deliberately disabled.
