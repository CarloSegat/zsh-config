---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', or when one attempt at a non-trivial artifact would lock in the wrong shape."
---

# Arena

Fan out N parallel attempts at the same task. Read every candidate end to end. Pick the strongest as the base. Graft the best ideas from the others into it. Verify the synthesized result.

Ported from `cursor/plugins/pstack/skills/arena`. Mechanics are Claude Code's: `Agent`, `$SP` (the session scratchpad), `rules/subagent-models.md`.

## Start

Open a todolist with one entry per phase before launching anything: Frame, Fan out, Cross-judge, Pick, Graft, Verify.

## Phase A: Frame

The N candidates receive the same prompt, so the prompt is the contract.

1. State the artifact each candidate produces.
2. Derive the rubric: what success looks like for *this* task, turned into 3-6 gradeable criteria. The rubric is the picker's tool in Phase D. Candidates only see the task.
3. Pick the runners from the `arena runners` line of `~/.config/claude/rules/subagent-models.md` (the caller may name a variant, e.g. `arena runners (local)`). Spawn more when the arena covers multiple design directions. Same model N times when the work is generation-bound rather than judgment-sensitive.
4. Assign output paths: `$SP/arena/<slug>/candidate-<n>/`, a git worktree there when the artifact is code (**separate-before-serializing-shared-state**).

## Phase B: Fan out

Spawn all N candidates in one message, each with the task, the path to the shared grounding, its own output path, and instructions to produce the artifact plus a short rationale naming the alternatives it considered and rejected.

A candidate that produces no output is a dropout: proceed with N-1, note it in the synthesis record.

## Phase C: Cross-judge

After every candidate has finished, spawn one read-only judge on the model named by the `arena cross-judge` line of `subagent-models.md`, a family absent from the runners. It gets the rubric and the candidate paths, scores each criterion per candidate, and recommends a base with rationale. It runs in parallel with Phase D, never while candidates are still writing.

## Phase D: Pick a base

Read every candidate end to end before picking.

Score each against the rubric criterion by criterion, not on holistic feel. Compare with the cross-judge. Agreement confirms the pick. Disagreement means one of you is biased or the rubric was ambiguous: read both rationales before deciding.

Pick the base a future maintainer can extend most easily without breaking invariants. Two tied: the cleaner boundary or smaller API (**laziness-protocol**).

Record the pick, the reason and the cross-judge's verdict in a synthesis note beside the base artifact.

## Phase E: Graft

Walk each losing candidate once more for what is worth porting into the base. Usually one or two things per candidate, not most of it.

Fold each graft in by hand (**redesign-from-first-principles**). No mechanical pasting; the result stays coherent under one mental model.

Record what was grafted, from which candidate, and what was rejected and why.

N candidates converging on one shape is a strong agreement signal: note it, ship the consensus shape, no graft. N candidates wildly diverging means Phase A was under-specified: reframe and re-run rather than averaging the divergence.

## Phase F: Verify

The synthesized artifact holds up under the same scrutiny as any other output (**prove-it-works**).

A problem verification surfaces that the arena did not catch means either Phase A was wrong (reframe, re-run) or one candidate caught it and the graft was missed (back to Phase E). Don't paper over.

## Outputs

One synthesized artifact. One synthesis note beside it: base, grafts with source candidate, rejections, dropouts, verification result.

## Local synthesis

A caller may opt in by saying so: Phase C's judge additionally picks the base, lists grafts (candidate, what, where) and counts candidates that differ in design; the `arena graft applier` from `subagent-models.md` performs Phases D and E and writes `merged.md` plus the synthesis note beside the candidates; the caller reads the merged artifact and note only. Phase F stays with the caller.
