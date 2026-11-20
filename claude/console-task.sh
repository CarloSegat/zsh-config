#!/usr/bin/env bash
# Runs /task-plan or /task-commits headless on Opus, billed to the Claude
# Console org through the ant profile "default" instead of the subscription.
# The Console API cannot reach the qwen gateway, so qwen-worker runs on Sonnet.
# Usage: console-task.sh plan|commits <task folder> [max usd, default 10]
set -euo pipefail

step=${1:-}
[ "$step" = plan ] || [ "$step" = commits ] || {
  echo "usage: console-task.sh plan|commits <task folder> [max usd]" >&2
  exit 2
}
task=$(cd "$2" && pwd)
repo=$(git -C "$task" rev-parse --show-toplevel)

worker=$(awk 'n == 2; /^---$/ { n++ }' ~/.config/claude/agents/qwen-worker.md)
agents=$(jq -n --arg p "$worker" '{"qwen-worker": {
  description: "Literal worker for one scoped read, grep or check job.",
  prompt: $p, tools: ["Bash", "Read", "Glob", "Grep", "Edit", "Write"],
  model: "sonnet"}}')

cd "$repo"
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_BASE_URL \
  -u CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_PROFILE=default \
  claude -p "/task-$step $task" --model opus --agents "$agents" \
    --permission-mode bypassPermissions --max-budget-usd "${3:-10}" \
    --output-format json |
  jq -r '(.result // .subtype), "cost: $\(.total_cost_usd)"'
