---
name: can-clear
description: "End-of-session check before /clear: changes done, worktrees and branches deleted, everything merged into main, no unanswered questions. Verdict is CLEAR yes or no, then the open items. Use for /can-clear, 'can I clear', 'are we done here'."
---

# Can clear

Answer one question: is it safe to `/clear` this session?

1. Run `bash ~/.claude/skills/can-clear/check.sh`. It is the source of truth for git state; never answer that part from memory. A `BLOCK:` line is a blocker only when this session owns it.
2. Ownership: this session owns what it created, edited, committed, branched, stashed or started (per the conversation), in any repo, including worktrees outside the cwd. Dirty paths, worktrees, branches and stashes from another session or agent are not blockers; list them under `Ignored:` so the user knows they exist. When unsure whether you touched something, you own it.
3. Review the conversation for what the script can't see:
   - Work the user asked for that isn't done, or is done but unverified.
   - Questions you asked the user that got no answer.
   - Questions the user asked that you never answered.
   - Decisions you made on your own that the user hasn't confirmed.
   - Open tasks in the task list, subagents or background commands still running.
4. Reply in exactly this shape, nothing before or after:

```
CLEAR: yes
```

or

```
CLEAR: no

Unfinished:
- <one line each, git blockers first with their fix command>

Unanswered:
- <one line per open question, who owes the answer>

Ignored:
- <one line per foreign item the script flagged, and whose it looks like>
```

`Ignored:` can appear under `CLEAR: yes` too. Omit an empty section. If every blocker is mechanical (delete a merged branch, remove a worktree), offer to run the fixes in one line after the verdict.
