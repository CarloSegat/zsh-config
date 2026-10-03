#!/usr/bin/env bash
# Wakes the orchestrator when delegated work stalls. Run with run_in_background
# after an agent says it is waiting on background work; it exits, printing
# STALLED, once no file under the given paths has changed for <minutes> and no
# process name matches <regex> (default godot|make|kubectl; names, not command
# lines, so the watcher's own paths never match). Ignores .git and .godot.
# Silent while work goes on.
# Usage: stall-watch.sh <minutes> <path>... [-- <process-name regex>]
set -u
[ $# -ge 2 ] || { echo "usage: stall-watch.sh <minutes> <path>... [-- <process-name regex>]" >&2; exit 2; }
minutes=$1; shift
paths=(); pattern='godot|make|kubectl'
while [ $# -gt 0 ]; do
  if [ "$1" = -- ]; then pattern=$2; break; fi
  paths+=("$1"); shift
done
for p in "${paths[@]}"; do [ -e "$p" ] || { echo "stall-watch: $p does not exist" >&2; exit 2; }; done
while true; do
  recent=$(find "${paths[@]}" \( -name .git -o -name .godot \) -prune -o -newermt "-$minutes minutes" -print 2>/dev/null | head -n 1)
  if [ -z "$recent" ] && ! pgrep "$pattern" >/dev/null; then
    echo "STALLED $(date +%T): nothing changed under ${paths[*]} for $minutes min and no process matches '$pattern'"
    exit 0
  fi
  sleep 60
done
