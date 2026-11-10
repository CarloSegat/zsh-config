---
name: contextualize
description: "Explain one sentence the user names: everything a reader must know to make sense of it, in 1 plain paragraph. Use for /contextualize <sentence>."
argument-hint: <sentence or fragment>
disable-model-invocation: true
---

# Contextualize

The user has lost the context of this sentence: $ARGUMENTS

1. **Find it.** Grep the repos this conversation works in for a distinctive fragment, allowing for markup (LaTeX commands, math) and line breaks. If no file holds it, look in the conversation. Found nowhere: say so and stop.
2. **Read around it.** Read its paragraph. Follow every term, symbol, pronoun, `\ref` and `\cite` it uses to where the document defines it. From the conversation, take why the sentence exists: the request, review point or decision behind it.
3. **Answer** in 1 paragraph of at most 100 words: where it sits (section and `file:line`), what each term it relies on means, which earlier claims it builds on, and what it adds there. If it needs more, cover what the sentence cannot be read without and stop.

Rules:
- Assume no prior knowledge: resolve every name, symbol and referent ("it", "this", "the filter"), in the document's own terms.
- State only what the files or the conversation show. Name an unresolved term as unresolved; never fill it from memory.
- Short sentences, one claim each. No preamble, no restating the sentence, no headings, no bullets.
