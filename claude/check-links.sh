#!/usr/bin/env bash
# ~/.config/claude is the source of truth; ~/.claude holds only symlinks into it.
# Prints anything that breaks that: real config files in ~/.claude, dangling links,
# and things in ~/.config/claude that nothing links to. Silent when clean.
set -u
SRC=~/.config/claude; DST=~/.claude; bad=0
for f in CLAUDE.md settings.json rules; do
  [ "$(readlink "$DST/$f")" = "$SRC/$f" ] || { echo "not linked: $DST/$f"; bad=1; }
done
for d in skills agents; do
  for p in "$DST/$d"/*; do
    [ -e "$p" ] || [ -L "$p" ] || continue
    n=$(basename "$p")
    if [ ! -L "$p" ]; then echo "real file in $DST/$d: $n"; bad=1
    elif [ ! -e "$p" ]; then echo "dangling: $p"; bad=1
    elif [ "$(readlink "$p")" != "$SRC/$d/$n" ]; then echo "links elsewhere: $p -> $(readlink "$p")"; bad=1; fi
  done
  for p in "$SRC/$d"/*; do
    [ -e "$p" ] || continue
    [ -L "$DST/$d/$(basename "$p")" ] || { echo "unlinked: $p"; bad=1; }
  done
done
for p in "$DST"/skills/.trash "$DST"/skills/synced; do [ -e "$p" ] && { echo "leftover: $p"; bad=1; }; done
python3 -c 'import json,os;a=json.load(open(os.path.expanduser("~/.config/claude/mcp.json")))["mcpServers"];b=json.load(open(os.path.expanduser("~/.claude.json"))).get("mcpServers");raise SystemExit(a!=b)' || { echo "mcp drift: run ~/.config/claude/mcp-sync.sh"; bad=1; }
exit $bad
