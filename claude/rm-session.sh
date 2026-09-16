#!/usr/bin/env bash
set -euo pipefail

SID="${1:-}"
GO="${2:-}"
[ -z "$SID" ] && { echo "usage: rm-session.sh <session-id> [--yes]"; exit 1; }

CC=~/.claude
TMP=/private/tmp/claude-$(id -u)

for f in "$CC"/sessions/*.json; do
  [ -e "$f" ] || continue
  if grep -q "\"sessionId\": *\"$SID\"" "$f"; then
    pid=$(basename "$f" .json)
    if kill -0 "$pid" 2>/dev/null; then
      echo "REFUSING: session $SID is live (pid $pid). Exit it first."; exit 1
    fi
  fi
done

paths=(
  "$CC"/projects/*/"$SID".jsonl
  "$CC"/projects/*/"$SID"
  "$CC"/tasks/"$SID"
  "$CC"/file-history/"$SID"
  "$CC"/session-env/"$SID"
  "$TMP"/*/"$SID"
)

echo "--- paths ---"
for p in "${paths[@]}"; do [ -e "$p" ] && du -sh "$p"; done
echo "--- refs ---"
echo "history.jsonl lines: $(grep -c "$SID" "$CC"/history.jsonl 2>/dev/null || echo 0)"
echo "sessions/*.json:     $(grep -l "$SID" "$CC"/sessions/*.json 2>/dev/null | wc -l | tr -d ' ')"
grep -q "$SID" ~/.claude.json 2>/dev/null && echo ".claude.json:        lastSessionId"

if [ "$GO" != "--yes" ]; then echo; echo "dry run. re-run with --yes to delete."; exit 0; fi

for p in "${paths[@]}"; do [ -e "$p" ] && rm -rf "$p"; done
grep -v "$SID" "$CC"/history.jsonl > "$CC"/history.jsonl.tmp 2>/dev/null \
  && mv "$CC"/history.jsonl.tmp "$CC"/history.jsonl
grep -l "$SID" "$CC"/sessions/*.json 2>/dev/null | xargs -r rm -f
python3 - "$SID" <<'PY'
import json, sys, os
sid = sys.argv[1]; p = os.path.expanduser("~/.claude.json")
d = json.load(open(p))
n = 0
for proj in d.get("projects", {}).values():
    if proj.get("lastSessionId") == sid:
        proj["lastSessionId"] = None; n += 1
if n:
    json.dump(d, open(p, "w"), indent=2)
    print(f".claude.json: cleared {n} lastSessionId")
PY
echo "done: $SID"
