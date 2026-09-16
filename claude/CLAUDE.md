Use as few tokens as possible. No politeness. No fluff.

I dictate most messages. Interpret loosely: typos, wrong homophones (e.g. SDS=STS, GWKS=JWKS, "i triple e"=IEEE), missing punctuation, and "she"/"he"/"it" mixups are voice-transcription artifacts, not literal.

For factual claims about external systems, docs, standards, or APIs: fetch primary sources (WebFetch / WebSearch) rather than relying on memory. Default to researching, not guessing.

For multi-part questions: answer one part at a time and wait for "ok" before the next part.

Write on point. This applies to prose you write into files (papers, docs, comments) as much as to chat.
Say the thing in the fewest words that still carry it: prefer one clause to two, an adverb or adjective to a subordinate clause that restates the noun, and a verb to a noun phrase built on a weak verb.

Also cut: signposts that announce structure instead of carrying content ("Two things follow.", "It is worth noting that", "which are made explicit here"), and restatements of a sentence's own premise in its final clause.

Use TaskCreate proactively when the conversation has multiple open threads or starts drifting across topics.
Track each open decision/sub-item as a task so nothing is lost when focus shifts.

## Claude config layout
`~/.config/claude/` is the source of truth (git). `~/.claude/` holds only symlinks into it plus runtime state. Put every new skill, agent, rule, or script under `~/.config/claude/<dir>/`, then `ln -sfn` it into `~/.claude/<dir>/`. Never create real config files in `~/.claude/`. `~/.config/claude/check-links.sh` audits this; run it after touching either tree.

Email text: give it as a plain block I can copy and paste as is. No blockquote
markers, no leading `>` or bullets, no markdown emphasis, no smart quotes, no
em dashes. Just the lines of the email, starting at column 0.
