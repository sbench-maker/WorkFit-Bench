#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def records(prefix, count, categories):
    rows = []
    for i in range(1, count + 1):
        category = categories[(i * 7 + i // 9) % len(categories)]
        rows.append({
            "id": f"{prefix}-{i:04d}",
            "name": f"Aster {category.title()} Control {i:03d}",
            "category": category,
            "status": "deprecated" if i % 29 == 0 else "active",
            "risk": ["low", "medium", "high", "critical"][(i * 5 + 2) % 4],
        })
    return rows

def write_case(name, prefix, count, page_size, categories, target):
    case = ROOT / name
    case.mkdir(parents=True, exist_ok=True)
    (case / "site_data.json").write_text(json.dumps({
        "site_name": "Aster Controls Catalog",
        "records": records(prefix, count, categories),
        "page_size": page_size,
        "target_category": target,
    }, indent=2) + "\n")
    (case / "request.json").write_text(json.dumps({
        "url": "mock://aster.example/catalog",
        "target_category": target,
        "exclude_status": "deprecated",
    }, indent=2) + "\n")

write_case("primary", "CTL", 243, 17, ["security", "workflow", "network", "storage"], "security")
write_case("regression", "REG", 218, 13, ["network", "security", "storage", "workflow", "identity"], "identity")
