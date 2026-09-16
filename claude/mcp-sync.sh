#!/usr/bin/env bash
# ~/.config/claude/mcp.json is the source of truth for user-scope MCP servers.
# Claude Code only reads them from ~/.claude.json (a state file, not versioned),
# so this copies the mcpServers block across. Idempotent. Restart sessions after.
set -euo pipefail
python3 - <<'PY'
import json, os, tempfile
src = os.path.expanduser("~/.config/claude/mcp.json")
dst = os.path.expanduser("~/.claude.json")
want = json.load(open(src))["mcpServers"]
d = json.load(open(dst))
if d.get("mcpServers") == want:
    print("mcp: in sync"); raise SystemExit
d["mcpServers"] = want
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dst), prefix=".claude.json.")
with os.fdopen(fd, "w") as f: json.dump(d, f, indent=2)
os.replace(tmp, dst)
print("mcp: synced", ", ".join(sorted(want)))
PY
