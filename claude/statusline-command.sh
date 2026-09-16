#!/bin/bash

input=$(cat)

RESET=$'\033[0m'
DIM=$'\033[2m'
MODEL_COLOR=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'

model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
five=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')

pct_color() {
  int=${1%.*}
  if [ "$int" -ge 80 ]; then
    printf '%s' "$RED"
  elif [ "$int" -ge 50 ]; then
    printf '%s' "$YELLOW"
  else
    printf '%s' "$GREEN"
  fi
}

sep="${DIM} | ${RESET}"
out=""

if [ -n "$model" ]; then
  out="${MODEL_COLOR}${model}${RESET}"
fi

if [ -n "$used" ]; then
  c=$(pct_color "$used")
  seg="ctx: ${c}$(printf '%.0f' "$used")%${RESET}"
  if [ -n "$out" ]; then out="${out}${sep}${seg}"; else out="$seg"; fi
fi

if [ -n "$five" ]; then
  c=$(pct_color "$five")
  seg="usg: ${c}$(printf '%.0f' "$five")%${RESET}"
  if [ -n "$five_reset" ]; then
    now=$(date +%s)
    diff=$((five_reset - now))
    [ "$diff" -lt 0 ] && diff=0
    h=$((diff / 3600))
    m=$(( (diff % 3600) / 60 ))
    seg="${seg}${sep}rst: $(printf '%dH.%02d' "$h" "$m")"
  fi
  if [ -n "$out" ]; then out="${out}${sep}${seg}"; else out="$seg"; fi
fi

printf '%s%s' "$out" "$RESET"
