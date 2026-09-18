# claude-gw — Claude Code model-routing gateway

Routing rule (`gateway.mjs`, localhost:4141):
- model `claude-*` → api.anthropic.com, request untouched → claude.ai Max login stays active
- any other model → TU Berlin Ollama `/v1/messages` with `Bearer $SECRET_TOM` → no subscription usage
- `count_tokens` for Ollama models → 404 locally (Claude Code falls back to estimates)

Files (this dir): `gateway.mjs`, `claude-gw.sh` (sourced by `zsh/.zshrc`), `settings.json` (picker rows), `env` (token, git-ignored; copy `env.example`), `gateway.log` (git-ignored).

| Command | What it does |
| --- | --- |
| `claude-gw` | Start gateway if needed, launch Claude Code through it (Opus default) |
| `claude-gw --model qwen3-coder-next:q8_0` | Same, session starts on qwen |
| `claude-gw -p "…" --model qwen3-coder-next:q8_0` | One-shot prompt on qwen |
| `/model` then `s` on the Qwen row | Switch this session to qwen (Enter would save it as global default) |
| `/model opus` | Back to Opus |
| `/model default` | Clear a saved qwen default if you pressed Enter |
| `claude-gw-start` | Start gateway only |
| `claude-gw-stop` | Kill gateway |
| `claude-gw-log` | Tail request log: `ts route model status ms in=… cache_read=… cache_write=… out=…` (error body on 4xx/5xx) |
| `set -a; source ~/.config/claude-gateway/env; set +a; node ~/.config/claude-gateway/gateway.mjs` | Gateway in foreground |
| `claude` | Plain Claude Code, direct to Anthropic, no Qwen row |

Subagent on qwen (works from an Opus session under `claude-gw`): `.claude/agents/qwen-worker.md` with frontmatter `model: qwen3-coder-next:q8_0`.
pstack (later): add the slug to `models.json` `available` and a role's `models`; run under `claude-gw`.

Server checks (`O=https://gateway.snet.tu-berlin.de/echelon/ollama`, `A="Authorization: Bearer $SECRET_TOM"`):

| Command | What it does |
| --- | --- |
| `curl -s $O/api/tags -H "$A" \| jq '.models[].name'` | List routable models |
| `curl -s $O/api/version -H "$A"` | Ollama version (needs ≥ 0.14) |
| `curl -s $O/api/ps -H "$A" \| jq '.models[].context_length'` | Effective context of loaded models (needs ≥ 32k) |

## Do not re-add `tool_choice`

`OLLAMA_DROP_TOP` strips `tool_choice` because Ollama's `/v1/messages` does not
support it (Ollama's Anthropic-compatibility doc lists it under "Not supported":
"Forcing specific tool use or disabling tools"). Forwarding it does not make a
weak model call tools; it only risks a 400. A local model that will not call
tools is a model problem — see "Local models that do not use tools" in
`~/.config/claude/rules/subagent-models.md`.
