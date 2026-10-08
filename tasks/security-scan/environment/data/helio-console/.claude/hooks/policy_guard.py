#!/usr/bin/env python3
import json
import sys

payload = json.load(sys.stdin)
tool = payload.get("tool_name", "")
command = payload.get("tool_input", {}).get("command", "")
blocked = tool == "Bash" and command.startswith("rm -rf ")
print(json.dumps({"decision": "block" if blocked else "allow"}))
