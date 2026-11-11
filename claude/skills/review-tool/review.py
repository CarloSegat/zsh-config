#!/usr/bin/env python3
"""Local review page for text changes since a git ref (see SKILL.md).

    review.py serve --base REF [--repo DIR] [--port N] [--check CMD] [FILE ...]
    review.py reply --repo DIR ID TEXT
    review.py open --repo DIR
"""
import argparse, bisect, copy, difflib, hashlib, json, os, queue, re, subprocess, sys, threading, time, uuid, unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER_BUILD = Path(__file__).resolve().stat().st_mtime_ns   # the code this server runs
KEYCHAIN_SERVICE = "anthropic-api-credits"
MODELS = {"Sonnet": "claude-sonnet-5-5", "Opus": "claude-opus-5-5"}   # the page offers each for a comment
MODEL = MODELS["Sonnet"]
CONTEXT_TOOLS = "Read,Grep,Glob,Bash(grep:*),Bash(sed:*)"
EDIT_TOOLS = "Read,Grep,Glob,Edit(./**)"   # edits inside the repo only; no shell, so no commit
COMMENT_PROMPT = """A reviewer of the uncommitted text changes in this repository left a comment on {file}, near line {line}.

Selected text: {quote}
Comment: {text}{history}

Do what the comment asks, editing the files, under the rules of this repository's CLAUDE.md files. A deletion the comment asks for is approved by the comment. Do not commit. If the comment needs a decision the files cannot settle, change nothing and ask.

Then answer in 1 to 3 sentences: the changed sentence quoted in full, or your question. Nothing else."""
MESSAGE_PROMPT = """Write the git commit message for the staged change (read it with git diff --cached), following the commit rules of this repository's CLAUDE.md files. The edits were made during a review and approved by the author. Output the message only."""
MESSAGE = re.compile(r"(feat|fix|test|docs|refactor|tools)\([^()\n]+\)\n\n[^\n]+\n\n\S[\s\S]*")
PAGE_TYPES = {"comment", "dismiss", "split", "delete"}
# A reference, label, environment or inline math is one token, so a diff never
# splits it and the page can render it.
TOKEN = re.compile(r"\\(?:cite[a-z]*|ref|eqref|autoref|cref|label|path|url|begin|end|input|includegraphics)\*?"
                   r"(?:\[[^\]]*\])*\{[^{}]*\}|\$[^$]*\$|\\[a-zA-Z]+|\\.|\s+|\w+|[^\w\s]")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def blocks(text):
    """Paragraphs as (start, end) offsets: runs of lines that are not blank."""
    return [m.span() for m in re.finditer(r"(?m)^[^\n]*\S[^\n]*(?:\n[^\n]*\S[^\n]*)*", text)]


def new_of(segs):
    return "".join(s[1] for s in segs if s[0] != "-")


def old_of(segs):
    return "".join(s[1] for s in segs if s[0] != "+")


def word_diff(a, b):
    """Segments [op, text], op in = - +. A short unchanged stretch between two
    changes is folded into them, so a reworded clause reads as 1 deletion and
    1 insertion instead of alternating fragments; nothing folds across a
    paragraph break, kept or changed."""
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    raw = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            raw.append(("=", "".join(ta[i1:i2])))
        if op in ("delete", "replace"):
            raw.append(("-", "".join(ta[i1:i2])))
        if op in ("insert", "replace"):
            raw.append(("+", "".join(tb[j1:j2])))

    def short(t):
        return len(t.strip()) <= 3 and not re.search(r"\S\s+\S|\n\s*\n", t)

    out, run, pending = [], [], ""

    def flush():
        if any(o == "-" for o, _ in run) and any(o == "+" for o, _ in run) and \
                not any(re.search(r"\n\s*\n", t) for _, t in run):
            out.append(["-", "".join(t for o, t in run if o != "+")])
            out.append(["+", "".join(t for o, t in run if o != "-")])
        else:
            out.extend(["=" if o == "~" else o, t] for o, t in run)
        run.clear()

    for op, t in raw:
        if op == "=":
            if run and short(t):
                pending += t
                continue
            flush()
            out.append(["=", pending + t])
            pending = ""
        else:
            if pending:
                run.append(("~", pending))
                pending = ""
            run.append((op, t))
    flush()
    if pending:
        out.append(["=", pending])
    merged = []
    for o, t in out:
        if not t:
            continue
        if merged and merged[-1][0] == o:
            merged[-1][1] += t
        else:
            merged.append([o, t])
    return merged


def own(segs, pars):
    """Segments [op, text] as pieces [op, text, k]: k indexes pars, the
    paragraphs ((start, end) in the text without the "-" side) a piece goes
    with, None for an unchanged blank line between two. A paragraph takes its
    text and the removals at its place (one at its first character opens it).
    An added paragraph takes the added blank lines that keep it apart, before
    it or else after it. Other added blank lines go with the paragraph before,
    unless only the paragraph after keeps words apart that committing either
    alone would join, or the one before is added."""
    starts, out, pos = [s for s, _ in pars], [], 0
    for n, (o, t) in enumerate(segs):
        if o == "-":
            out.append([o, t, max(bisect.bisect_right(starts, pos) - 1, 0), n, False])
            continue
        i = 0
        while i < len(t):
            k = bisect.bisect_right(starts, pos + i) - 1
            gap = k < 0 or pos + i >= pars[k][1]
            end = (pars[k + 1][0] if k + 1 < len(pars) else pos + len(t)) if gap else pars[k][1]
            out.append([o, t[i:end - pos], k, n, gap])
            i = end - pos
        pos += len(t)
    pure = [True] * len(pars)
    for o, _, k, _, gap in out:
        if not gap and o != "+":
            pure[k] = False
    took = {}
    for x, (o, _, k, n, gap) in enumerate(out):
        if o == "+" and not gap and pure[k]:
            y = next((y for y in (x - 1, x + 1) if 0 <= y < len(out) and out[y][3] == n and out[y][4] and y not in took), None)
            if y is not None:
                took[y] = k
    def side(x, k):
        if k < 0 or k + 1 == len(pars):
            return max(k, 0)
        if pure[k] or pure[k + 1]:
            return k + 1 if pure[k] and not pure[k + 1] else k
        new = lambda ps: next(((o, t) for o, t, *_ in ps if o != "-" and t), ("=", " "))
        old = lambda ps: next((t for o, t, *_ in ps if o != "+" and t), " ")
        (oa, ta), (ob, tb) = new(reversed(out[:x])), new(out[x + 1:])
        joins_after = ob == "+" and not tb[0].isspace() and not old(reversed(out[:x]))[-1].isspace()
        joins_before = oa == "+" and not ta[-1].isspace() and not old(out[x + 1:])[0].isspace()
        return k + 1 if joins_after and not joins_before else k
    res = [[o, t, k if not gap else None if o == "=" else took.get(x, side(x, k))]
           for x, (o, t, k, _, gap) in enumerate(out)]
    owned = [x for x, p in enumerate(res) if p[2] is not None]
    for a, b in zip(owned, owned[1:]):   # a blank line inside a paragraph's changes is the paragraph's
        if res[a][2] == res[b][2]:
            for x in range(a + 1, b):
                res[x][2] = res[a][2]
    return [p for p in res if p[1]]


def shared_breaks(old, new, ob, nb):
    """The paragraph breaks between old paragraphs ob and new ones nb that both
    keep, as (i, j): the break before ob[i] is the one before nb[j]. As many
    pair, in order, as can; one whose paragraph before ends, or after starts,
    the same way in both counts more."""
    def ends(text, bs):
        out = []
        for a, b in bs:
            t = [x for x in TOKEN.findall(text[a:b]) if not x.isspace()]
            out.append((t[:3], t[-3:]))
        return out
    eo, en = ends(old, ob), ends(new, nb)
    w = lambda i, j: 1 + (eo[i - 1][1] == en[j - 1][1]) + (eo[i][0] == en[j][0])
    best = [[0] * len(en) for _ in eo]
    for i in range(1, len(eo)):
        for j in range(1, len(en)):
            best[i][j] = max(best[i - 1][j], best[i][j - 1], best[i - 1][j - 1] + w(i, j))
    out, i, j = [], len(eo) - 1, len(en) - 1
    while i > 0 and j > 0:
        if best[i][j] == best[i - 1][j - 1] + w(i, j):
            out.append((i, j))
            i, j = i - 1, j - 1
        elif best[i][j] == best[i - 1][j]:
            i -= 1
        else:
            j -= 1
    return out[::-1]


def passages(path, old, new):
    """The diff of old to new: a passage per paragraph of new, and per paragraph
    of old removed between kept ones. A passage's segments cover new from "at"
    and old from "old_at", blank lines it adds or removes included, so each
    passage applied alone keeps paragraphs apart and all of them give new.
    Breaks both texts keep stay put, so text moved across one shows as removed
    on one side and added on the other. "key" places it in any diff to new:
    its paragraph of new ("par") and last line, or for a removed paragraph the
    paragraph after it, its text and which of equal ones it is."""
    ob, nb = blocks(old), blocks(new)
    breaks = [m.start() for m in re.finditer("\n", new)]
    out, seen = [], {}

    def add(segs, at, old_at, par):
        a, b = old_of(segs), new_of(segs)
        pid = hashlib.sha1(f"{path}\0{a}\0{b}".encode()).hexdigest()[:12]
        seen[pid] = seen.get(pid, 0) + 1
        if seen[pid] > 1:
            pid += f"-{seen[pid]}"
        start = bisect.bisect_left(breaks, at) + 1
        out.append({"id": pid, "file": path, "start": start, "end": start + b.rstrip().count("\n"),
                    "kind": "changed" if any(o != "=" for o, _ in segs) else "same", "segs": segs,
                    "at": at, "old_at": old_at, "par": par})

    sm = difflib.SequenceMatcher(None, [old[a:b] for a, b in ob], [new[a:b] for a, b in nb], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for (a, _), (c, d), j in zip(ob[i1:i2], nb[j1:j2], range(j1, j2)):
                add([["=", new[c:d]]], c, a, j)
            continue
        # The edited run, with the blank lines around it, in groups between the breaks both keep.
        cut = [(i1, j1)] + [(i1 + i, j1 + j) for i, j in shared_breaks(old, new, ob[i1:i2], nb[j1:j2])] + [(i2, j2)]
        for (ia, ja), (iz, jz) in zip(cut, cut[1:]):
            oa = ob[ia][0] if ia > i1 else ob[i1 - 1][1] if i1 else 0
            na = nb[ja][0] if ja > j1 else nb[j1 - 1][1] if j1 else 0
            a = old[oa:ob[iz][0] if iz < len(ob) else len(old)]
            b = new[na:nb[jz][0] if jz < len(nb) else len(new)]
            if ia < iz and ja < jz:   # the blank lines around the group change only as a whole
                (a1, a2), (b1, b2) = (ob[ia][0] - oa, ob[iz - 1][1] - oa), (nb[ja][0] - na, nb[jz - 1][1] - na)
                edge = lambda x, y: [["=", x]] if x == y else [["-", x], ["+", y]]
                segs = []
                for s in edge(a[:a1], b[:b1]) + word_diff(a[a1:a2], b[b1:b2]) + edge(a[a2:], b[b2:]):
                    if segs and segs[-1][0] == s[0]:
                        segs[-1][1] += s[1]
                    elif s[1]:
                        segs.append(s)
            else:   # whole paragraphs added or removed: the blank lines both have stay
                kept, more, o = (a, b, "+") if ja < jz else (b, a, "-")
                segs = ([["=", kept], [o, more[len(kept):]]] if more.startswith(kept) else
                        [[o, more[:len(more) - len(kept)]], ["=", kept]] if more.endswith(kept) else [["-", a], ["+", b]])
            segs = [s for s in segs if s[1]]
            if ja < jz:
                pieces = own(segs, [(s - na, e - na) for s, e in nb[ja:jz]])
            else:   # removed paragraphs own their text as added ones do
                flip = {"+": "-", "-": "+", "=": "="}
                pieces = [[flip[o], t, k] for o, t, k in own([[flip[o], t] for o, t in segs],
                                                            [(s - oa, e - oa) for s, e in ob[ia:iz]])]
            po, pn, got = oa, na, {}
            for o, t, k in pieces:
                if k is not None:
                    g = got.setdefault(k, ([], pn, po))[0]
                    if g and g[-1][0] == o:
                        g[-1][1] += t
                    else:
                        g.append([o, t])
                po += 0 if o == "+" else len(t)
                pn += 0 if o == "-" else len(t)
            for k in sorted(got):
                add(*got[k], ja + k if ja < jz else None)
    slot, count = 0, {}
    for p in out:
        if p["par"] is None:
            k = (slot, old_of(p["segs"]).strip())
            count[k] = count.get(k, 0) + 1
            p["key"] = [*k, count[k]]
        else:
            slot = p["par"] + 1
            p["key"] = [p["par"], p["end"]]
    return out


def cut_at(o, t, pos, at):
    """Segment text t at pos, in pieces that no position in `at` falls inside."""
    if o == "-":
        return [t]
    out, last = [], 0
    for c in at:
        if pos + last < c < pos + len(t):
            out.append(t[last:c - pos])
            last = c - pos
    return out + [t[last:]]


def pieces(segs, at):
    """Segments cut at positions `at` of their new text, as 1 list per part; a
    removed text there opens the later part."""
    parts, pos = [[] for _ in range(len(at) + 1)], 0
    for o, t in segs:
        for piece in cut_at(o, t, pos, at):
            parts[bisect.bisect_right(at, pos)].append([o, piece])
            if o != "-":
                pos += len(piece)
    return parts


def old_place(segs, c):
    """Where place c of a diff's new text is in its old text; a removal at c
    comes after it."""
    a = b = 0
    for o, t in segs:
        if o == "-":
            if b == c:
                return a
            a += len(t)
        elif b <= c < b + len(t):
            return a + (c - b if o == "=" else 0)
        else:
            a, b = a + (len(t) if o == "=" else 0), b + len(t)
    return a


def similar(a, b):
    """The words of a found, in order, in b, a's word count, and how alike a and
    b are, counting spaces too (2 * tokens found / tokens of both)."""
    def found(ta, tb):
        return sum(m.size for m in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_matching_blocks())
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    words = [[t for t in x if not t.isspace()] for x in (ta, tb)]
    return found(*words), len(words[0]), 2 * found(ta, tb) / ((len(ta) + len(tb)) or 1)


def match(units, records):
    """The approve_text record in force for each unit (a changed passage before
    splitting), or None. A record goes with a unit of its base text; units and
    records of one base pair 1 to 1, the most alike first. Inserted text has
    base "", so its record goes only to a unit holding half its words or more."""
    groups, out = {}, [None] * len(units)
    for x, u in enumerate(units):
        groups.setdefault(u["base"], ([], []))[0].append(x)
    for y, r in enumerate(records):
        if r["base"] in groups:
            groups[r["base"]][1].append(y)
    for base, (xs, ys) in groups.items():
        if base and len(xs) == len(ys) == 1:
            out[xs[0]] = records[ys[0]]
            continue
        pairs = []
        for x in xs:
            for y in ys:
                m, n, alike = similar(records[y]["text"], new_of(units[x]["segs"]))
                if base or 2 * m >= n > 0:
                    pairs.append((-m, -alike, x, -y))   # most words, most alike, the first unit, the latest record
        used = set()
        for *_, x, y in sorted(pairs):
            if out[x] is None and -y not in used:
                out[x] = records[-y]
                used.add(-y)
    return out


def approvals(units, records, cmap):
    """Give each unit (changed passage) its approval: "base", its text at the
    base, which keys its approve_text records; "rec", the record in force (or
    None); and, with one, "shows": the diff from the approved text to the
    unit's text, 1 per part between the split positions cmap ({position: split
    entry id}). A part's share of the approved text starts where the record
    says ("cuts", by split entry), else where the whole diff puts it."""
    for u in units:
        u["base"] = old_of(u["segs"])
    for u, r in zip(units, match(units, records)):
        u["rec"] = r and r["id"]
        if not r:
            continue
        a, w = r["text"], new_of(u["segs"])
        at = [(x - u["at"], s) for x, s in cmap.items() if u["at"] < x < u["at"] + len(w)]
        whole = word_diff(a, w) if at else None
        alpha = [r.get("cuts", {}).get(s, old_place(whole, c)) for c, s in at]
        if alpha != sorted(alpha) or any(not 0 <= x <= len(a) for x in alpha):
            alpha = [old_place(whole, c) for c, _ in at]
        cs, al = [0, *(c for c, _ in at), len(w)], [0, *alpha, len(a)]
        u["shows"] = [word_diff(a[al[i]:al[i + 1]], w[cs[i]:cs[i + 1]]) for i in range(len(cs) - 1)]


def split(path, ps, cmap):
    """Cut each passage at its split positions (cmap: {position in the new text:
    split entry id}); a removed text there opens the later part. A part's id and
    kind depend on its own diff from the base, so approving, editing or
    splitting another part leaves them as they were. A part shows its share of
    the passage's "shows" (the diff from its approved text), else of its own
    diff, and carries "unit" (the passage's id), "base" and "rec" (its
    approval), "split" (the split entry it starts at), "a_at" (where its share
    starts in the approved text) and "whole": the hunk of the passage, as [old,
    new], each of its hunks is in."""
    out, seen = [], {}
    for p in ps:
        w = new_of(p["segs"])
        cut = [(x - p["at"], s) for x, s in cmap.items() if p["kind"] == "changed" and p["at"] < x < p["at"] + len(w)]
        at = [c for c, _ in cut]
        raw = pieces(p["segs"], at)
        shows = p.pop("shows", None) or raw
        whole, tag, run = [], [], False   # the passage's hunks, and the one each segment is in
        for segs in shows:
            tag.append([])
            for o, t in segs:
                if o == "=":
                    run = False
                elif not run:
                    whole.append(["", ""])
                    run = True
                if o != "=":
                    whole[-1][o == "+"] += t
                tag[-1].append(len(whole) - 1)
        old_at, a_at = p["old_at"], 0
        for i, segs in enumerate(shows):
            mine = [whole[k] for n, k in enumerate(tag[i]) if segs[n][0] != "=" and (n == 0 or segs[n - 1][0] == "=")]
            part = {**p, "segs": segs, "unit": p["id"], "base": p.get("base", old_of(p["segs"])), "rec": p.get("rec"),
                    "split": cut[i - 1][1] if i else None, "a_at": a_at, "whole": mine}
            a_at += len(old_of(segs))
            if at:
                olds, news = old_of(raw[i]), new_of(raw[i])
                pid = hashlib.sha1(f"{path}\0{olds}\0{news}\0part".encode()).hexdigest()[:12]
                seen[pid] = seen.get(pid, 0) + 1
                off = at[i - 1] if i else 0
                start = p["start"] + w.count("\n", 0, off)
                end = start + news.rstrip().count("\n")
                changed = any(o != "=" for o, _ in raw[i] + segs)
                part.update({"id": pid + (f"-{seen[pid]}" if seen[pid] > 1 else ""), "start": start, "end": end,
                             "kind": "changed" if changed else "same", "at": p["at"] + off, "old_at": old_at,
                             "key": [p["par"], end]})
                old_at += len(olds)
            out.append(part)
    return out


def cuts(ps, splits):
    """Where the reviewer's split entries cut the changed passages ps, as
    {position in their new text: the split entry's id}. A split stays with its
    passage (the one it was made on, else the one holding its line), at the
    line reading as its anchor nearest its line, else at its line."""
    live, out = [p for p in ps if p["kind"] == "changed"], {}
    for e in splits:
        p = next((p for p in live if p["id"] == e.get("passage")), None) or \
            next((p for p in live if p["start"] < e["line"] <= p["end"]), None)
        if not p:
            continue
        lines, want = new_of(p["segs"]).split("\n"), e["line"] - p["start"]
        k = min([k for k in range(1, len(lines)) if lines[k] == e.get("text")] or [want], key=lambda k: abs(k - want))
        if 0 < k < len(lines) and lines[k].strip() and any(l.strip() for l in lines[:k]):
            out.setdefault(p["at"] + sum(len(l) + 1 for l in lines[:k]), e.get("id"))
    return dict(sorted(out.items()))


def rebase(head, base, work, ps):
    """ps, a diff from base to work, as changes to head when head is base with
    some of them made: those not made yet, each at its place in head. None
    when head is something else."""
    at, o, n = {0: []}, 0, 0   # place in head -> the passages not made before it
    for p in ps + [None]:
        oa, na = (p["old_at"], p["at"]) if p else (len(base), len(work))
        at = {x + len(g): c for x, c in at.items() for g in {base[o:oa], work[n:na]} if head.startswith(g, x)}
        if not p:
            return at.get(len(head))
        a, b, nxt = old_of(p["segs"]), new_of(p["segs"]), {}
        for x, c in at.items():
            if head.startswith(b, x):
                nxt.setdefault(x + len(b), c)
            if a != b and head.startswith(a, x):
                nxt.setdefault(x + len(a), c + [{**p, "old_at": x}])
        at, o, n = nxt, oa + len(a), na + len(b)


def view(path, base, head, work, splits=(), records=(), edits=None):
    """A file's passages as the page shows them, and the changes from head that
    commits make. The page shows the diff from base cut at the reviewer's
    splits, each passage against its approved text (records), each hunk with
    the edit that made it (edits: {(old, new): edit id}, by the passage's hunk
    it is in) and "dirty" when its lines differ from head. Commits make the
    shown passages not in head yet when head is base with some made, else the
    diff from head cut the same way; then a change from head the base diff
    does not show (a committed change reverted) shows as a passage of its own."""
    ps = passages(path, base, work)
    cmap = cuts(ps, splits)
    raw = split(path, copy.deepcopy(ps), cmap)
    ours, extra, put = rebase(head, base, work, raw), [], {}
    if ours is None:
        ours = split(path, passages(path, head, work), cmap)
        where = {tuple(q["key"]): i for i, q in enumerate(raw)}
        for u in ours:
            i = where.get(tuple(u["key"]))
            if u["kind"] != "changed":
                continue
            if i is None:
                extra.append(dict(u))
            elif raw[i]["kind"] != "changed":
                put[i] = dict(u)
    approvals([p for p in ps if p["kind"] == "changed"] + extra + list(put.values()), records, cmap)
    shown = split(path, ps, cmap)
    for i, u in put.items():
        shown[i] = split(path, [u], {})[0]
    for u in extra:
        u = split(path, [u], {})[0]
        shown.insert(bisect.bisect_left([q["at"] for q in shown], u["at"]), u)
    for p in shown:
        p["dirty"] = any(u["kind"] == "changed" and u["key"] == p["key"] for u in ours)
        p["edits"] = [(edits or {}).get(tuple(h)) for h in p.pop("whole")]
    return shown, ours


def unit_hunks(path, base, work, splits=(), records=()):
    """The hunks, as (old, new), of the changed passages of the diff from base
    to work, each against its approved text, before the splits cut them."""
    ps = [p for p in passages(path, base, work) if p["kind"] == "changed"]
    cmap = cuts(ps, splits)
    approvals(ps, records, cmap)
    return {tuple(h) for p in split(path, ps, cmap) for h in p["whole"]}


def approve_texts(shown, pick, texts):
    """The approve_text entries that make hunks `pick` ({part id: hunk
    indices}) of the parts shown: per passage, its approved text (texts:
    {record id: text}, else its base) with those hunks made, and where each of
    its parts starts in it now ("cuts", by split entry)."""
    units, out = {}, []
    for p in shown:
        units.setdefault(p["unit"], []).append(p)
    for parts in units.values():
        if not any(pick.get(p["id"]) for p in parts):
            continue
        first = parts[0]
        text, shift, at = texts[first["rec"]] if first["rec"] else first["base"], 0, {}
        for p in parts:
            old, start = old_of(p["segs"]), p["a_at"] + shift
            if text[start:start + len(old)] != old:
                raise LookupError("the passage changed since the page loaded")
            if p["split"]:
                at[p["split"]] = start
            if p["id"] not in pick:
                continue
            ks, k, run, new = pick[p["id"]], -1, False, ""
            for o, t in p["segs"]:
                if o != "=" and not run:
                    k += 1
                run = o != "="
                if o == "=" or (o == "+") == (k in ks):
                    new += t
            text, shift = text[:start] + new + text[start + len(old):], shift + len(new) - len(old)
        out.append({"type": "approve_text", "file": first["file"], "base": first["base"], "text": text,
                    **({"cuts": at} if at else {}), **({"replaces": first["rec"]} if first["rec"] else {})})
    return out


def hunks(segs):
    """Each run of changed segments as (start, end, old, new), positions in the
    passage's new text. The page numbers hunks the same way."""
    out, pos, cur = [], 0, None
    for o, t, *_ in segs:
        if o == "=":
            cur = None
            pos += len(t)
            continue
        if cur is None:
            cur = [pos, pos, "", ""]
            out.append(cur)
        if o == "-":
            cur[2] += t
        else:
            cur[3] += t
            pos += len(t)
            cur[1] = pos
    return [tuple(h) for h in out]


def staged(old, ps):
    """old with the changes of passages ps (of a diff from old, in order) made."""
    for p in reversed(ps):
        old = old[:p["old_at"]] + new_of(p["segs"]) + old[p["old_at"] + len(old_of(p["segs"])):]
    return old


class Review:
    def __init__(self, repo, base, files, check=None):
        self.repo, self.base, self.files, self.check = repo, base, files, check
        self.dir = repo / ".review"
        self.dir.mkdir(exist_ok=True)
        (self.dir / ".gitignore").write_text("*\n")
        self.log_path = self.dir / "log.jsonl"
        self.log_path.touch()
        self.lock = threading.Lock()
        self.track_lock = threading.Lock()
        self.edit = threading.Lock()   # a revert's read and write of a file, a commit's look at it
        self.seen = {}   # path -> (text, hunk keys) at the last look, for track()
        self.queue = queue.Queue()   # comments and approvals, handled one at a time
        self.agent = False           # comments go to claude -p (there is an API key)

    def text(self, path):
        f = self.repo / path
        return f.read_text(errors="replace") if f.exists() else ""

    def old_text(self, path):
        r = git(self.repo, "show", f"{self.base}:{path}")
        return r.stdout if r.returncode == 0 else ""

    def doc(self):
        self.track()
        return {"files": [{"path": p, "passages": self.shown(p)} for p in self.files]}

    def state(self, path):
        """The log's splits of a file, its approve_text records in force (an entry
        replaces the one it names; one back to the base text approves nothing)
        and its edits, {(old, new): the latest edit with that hunk}."""
        splits, records, edits = [], {}, {}
        for e in self.log():
            if e.get("file") != path:
                continue
            if e["type"] == "split":
                splits.append(e)
            elif e["type"] == "approve_text":
                records.pop(e.get("replaces"), None)
                if e["text"] != e["base"]:
                    records[e["id"]] = e
            elif e["type"] == "edit":
                edits.update({(o, n): e["id"] for o, n in e["hunks"]})
        return splits, list(records.values()), edits

    def view(self, path, head="HEAD"):
        """view() of a reviewed file, and head's text."""
        r = git(self.repo, "show", f"{head}:{path}")
        old = r.stdout if r.returncode == 0 else ""
        return (*view(path, self.old_text(path), old, self.text(path), *self.state(path)), old)

    def shown(self, path):
        return self.view(path)[0]

    def track(self):
        """Log the hunks each change to a reviewed file introduced, as one edit the
        page can approve in one click: those the page shows now (against the
        approved texts, before splits) and did not show for the text before.
        Before the first look, the file is taken as it was at HEAD, so the
        uncommitted changes form the first edit."""
        with self.track_lock:
            for path in self.files:
                text = self.text(path)
                if path not in self.seen:
                    head = git(self.repo, "show", f"HEAD:{path}")
                    self.seen[path] = head.stdout if head.returncode == 0 else ""
                if self.seen[path] == text:
                    continue
                splits, records, _ = self.state(path)
                new = unit_hunks(path, self.old_text(path), text, splits, records) - \
                    unit_hunks(path, self.old_text(path), self.seen[path], splits, records)
                if new:
                    self.append({"type": "edit", "file": path, "hunks": sorted(map(list, new))})
                self.seen[path] = text

    def approve(self, body):
        """Approve hunks the page showed: each item {file, passage, hunks: [k, ...]
        or "all", seen: [[old, new], ...]} makes those hunks in its passage's
        approved text. A passage (or part) then left with no hunk and with
        uncommitted lines is approved whole, which commits it. Refused, with
        nothing logged, when a passage or the hunks the page saw are gone."""
        items, out = body if isinstance(body, list) else [body], []
        with self.edit:
            todo = []
            for path in dict.fromkeys(it["file"] for it in items):
                if path not in self.files:
                    raise LookupError("not a reviewed file")
                shown, pick = self.shown(path), {}
                for it in (it for it in items if it["file"] == path):
                    p = next((p for p in shown if p["id"] == it["passage"]), None)
                    hs = hunks(p["segs"]) if p else []
                    ks = list(range(len(hs))) if it["hunks"] == "all" else it["hunks"]
                    if not p or not all(isinstance(k, int) and 0 <= k < len(hs) for k in ks) or \
                            [list(hs[k][2:]) for k in ks] != it["seen"]:
                        raise LookupError("the passage changed since the page loaded")
                    pick[p["id"]] = set(ks)
                texts = {r["id"]: r["text"] for r in self.state(path)[1]}
                todo.append((path, pick, approve_texts(shown, pick, texts)))
            for path, pick, entries in todo:
                out += [self.append(e) for e in entries]
                for p in self.shown(path):
                    if p["id"] in pick and p["dirty"] and not hunks(p["segs"]):
                        e = self.append({"type": "approve", "passage": p["id"], "file": path, "line": p["start"]})
                        self.enqueue(e)
                        out.append(e)
        return out

    def withdraw(self, body):
        """Put the approved text of the passage a part is in back to its base text."""
        with self.edit:
            p = next((p for p in self.shown(body["file"]) if p["id"] == body["passage"]), None) \
                if body["file"] in self.files else None
            if not p or not p["rec"]:
                raise LookupError("nothing approved in the passage")
            return self.append({"type": "approve_text", "file": p["file"], "base": p["base"], "text": p["base"],
                                "replaces": p["rec"]})

    def version(self):
        h = hashlib.sha1((self.base + git(self.repo, "rev-parse", "HEAD").stdout).encode())   # a commit changes what is dirty
        for p in self.files:
            f = self.repo / p
            st = f.stat() if f.exists() else None
            h.update(f"{p}:{st and st.st_mtime_ns}:{st and st.st_size};".encode())
        return h.hexdigest()

    def log(self):
        return [json.loads(l) for l in self.log_path.read_text().splitlines() if l.strip()]

    def append(self, entry):
        entry = {"id": uuid.uuid4().hex[:8], "ts": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}
        with self.lock, open(self.log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def revert(self, body):
        """Put one hunk's old text (the approved text, else the base) back into the
        file, if the passage and the hunk ("seen": [old, new]) still read as the
        page showed them."""
        path = body["file"]
        if path not in self.files:
            raise LookupError("not a reviewed file")
        with self.edit:
            p = next((p for p in self.shown(path) if p["id"] == body["passage"]), None)
            hs = hunks(p["segs"]) if p else []
            k = int(body["hunk"])
            text, shown = self.text(path), new_of(p["segs"]) if p else ""
            if not 0 <= k < len(hs) or text[p["at"]:p["at"] + len(shown)] != shown or \
                    body.get("seen", list(hs[k][2:])) != list(hs[k][2:]):
                raise LookupError("the passage changed since the page loaded")
            start, end, old, new = hs[k]
            (self.repo / path).write_text(text[:p["at"] + start] + old + text[p["at"] + end:])
            return self.append({"type": "revert", "passage": p["id"], "file": path, "line": p["start"],
                                "removed": new, "restored": old})

    def claude(self, prompt, tools, model=MODEL):
        """Run claude -p in the repo on the Keychain API key; return its result
        event, with "edits", the files its tool calls changed."""
        key = api_key()
        if not key:
            raise RuntimeError(f"No API key in the Keychain (service {KEYCHAIN_SERVICE}).")
        # A clean environment: no variable of the session that started the server,
        # and no credential that outranks the key.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE") and k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}
        env["ANTHROPIC_API_KEY"] = key
        r = subprocess.run(["claude", "-p", prompt, "--model", model, "--allowedTools", tools,
                            "--permission-mode", "dontAsk", "--output-format", "stream-json", "--verbose"],
                           cwd=self.repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=600)
        events = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
        init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
        result = next((e for e in events if e.get("type") == "result"), None)
        if init.get("apiKeySource") != "ANTHROPIC_API_KEY":
            raise RuntimeError(f"claude -p did not use the API key (apiKeySource={init.get('apiKeySource')}).")
        if not result or result.get("is_error"):
            raise RuntimeError((result or {}).get("result") or r.stderr[-500:] or "claude -p failed")
        return {**result, "edits": edits(events)}

    def history(self, ids):
        """The comments (with Claude's replies) and contextualizations ids names,
        oldest first, as a comment's prompt quotes them."""
        log, ids = self.log(), set(ids)
        replies = {}
        for e in log:
            if e["type"] == "reply":
                replies.setdefault(e["to"], []).append(e)
        out = []
        for e in log:
            if e["id"] in ids and e["type"] == "comment":
                out.append(f"Reviewer, on: {e.get('quote') or '(the whole passage)'}\n{e['text']}")
                out += [f"Claude: {r['text']}" for r in replies.get(e["id"], [])]
            elif e["id"] in ids and e["type"] == "context":
                out.append(f"Reviewer asked for context on: {e['quote']}\nClaude: {e['text']}")
        return "\n\n".join(out)

    def contextualize(self, body):
        result = self.claude(f"/contextualize {body['quote']}\n\n(It is in {body['file']}, near line {body['line']}.)",
                             CONTEXT_TOOLS)
        return self.append({"type": "context", "passage": body["passage"], "file": body["file"],
                            "line": body["line"], "quote": body["quote"], "text": result["result"],
                            "cost": result.get("total_cost_usd"), "model": MODEL})

    def start_worker(self):
        """Handle comments (with an API key) and passage approvals one at a time,
        so no 2 jobs touch a file at once. The jobs a stopped server left open
        (a comment with no reply, an approval with no later commit or
        unapproval) run first, in log order."""
        self.agent = api_key() is not None
        threading.Thread(target=self.work, daemon=True).start()
        done, todo = set(), []
        for e in reversed(self.log()):
            if e["type"] in ("commit", "unapprove"):
                done.add(("approve", e.get("passage")))
            elif e["type"] == "reply":
                done.add(("comment", e["to"]))
            elif e["type"] in ("approve", "comment"):
                k = (e["type"], e["passage"] if e["type"] == "approve" else e["id"])
                if k not in done:
                    done.add(k)
                    todo.append(e)
        for e in reversed(todo):
            self.enqueue(e)

    def enqueue(self, e):
        if e["type"] == "approve" or (e["type"] == "comment" and self.agent):
            self.queue.put(e)

    def work(self):
        while True:
            e = self.queue.get()
            try:
                self.answer(e) if e["type"] == "comment" else self.commit(e)
            except Exception as err:   # keep the worker alive
                self.append({"type": "commit", "passage": e.get("passage"), "file": e.get("file"),
                             "line": e.get("line"), "error": str(err)})

    def stage(self, path, pid):
        """The shown passage pid, what its commit makes of the file at HEAD,
        HEAD's text and HEAD."""
        with self.edit:
            sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
            shown, ours, head = self.view(path, sha)
            p = next((p for p in shown if p["id"] == pid), None)
            ps = [u for u in ours if p and u["kind"] == "changed" and u["key"] == p["key"]]
            return p, staged(head, ps), head, sha

    def commit(self, e):
        """Commit the uncommitted edits inside an approved passage, and nothing
        else, on the HEAD they were computed from."""
        path, at = e["file"], {"type": "commit", "passage": e["passage"], "file": e["file"], "line": e["line"]}
        for checked in (False, True):   # again after the check, which may take long
            p, text, head, sha = self.stage(path, e["passage"])
            if not p:
                return self.append({**at, "error": "the passage changed after it was approved"})
            if git(self.repo, "diff", "--cached", "--quiet").returncode:
                return self.append({**at, "error": "other changes are staged; commit or unstage them first"})
            if text == head:
                return self.append({**at, "skipped": "nothing uncommitted in the passage"})
            if checked or not self.check:
                break
            r = subprocess.run(self.check, shell=True, cwd=self.repo, capture_output=True, text=True, timeout=900)
            if r.returncode:
                return self.append({**at, "error": f"check failed: {self.check}\n{(r.stdout + r.stderr)[-400:]}"})
        blob = subprocess.run(["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"], input=text,
                              capture_output=True, text=True).stdout.strip()
        mode = git(self.repo, "ls-files", "-s", "--", path).stdout.split(" ")[0] or "100644"
        r = git(self.repo, "update-index", "--cacheinfo", f"{mode},{blob},{path}")
        if r.returncode:
            return self.append({**at, "error": "git update-index: " + r.stderr[-400:]})
        msg, cost = None, None
        if self.agent:
            try:
                res = self.claude(MESSAGE_PROMPT, "Read,Bash(git diff:*)")
                msg, cost = res["result"].strip().strip("`").strip(), res.get("total_cost_usd")
            except Exception:
                pass
        if not msg or not MESSAGE.fullmatch(msg):
            span = f"line {p['start']}" if p["start"] == p["end"] else f"lines {p['start']}-{p['end']}"
            msg = (f"docs(review {Path(path).stem})\n\nApply approved review edits to {path}, {span}\n\n"
                   f"Edits made during the review of {path}, {span}, approved by the author on the review page.")
        if git(self.repo, "rev-parse", "HEAD").stdout.strip() != sha or \
                git(self.repo, "diff", "--cached", "--name-only").stdout != path + "\n" or \
                git(self.repo, "rev-parse", f":{path}").stdout.strip() != blob:
            git(self.repo, "reset", "-q", "--", path)
            return self.append({**at, "error": "HEAD moved while committing; approve again"})
        r = subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-F", "-"], input=msg + "\n",
                           capture_output=True, text=True)
        if r.returncode:
            git(self.repo, "reset", "-q", "--", path)
            return self.append({**at, "error": "git commit: " + (r.stderr or r.stdout)[-400:]})
        sha = git(self.repo, "rev-parse", "--short", "HEAD").stdout.strip()
        return self.append({**at, "sha": sha, "message": msg, "cost": cost, "model": MODEL if cost else None})

    def answer(self, c):
        model, edited = c.get("model", MODEL), set()
        try:
            earlier = self.history(c.get("history") or [])
            r = self.claude(COMMENT_PROMPT.format(file=c["file"], line=c["line"], text=c["text"],
                                                  quote=c.get("quote") or "(none: the whole passage)",
                                                  history=earlier and "\n\nEarlier exchanges on this passage, oldest first "
                                                  "(the text may have changed since):\n\n" + earlier), EDIT_TOOLS, model)
            text, cost = r["result"], r.get("total_cost_usd")
            edited = {(self.repo / f).resolve() for f in r["edits"]}
        except Exception as e:
            text, cost = f"Failed: {e}", None
        # edited: whether the answer itself changed a reviewed file; the page
        # keeps showing the comment when it did not (a question, a refusal, a failure).
        self.track()
        self.append({"type": "reply", "to": c["id"], "text": text, "cost": cost, "model": model,
                     "edited": any((self.repo / p).resolve() in edited for p in self.files)})


def bib_field(entry, name):
    """A BibTeX field's value: braced (nesting allowed), quoted or bare."""
    m = re.search(r"(?im)^\s*" + name + r"\s*=\s*", entry)
    if not m:
        return ""
    i = m.end()
    if entry[i:i + 1] == "{":
        depth, j = 0, i
        for j in range(i, len(entry)):
            depth += {"{": 1, "}": -1}.get(entry[j], 0)
            if depth == 0:
                break
        return entry[i + 1:j]
    if entry[i:i + 1] == '"':
        return entry[i + 1:entry.find('"', i + 1)]
    return re.match(r"[^,\s}]*", entry[i:]).group()


def accents(v):
    """LaTeX accents ({\\"o}, \\'e) as Unicode letters."""
    marks = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303"}
    return unicodedata.normalize("NFC", re.sub(r"""\\(["'`^~])\{?([A-Za-z])\}?""",
                                               lambda m: m.group(2) + marks[m.group(1)], v))


def refs(repo):
    """What the page needs to render LaTeX: citation keys as "Author Year" (with
    the title) from the repo's .bib files, and label numbers from its .aux files,
    so \\ref shows what the last build printed."""
    cites, labels = {}, {}
    for f in sorted(repo.rglob("*.bib")):
        if ".review" in f.parts:
            continue
        for entry in re.split(r"(?m)^(?=@)", f.read_text(errors="replace")):
            m = re.match(r"@\w+\s*\{\s*([^,\s]+)\s*,", entry)
            if not m:
                continue
            clean = lambda v: re.sub(r"\\[a-zA-Z]+|[{}\\]", "", re.sub(r"\s+", " ", accents(v))).strip()
            # A fully braced author is an organization: keep its whole name.
            last = [clean(a) if a.strip().startswith("{") else
                    clean(a).split(",")[0] if "," in a else clean(a).split(" ")[-1]
                    for a in re.split(r"\s+and\s+", bib_field(entry, "author")) if a.strip()]
            who = (last[0] if len(last) == 1 else " & ".join(last) if len(last) == 2 else f"{last[0]} et al." if last
                   else clean(bib_field(entry, "organization") or bib_field(entry, "title"))[:40])
            year = (bib_field(entry, "year") or bib_field(entry, "date"))[:4]
            cites[m.group(1)] = {"short": f"{who} {year}".strip(), "title": clean(bib_field(entry, "title"))}
    for f in sorted(repo.rglob("*.aux")):
        for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", f.read_text(errors="replace")):
            labels.setdefault(m.group(1), m.group(2))
    return {"cites": cites, "labels": labels}


def edits(events):
    """The file_path of each file tool call in claude -p's stream-json events
    that did not fail."""
    calls, failed = {}, set()
    for e in events:
        for b in (e.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") in ("Edit", "MultiEdit", "Write"):
                calls[b.get("id")] = (b.get("input") or {}).get("file_path")
            elif b.get("type") == "tool_result" and b.get("is_error"):
                failed.add(b.get("tool_use_id"))
    return sorted({f for i, f in calls.items() if f and i not in failed})


def api_key():
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def handler(review, port):
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):   # the page left before the reply
                self.close_connection = True

        def guard(self):
            # Refuse other sites' pages (DNS rebinding, cross-site POSTs): the Host
            # must be this server, and POSTs carry a header a cross-site form cannot set.
            if self.headers.get("Host") not in hosts:
                return self.send(403, {"error": "bad host"}) or False
            if self.command == "POST" and self.headers.get("X-Review") != "1":
                return self.send(403, {"error": "missing X-Review header"}) or False
            return True

        def do_GET(self):
            if not self.guard():
                return
            if self.path == "/":
                return self.send(200, (HERE / "page.html").read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/info":
                return self.send(200, {"repo": str(review.repo), "base": review.base, "model": MODEL, "models": MODELS,
                                       "has_key": api_key() is not None, "service": KEYCHAIN_SERVICE,
                                       "worker": review.agent})
            if self.path == "/api/refs":
                return self.send(200, refs(review.repo))
            if self.path == "/api/doc":
                return self.send(200, review.doc())
            if self.path == "/api/state":
                # build: the page reloads itself when it differs from the code it was loaded with.
                return self.send(200, {"version": review.version(), "log": len(review.log()),
                                       "build": f"{SERVER_BUILD}-{(HERE / 'page.html').stat().st_mtime_ns}"})
            if self.path == "/api/log":
                return self.send(200, review.log())
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if not self.guard():
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/log":
                    if body.get("type") not in PAGE_TYPES:
                        return self.send(400, {"error": "bad type"})
                    if body.get("model", MODEL) not in MODELS.values():
                        return self.send(400, {"error": "bad model"})
                    keep = {k: body[k] for k in ("type", "passage", "file", "line", "quote", "text", "to", "model", "history") if k in body}
                    e = review.append(keep)
                    review.enqueue(e)
                    return self.send(200, e)
                act = {"/api/revert": review.revert, "/api/approve": review.approve, "/api/withdraw": review.withdraw}
                if self.path in act:
                    try:
                        return self.send(200, act[self.path](body))
                    except LookupError as e:
                        return self.send(409, {"error": str(e)})
                if self.path == "/api/contextualize":
                    return self.send(200, review.contextualize(body))
                self.send(404, {"error": "not found"})
            except Exception as e:
                self.send(500, {"error": str(e)})

    return H


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.returncode:
        sys.exit(f"not a git repository: {path}")
    return Path(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--base", required=True)
    s.add_argument("--repo", default=".")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--check", help="shell command that must pass before an approval commits, e.g. a build")
    s.add_argument("files", nargs="*")
    r = sub.add_parser("reply")
    r.add_argument("--repo", default=".")
    r.add_argument("id")
    r.add_argument("text")
    o = sub.add_parser("open")
    o.add_argument("--repo", default=".")
    a = ap.parse_args()
    repo = repo_root(Path(a.repo).resolve())

    if a.cmd == "serve":
        if git(repo, "rev-parse", "--verify", a.base + "^{commit}").returncode:
            sys.exit(f"unknown ref: {a.base}")
        files = a.files or git(repo, "diff", "--name-only", a.base).stdout.split()
        review = Review(repo, a.base, files, a.check)
        review.start_worker()
        for port in range(a.port, a.port + 20):
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), handler(review, port))
                break
            except OSError:
                continue
        else:
            sys.exit("no free port")
        print(f"http://127.0.0.1:{port}  log: {review.log_path}", flush=True)
        server.serve_forever()

    log_path = repo / ".review" / "log.jsonl"
    entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()] if log_path.exists() else []
    if a.cmd == "reply":
        if not any(e["id"] == a.id and e["type"] == "comment" for e in entries):
            sys.exit(f"no comment {a.id}")
        Review(repo, "", []).append({"type": "reply", "to": a.id, "text": a.text})
    else:
        answered = {e["to"] for e in entries if e["type"] == "reply"}
        for e in entries:
            if e["type"] == "comment" and e["id"] not in answered:
                print(json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
