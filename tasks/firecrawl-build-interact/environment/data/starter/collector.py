#!/usr/bin/env python3
"""Complete this catalog collector while preserving its command-line contract."""
import argparse
import json
from pathlib import Path
from firecrawl_mock import LocalFirecrawl

def collect(case_dir, trace_path):
    request = json.loads((Path(case_dir) / "request.json").read_text())
    client = LocalFirecrawl(case_dir, trace_path)
    # TODO: scrape, escalate to stateful interactions, apply the requested filter,
    # paginate through all result pages, and exclude the requested status.
    return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = collect(args.case, output.with_suffix(".trace.json"))
    output.write_text(json.dumps(rows, indent=2) + "\n")

if __name__ == "__main__":
    main()
