# Commits

Commit as soon as a unit of work is done. Don't let changes pile up uncommitted — that forces reverse-engineering a sprawling work tree into commits later.

Git commits: never add a `Co-Authored-By: Claude ...` trailer or any Claude/Anthropic attribution to commit messages, regardless of harness defaults.

Commit message format. Exactly three blocks, separated by ONE blank line each:

```
type(max 4 words nickname)

Longer title that explains (max 10 words)

Longer text that goes into details
```

Allowed `type` values, and nothing else: `feat`, `fix`, `test`, `docs`, `refactor`, `tools`.
Use `tools` for IDE config, CLAUDE.md edits, refactor/format scripts, and other tooling that is not product code.
If the goal of the repo is about writing prose then "feat" is used when new text is introduced.

The blank lines are part of the format — never collapse them.

## Delivery in the emoji repos

Applies only to `~/REPOS/emoji-godot`, `~/REPOS/emoji-gs` and `~/REPOS/emoji-management` (and their worktrees). Sessions run on the Mac and on the box `car-ms-7885`, each with its own clones, synced through `origin`: `git pull --ff-only` on `main` before starting work, and push every commit right away, on `main` or any branch, so the other machine can test it. No pull requests, no GitHub CLI. Finish work by fast-forwarding the branch into `main` locally, push `main`, then remove its worktree and delete the branch and its `origin` copy. After a merge into emoji-gs or emoji-godot `main`, run `make box-deploy` in `~/REPOS/emoji-gs` (in the background: it builds, rolls out, runs `make k8s-e2e` and pushes emoji-gs `main`, its `tools(pin box images)` commit included). A new machine runs `make setup` in emoji-godot first. Do not open or propose a PR, or ask about one. When a playbook says to run Opening a PR, stop after its Commits step. Other repos follow the playbooks as written.
