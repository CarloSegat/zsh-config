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
- arena runners (local, claude-gw session only): `local-qwen-coder`, `local-gpt-oss`; a third slot only for a model with proven tool use (try `qwen-worker`, confirm it calls tools before trusting the draft)
- arena cross-judge (local): `local-gpt-oss` when the runners are qwen-family, else `local-qwen-coder`. No non-qwen, non-gpt-oss local model judges anything (see below)
- arena graft applier (local): `local-qwen-coder`
- plan critics: the local arena runners above (two, until a third proves it calls tools)
- dumb-loop thread executor: `qwen-coder-worker`; A/B against `qwen-worker` on the Water plan, findings per run recorded in `dumb_agents/RUNS.md`
- prose and judgment: `model: opus`

## Local models that do not use tools

Measured 2026-09-17, arena run on `menu-roamers`: `local-deepseek` and
`local-mistral` made zero tool calls on prompts that named the exact files to
read, and fabricated the answer — invented quotes, invented line numbers,
invented a score table. `local-mistral` did it twice; the second prompt opened
with four mandatory reads and voided any score without a verbatim quote, and it
fabricated anyway. Same prompt, same session, same gateway: `local-qwen-coder`
made 40 tool calls and `local-gpt-oss` 3, both producing real work.

Not fixable by prompting or by config: Ollama's `/v1/messages` does not support
`tool_choice` (Ollama docs, "Not supported"), so no request can force a call.
Do not re-add `tool_choice` to the gateway hoping it will.

Never give either a role that requires reading a file, running a command, or
inspecting a repo. They are **inline-only**: everything they judge must be pasted
into the prompt. Inline use is itself unverified — check a first inline result
against the source before trusting a second.
