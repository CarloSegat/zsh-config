# Subagent models

Skills say "your configured <role> model (default `sonnet` / `opus`)". Resolve the role here. A role with no line inherits the parent model.

`qwen-worker` is a custom agent (local gateway, zero token cost, tools: Bash/Read/Glob/Grep/Edit/Write, no MCP, no Agent). Use it wherever the task is literal and the fan-out is wide.

- code (bug-fix, feature, refactoring delegates): `general-purpose`, `model: sonnet`; hardest changes (cross-cutting design, concurrency, subtle algorithms) `model: opus`
- trivial mechanical edits: `qwen-worker`
- how-explorer: `Explore`; more than 3 explorers → `qwen-worker`
- how-explainer: `Explore`, `model: opus`
- why-investigators: `general-purpose`, `model: sonnet` (need MCP tools, so not qwen)
- why-synthesizer: `general-purpose`, `model: opus`
- architect runners: `general-purpose`, one each on `opus`, `fable`, `sonnet`
- arena runners: same as architect runners
- prose and judgment: `model: opus`

`qwen-worker` is the only local agent left. The others (`local-gpt-oss`,
`local-mistral-medium`, `local-mistral-large`, `local-qwen-coder`,
`qwen-coder-worker`) were deleted 2026-09-20 as not worth their output; the
only local models still worth an agent are `qwen3.8-flash-next` and
`qwen3.8:27b`.

## Local models that do not use tools

Measured 2026-09-17: given a `read_file` tool and a question about a file they
could not otherwise see, each local model either called the tool or answered
without it.

| model | verdict | note |
|---|---|---|
| `qwen3-coder-next:q8_0` | calls tools | 12s |
| `qwen3.6:35b-a3b` | calls tools | 11s, fastest |
| `qwen3.8-flash-next:125b` | calls tools | 15s |
| `gpt-oss:120b` | calls tools | 21s |
| `gemma4:31b` | calls tools | 37s |
| `qwen3.8:27b` | calls tools | 45s |
| `nemotron-3.5-lightning:30b-a3b` | calls tools | 36s |
| `nemotron-3-super:120b` | calls tools | 109s |
| `mistral-medium-3.5:128b` | calls tools | 157s |
| `qwen3.5:122b` | calls tools | 364s, slowest |
| `llama4:16x17b` | **no** | emits OpenAI-format `{"name":...,"parameters":...}` as text, not an Anthropic `tool_use` block |
| `mistral-large:123b` | **no** | replies "I will now read the file", never calls |
| `deepseek-r1:70b` | **no** | refuses, or fabricates when given a template to imitate |

The `local-deepseek` and `local-mistral` agents were deleted on 2026-09-18: both
failed this test, and `mistral-large:123b` is beaten outright by
`mistral-medium-3.5:128b`, the same vendor's newer model, which passes. Vintage
is the variable, not the vendor — do not generalise a failure to a family.

How they failed in practice (arena run, `menu-roamers`, 2026-09-17): both made
zero tool calls on prompts naming the exact files to read, and fabricated the
answer — invented quotes, invented line numbers, invented a score table.
`local-mistral` did it twice; the second prompt opened with four mandatory reads
and voided any score lacking a verbatim quote, and it fabricated anyway.

Not fixable by prompting or by config: Ollama's `/v1/messages` does not support
`tool_choice` (Ollama docs, "Not supported"), so no request can force a call. Do
not re-add `tool_choice` to the gateway hoping it will.

Before trusting any local model in a new role, re-run the probe: any request
carrying a tool plus a question unanswerable without it. A model that answers
confidently with zero tool calls has fabricated, whatever the reply looks like.
