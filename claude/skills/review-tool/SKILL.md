---
name: review-tool
description: "Open a local page to review text changes since a git ref: each changed passage in full with insertions and deletions marked; the user approves or reverts single changes, approves passages, comments on selected text (prompts for Claude) and runs /contextualize on Sonnet with Console API credits. Use for /review-tool [base-ref] [files...]."
argument-hint: [base-ref] [files...]
disable-model-invocation: true
---

# Review tool

Arguments: $ARGUMENTS

## Start

1. Base ref: the first argument; without one, the commit the user is reviewing against (for a paper revision, the version the reviewers read). Files: the rest, in reading order (for LaTeX, the `\input` order of `main.tex`); without them, every file changed since the base.
2. Run with `run_in_background`, from the repo root:
   `python3 ~/.claude/skills/review-tool/review.py serve --base <ref> [--check "<build command>"] <files...>`
   `--check`: the command that must pass before an approval commits (for a LaTeX paper, its build).
   It prints the URL (port 8765 or the next free one). Open it with `open <url>` and give it to the user.
3. Watch the log with Monitor (`timeout_ms` 1800000, re-armed at each expiry while the server runs). With an API key (see Contextualize) the server answers comments itself, so watch reverts only:
   `tail -n0 -F .review/log.jsonl | grep --line-buffered -E '"type": "revert"'`
   Without a key, watch comments too: `-E '"type": "(comment|revert)"'`.

## Act on each comment

With an API key the server does this step: each comment goes, one at a time, to `claude -p` on `claude-sonnet-5-5` in the repo, with Read, Grep, Glob and Edit inside the repo, no shell, and the repo's CLAUDE.md rules. Its answer is logged as the reply, with its cost and `edited` (whether a reviewed file changed). Comments a stopped server left open run when it starts. Without a key:

A comment is a prompt from the user, anchored to `file`, `line` and the selected `quote` (empty when the whole passage is meant). Do what it asks under the repo's rules (wording, asking before deleting, committing only when told). Then answer it, in 1 to 3 sentences, saying what changed or why nothing did:

`python3 ~/.claude/skills/review-tool/review.py reply <id> "<text>"`

The page drops a comment once it has a reply and re-renders by itself when the text changes: the user reads the result in the text, so the reply is a record. Clicking one change (a deletion with its insertion) offers Approve, Revert and Comment.

Approving a whole passage (its Approve button) commits that passage's uncommitted edits and nothing else: the server runs `--check`, stages only the diff hunks inside the passage, and commits with a message `claude -p` writes under the repo's commit rules (a fixed `docs(review <file>)` message without a key, or when the output breaks the 3-block format). It refuses while other changes are staged, never pushes, and logs a `commit` entry with the sha or the error, which the page shows on the button or under the passage.

A `revert` entry means the server already wrote the base text back into the file (`removed` went, `restored` came back). Bring whatever describes that change (a change log, a response letter) in step, then reply to its id the same way (the page does not show reverts). A comment that needs the user's decision: ask in the conversation, and reply once it is settled. After a restart, `review.py open` lists comments without a reply.

## Contextualize

The button runs `claude -p "/contextualize <selection>"` on `claude-sonnet-5-5`, with the API key from the macOS Keychain service `anthropic-api-credits`, so it spends the Console credits, not the plan. It refuses to run when `claude -p` does not report that key as its credential. Without the key the button is disabled; the user adds it in their own terminal:

`security add-generic-password -a "$USER" -s anthropic-api-credits -w`

(it prompts for the key; take it from the Console organization linked to the plan under claude.ai Settings > Billing > API credits).

State lives in `<repo>/.review/log.jsonl`, append-only and ignored by git: comments, replies, approvals and contextualize results with their cost.
