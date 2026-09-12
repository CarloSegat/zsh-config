# Source from ~/.zshrc. Defines claude-gw: Claude Code through the local model-routing gateway.
CLAUDE_GW_DIR="${CLAUDE_GW_DIR:-$HOME/.config/claude-gateway}"
CLAUDE_GW_SCRIPT="${CLAUDE_GW_SCRIPT:-$CLAUDE_GW_DIR/gateway.mjs}"

claude-gw-start() {
  local port="${GATEWAY_PORT:-4141}"
  nc -z 127.0.0.1 "$port" 2>/dev/null && return 0
  [ -r "$CLAUDE_GW_DIR/env" ] || { echo "claude-gw: missing $CLAUDE_GW_DIR/env" >&2; return 1; }
  (
    set -a; source "$CLAUDE_GW_DIR/env"; set +a
    nohup node "$CLAUDE_GW_SCRIPT" >> "$CLAUDE_GW_DIR/gateway.log" 2>&1 &
  )
  local i
  for i in {1..20}; do nc -z 127.0.0.1 "$port" 2>/dev/null && return 0; sleep 0.25; done
  echo "claude-gw: gateway did not start; see $CLAUDE_GW_DIR/gateway.log" >&2
  return 1
}

claude-gw() {
  claude-gw-start || return 1
  # Only the base URL is set: no ANTHROPIC_AUTH_TOKEN/API_KEY, so the claude.ai login stays active.
  # MAX_CONTEXT_TOKENS applies only to model IDs Claude Code doesn't recognize (qwen: 262144 on the TU server).
  ANTHROPIC_BASE_URL="http://127.0.0.1:${GATEWAY_PORT:-4141}" \
  CLAUDE_CODE_MAX_CONTEXT_TOKENS="${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-262144}" \
  claude --settings "$CLAUDE_GW_DIR/settings.json" "$@"
}

claude-gw-stop() { pkill -f "node .*gateway.mjs"; }
claude-gw-log() { tail -f "$CLAUDE_GW_DIR/gateway.log"; }
