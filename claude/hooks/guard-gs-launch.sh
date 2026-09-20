#!/bin/sh
# PreToolUse(Bash): deny ad-hoc emoji game-server launches. The only sanctioned
# path is emoji-gs/scripts/gs-dev.sh (make dev / make run), which registers
# the instance so a later reap can kill it when its session is gone.
cmd=$(jq -r '.tool_input.command // empty')
case "$cmd" in *gs-dev.sh*) exit 0 ;; esac
if printf '%s' "$cmd" | grep -Eq 'go (run|build) [^;&|]*cmd/server|/gs-server[[:space:]]|/gs-server$|GS_SERVER_ADDR=[^ ]+ +(nohup +)?[^ ]*/(gs[^ /]*|server)([[:space:]]|$)'; then
	jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Do not start the game server by hand. Use `make dev` / `make run` in emoji-gs (scripts/gs-dev.sh up), which registers the instance; another port: `GS_SERVER_ADDR=:8472 make run`. See emoji-gs/CLAUDE.md."}}'
fi
