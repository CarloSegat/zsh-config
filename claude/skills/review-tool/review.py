#!/usr/bin/env python3
"""Local review page for text changes since a git ref (see SKILL.md).

    review.py serve --base REF [--repo DIR] [--port N] [--check CMD] [FILE ...]
    review.py reply --repo DIR ID TEXT
    review.py open --repo DIR
"""
import argparse, bisect, difflib, functools, hashlib, json, os, queue, re, subprocess, sys, threading, time, uuid, unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYCHAIN_SERVICE = "anthropic-api-credits"
MODEL = "claude-sonnet-5-5"
CONTEXT_TOOLS = "Read,Grep,Glob,Bash(grep:*),Bash(sed:*)"
EDIT_TOOLS = "Read,Grep,Glob,Edit(./**)"   # edits inside the repo only; no shell, so no commit
COMMENT_PROMPT = """A reviewer of the uncommitted text changes in this repository left a comment on {file}, near line {line}.

Selected text: {quote}
Comment: {text}

Do what the comment asks, editing the files, under the rules of this repository's CLAUDE.md files. A deletion the comment asks for is approved by the comment. Do not commit. If the comment needs a decision the files cannot settle, change nothing and ask.

Then answer in 1 to 3 sentences: the changed sentence quoted in full, or your question. Nothing else."""
MESSAGE_PROMPT = """Write the git commit message for the staged change (read it with git diff --cached), following the commit rules of this repository's CLAUDE.md files. The edits were made during a review and approved by the author. Output the message only."""
MESSAGE = re.compile(r"(feat|fix|test|docs|refactor|tools)\([^()\n]+\)\n\n[^\n]+\n\n\S[\s\S]*")
PAGE_TYPES = {"comment", "approve", "unapprove", "approve_hunk", "unapprove_hunk", "dismiss", "split"}
# A reference, label, environment or inline math is one token, so a diff never
# splits it and the page can render it.
TOKEN = re.compile(r"\\(?:cite[a-z]*|ref|eqref|autoref|cref|label|path|url|begin|end|input|includegraphics)\*?"
                   r"(?:\[[^\]]*\])*\{[^{}]*\}|\$[^$]*\$|\\[a-zA-Z]+|\\.|\s+|\w+|[^\w\s]")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def blocks(text):
    """Paragraphs as (first line, last line, text); a blank line separates them."""
    out, cur, start = [], [], 0
    for n, line in enumerate(text.split("\n"), 1):
        if line.strip():
            start = start if cur else n
            cur.append(line)
        elif cur:
            out.append((start, n - 1, "\n".join(cur)))
            cur = []
    if cur:
        out.append((start, start + len(cur) - 1, "\n".join(cur)))
    return out


def word_diff(a, b):
    """Segments [op, text], op in = - +. A short unchanged stretch between two
    changes is folded into them, so a reworded clause reads as 1 deletion and
    1 insertion instead of alternating fragments."""
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
        return len(t.strip()) <= 3 and not re.search(r"\S\s+\S", t)

    out, run, pending = [], [], ""

    def flush():
        if any(o == "-" for o, _ in run) and any(o == "+" for o, _ in run):
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


def passages(path, old, new):
    ob, nb = blocks(old), blocks(new)
    out, seen = [], {}

    def add(kind, start, end, segs, a, b):
        pid = hashlib.sha1(f"{path}\0{a}\0{b}".encode()).hexdigest()[:12]
        seen[pid] = seen.get(pid, 0) + 1
        if seen[pid] > 1:
            pid += f"-{seen[pid]}"
        out.append({"id": pid, "file": path, "start": start, "end": end, "kind": kind, "segs": segs})

    def line_at(j):
        return nb[j][0] if j < len(nb) else (nb[-1][1] + 1 if nb else 1)

    sm = difflib.SequenceMatcher(None, [x[2] for x in ob], [x[2] for x in nb], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for s, e, t in nb[j1:j2]:
                add("same", s, e, [["=", t]], t, t)
        elif op == "insert":
            for s, e, t in nb[j1:j2]:
                add("changed", s, e, [["+", t]], "", t)
        elif op == "delete":
            for _, _, t in ob[i1:i2]:
                add("changed", line_at(j1), line_at(j1), [["-", t]], t, "")
        else:
            # Diff the edited run as a whole, then cut it at the new paragraph
            # breaks: each new paragraph is a passage, a merge or split included.
            # Deleted text stays with the paragraph it follows.
            b = "\n\n".join(x[2] for x in nb[j1:j2])
            owner = []
            for k, (_, _, t) in enumerate(nb[j1:j2]):
                owner += [k] * len(t) + ([-1, -1] if k < j2 - j1 - 1 else [])
            parts = [[] for _ in range(j2 - j1)]
            pos = k = 0
            for o, t in word_diff("\n\n".join(x[2] for x in ob[i1:i2]), b):
                if o == "-":
                    parts[k].append([o, t])
                    continue
                for i, ch in enumerate(t):
                    w = owner[pos + i]
                    if w < 0:
                        continue
                    k = w
                    if parts[k] and parts[k][-1][0] == o:
                        parts[k][-1][1] += ch
                    else:
                        parts[k].append([o, ch])
                pos += len(t)
            for (s, e, _), segs in zip(nb[j1:j2], parts):
                a = "".join(t for o, t in segs if o != "+")
                n = "".join(t for o, t in segs if o != "-")
                add("changed" if any(o != "=" for o, _ in segs) else "same", s, e, segs, a, n)
    return out


@functools.lru_cache(maxsize=4096)
def matched(a, b):
    """Tokens of a found, in order, in b, and the token count of a and of b."""
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()), len(ta), len(tb)


def approved_for(cands, new):
    """The approved text that new grew from: most of it survives in new, and it
    is no stray phrase beside it. The one sharing most of new wins."""
    best, most = None, 0
    for c in cands:
        m, la, lb = matched(c, new)
        if la and m >= 0.6 * la and la >= 0.15 * lb and m > most:
            best, most = c, m
    return best


def since_approved(path, ps, approved, cuts):
    """Show a hunk changed after its approval as the change since: its segments
    become the diff from the text approved for the same base text, each change
    tagged with an index into the passage's "subs". A hunk a split line crosses
    is tagged the same way against its base text, cut there. A sub carries the
    hunk's base key (old, new), the approved text `prev`, and its own change to
    prev: `ins` in place of prev[a:b]."""
    mine = {}
    for f, o, n in approved:
        if f == path and n:
            mine.setdefault(o, []).append(n)
    for p in ps:
        if p["kind"] != "changed":
            continue
        at = cuts.get(p["id"], [])
        out, run, p["subs"], p["base"] = [], [], [], p["segs"]
        pos = 0   # in the passage's new text

        def flush():
            nonlocal pos
            old = "".join(t for o, t in run if o == "-")
            new = "".join(t for o, t in run if o == "+")
            start = pos
            prev = None if (path, old, new) in approved else approved_for(mine.get(old, ()), new)
            if prev is None and not any(start < c < start + len(new) for c in at):
                out.extend(run)
                pos += len(new)
                run.clear()
                return
            segs = run[:] if prev is None else word_diff(prev, new)
            prev = old if prev is None else prev
            ppos, cur = 0, None
            for o, t in segs:
                for piece in cut_at(o, t, pos, at):
                    if o == "=":
                        out.append([o, piece])
                        cur = None
                    else:
                        side = bisect.bisect_right(at, pos)
                        if cur is None or cur["side"] != side:
                            cur = {"old": old, "new": new, "prev": prev, "a": ppos, "b": ppos, "ins": "", "side": side}
                            p["subs"].append(cur)
                        if o == "-":
                            cur["b"] = ppos + len(piece)
                        else:
                            cur["ins"] += piece
                        out.append([o, piece, len(p["subs"]) - 1])
                    if o != "-":
                        pos += len(piece)
                    if o != "+":
                        ppos += len(piece)
            run.clear()

        for seg in p["segs"]:
            if seg[0] == "=":
                flush()
                for piece in cut_at("=", seg[1], pos, at):
                    out.append(["=", piece])
                    pos += len(piece)
            else:
                run.append(seg)
        flush()
        p["segs"] = out
        for sub in p["subs"]:
            del sub["side"]
    return ps


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


def split(path, ps, cuts):
    """Cut each passage at its split positions; a removed text there opens the
    later part. A part's id and kind depend on the passage's diff from the base
    only, so approving the part leaves them as they were."""
    out = []
    for p in ps:
        base = p.pop("base", [])
        at = cuts.get(p["id"])
        if not at:
            out.append(p)
            continue
        changed, pos = set(), 0
        for o, t in base:
            if o != "=":
                changed.update(range(bisect.bisect_right(at, pos), bisect.bisect_right(at, pos + max(len(t), 1) - 1) + 1)
                               if o == "+" else [bisect.bisect_right(at, pos)])
            if o != "-":
                pos += len(t)
        parts = [[] for _ in range(len(at) + 1)]
        pos = 0
        for seg in p["segs"]:
            parts[bisect.bisect_right(at, pos)].append(seg)
            if seg[0] != "-":
                pos += len(seg[1])
        line = p["start"]
        for i, segs in enumerate(parts):
            new = "".join(t for o, t, *_ in segs if o != "-")
            subs, index = [], {}
            for seg in segs:
                if len(seg) > 2:
                    if seg[2] not in index:
                        index[seg[2]] = len(subs)
                        subs.append(p["subs"][seg[2]])
                    seg[2] = index[seg[2]]
            q = {"id": hashlib.sha1(f"{p['id']}\0{i}\0{new}".encode()).hexdigest()[:12], "file": path,
                 "start": line, "end": line + new.rstrip("\n").count("\n"),
                 "kind": "changed" if i in changed else "same", "segs": segs, "subs": subs}
            line = q["end"] + 1
            out.append(q)
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


def staged(head, work, start, end):
    """HEAD's text with work's lines start..end (from 1) in place of the lines
    they replace. A run of changed lines crossing the range gives it a share of
    its removed lines in proportion; a removal right after the range's last
    line is the range's when a blank line or the end of the file follows. The
    blank lines that open or close a run go with any range taking from it."""
    a, b = head.splitlines(keepends=True), work.splitlines(keepends=True)
    lo, hi, out = start - 1, end, []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out += a[i1:i2]
            continue
        at = [j1 + (i - i1) * (j2 - j1) / (i2 - i1) for i in range(i1, i2)]
        mine = (lambda j: lo <= j < hi) if j2 > j1 else \
            (lambda j: lo <= j < hi or (j == hi and (hi >= len(b) or not b[hi].strip())))
        take = {j for j in range(j1, j2) if lo <= j < hi}
        if take:   # the blank lines opening or closing the run keep paragraphs apart
            for js in (range(j1, j2), range(j2 - 1, j1 - 1, -1)):
                for j in js:
                    if b[j].strip():
                        break
                    take.add(j)
        out += [a[i] for i, j in zip(range(i1, i2), at) if j < lo and not mine(j)]
        out += [b[j] for j in sorted(take)]
        out += [a[i] for i, j in zip(range(i1, i2), at) if j >= lo and not mine(j)]
    return "".join(out)


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

    def shown(self, path):
        """A file's passages as the page shows them: cut where the reviewer split
        them, a change made after approval shown as the change since."""
        approved, anchors = set(), []
        for e in self.log():
            if e.get("file") != path:
                continue
            k = (path, e.get("old"), e.get("new"))
            if e["type"] == "approve_hunk":
                approved.add(k)
            elif e["type"] == "unapprove_hunk":
                approved.discard(k)
            elif e["type"] == "split":
                anchors.append((e["line"], e["text"]))
        ps = passages(path, self.old_text(path), self.text(path))
        lines = {p["id"]: "".join(t for o, t in p["segs"] if o != "-").split("\n") for p in ps if p["kind"] == "changed"}
        cuts = {}
        for line, anchor in anchors:
            # A split opens at its line where that still reads the same, else at
            # its line number in the passage that holds that number.
            p = next((p for p in ps if p["id"] in lines and p["start"] < line <= p["end"]), None)
            hit = next(((q, lines[q["id"]].index(anchor, 1)) for q in ([p] if p else []) + ps
                        if q["id"] in lines and anchor in lines[q["id"]][1:]), None) or (p and (p, line - p["start"]))
            if hit:
                p, k = hit
                cuts.setdefault(p["id"], set()).add(sum(len(l) + 1 for l in lines[p["id"]][:k]))
        cuts = {pid: sorted(at) for pid, at in cuts.items()}
        return split(path, since_approved(path, ps, approved, cuts), cuts)

    def keys(self, path, text):
        return {(h[2], h[3]) for p in passages(path, self.old_text(path), text) if p["kind"] == "changed"
                for h in hunks(p["segs"])}

    def track(self):
        """Log the hunks each change to a reviewed file introduced, as one edit the
        page can approve in one click. Before the first look, the file is taken as
        it was at HEAD, so the uncommitted changes form the first edit."""
        with self.track_lock:
            for path in self.files:
                text = self.text(path)
                if path not in self.seen:
                    head = git(self.repo, "show", f"HEAD:{path}")
                    head_text = head.stdout if head.returncode == 0 else ""
                    self.seen[path] = (head_text, self.keys(path, head_text))
                if self.seen[path][0] == text:
                    continue
                keys = self.keys(path, text)
                new = keys - self.seen[path][1]
                if new:
                    self.append({"type": "edit", "file": path, "hunks": sorted(map(list, new))})
                self.seen[path] = (text, keys)

    def version(self):
        h = hashlib.sha1(self.base.encode())
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
        """Put one hunk's old text (base, or approved for a change since approval)
        back into the file, if the passage still reads as the page showed it."""
        path = body["file"]
        if path not in self.files:
            raise LookupError("not a reviewed file")
        p = next((p for p in self.shown(path) if p["id"] == body["passage"]), None)
        hs = hunks(p["segs"]) if p else []
        k = int(body["hunk"])
        if not p or not 0 <= k < len(hs):
            raise LookupError("the passage changed since the page loaded")
        start, end, old, new = hs[k]
        text = self.text(path)
        lines = text.split("\n")
        base = sum(len(l) + 1 for l in lines[:p["start"] - 1])
        shown = "".join(t for o, t, *_ in p["segs"] if o != "-")
        if not shown:   # a removed paragraph: put it back before the line it preceded
            text = (text[:base] + old + "\n\n" + text[base:]) if p["start"] <= len(lines) \
                else text.rstrip("\n") + "\n\n" + old + "\n"
        elif text[base:base + len(shown)] == shown:
            text = text[:base + start] + old + text[base + end:]
        else:
            raise LookupError("the passage changed since the page loaded")
        (self.repo / path).write_text(text)
        return self.append({"type": "revert", "passage": p["id"], "file": path, "line": p["start"],
                            "removed": new, "restored": old})

    def claude(self, prompt, tools):
        """Run claude -p in the repo on the Keychain API key; return its result event."""
        key = api_key()
        if not key:
            raise RuntimeError(f"No API key in the Keychain (service {KEYCHAIN_SERVICE}).")
        # A clean environment: no variable of the session that started the server,
        # and no credential that outranks the key.
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE") and k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}
        env["ANTHROPIC_API_KEY"] = key
        r = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--allowedTools", tools,
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
        return result

    def contextualize(self, body):
        result = self.claude(f"/contextualize {body['quote']}\n\n(It is in {body['file']}, near line {body['line']}.)",
                             CONTEXT_TOOLS)
        return self.append({"type": "context", "passage": body["passage"], "file": body["file"],
                            "line": body["line"], "quote": body["quote"], "text": result["result"],
                            "cost": result.get("total_cost_usd"), "model": MODEL})

    def start_worker(self):
        """Handle comments (with an API key) and passage approvals one at a time,
        so no 2 jobs touch a file at once; comments an earlier server left
        unanswered go first."""
        self.agent = api_key() is not None
        threading.Thread(target=self.work, daemon=True).start()
        if not self.agent:
            return
        log = self.log()
        answered = {e["to"] for e in log if e["type"] == "reply"}
        for e in log:
            if e["type"] == "comment" and e["id"] not in answered:
                self.queue.put(e)

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

    def commit(self, e):
        """Commit the uncommitted edits inside an approved passage, and nothing else."""
        path, at = e["file"], {"type": "commit", "passage": e["passage"], "file": e["file"], "line": e["line"]}
        p = next((p for p in self.shown(path) if p["id"] == e["passage"]), None)
        if not p:
            return self.append({**at, "error": "the passage changed after it was approved"})
        if git(self.repo, "diff", "--cached", "--quiet").returncode:
            return self.append({**at, "error": "other changes are staged; commit or unstage them first"})
        head = git(self.repo, "show", f"HEAD:{path}").stdout
        text = staged(head, self.text(path), p["start"], p["end"])
        if text == head:
            return self.append({**at, "skipped": "nothing uncommitted in the passage"})
        if self.check:
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
        r = subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-F", "-"], input=msg + "\n",
                           capture_output=True, text=True)
        if r.returncode:
            git(self.repo, "reset", "-q", "--", path)
            return self.append({**at, "error": "git commit: " + (r.stderr or r.stdout)[-400:]})
        sha = git(self.repo, "rev-parse", "--short", "HEAD").stdout.strip()
        return self.append({**at, "sha": sha, "message": msg, "cost": cost, "model": MODEL if cost else None})

    def answer(self, c):
        before = self.version()
        try:
            r = self.claude(COMMENT_PROMPT.format(file=c["file"], line=c["line"], text=c["text"],
                                                  quote=c.get("quote") or "(none: the whole passage)"), EDIT_TOOLS)
            text, cost = r["result"], r.get("total_cost_usd")
        except Exception as e:
            text, cost = f"Failed: {e}", None
        # edited: whether a reviewed file changed; the page keeps showing the
        # comment when it did not (a question, a refusal, a failure).
        self.track()
        self.append({"type": "reply", "to": c["id"], "text": text, "edited": self.version() != before,
                     "cost": cost, "model": MODEL})


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
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

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
                return self.send(200, {"repo": str(review.repo), "base": review.base, "model": MODEL,
                                       "has_key": api_key() is not None, "service": KEYCHAIN_SERVICE,
                                       "worker": review.agent})
            if self.path == "/api/refs":
                return self.send(200, refs(review.repo))
            if self.path == "/api/doc":
                return self.send(200, review.doc())
            if self.path == "/api/state":
                return self.send(200, {"version": review.version(), "log": len(review.log())})
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
                    keep = {k: body[k] for k in ("type", "passage", "file", "line", "quote", "text", "old", "new", "to") if k in body}
                    e = review.append(keep)
                    review.enqueue(e)
                    return self.send(200, e)
                if self.path == "/api/revert":
                    try:
                        return self.send(200, review.revert(body))
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
