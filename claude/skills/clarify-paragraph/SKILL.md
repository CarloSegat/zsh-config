---
name: clarify-paragraph
description: "Make a paragraph of a paper easier to read: simplify it in place, then check it is correct (language, LaTeX, consistency with the rest of the paper, numbers and facts against their sources, meaning kept). Use for /clarify-paragraph <file> <paragraph>."
argument-hint: <paper file> <paragraph: quote it, or give section + first words>
disable-model-invocation: true
---

# Clarify paragraph

Target: $ARGUMENTS

No file given: ask for one. Paragraph ambiguous: quote the candidates and ask which.

## 1. Read

- The whole paper, not only the paragraph. Record its defined terms and notation, where else each claim of the paragraph appears, and the job of the section holding the paragraph.
- The repo's CLAUDE.md: its style rules (numbers, dashes, banned words, person) bind every edit; its source pointers (code, data, bibliography) feed step 4.
- `~/.config/claude/skills/tighten-paragraph-paper/SKILL.md`: its COMPRESSION RULES, NO AI TELLS and HARD CONSTRAINTS apply here, except "Do not edit any file".

## 2. Diagnose

Mark every sentence that breaks one of these. Leave the rest untouched.

- **Point first.** A paragraph's first sentence states what the paragraph establishes.
- **One idea per sentence.** Split a sentence that carries 2 claims or nests a clause inside a clause.
- **Subject and verb early.** No long preamble before the main verb; no noun stacks ("group membership update proof").
- **Old before new.** A sentence opens with what the reader already has and ends with what is new, so each picks up where the last ended.
- **Defined before used.** Every term, acronym and symbol is defined at or before first use; one name per concept across the paper.
- **Clear reference.** Every "it", "this", "they", "the former" has one possible antecedent; "this" takes a noun ("this check").
- **Logical links.** Connectives state the relation (because, so, but, unless). Replace "Moreover", "Additionally", "Also" with the actual relation, or with nothing.
- **Plain words.** A common word beats jargon the paper does not define. The paper's defined terms stay.

## 3. Rewrite

Rewrite the marked sentences in the file. Keep every claim, qualifier, quantifier, number and citation. A sentence whose removal would simplify the paragraph stays: list it with why it looks removable and ask with AskUserQuestion before deleting it.

Already clear: say so and change nothing.

## 4. Check correctness

On the rewritten paragraph:

1. **Language.** Grammar, spelling, agreement, articles, tense.
2. **LaTeX.** Balanced braces and environments; every `\ref`/`\cref` label and every `\cite` key exists (grep, do not compile); `~` before `\ref` and `\cite`.
3. **Consistency.** Every number, term, symbol and claim matches its definition and every other statement of it in the paper: tables, figures, other sections.
4. **Sources.** Open the source the repo CLAUDE.md names for each number (e.g. a measurements file) and compare. Fetch the primary source for a claim about an external standard, spec or system. For a cited claim, check the bib entry is the work that says it.
5. **Meaning kept.** Spawn one fresh agent (`general-purpose`, `model: opus`) given only the original paragraph and the rewrite (the `git diff` of the file). It lists every claim, condition and number of the original and marks each kept, changed, lost or added. Restore what changed or got lost, unless the change fixes an error found in 1 to 4.

Fix language and LaTeX errors directly. Never fix a factual or consistency error silently: report it.

## 5. Report

- **Changes:** one line per edited sentence, saying what got easier.
- **Errors:** `file:line`, what is wrong, the evidence (`source:line` or URL), the proposed fix.
- **Questions:** deletions and factual fixes, through AskUserQuestion.

Compile or commit only if the repo CLAUDE.md says to.
