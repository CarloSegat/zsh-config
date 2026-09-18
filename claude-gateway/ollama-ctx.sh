#!/bin/bash
# Effective context window per model on the Ollama server: load each model with a
# one-token request through the same /v1/messages path the gateway uses, then read
# context_length from /api/ps. usage: ollama-ctx.sh <model> [<model>...]
set -u
source "$(dirname "$0")/env"
B="${OLLAMA_BASE_URL:-https://gateway.snet.tu-berlin.de/echelon/ollama}"
[[ $# -ge 1 ]] || { echo "usage: ollama-ctx.sh <model> [<model>...]"; exit 2; }
for M in "$@"; do
  curl -s -m 300 -o /dev/null -H "Authorization: Bearer $SECRET_TOM" -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01' \
    "$B/v1/messages" -d "{\"model\":\"$M\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"
  curl -s -m 30 -H "Authorization: Bearer $SECRET_TOM" "$B/api/ps" | python3 -c '
import sys, json
m = sys.argv[1]
rows = [x for x in json.load(sys.stdin).get("models", []) if x.get("name") == m or x.get("model") == m]
print(m, "context_length =", rows[0].get("context_length") if rows else "not loaded (request failed?)")' "$M"
done
