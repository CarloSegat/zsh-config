#!/bin/bash
# Every engine API a plan names, checked against the engine: ClassDB for engine classes,
# the declaration text (with the extends chain) for project class_names and autoloads.
set -uo pipefail
usage() { echo "usage: dumb-loop-api-check.sh <plan.md> <project-dir>"; exit 2; }
[[ $# -eq 2 && -f "$1" && -d "$2" ]] || usage
plan="$1"; project="$2"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
godot="${GODOT:-}"
[[ -z "$godot" ]] && godot="$(sed -n 's/^import: //p' "$plan" | head -1 | cut -d' ' -f1)"
[[ -n "$godot" && -x "$godot" ]] || godot="$(command -v godot || true)"
[[ -n "$godot" ]] || { [[ -x /Applications/Godot.app/Contents/MacOS/Godot ]] && godot=/Applications/Godot.app/Contents/MacOS/Godot; }
[[ -n "$godot" ]] || { echo "no Godot binary: set GODOT, or an import: line in the plan"; exit 2; }
tokens="$(mktemp)"; out="$(mktemp)"; trap 'rm -f "$tokens" "$out"' EXIT
python3 - "$plan" > "$tokens" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
skip = re.compile(r"\.(md|app|gd|tscn|tres|py|sh|json|png|txt)$")
found = set(re.findall(r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9]*\.[A-Za-z_][A-Za-z0-9_]*", text))
found |= set(re.findall(r"\bextends ([A-Z][A-Za-z0-9]*)", text))
found |= set(re.findall(r"(?<![A-Za-z0-9_])([A-Z][A-Za-z0-9]*)\.new\(", text))
for t in sorted(found):
    if not skip.search(t):
        print(t)
PY
[[ -s "$tokens" ]] || { echo "api-check: 0 tokens, 0 missing"; exit 0; }
"$godot" --headless --path "$project" --script "$here/dumb-loop-api-check.gd" -- "$tokens" > "$out" 2>&1
grep -q "^APICHECK" "$out" || { echo "api-check: the engine script produced no result lines"; tail -5 "$out"; exit 2; }
missing=0
while IFS= read -r line; do
  [[ "$line" == APICHECK* ]] || continue
  line="${line#APICHECK }"; echo "$line"
  [[ "$line" == MISSING* ]] && missing=$((missing + 1))
done < "$out"
echo "api-check: $missing missing"
[[ $missing -eq 0 ]]
