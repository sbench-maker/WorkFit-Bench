#!/usr/bin/env python3
from pathlib import Path
import sys

for raw in sys.argv[1:]:
    path = Path(raw)
    if path.name.startswith("."):
        raise SystemExit("hidden files require manual review")
