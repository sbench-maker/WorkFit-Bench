#!/usr/bin/env python3
"""Offline, stateful stand-in for the Firecrawl scrape/interact client."""
import json
from pathlib import Path

class LocalFirecrawl:
    def __init__(self, case_dir, trace_path=None):
        self.case_dir = Path(case_dir)
        self.data = json.loads((self.case_dir / "site_data.json").read_text())
        self.trace_path = Path(trace_path) if trace_path else None
        self.sessions = {}
        self.seq = 0
        self.trace = []

    def _record(self, event):
        self.trace.append(event)
        if self.trace_path:
            self.trace_path.write_text(json.dumps(self.trace, indent=2) + "\n")

    def scrape(self, url):
        self.seq += 1
        sid = f"browser-{self.seq}"
        self.sessions[sid] = {"category": None, "page": 1, "applied": False}
        self._record({"endpoint": "scrape", "url": url, "session_id": sid})
        return {"session_id": sid, "markdown": "# Aster Controls Catalog\nResults load after applying a category filter.", "requires_interaction": True}

    def interact(self, session_id, actions):
        if session_id not in self.sessions:
            raise ValueError("unknown browser session")
        state = self.sessions[session_id]
        extracted = None
        for action in actions:
            kind = action.get("type")
            if kind == "fill" and action.get("selector") == "#category":
                state["category"] = action.get("value")
            elif kind == "click" and action.get("selector") == "#apply":
                if not state["category"]:
                    raise ValueError("category must be filled before apply")
                state["page"] = 1
                state["applied"] = True
            elif kind == "click" and action.get("selector") == "button.next":
                if not state["applied"]:
                    raise ValueError("apply a filter before pagination")
                state["page"] += 1
            elif kind == "extract":
                if not state["applied"]:
                    raise ValueError("apply a filter before extraction")
                filtered = [r for r in self.data["records"] if r["category"] == state["category"]]
                size = self.data["page_size"]
                start = (state["page"] - 1) * size
                page = filtered[start:start + size]
                extracted = {"records": page, "page": state["page"], "has_next": start + size < len(filtered)}
            else:
                raise ValueError(f"unsupported action: {action}")
        self._record({"endpoint": "interact", "session_id": session_id, "actions": actions, "state": dict(state)})
        return extracted or {"ok": True, "state": dict(state)}
