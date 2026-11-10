---
name: review-tool
description: "Open a local page to review text changes since a git ref: each changed passage in full with insertions and deletions marked; the user approves passages, comments on selected text (prompts for Claude) and runs /contextualize on Sonnet, billed to the Console organization. Use for /review-tool [base-ref] [files...]."
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
   `tail -n0 -F .review/log.jsonl | grep --line-buffered '"type": "comment"'`

## Act on each comment

A comment is a prompt from the user, anchored to `file`, `line` and the selected `quote` (empty when the whole passage is meant). Do what it asks under the repo's rules (wording, asking before deleting, committing only when told). Then answer it, in 1 to 3 sentences, saying what changed or why nothing did:

`python3 ~/.claude/skills/review-tool/review.py reply <id> "<text>"`

The page shows the reply under the comment and offers a reload when the text changed. A comment that needs the user's decision gets a reply with the question; the user answers in a new comment. After a restart, `review.py open` lists comments without a reply.

## Contextualize

The button runs `claude -p "/contextualize <selection>"` on `claude-sonnet-5-5` with `ANTHROPIC_PROFILE=default`, the Console login `ant auth login` writes, so it bills that Console organization (the API credits, when it is the one linked under claude.ai Settings > Billing > API credits), not the plan. Before each run it checks with `claude auth status` that the profile is the credential, and refuses otherwise. Without that login the button is disabled; the user runs `ant auth login`. Interactive sessions keep the claude.ai login, which outranks an unnamed profile.

State lives in `<repo>/.review/log.jsonl`, append-only and ignored by git: comments, replies, approvals and contextualize results with their cost.
