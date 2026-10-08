"""Command-line inspection for retry budgets."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="retry-budget")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--capacity", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true", help="show the decision without consuming budget")
    return parser
