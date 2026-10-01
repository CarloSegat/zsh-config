# Commits

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

Applies only to `~/REPOS/emoji-godot`, `~/REPOS/emoji-gs` and `~/REPOS/emoji-management` (and their worktrees). No pull requests, no GitHub CLI. Finish work by fast-forwarding the branch into `main` locally, then remove its worktree and delete the branch. After a merge into emoji-gs or emoji-godot `main`, run `make box-deploy` in `~/REPOS/emoji-gs` (in the background: it builds, rolls out and ends with `make k8s-e2e`). Do not push, open or propose a PR, or ask about one. When a playbook says to run Opening a PR, stop after its Commits step. Other repos follow the playbooks as written.
