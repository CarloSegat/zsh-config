---
name: dumb-loop
description: "Run a backlog task through local-model threads from a strong-model plan, review the merge, turn every mistake into a rule, re-run to prove the rule. Use for /dumb-loop <task>."
---

### dumb-loop

The strong model plans and reviews; local models (free, zero token cost) write the code. Every mistake a local model makes becomes a rule: engine/language mistakes go to `~/.config/claude/dumb_agents/<LANG>.md`, planning mistakes go to this file. Round 2 re-runs the same plan to prove the rule.

**Hard limits.**
- No argument → print `usage: /dumb-loop <backlog task name>` and stop.
- `ANTHROPIC_BASE_URL` unset → print `dumb-loop needs a claude-gw session: run claude-gw, then /dumb-loop <task>` and stop before Phase 0. Every local model is only reachable through the gateway, planning included.
- Only the model runs on the Ollama server. Every tool call a local agent makes (Bash, Read, Edit) executes in this Claude Code process, on this machine, against these worktrees. Godot, python, the repo and the scripts under `skills/dumb-loop/` must exist here; the server needs nothing.
- Strong-model contexts: this session plus the one `/code-review` fork. `Agent` types allowed: any local model (Phase 1 and Phase 4 only) — which one backs a given role is `rules/subagent-models.md`'s concern, not this skill's. Skills allowed: `arena` (Phase 1 only), `code-review`. Never invoke `architect`, `playbook-*`, `Plan`, `Explore`, `Workflow`.
- At most 5 requests to the gateway in flight at once, whatever the model. Every phase, every time. At most 2 rounds.
- The executor runs `git` only where a step gives the exact command, one per unit. The `type(nickname)` subject is fixed and copied verbatim from the plan; title and body are the executor's own account of what the unit actually did. Never amend, squash, rebase or reorder. The orchestrator merges.
- Never commit in `~/.config/claude`; the user reviews and commits the guide edits.

**Paths.** Plan beside the backlog: `<backlog dir>/plans/<TASK-SLUG>.md` (for `emoji-godot`: `~/REPOS/emoji-management/client/plans/`). `$SP` = the session scratchpad; worktrees under `$SP/dumb-loop/wt/<thread-slug>`, review worktree at `$SP/dumb-loop/wt/review`.

#### Phase 0 — locate

Read, in order: the task's section in the backlog (`~/REPOS/emoji-management/client/BACKLOG.md` for `emoji-godot`; otherwise the text the user gave), the `RUNS.md` entries for this repo, and the repo `CLAUDE.md` plus every doc its router names for the touched area. Keep the backlog section (or the user's original prompt, when there is no backlog entry) verbatim, unedited, uncondensed — it is copied as-is into the plan's `Backlog text:` field in Phase 1. No source files: what the plan needs from them is a 1a question, and a file is opened here only when a finding cites it. `dumb_agents/<LANG>.md` (LANG from the CLAUDE.md tech stack) is read at Phase 4, for classifying. Confirm `~/.config/claude` has no uncommitted changes under `dumb_agents/` or `skills/dumb-loop/` (`git status --short`); if it does, stop and say so.

**Fit gate.** A local model pays off only when the plan is much shorter than the diff: a shape repeated across many files (a field added to every entity script, a rename sweep, callers migrated to a new API, a file cloned from an existing one). Stop with `does not fit dumb-loop: <reason>; do it by hand` when either holds:
- the task touches fewer than 5 files, or no edit shape repeats across files;
- a step would dictate more than 5 lines of `.gd`, as a code block or as prose that names every line (water-emoji thread 1). `.tscn`/`.tres` blocks are exempt (GODOT #4, #5): short, and a local model cannot compose them.
- the mechanical part is a `sed`/python one-liner (delete N contiguous blocks, swap one line): write the script, don't dispatch an agent.
Searching-overlay round 2 failed both: 4 novel files whose whole difficulty was engine semantics, so the plan became the code and the local model pasted it.

#### Phase 1 — plan

If `<backlog dir>/plans/<TASK-SLUG>.md` exists, use it. Otherwise fan the drafting and the critique out to the local models, keep merge and triage here:

- **1a facts**: at most 5 local models in one message, one grep/read question each (node offsets, every reference to the touched resources, repo files that show the pattern the plan will cite). Collect the answers into `$SP/dumb-loop/facts.md`.
- **1b drafts**: unchanged (arena, local runners).
- **1c synthesis, local**: the arena's cross-judge (`arena cross-judge (local)`) scores, picks the base, lists the grafts (candidate, what, where) and counts drafts that differ in design; the `arena graft applier (local)` applies the grafts and writes `$SP/arena/<slug>/merged.md` plus the synthesis note. Then one local model runs `dumb-loop-api-check.sh merged.md <repo>` and `dumb-loop-lint.sh merged.md main..main` (no diff yet, so only `disjoint` has input), pasting both outputs; every `MISSING` and every lint line is a plan finding for 1e. The orchestrator reads `merged.md` and the synthesis note only, never the candidates.
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
1c. Run `<check>` (`<import>` first only if this unit adds/renames a file or touches
    `.tscn`/`.tres`); expected last line `<...>`. Paste the last 10 lines.
    Run: git add -A && git commit -m "<type>(<nick>)" -m "<title>" -m "<body>"
2. <file>: <exact change>. Pattern: <reference file:symbol to copy>.
3. <file>: <exact change>. Bundled with 2: <why `<check>` is red between them>.
3c. Run `<import>`, then `<check>`; expected last line `<...>`. Paste the last 10 lines.
    Run: git add -A && git commit -m "<type>(<nick>)" -m "<title>" -m "<body>"
...
```

A step numbered `Nc` is a checkpoint (check + commit), not a code step — the
8-code-step cap below still bounds it, and now also bounds commits and check
runs per thread (≤8 of each).

Planning rules (grows from run findings):
- A step states constraints and a pattern source, never the file body. "Gate `_process` on `visibility_changed`" is a step; "create exactly this" followed by the file is the answer, and a plan that needs it fails the fit gate.
- No step says "figure out", "investigate", "as needed". Every step names one file and a pattern source.
- At most 8 code steps per thread, at most 5 threads per wave.
- One commit per code step by default. Steps bundle into a single unit only when `<check>` cannot pass in between them (a new `.gd` plus the `.tscn` that references it, a rename plus its callers, one `.tscn`'s `load_steps`/`[ext_resource]`/`[node]` blocks). Bundling for convenience, or because a step looks trivial, is not allowed — a bundled unit states in one clause why the check would be red split apart.
- Every unit ends with check (output pasted), then commit, in that order (GODOT #0: run it after every edit and before every commit). The commit's `type(nickname)` is written in full by the planner (`rules/commits.md` format via three `-m`) and copied verbatim; its title and body are the planner's draft of the *intended* change, which the executing agent may rewrite to state what it actually did if reality diverged from the plan. Phase 4 checks the final message against the commit's own diff — a mismatch between what it says and what it did is a finding in its own right.
- `dumb-loop-lint.sh` enforces disjoint file sets, no path outside a thread's list, no comments, no magic numbers, `.gd.uid` sidecars, `ext_resource` uids and every planned commit subject of every thread's units. The plan's `disjoint:` line is the lint's output, not the planner's arithmetic.
- `.tscn` and `.tres` edits: give the exact block text to write; name the existing node block it was copied from; never let a local model compose one (see `GODOT.md` #4, #5).
- New source files: omit `uid=` in scene references; the unit that adds the file runs `<import>` to mint the sidecar and commits it; the next unit fills the minted uid into the scene reference. The lint checks the end state, not the order.
- New constants: the step names the constant, its type, its value and the file that declares it.
- Waves: wave k holds the threads whose `depends_on` are all merged. Wave 2+ branches from the merged task branch.
- Every `add_child(X.new(...))` step sets the node's `name`; an unnamed child shows as `@Node@2` in the remote scene tree.
- State kept in a member that no later step reads is a local. Name the reader in the step, or say local.
- A node that the scene keeps alive and only shows and hides gets a step gating `_process` and any tween on `visibility_changed` (GODOT.md #11).
- The plan's `check:` compiles; it does not run. A unit that adds behaviour to `_ready`, `_process` or a tween callback gets a probe inside that same unit, after `<check>` and before the commit: write `extends SceneTree`, instantiate the scene, `await process_frame`, print the measured values, paste the printed lines, then delete the probe file before `git add -A` (GODOT.md #15) — a probe left on disk lands in the commit and lint reports it `outside`. Quote the key measured values in the commit body; the next unit's only handoff is this thread's commit log, so a number worth knowing is a number worth committing.
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

Then, per thread, one `Agent` per **unit** on the `dumb-loop thread executor` from `rules/subagent-models.md` — never a resume, never a fork, so a unit never inherits an earlier unit's tool-call noise. Dispatch unit 1 for every thread in the wave, all in one message. The prompt is that unit's step(s) verbatim plus:

```
Work only in <worktree path>. Touch only the files listed. Run git only where this unit's step gives the exact command.
Read <guide> and the "Code Style Guide" section of <worktree path>/CLAUDE.md before editing.
Report: `step N — done` or `step N — stopped: <reason>`; paste the last 10 lines of the check's output.
A check without pasted output counts as not run. If the check fails twice, stop and report; do not commit.
```

For unit 2 onward, prepend to that prompt the thread's commit log so far —
`git -C <worktree path> log --reverse --format='%s%n%n%b%n---' <base>..HEAD` — as the
unit's only inherited context, framed as "what happened in this thread before you":
no other summary, no resumed conversation. A unit that needs more than the log reads
`git show`/the files itself.

On each unit's completion notification: verify it directly against the worktree —
`git -C <worktree path> log -1` shows the exact planned subject, and the check output
was actually pasted — trust that, not the agent's self-report. Then dispatch that
thread's next unit. Threads progress independently (thread A can be on unit 3 while
thread B is on unit 1); since each thread has at most one unit in flight, a 5-thread
wave stays within the "5 requests to the gateway in flight" limit on its own.

A unit that stops early, or whose check fails twice, halts that thread there; units
already committed stay committed — each is green by construction. The round continues
with the other threads (the stop, and the thread's uncommitted remainder, are findings).

#### Phase 3 — merge

Per thread: `git -C <wt> status --short` must be empty, and `git -C <wt> log --format=%s <base>..HEAD` must list every subject the thread's units planned, in order. A missing subject is a finding (bucket *skill*: skipped or stopped unit); a subject present but not planned is a finding (invented commit); a dirty worktree is a finding (report contract). Merge anyway — committed units are green by construction. `git merge --no-ff` the thread branch into `dumb/<task-slug>` (never squash: per-unit history is the point). A conflict is a finding, bucket *skill* (the file lists were not disjoint). Remove the thread worktrees. Next wave.

#### Phase 4 — review

`git worktree add $SP/dumb-loop/wt/review dumb/<task-slug>`, then `<import>`.

1. One local-model verify thread on the review worktree: `<import>`, `check`, every `e2e` suite, then `dumb-loop-lint.sh <plan> main..dumb/<task-slug> --wt $SP/dumb-loop/wt`; pastes the last 10 lines of each and the full lint output. Every lint line and every failed suite is a finding.
2. Three local critics (`plan critics`) on the review worktree, read-only, one message, each given the plan, the thread reports, and `git log --reverse --format='%h %s' main..dumb/<task-slug>` plus `git show <sha>` per commit (not a flattened diff): plan-vs-commit 1:1 (the commit's diff does what its unit said, the pattern was followed, report holds output for every check step, a plan unit with no matching commit or a commit with no matching unit is a finding), the commit's title/body against its own `git show` (a message that claims something the diff doesn't do, or omits a real deviation, is a finding), and a bug hunt; each returns at most 10 findings as `file:line · what · step`; the cross-judge dedupes and ranks into at most 10 at `$SP/dumb-loop/review-findings.md`.
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
- skill findings → new bullet under "Planning rules" or a line in the dispatch prompt above. A rule is a constraint a local model can apply to the next task ("every `add_child(X.new())` step sets `name`"); a rule that only restates this task's code is not a rule.
- Append to `dumb_agents/RUNS.md`:
  ```
  ## <date> <repo> <task> round <n>
  threads: <n>  commits: <n> planned / <n> landed  findings: GODOT <n>, skill <n>, unpreventable <n>, rule failed <n>
  - <bucket> · <file> · <one sentence> · <rule written, e.g. GODOT #11 / skill: "..." / none>
  ```
- Leave `~/.config/claude` uncommitted.

#### Phase 6 — loop or finish

Findings non-empty and round 1: remove the review worktree, `git branch -D dumb/<task-slug>` and every thread branch, revise the plan only where a *skill* finding names the plan as cause, go to Phase 2 as round 2. A revision replaces a step's constraint with a tighter constraint, never with the step's code; if the only fix is the code, the task failed the fit gate: stop and report.

Otherwise, never fix by hand:
- No findings left: `git checkout main && git merge --no-ff dumb/<task-slug>` with a `rules/commits.md` message (`feat(<nick>)` / long title / body summarising the threads). No push; no PR (solo repo). Remove the worktrees and the thread branches; keep `dumb/<task-slug>` until the user deletes it.
- Findings left: no merge. Keep `dumb/<task-slug>` and the review worktree for inspection. The final message lists every open finding as `file:line · what is wrong · bucket`.

Final message: the merge commit hash or the open-findings list, the `RUNS.md` block(s) of this run, `git -C ~/.config/claude status --short` and `git -C ~/.config/claude diff --stat`.
