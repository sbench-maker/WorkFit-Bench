#!/usr/bin/env python3
import json
import sys

KNOWN = {"packages", "services", "migrations", "scripts", "workers", "web", "ops", "config", "docs", "tests", "benchmarks"}
component = sys.argv[1] if len(sys.argv) > 1 else ""
if component not in KNOWN:
    print(json.dumps({"component": component, "status": "unknown"}))
    raise SystemExit(2)
print(json.dumps({"component": component, "status": "passed", "mode": "offline-fixture"}))
