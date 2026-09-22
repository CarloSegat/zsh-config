#!/usr/bin/env bash
# Increments a usage counter in logs.md. Called from PostToolUse hooks
# (settings.json) on Skill/Read/Bash — never run by hand.
# Usage: log-usage.sh <principles|skills|scripts> <name>
set -eu
cat=$1; name=$2
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/logs.md"
LOCK="$DIR/.logs.lock"

python3 - "$cat" "$name" "$LOG" "$LOCK" <<'EOF'
import sys, re, datetime, os, fcntl

cat, name, path, lockpath = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lockfd = os.open(lockpath, os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(lockfd, fcntl.LOCK_EX)

today = datetime.date.today().isoformat()

CATS = ["principles", "skills", "scripts"]
TITLES = {"principles": "Principles", "skills": "Skills", "scripts": "Scripts"}
data = {c: {} for c in CATS}

if os.path.exists(path):
    current = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"^## (Principles|Skills|Scripts)$", line)
            if m:
                current = {v: k for k, v in TITLES.items()}[m.group(1)]
                continue
            m = re.match(r"^- (\S+): (\d+) \(last: ([\d-]+)\)$", line)
            if m and current:
                data[current][m.group(1)] = (int(m.group(2)), m.group(3))

count, _ = data[cat].get(name, (0, today))
data[cat][name] = (count + 1, today)

out = ["# Usage Logs", "",
       "Auto-updated by hooks (settings.json) on every skill/principle/script use. Do not hand-edit.",
       ""]
for c in CATS:
    out.append(f"## {TITLES[c]}")
    for n in sorted(data[c]):
        n_count, last = data[c][n]
        out.append(f"- {n}: {n_count} (last: {last})")
    out.append("")

with open(path, "w") as f:
    f.write("\n".join(out).rstrip("\n") + "\n")
EOF
