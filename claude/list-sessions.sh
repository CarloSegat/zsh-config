#!/bin/bash
# List all Claude Code sessions: size | date | project | title
# Title priority: customTitle (user rename) > aiTitle > first user prompt
for f in ~/.claude/projects/*/*.jsonl; do
  [ -e "$f" ] || continue
  proj=$(basename "$(dirname "$f")")
  sz=$(wc -c < "$f" | tr -d ' ')
  mt=$(stat -f%Sm -t '%Y-%m-%d' "$f")
  id=$(basename "$f" .jsonl)
  ct="$(dirname "$f")/$id/custom-title.json"
  title=$(grep -a -m1 -o '"customTitle":"[^"]*"' "$f" | sed 's/.*:"//;s/"$//')
  [ -z "$title" ] && [ -f "$ct" ] && title=$(jq -r '.customTitle // empty' "$ct" 2>/dev/null)
  [ -z "$title" ] && title=$(grep -a -m1 '"type":"ai-title"' "$f" | jq -r '.aiTitle // empty' 2>/dev/null)
  if [ -z "$title" ] || [ "$title" = "null" ]; then
    title=$(grep -a -m1 '"type":"user"' "$f" | jq -r '
      (.message.content // .content) |
      if type=="string" then . else (map(select(.type=="text").text)|join(" ")) end' 2>/dev/null | tr '\n' ' ' | cut -c1-80)
  fi
  [ -z "$title" ] && title="(no title)"
  printf '%s\t%s\t%s\t%s\t%s\n' "$sz" "$mt" "$proj" "$title" "$f"
done | sort -rn | awk -F'\t' '{
  s=$1; u="B";
  if (s>1048576) {s=s/1048576; u="M"} else if (s>1024) {s=s/1024; u="K"}
  printf "%7.1f%s  %s  %-45.45s  %s\n", s, u, $2, $3, $4
}'
