from src.cli import build_parser


def test_required_tenant_and_requested_flags():
    args = build_parser().parse_args(["--tenant", "north", "--capacity", "12", "--dry-run"])
    assert args.tenant == "north"
    assert args.capacity == 12
    assert args.dry_run is True

