---
name: dumb-loop
description: "Run a backlog task through qwen-worker threads from a strong-model plan, review the merge, turn every mistake into a rule, re-run to prove the rule. Use for /dumb-loop <task>."
---

### dumb-loop

The strong model plans and reviews; `qwen-worker` (free) writes the code. Every mistake qwen makes becomes a rule: engine/language mistakes go to `~/.config/claude/dumb_agents/<LANG>.md`, planning mistakes go to this file. Round 2 re-runs the same plan to prove the rule.

**Hard limits.**
- No argument → print `usage: /dumb-loop <backlog task name>` and stop.
- `ANTHROPIC_BASE_URL` unset → run Phase 0 and 1 only (planning needs no qwen), then stop after the plan is written: `qwen-worker` is only reachable from a `claude-gw` session, which picks the plan up.
- Strong-model contexts: this session plus the one `/code-review` fork. Never call `Agent` with a type other than `qwen-worker`. Never invoke `architect`, `playbook-*`, `Plan`, `Explore`, `Workflow`.
- At most 5 `qwen-worker` agents alive at once. At most 2 rounds.
- qwen runs `git` only where a step gives the exact command (the thread's final commit). The orchestrator merges and pushes.
- Never commit in `~/.config/claude`; the user reviews and commits the guide edits.

**Paths.** Plan beside the backlog: `<backlog dir>/plans/<TASK-SLUG>.md` (for `emoji-godot`: `~/REPOS/emoji-management/client/plans/`). `$SP` = the session scratchpad; worktrees under `$SP/dumb-loop/wt/<thread-slug>`, review worktree at `$SP/dumb-loop/wt/review`.

#### Phase 0 — locate

Read, in order: the task's section in the backlog (`~/REPOS/emoji-management/client/BACKLOG.md` for `emoji-godot`; otherwise the text the user gave), the repo `CLAUDE.md` and every doc its router names for the touched area, the source files the task names, `dumb_agents/<LANG>.md` (LANG from the CLAUDE.md tech stack), and the `RUNS.md` entries for this repo. Confirm `~/.config/claude` has no uncommitted changes under `dumb_agents/` or `skills/dumb-loop/` (`git status --short`); if it does, stop and say so.

#### Phase 1 — plan

If `<backlog dir>/plans/<TASK-SLUG>.md` exists, use it. Otherwise write it:

```
task: <backlog heading>
repo: <path>
guide: ~/.config/claude/dumb_agents/<LANG>.md
import: <command that refreshes the engine cache and mints sidecar files, or none>
check: <command, e.g. python3 test/run_unit.py>
e2e: <suites run at review, e.g. python3 test/run_e2e.py --suite=fight; or none>
branch: dumb/<task-slug>
disjoint: <"yes" after intersecting every pair of thread file lists>

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
- Thread file sets are pairwise disjoint; write the intersection result in `disjoint:`.
- No step says "figure out", "investigate", "as needed". Every step names one file and a pattern source.
- At most 8 code steps per thread, at most 5 threads per wave.
- Every thread ends with import, check with pasted output, commit, in that order. The commit command is written in full by the planner (`rules/commits.md` format via three `-m`).
- `.tscn` and `.tres` edits: give the exact block text to write; name the existing node block it was copied from; never let qwen compose one (see `GODOT.md` #4, #5).
- New source files: omit `uid=` in scene references; the import step mints the sidecar.
- New constants: the step names the constant, its type, its value and the file that declares it.
- Waves: wave k holds the threads whose `depends_on` are all merged. Wave 2+ branches from the merged task branch.

#### Phase 2 — dispatch, per wave

`ANTHROPIC_BASE_URL` unset → stop here and print the plan path and `claude-gw` + `/dumb-loop <task>` as the next step.

Round start: `git branch dumb/<task-slug> main` (delete it first if left over).

Per thread in the wave:
```
git worktree add -b dumb/<task-slug>/<thread-slug> $SP/dumb-loop/wt/<thread-slug> <base>
<import> --path $SP/dumb-loop/wt/<thread-slug>      # cache is gitignored; the check needs it
```
`<base>` is `main` for wave 1, `dumb/<task-slug>` after.

Then one `Agent(subagent_type: "qwen-worker")` per thread, all in one message. The prompt is the thread section verbatim plus:

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

1. Run `check`, then every `e2e` suite. A failure is a finding.
2. Start `/code-review high` on the review worktree (background fork).
3. While it runs, do the plan-vs-diff pass yourself, per thread, per step: the diff does what the step said; the report holds output for every check step; no file outside the thread list; no comments added; no magic numbers; the reference pattern was followed.
4. Collect the `/code-review` findings.
5. Classify every finding into one bucket:
   - **GODOT** (or the repo's LANG): an engine/language mistake a rule could prevent.
   - **skill**: plan ambiguity, missing pattern source, missing checkpoint, overlapping files, report contract gap.
   - **unpreventable**: no rule would have caught it.
   - **rule failed**: round 2 only, the finding matches a rule written in round 1.

#### Phase 5 — learn

- GODOT findings → new numbered entry in `dumb_agents/<LANG>.md`, same shape as the existing ones: what was done, what it broke, the rule. *Rule failed* → rewrite that entry instead of adding one.
- skill findings → new bullet under "Planning rules" or a line in the dispatch prompt above.
- Append to `dumb_agents/RUNS.md`:
  ```
  ## <date> <repo> <task> round <n>
  threads: <n>  findings: GODOT <n>, skill <n>, unpreventable <n>, rule failed <n>
  - <bucket> · <file> · <one sentence> · <rule written, e.g. GODOT #11 / skill: "..." / none>
  ```
- Leave `~/.config/claude` uncommitted.

#### Phase 6 — loop or finish

Findings non-empty and round 1: remove the review worktree, `git branch -D dumb/<task-slug>` and every thread branch, revise the plan only where a *skill* finding names the plan as cause, go to Phase 2 as round 2.

Otherwise: fix what is left by hand on the review worktree, commit, `git push -u origin dumb/<task-slug>`, `gh pr create` with the title from the commit long-title line and a body of `## Why`, `## Scope`, `## Verification` (under 40 lines, not a draft). Do not merge. Remove the worktrees.

Final message: the PR URL, the `RUNS.md` block(s) of this run, `git -C ~/.config/claude status --short` and `git -C ~/.config/claude diff --stat`.
