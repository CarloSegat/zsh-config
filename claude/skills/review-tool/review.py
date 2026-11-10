#!/usr/bin/env python3
"""Local review page for text changes since a git ref (see SKILL.md).

    review.py serve --base REF [--repo DIR] [--port N] [--check CMD] [FILE ...]
    review.py reply --repo DIR ID TEXT
    review.py open --repo DIR
"""
import argparse, difflib, hashlib, json, os, queue, re, subprocess, sys, threading, time, uuid
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
PAGE_TYPES = {"comment", "approve", "unapprove", "approve_hunk", "unapprove_hunk", "dismiss"}
TOKEN = re.compile(r"\s+|\w+|[^\w\s]")


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


def hunks(segs):
    """Each run of changed segments as (start, end, old, new), positions in the
    passage's new text. The page numbers hunks the same way."""
    out, pos, cur = [], 0, None
    for o, t in segs:
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


class Review:
    def __init__(self, repo, base, files, check=None):
        self.repo, self.base, self.files, self.check = repo, base, files, check
        self.dir = repo / ".review"
        self.dir.mkdir(exist_ok=True)
        (self.dir / ".gitignore").write_text("*\n")
        self.log_path = self.dir / "log.jsonl"
        self.log_path.touch()
        self.lock = threading.Lock()
        self.queue = queue.Queue()   # comments and approvals, handled one at a time
        self.agent = False           # comments go to claude -p (there is an API key)

    def text(self, path):
        f = self.repo / path
        return f.read_text(errors="replace") if f.exists() else ""

    def old_text(self, path):
        r = git(self.repo, "show", f"{self.base}:{path}")
        return r.stdout if r.returncode == 0 else ""

    def doc(self):
        return {"files": [{"path": p, "passages": passages(p, self.old_text(p), self.text(p))} for p in self.files]}

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
        """Put one hunk's old text back into the file, if the passage still reads
        as the page showed it."""
        path = body["file"]
        if path not in self.files:
            raise LookupError("not a reviewed file")
        p = next((p for p in passages(path, self.old_text(path), self.text(path)) if p["id"] == body["passage"]), None)
        hs = hunks(p["segs"]) if p else []
        k = int(body["hunk"])
        if not p or not 0 <= k < len(hs):
            raise LookupError("the passage changed since the page loaded")
        start, end, old, new = hs[k]
        text = self.text(path)
        lines = text.split("\n")
        base = sum(len(l) + 1 for l in lines[:p["start"] - 1])
        shown = "".join(t for o, t in p["segs"] if o != "-")
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
        p = next((p for p in passages(path, self.old_text(path), self.text(path)) if p["id"] == e["passage"]), None)
        if not p:
            return self.append({**at, "error": "the passage changed after it was approved"})
        if git(self.repo, "diff", "--cached", "--quiet").returncode:
            return self.append({**at, "error": "other changes are staged; commit or unstage them first"})
        diff = git(self.repo, "diff", "-U0", "HEAD", "--", path).stdout
        head, *hs = re.split(r"(?m)^(?=@@ )", diff) if diff else [""]
        keep = []
        for h in hs:
            c, d = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", h).groups()
            c, d = int(c), 1 if d is None else int(d)
            if (c <= p["end"] and c + d - 1 >= p["start"]) if d else p["start"] - 1 <= c <= p["end"]:
                keep.append(h)
        if not keep:
            return self.append({**at, "skipped": "nothing uncommitted in the passage"})
        if self.check:
            r = subprocess.run(self.check, shell=True, cwd=self.repo, capture_output=True, text=True, timeout=900)
            if r.returncode:
                return self.append({**at, "error": f"check failed: {self.check}\n{(r.stdout + r.stderr)[-400:]}"})
        r = subprocess.run(["git", "-C", str(self.repo), "apply", "--cached", "--unidiff-zero", "-"],
                           input=head + "".join(keep), capture_output=True, text=True)
        if r.returncode:
            return self.append({**at, "error": "git apply: " + r.stderr[-400:]})
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
        self.append({"type": "reply", "to": c["id"], "text": text, "edited": self.version() != before,
                     "cost": cost, "model": MODEL})


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
