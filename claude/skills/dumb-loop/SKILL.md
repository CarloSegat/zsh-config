---
name: dumb-loop
description: "Run a backlog task through qwen-worker threads from a strong-model plan, review the merge, turn every mistake into a rule, re-run to prove the rule. Use for /dumb-loop <task>."
---

### dumb-loop

The strong model plans and reviews; `qwen-worker` (free) writes the code. Every mistake qwen makes becomes a rule: engine/language mistakes go to `~/.config/claude/dumb_agents/<LANG>.md`, planning mistakes go to this file. Round 2 re-runs the same plan to prove the rule.

**Hard limits.**
- No argument → print `usage: /dumb-loop <backlog task name>` and stop.
- `ANTHROPIC_BASE_URL` unset → print `dumb-loop needs a claude-gw session: run claude-gw, then /dumb-loop <task>` and stop before Phase 0. Every local agent (`qwen-worker`, `local-*`) is only reachable through the gateway, planning included.
- Only the model runs on the Ollama server. Every tool call a local agent makes (Bash, Read, Edit) executes in this Claude Code process, on this machine, against these worktrees. Godot, python, the repo and the scripts under `skills/dumb-loop/` must exist here; the server needs nothing.
- Strong-model contexts: this session plus the one `/code-review` fork. `Agent` types allowed: `qwen-worker` and the `local-*` agents (Phase 1 and Phase 4 only). Skills allowed: `arena` (Phase 1 only), `code-review`. Never invoke `architect`, `playbook-*`, `Plan`, `Explore`, `Workflow`.
- At most 5 requests to the gateway in flight at once, whatever the model. Every phase, every time. At most 2 rounds.
- qwen runs `git` only where a step gives the exact command (the thread's final commit). The orchestrator merges.
- Never commit in `~/.config/claude`; the user reviews and commits the guide edits.

**Paths.** Plan beside the backlog: `<backlog dir>/plans/<TASK-SLUG>.md` (for `emoji-godot`: `~/REPOS/emoji-management/client/plans/`). `$SP` = the session scratchpad; worktrees under `$SP/dumb-loop/wt/<thread-slug>`, review worktree at `$SP/dumb-loop/wt/review`.

#### Phase 0 — locate

Read, in order: the task's section in the backlog (`~/REPOS/emoji-management/client/BACKLOG.md` for `emoji-godot`; otherwise the text the user gave), the `RUNS.md` entries for this repo, and the repo `CLAUDE.md` plus every doc its router names for the touched area. Keep the backlog section (or the user's original prompt, when there is no backlog entry) verbatim, unedited, uncondensed — it is copied as-is into the plan's `Backlog text:` field in Phase 1. No source files: what the plan needs from them is a 1a question, and a file is opened here only when a finding cites it. `dumb_agents/<LANG>.md` (LANG from the CLAUDE.md tech stack) is read at Phase 4, for classifying. Confirm `~/.config/claude` has no uncommitted changes under `dumb_agents/` or `skills/dumb-loop/` (`git status --short`); if it does, stop and say so.

**Fit gate.** qwen pays off only when the plan is much shorter than the diff: a shape repeated across many files (a field added to every entity script, a rename sweep, callers migrated to a new API, a file cloned from an existing one). Stop with `does not fit dumb-loop: <reason>; do it by hand` when either holds:
- the task touches fewer than 5 files, or no edit shape repeats across files;
- a step would dictate more than 5 lines of `.gd`, as a code block or as prose that names every line (water-emoji thread 1). `.tscn`/`.tres` blocks are exempt (GODOT #4, #5): short, and qwen cannot compose them.
- the mechanical part is a `sed`/python one-liner (delete N contiguous blocks, swap one line): write the script, don't dispatch an agent.
Searching-overlay round 2 failed both: 4 novel files whose whole difficulty was engine semantics, so the plan became the code and qwen pasted it.

#### Phase 1 — plan

If `<backlog dir>/plans/<TASK-SLUG>.md` exists, use it. Otherwise fan the drafting and the critique out to the local models, keep merge and triage here:

- **1a facts**: at most 5 `qwen-worker` in one message, one grep/read question each (node offsets, every reference to the touched resources, repo files that show the pattern the plan will cite). Collect the answers into `$SP/dumb-loop/facts.md`.
- **1b drafts**: unchanged (arena, local runners).
- **1c synthesis, local**: the arena's cross-judge (`arena cross-judge (local)`) scores, picks the base, lists the grafts (candidate, what, where) and counts drafts that differ in design; the `arena graft applier (local)` applies the grafts and writes `$SP/arena/<slug>/merged.md` plus the synthesis note. Then one `qwen-worker` runs `dumb-loop-api-check.sh merged.md <repo>` and `dumb-loop-lint.sh merged.md main..main` (no diff yet, so only `disjoint` has input), pasting both outputs; every `MISSING` and every lint line is a plan finding for 1e. The orchestrator reads `merged.md` and the synthesis note only, never the candidates.
- **1d critique**: the three `plan critics` as now, read-only, `PASS`/`ISSUES` with at most 10 findings each, then the cross-judge dedupes and ranks the three reports into at most 10 findings at `$SP/dumb-loop/plan-findings.md`.
- **1e triage**: the orchestrator reads `plan-findings.md` and the api-check output only; keeps a finding only if it names a step and a rule; patches the plan. RUNS.md counts: `planning: drafts differing in design <n> (judge), critic findings kept <n> / dropped <n>, api-check missing <n>`.

Template:

```
task: <backlog heading>
repo: <path>
guide: ~/.config/claude/dumb_agents/<LANG>.md
import: <command that refreshes the engine cache and mints sidecar files, or none>
check: <command, e.g. python3 test/run_unit.py>
e2e: <suites run at review, e.g. python3 test/run_e2e.py --suite=fight; or none>
branch: dumb/<task-slug>
disjoint: <"yes" after intersecting every pair of thread file lists>

Backlog text: <the backlog section, or the user's original prompt if there is no backlog entry, copied verbatim from Phase 0>

## Thread 1: <name>
files: <exclusive list>
depends_on: none | <thread numbers>
steps:
1. <file>: <exact change>. Pattern: <reference file:symbol to copy>.
2. ...
N-2. Run `<import>`.
N-1. Run `<check>`; expected last line `<...>`. Paste the last 10 lines.
N. Run exactly: git add -A && git commit -m "<type>(<nick>)" -m "<title>" -m "<body>"
```

Planning rules (grows from run findings):
- A step states constraints and a pattern source, never the file body. "Gate `_process` on `visibility_changed`" is a step; "create exactly this" followed by the file is the answer, and a plan that needs it fails the fit gate.
- No step says "figure out", "investigate", "as needed". Every step names one file and a pattern source.
- At most 8 code steps per thread, at most 5 threads per wave.
- Every thread ends with import, check with pasted output, commit, in that order. The commit command is written in full by the planner (`rules/commits.md` format via three `-m`).
- `dumb-loop-lint.sh` enforces disjoint file sets, no path outside a thread's list, no comments, no magic numbers, `.gd.uid` sidecars, `ext_resource` uids and the planned commit subjects. The plan's `disjoint:` line is the lint's output, not the planner's arithmetic.
- `.tscn` and `.tres` edits: give the exact block text to write; name the existing node block it was copied from; never let qwen compose one (see `GODOT.md` #4, #5).
- New source files: omit `uid=` in scene references; the import step mints the sidecar; a later step in the same thread fills the uid in from it. The lint checks the end state, not the order.
- New constants: the step names the constant, its type, its value and the file that declares it.
- Waves: wave k holds the threads whose `depends_on` are all merged. Wave 2+ branches from the merged task branch.
- Every `add_child(X.new(...))` step sets the node's `name`; an unnamed child shows as `@Node@2` in the remote scene tree.
- State kept in a member that no later step reads is a local. Name the reader in the step, or say local.
- A node that the scene keeps alive and only shows and hides gets a step gating `_process` and any tween on `visibility_changed` (GODOT.md #11).
- The plan's `check:` compiles; it does not run. Any thread that adds behaviour to `_ready`, `_process` or a tween callback gets a probe step before its commit: write `extends SceneTree`, instantiate the scene, `await process_frame`, print the measured values, delete the probe, paste the printed lines (GODOT.md #15).
- The planner reads; it never runs a suite, a scene or a probe worktree. Verification that must precede the code (arena bounds, fixture stats, scenario timing, flakiness) is a *probe thread* in wave 1: exact commands, pasted output, no commit, worktree removed after the report. The orchestrator copies the measured values into the later threads' steps before dispatching the next wave. The flamingo run had the planner run nine e2e probes itself.
- Every engine API the plan names is confirmed by `dumb-loop-api-check.sh` (ClassDB, project `class_name`s, autoloads), never by the planner's memory. Round 2 lost a step to `Label.get_line_width()`, which the planner invented. Builtin types (`Array`, `String`) are skipped: typed variables catch those at compile time (GODOT.md #3).
- A probe assertion has to be able to fail. Round 2's `get_minimum_size().x` was constant across every dot frame because line 1 of the label was the wider one, so it would have passed whether or not the fix worked; `get_character_bounds()` on the glyph that must not move was the sensitive test. State what the number would read if the change were absent.
- Do not specify an exotic literal (a `\u` escape, a zero-width or non-breaking character) unless a probe has shown the plain one fails. Round 2 demanded NO-BREAK SPACE for the dot padding; the worker wrote ASCII spaces and the glyph probe measured them identical.

#### Phase 2 — dispatch, per wave

Round start: `git branch dumb/<task-slug> main` (delete it first if left over). Thread
branches are `dumb/<task-slug>-<thread-slug>`, flat: git cannot hold both a ref and a
directory at `dumb/<task-slug>`.

Per thread in the wave:
```
git worktree add -b dumb/<task-slug>-<thread-slug> $SP/dumb-loop/wt/<thread-slug> <base>
<import> --path $SP/dumb-loop/wt/<thread-slug>      # cache is gitignored; the check needs it
```
`<base>` is `main` for wave 1, `dumb/<task-slug>` after.

Then one `Agent` per thread on the `dumb-loop thread executor` from `rules/subagent-models.md`, all in one message. The prompt is the thread section verbatim plus:

```
Work only in <worktree path>. Touch only the files listed. Run git only where a step gives the exact command.
Read <guide> and the "Code Style Guide" section of <worktree path>/CLAUDE.md before editing.
For each step report: `step N — done` or `step N — stopped: <reason>`; after every check step paste the last 10 lines of its output.
A check step without pasted output counts as not run. If the check fails twice on one step, stop and report.
```

A thread that stops early ends its work there; the round continues with the other threads (its stop is a finding).

#### Phase 3 — merge

Per thread: `git -C <wt> status --short` must be empty and `git -C <wt> log -1` must show the planned commit; anything else is a finding (bucket *skill*: report contract). `git merge --no-ff` the thread branch into `dumb/<task-slug>`. A conflict is a finding, bucket *skill* (the file lists were not disjoint). Remove the thread worktrees. Next wave.

#### Phase 4 — review

`git worktree add $SP/dumb-loop/wt/review dumb/<task-slug>`, then `<import>`.

1. One `qwen-worker` verify thread on the review worktree: `<import>`, `check`, every `e2e` suite, then `dumb-loop-lint.sh <plan> main..dumb/<task-slug> --wt $SP/dumb-loop/wt`; pastes the last 10 lines of each and the full lint output. Every lint line and every failed suite is a finding.
2. Three local critics (`plan critics`) on the review worktree, read-only, one message, each given the plan, the thread reports and the range `main..dumb/<task-slug>`: plan-vs-diff per step (the diff does what the step said, the pattern was followed, report holds output for every check step) and a bug hunt; each returns at most 10 findings as `file:line · what · step`; the cross-judge dedupes and ranks into at most 10 at `$SP/dumb-loop/review-findings.md`.
3. The orchestrator reads `review-findings.md` and only the hunks it cites (`git diff main..dumb/<task-slug> -- <file>` for that file, or `sed -n`), never the whole diff, and classifies each finding (buckets unchanged).
4. `/code-review high` fork runs only on a round that would merge into main: round 1 with zero findings after step 3, or round 2. Its findings are classified the same way.
5. Classify every finding into one bucket:
   - **GODOT** (or the repo's LANG): an engine/language mistake a rule could prevent.
   - **skill**: plan ambiguity, missing pattern source, missing checkpoint, overlapping files, report contract gap.
   - **unpreventable**: no rule would have caught it.
   - **rule failed**: round 2 only, the finding matches a rule written in round 1.
6. Add to the RUNS.md block: `review: local findings <n>, confirmed <n>, code-review findings <n>`.

#### Phase 5 — learn

- GODOT findings → new numbered entry in `dumb_agents/<LANG>.md`, same shape as the existing ones: what was done, what it broke, the rule. *Rule failed* → rewrite that entry instead of adding one.
- skill findings → new bullet under "Planning rules" or a line in the dispatch prompt above. A rule is a constraint qwen can apply to the next task ("every `add_child(X.new())` step sets `name`"); a rule that only restates this task's code is not a rule.
- Append to `dumb_agents/RUNS.md`:
  ```
  ## <date> <repo> <task> round <n>
  threads: <n>  findings: GODOT <n>, skill <n>, unpreventable <n>, rule failed <n>
  - <bucket> · <file> · <one sentence> · <rule written, e.g. GODOT #11 / skill: "..." / none>
  ```
- Leave `~/.config/claude` uncommitted.

#### Phase 6 — loop or finish

Findings non-empty and round 1: remove the review worktree, `git branch -D dumb/<task-slug>` and every thread branch, revise the plan only where a *skill* finding names the plan as cause, go to Phase 2 as round 2. A revision replaces a step's constraint with a tighter constraint, never with the step's code; if the only fix is the code, the task failed the fit gate: stop and report.

Otherwise, never fix by hand:
- No findings left: `git checkout main && git merge --no-ff dumb/<task-slug>` with a `rules/commits.md` message (`feat(<nick>)` / long title / body summarising the threads). No push; no PR (solo repo). Remove the worktrees and the thread branches; keep `dumb/<task-slug>` until the user deletes it.
- Findings left: no merge. Keep `dumb/<task-slug>` and the review worktree for inspection. The final message lists every open finding as `file:line · what is wrong · bucket`.

Final message: the merge commit hash or the open-findings list, the `RUNS.md` block(s) of this run, `git -C ~/.config/claude status --short` and `git -C ~/.config/claude diff --stat`.
