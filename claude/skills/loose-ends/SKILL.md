---
name: loose-ends
description: "Walk the user, one item at a time, through what they have not answered and what Claude decided without them. Use for /loose-ends, 'what did I miss', 'what's open', or when the user comes back after a while."
---

# Loose ends

The user has been away. Give them what needs them, one item per message, and record each answer where it belongs.

## 1. Collect

From the conversation:
- **Unanswered**: every question Claude asked the user that got no answer, and every question the user asked that Claude never answered.
- **Guessed**: every decision Claude or a subagent made without the user: a default taken, an assumption written into a file, a deviation from a plan, a review finding dropped, a scope cut, a recommendation the user never confirmed. A decision the user explicitly answered is not a guess.

From files that outlive the conversation, in the cwd repo and any repo the conversation worked in:
- `Q:` entries with an empty `A:` in plan-style files (`PLAN.md`, `COMMITS.md`, `HANDOFF.md`, under `work-in-progress/` when it exists).
- Deviations and "noticed, not fixed" lines in build logs (`BUILD.md`) newer than the user's last reply.

Drop items the user already answered anywhere. Merge duplicates.

## 2. Order

1. Unanswered items that block running work (an agent, a build, a merge waiting on them).
2. Other unanswered items.
3. Guesses, costliest to undo first (hardware, data, public or shared state, then architecture, then code, then wording).

## 3. Present

First message: the counts and nothing else of substance, e.g. `4 open: 2 unanswered, 2 guesses. #1:` followed by item 1.

Each item, as short as it can be:
- `#k of n, <unanswered | guessed>: <title>`
- Two or three lines of context: what it is about, where it lives (`path:line` for a file entry), and what happens if the user never answers.
- For a guess: what Claude chose and why, in one line.
- Options through the `AskUserQuestion` tool (per `rules/questions.md`), never lettered in text: the recommendation first, labelled "(Recommended)". For a guess, the first option is always "Keep it".

One item per `AskUserQuestion` call; never two items in one message.

## 4. Record

On each answer:
- A file entry: write the answer into its `A:` (or the file the guess lives in) and commit it the way the repo's instructions say.
- A guess the user overturns: say what changes and do it, or queue it as the next step of the work it belongs to.
- Then show the next item.

"skip" moves an item to the end; "stop" ends the walk with a one-line tally of what is still open.

After the last item: `All answered.` plus one line per change the answers caused.
