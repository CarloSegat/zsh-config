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
