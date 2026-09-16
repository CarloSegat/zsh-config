---
name: tighten-paragraph-paper
description: Tighten one paragraph of a paper, globally aware of the rest
disable-model-invocation: true
argument-hint: <paper file> <which paragraph — quote it, or give section + first words>
---

Target: $ARGUMENTS

If no paper file is given, ask for one. If the paragraph is ambiguous, quote the candidates back
and ask which. Otherwise proceed.

You are tightening one paragraph of a paper. Read the entire paper first. The edit is local in
output but global in reasoning: use the rest of the paper to justify cutting, referencing, or
relocating text.

STEP 1 — Read the whole paper. Record:
  - where each claim in the target is already stated (section + label),
  - the job of the section the target sits in,
  - notation, defined terms, citation and label conventions,
  - the author's register (we/passive, tense, formality).

STEP 2 — Classify every sentence of the target as:
  (a) load-bearing here,
  (b) already stated elsewhere -> replace with a cross-reference to the real section/Eq/Thm number,
  (c) belongs in a different section -> relocate, don't dilute it,
  (d) no content -> cut.

STEP 3 — Rewrite (a), fold in (b), list (c) and (d) separately.

COMPRESSION RULES
  - Fewest words that still carry the claim. One clause instead of two. An adjective or adverb
    instead of a relative clause restating the noun. A verb instead of a nominalization
    ("provides a demonstration of" -> "demonstrates"; "performs an evaluation" -> "evaluates").
  - Cut clauses that justify a word the reader already accepts.
  - Cut signposts that announce structure instead of carrying content: "It is worth noting that",
    "Two things follow", "In this section, we will", "As mentioned above".
  - Cut a final clause that restates the sentence's own premise.
  - Prefer active voice unless the field's convention forbids it.
  - No rule-of-three padding; no lists inflated to look complete.

  Bad:  The filter is public, since it resides on the ledger.
  Good: The filter publicly resides on the ledger.

  Bad:  An enrolled controller is never denied, but a controller that was never enrolled is
        accepted with the filter's false-positive probability, which in an access-control setting
        means an authorization granted to a non-member.
  Good: A false positive grants authorization to a controller that was never enrolled.

NO AI TELLS. Never use: delve, leverage (verb), robust (as filler), seamless, crucial, pivotal,
vital, underscore, showcase, realm, landscape, tapestry, testament, harness (verb), unlock,
navigate, shed light on, paradigm shift, cutting-edge, comprehensive, holistic, intricate, myriad,
foster, facilitate, utilize (use "use"), boasts, serves as, aims to, plays a key role in,
in order to (use "to"), it is important to note, moreover-furthermore chains, "not only X but also
Y", "isn't just X, it's Y", "In the ever-evolving...". Also avoid unearned intensifiers:
significantly, notably, remarkably, dramatically, extremely — unless quantified.

HARD CONSTRAINTS
  - Never drop a technical claim, qualifier, quantifier, or hedge to save words. If a condition is
    load-bearing ("under an honest majority"), it stays.
  - Invent nothing: no citations, numbers, results, or definitions not already in the paper.
  - Don't rename notation or redefine terms.
  - Cross-reference only targets that exist; give the actual number/label.
  - Don't reorder the argument except through an explicit MOVE.
  - If the paragraph is already tight, say so and change nothing. Shortness is not the goal;
    density is.
  - Do not edit any file. Output only.

OUTPUT
  REWRITE — the paragraph, final, paste-ready. Nothing else in this block.
  MOVES — each relocated fragment: the text, its destination section, and the sentence it should
          follow. Say what glue sentence, if any, the destination now needs.
  CUTS — one line each: what was removed and why it is safe (stated in section X, follows from Y,
         or carried no content).
  RISKS — anything you could not compress without losing a claim, any ambiguity you resolved, any
          cross-reference you are unsure exists.
  Words: N -> M.
