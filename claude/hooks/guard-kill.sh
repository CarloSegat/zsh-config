#!/bin/sh
# PreToolUse(Bash): deny kills that can reach launchd's children. A detached
# process whose starter exited is reparented to launchd (pid 1), so a kill by
# parent pid can SIGTERM every app, Docker and the API gateway (2026-09-28).
# Kill only exact pids you started.
cmd=$(jq -r '.tool_input.command // empty')
deny() {
	jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
	exit 0
}
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])pkill([[:space:]][^;&|]*)?[[:space:]](-[A-Za-z]*P|--parent)'; then
	deny "pkill -P kills by parent pid; an orphan's parent is launchd (pid 1), which would SIGTERM every user process. Kill the exact pids you started: kill <pid> ..."
fi
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])kill([[:space:]]+-[A-Za-z0-9]+)*([[:space:]]+[0-9]+)*[[:space:]]+(--[[:space:]]+)?-?1([[:space:];&|)]|$)'; then
	deny "kill of pid 1 or -1 reaches launchd or every user process. Kill the exact pids you started."
fi
if printf '%s' "$cmd" | grep -q 'ppid' && printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])(p?kill|killall)([[:space:]]|$)|xargs[[:space:]]+kill'; then
	deny "Do not kill a pid derived from ppid in the same command: an orphan's parent is launchd (pid 1). Look up the parent first, check it, then kill exact pids in a separate command."
fi
