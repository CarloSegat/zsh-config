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
   `python3 ~/.claude/skills/review-tool/review.py serve --base <ref> <files...>`
   It prints the URL (port 8765 or the next free one). Open it with `open <url>` and give it to the user.
3. Watch the log with Monitor (`timeout_ms` 1800000, re-armed at each expiry while the server runs):
   `tail -n0 -F .review/log.jsonl | grep --line-buffered -E '"type": "(comment|revert)"'`

## Act on each comment

A comment is a prompt from the user, anchored to `file`, `line` and the selected `quote` (empty when the whole passage is meant). Do what it asks under the repo's rules (wording, asking before deleting, committing only when told). Then answer it, in 1 to 3 sentences, saying what changed or why nothing did:

`python3 ~/.claude/skills/review-tool/review.py reply <id> "<text>"`

The page shows the reply under the comment, with buttons to approve the passage or comment again, and re-renders by itself when the text changes. Clicking one change (a deletion with its insertion) offers Approve, Revert and Comment.

A `revert` entry means the server already wrote the base text back into the file (`removed` went, `restored` came back). Bring whatever describes that change (a change log, a response letter) in step, then reply to its id the same way. A comment that needs the user's decision gets a reply with the question; the user answers in a new comment. After a restart, `review.py open` lists comments without a reply.

## Contextualize

The button runs `claude -p "/contextualize <selection>"` on `claude-sonnet-5-5`, with the API key from the macOS Keychain service `anthropic-api-credits`, so it spends the Console credits, not the plan. It refuses to run when `claude -p` does not report that key as its credential. Without the key the button is disabled; the user adds it in their own terminal:

`security add-generic-password -a "$USER" -s anthropic-api-credits -w`

(it prompts for the key; take it from the Console organization linked to the plan under claude.ai Settings > Billing > API credits).

State lives in `<repo>/.review/log.jsonl`, append-only and ignored by git: comments, replies, approvals and contextualize results with their cost.
