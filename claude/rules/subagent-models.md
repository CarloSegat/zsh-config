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
- arena runners (local, claude-gw session only): `local-qwen-coder`, `local-gpt-oss`, `local-deepseek`
- arena cross-judge (local): `local-mistral`
- plan critics: the three local arena runners
- prose and judgment: `model: opus`
