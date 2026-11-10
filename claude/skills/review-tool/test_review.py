"""Tests for review.py: python3 -m unittest test_review (from this directory)."""
import io, json, random, shutil, socket, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review

review.api_key = lambda: None   # no Keychain, no claude -p


def sh(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout


def newtext(p):
    return "".join(s[1] for s in p["segs"] if s[0] != "-")


def page_split(p):
    """The line page.html's Split in half picks: (line, text)."""
    text = newtext(p)
    lines, half, best, at = text.split("\n"), len(text) / 2, 0, 0
    for k, l in enumerate(lines):
        if k and l.strip() and (not best or abs(at - half) < abs(best[1] - half)):
            best = [k, at]
        at += len(l) + 1
    return p["start"] + best[0], lines[best[0]]


class Case(unittest.TestCase):
    def make(self, base, work, head=None, path="f.tex"):
        """A repo whose tag base holds base, HEAD head (default base), the work tree work."""
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, True)
        sh(repo, "init", "-q")
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            sh(repo, "config", k, v)
        (repo / path).write_text(base)
        sh(repo, "add", path)
        sh(repo, "commit", "-qm", "base")
        sh(repo, "tag", "base")
        if head is not None and head != base:
            (repo / path).write_text(head)
            sh(repo, "commit", "-qam", "head")
        (repo / path).write_text(work)
        return review.Review(repo, "base", [path])

    def changed(self, rv, path="f.tex"):
        return [p for p in rv.shown(path) if p["kind"] == "changed"]

    def approve(self, rv, p):
        return rv.commit(rv.append({"type": "approve", "passage": p["id"], "file": p["file"], "line": p["start"]}))

    def head(self, rv, path="f.tex"):
        return sh(rv.repo, "show", f"HEAD:{path}")

    def revert(self, rv, p, k=0):
        rv.revert({"file": p["file"], "passage": p["id"], "hunk": k})
        return rv.text(p["file"])


class ParagraphEdges(Case):
    """Bugs 1 and 2: changes at a paragraph break stay with their paragraph."""

    def test_revert_reworded_second_paragraph(self):
        base, work = "Old first.\n\nOld second.\n", "New first.\n\nNew second.\n"
        p1, p2 = self.changed(self.make(base, work))
        self.assertEqual([s[:2] for s in p2["segs"]], [["-", "Old"], ["+", "New"], ["=", " second."]])
        rv = self.make(base, work)
        self.assertEqual(self.revert(rv, self.changed(rv)[1]), "New first.\n\nOld second.\n")
        rv = self.make(base, work)
        self.approve(rv, self.changed(rv)[1])
        self.assertEqual(self.head(rv), "Old first.\n\nNew second.\n")

    def test_revert_across_paragraph_break(self):
        base, work = "Members vote.\n\nThe key rotates.\n", "Members decide.\n\nA key rotates.\n"
        rv = self.make(base, work)
        self.assertEqual(self.revert(rv, self.changed(rv)[0]), "Members vote.\n\nA key rotates.\n")
        rv = self.make(base, work)
        self.assertEqual(self.revert(rv, self.changed(rv)[1]), "Members decide.\n\nThe key rotates.\n")
        rv = self.make(base, work)
        self.approve(rv, self.changed(rv)[0])
        self.assertEqual(self.head(rv), "Members decide.\n\nThe key rotates.\n")

    def test_added_paragraph_break_reverts_and_commits(self):
        base, work = "First sentence.\nSecond sentence.\n", "First sentence.\n\nSecond sentence.\n"
        rv = self.make(base, work)
        (p,) = self.changed(rv)
        self.assertEqual(self.revert(rv, p), base)
        self.assertEqual(self.changed(rv), [])
        rv = self.make(base, work)
        self.assertIn("sha", self.approve(rv, self.changed(rv)[0]))
        self.assertEqual(self.head(rv), work)


class Commits(Case):
    """Bug 3: approving a passage commits exactly the changes it shows."""

    def test_commit_moved_lines(self):
        base = "Intro sentence.\nMoved sentence one.\nMoved sentence two.\n\nSecond paragraph.\n"
        work = "Intro sentence.\nNew closing sentence.\n\nSecond paragraph.\nMoved sentence one.\nMoved sentence two.\n"
        rv = self.make(base, work)
        self.approve(rv, self.changed(rv)[1])
        self.assertEqual(self.head(rv), "Intro sentence.\nMoved sentence one.\nMoved sentence two.\n\n"
                                        "Second paragraph.\nMoved sentence one.\nMoved sentence two.\n")
        rv = self.make(base, work)
        self.approve(rv, self.changed(rv)[0])
        self.assertEqual(self.head(rv), "Intro sentence.\nNew closing sentence.\n\nSecond paragraph.\n")

    def test_commit_duplicate_lines(self):
        head = "P1\na\na\n\nP2\n"
        rv = self.make(head, "P1\n\nP2\na\na\n")
        self.approve(rv, self.changed(rv)[0])
        self.assertEqual(self.head(rv), "P1\n\nP2\n")
        rv = self.make(head, "P1\n\nP2\na\na\n")
        self.approve(rv, self.changed(rv)[1])
        self.assertEqual(self.head(rv), "P1\na\na\n\nP2\na\na\n")
        rv = self.make(head, "P1\nb\n\nP2\na\na\n")
        self.approve(rv, self.changed(rv)[1])
        self.assertEqual(self.head(rv), "P1\na\na\n\nP2\na\na\n")

    def test_split_half_commits_what_it_shows(self):
        rv = self.make("Alpha.\nBravo.\nCharlie.\nDelta.\nEcho.\n", "Alpha.\nCharlie.\nEcho.\nFoxtrot.\n")
        (p,) = self.changed(rv)
        rv.append({"type": "split", "passage": p["id"], "file": "f.tex", "line": 2, "text": "Charlie."})
        a, b = rv.shown("f.tex")
        self.assertEqual([s[:2] for s in a["segs"]], [["=", "Alpha"], ["-", ".\nBravo"], ["=", ".\n"]])
        self.assertIn("sha", self.approve(rv, a))
        self.assertEqual(self.head(rv), "Alpha.\nCharlie.\nDelta.\nEcho.\n")
        self.assertIn("sha", self.approve(rv, b))
        self.assertEqual(self.head(rv), "Alpha.\nCharlie.\nEcho.\nFoxtrot.\n")

    def test_commit_paragraph_after_unterminated_last_line(self):
        rv = self.make("First paragraph.", "First paragraph.\n\nNew paragraph.\n")
        self.approve(rv, self.changed(rv)[0])
        self.assertEqual(self.head(rv), "First paragraph.\n\nNew paragraph.\n")
        rv = self.make("Alpha one.\n\nBeta two.", "Alpha one, edited.\n\nBeta two.\n")
        self.approve(rv, self.changed(rv)[0])
        self.assertEqual(self.head(rv), "Alpha one, edited.\n\nBeta two.")

    def test_commit_one_of_consecutive_deleted_paragraphs(self):
        base = "Keep A.\n\nDrop B.\n\nDrop C.\n\nKeep D.\n"
        rv = self.make(base, "Keep A.\n\nKeep D.\n")
        b, c = self.changed(rv)
        self.assertNotEqual(b["id"], c["id"])
        self.approve(rv, b)
        self.assertEqual(self.head(rv), "Keep A.\n\nDrop C.\n\nKeep D.\n")
        self.approve(rv, c)
        self.assertEqual(self.head(rv), "Keep A.\n\nKeep D.\n")


class Splits(Case):
    """Bug 4: a split stays where the reviewer made it, and parts keep their ids."""

    def test_split_at_duplicate_line(self):
        rows = ["Governance group & members \\\\", "Proposal & votes \\\\", "Revocation & key \\\\", "Quorum & 2 \\\\"]
        base = "\\begin{tabular}{ll}\n\\hline\n" + "\n\\hline\n".join(rows) + "\n\\hline\n\\end{tabular}\n"
        rv = self.make(base, base.replace("votes", "Votes").replace("& 2", "& 3"))
        (p,) = self.changed(rv)
        line, text = page_split(p)
        self.assertEqual((line, text), (6, "\\hline"))
        rv.append({"type": "split", "passage": p["id"], "file": "f.tex", "line": line, "text": text})
        self.assertEqual([(q["start"], q["end"]) for q in rv.shown("f.tex")], [(1, 5), (6, 11)])

    def test_split_stays_with_its_passage(self):
        y = "\\begin{tabular}{ll}\nGovernance group & members \\\\\n\\hline\nProposal & votes \\\\\n\\end{tabular}"
        x = "\\begin{tabular}{ll}\nRevocation & key \\\\\n\\hline\nQuorum & 2 \\\\\n\\end{tabular}"
        rv = self.make(y + "\n\nSome text.\n\n" + x + "\n",
                       y.replace("votes", "ballots") + "\n\nSome text.\n\n" + x.replace("& 2", "& 3") + "\n")
        xp = self.changed(rv)[1]
        rv.append({"type": "split", "passage": xp["id"], "file": "f.tex", "line": 11, "text": "\\hline"})
        self.assertEqual([(q["start"], q["end"]) for q in self.changed(rv)], [(1, 5), (11, 13)])
        self.revert(rv, self.changed(rv)[1])
        self.assertEqual([(q["start"], q["end"]) for q in self.changed(rv)], [(1, 5)])

    def test_part_id_depends_on_its_own_text(self):
        lines = [f"Sentence {i} of the paragraph." for i in range(1, 9)]
        base = "\n".join(lines) + "\n"
        work = base.replace("of the", "in the")
        rv = self.make(base, work)
        (p,) = rv.shown("f.tex")
        rv.append({"type": "split", "passage": p["id"], "file": "f.tex", "line": 5, "text": lines[4].replace("of", "in")})
        a, b = rv.shown("f.tex")
        rv.append({"type": "split", "passage": a["id"], "file": "f.tex", "line": 3, "text": lines[2].replace("of", "in")})
        self.assertEqual([(q["start"], q["id"]) for q in rv.shown("f.tex")][-1], (5, b["id"]))
        e = rv.append({"type": "approve", "passage": b["id"], "file": "f.tex", "line": 5})
        (rv.repo / "f.tex").write_text(work.replace("Sentence 1 in", "Sentence one in"))   # an edit in the first half
        self.assertEqual(rv.shown("f.tex")[-1]["id"], b["id"])
        self.assertIn("sha", rv.commit(e))
        self.assertEqual(self.head(rv), "\n".join(lines[:4] + [l.replace("of", "in") for l in lines[4:]]) + "\n")


class Reverts(Case):
    """Bug 5."""

    def test_revert_deleted_last_paragraph(self):
        base = "First paragraph.\n\nLast paragraph.\n"
        rv = self.make(base, "First paragraph.\n")
        self.assertEqual(self.revert(rv, self.changed(rv)[0]), base)

    def test_revert_committed_hunk_leaves_a_card(self):
        base, head = "Alpha one.\n\nBeta two.\n", "Alpha ONE.\n\nBeta two.\n"
        rv = self.make(base, head, head=head)
        self.assertEqual(self.revert(rv, self.changed(rv)[0]), base)
        (p,) = self.changed(rv)
        self.assertEqual([s[:2] for s in p["segs"]], [["=", "Alpha "], ["-", "ONE"], ["+", "one"], ["=", "."]])
        self.assertIn("sha", self.approve(rv, p))
        self.assertEqual(self.head(rv), base)


class Concurrency(Case):
    """Bug 6."""

    def test_concurrent_reverts(self):
        base = "Alpha one.\n\nBeta two.\n"
        rv = self.make(base, "Alpha ONE.\n\nBeta TWO.\n")
        ps = self.changed(rv)
        read = rv.text
        rv.text = lambda path: (read(path), time.sleep(0.2))[0]
        ts = [threading.Thread(target=rv.revert, args=({"file": "f.tex", "passage": p["id"], "hunk": 0},)) for p in ps]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(read("f.tex"), base)

    def test_commit_after_terminal_commit_during_check(self):
        work = "Alpha ONE.\n\nBeta TWO.\n"
        rv = self.make("Alpha one.\n\nBeta two.\n", work)
        rv.check = "git commit -qam terminal"   # the main session commits while the build runs
        e = self.approve(rv, self.changed(rv)[0])
        self.assertEqual(e.get("skipped"), "nothing uncommitted in the passage")
        self.assertEqual(self.head(rv), work)
        self.assertEqual(sh(rv.repo, "log", "-1", "--format=%s").strip(), "terminal")

    def test_commit_refused_when_head_moves_while_writing_message(self):
        work = "Alpha ONE.\n\nBeta TWO.\n"
        rv = self.make("Alpha one.\n\nBeta two.\n", work)
        rv.agent = True

        def claude(prompt, tools, model=review.MODEL):
            sh(rv.repo, "commit", "-qam", "terminal")
            return {"result": "docs(x)\n\nTitle\n\nBody"}
        rv.claude = claude
        e = self.approve(rv, self.changed(rv)[0])
        self.assertIn("HEAD moved", e.get("error", ""))
        self.assertEqual(self.head(rv), work)
        self.assertEqual(sh(rv.repo, "log", "-1", "--format=%s").strip(), "terminal")
        self.assertEqual(sh(rv.repo, "status", "--porcelain"), "")


class Worker(Case):
    def test_restart_commits_queued_approval(self):
        rv = self.make("Alpha one.\n", "Alpha ONE.\n")
        (p,) = self.changed(rv)
        rv.append({"type": "approve", "passage": p["id"], "file": "f.tex", "line": 1})   # server stopped here
        again = review.Review(rv.repo, "base", ["f.tex"])
        again.start_worker()
        for _ in range(100):
            if any(e["type"] == "commit" for e in again.log()):
                break
            time.sleep(0.05)
        self.assertEqual([e.get("sha") is not None for e in again.log() if e["type"] == "commit"], [True])
        self.assertEqual(self.head(rv), "Alpha ONE.\n")

    def run_answer(self, rv, events, during):
        """answer() with claude -p printing events while during() runs."""
        real = review.subprocess.run

        def run(cmd, *a, **kw):
            if cmd[0] != "claude":
                return real(cmd, *a, **kw)
            during()
            out = [{"type": "system", "subtype": "init", "apiKeySource": "ANTHROPIC_API_KEY"}, *events,
                   {"type": "result", "subtype": "success", "is_error": False, "result": "Done.", "total_cost_usd": 0.01}]
            return subprocess.CompletedProcess(cmd, 0, "\n".join(map(json.dumps, out)), "")
        review.subprocess.run, key = run, review.api_key
        review.api_key = lambda: "k"
        try:
            c = rv.append({"type": "comment", "passage": "x", "file": "f.tex", "line": 1, "text": "?", "quote": ""})
            rv.answer(c)
        finally:
            review.subprocess.run, review.api_key = real, key
        return [e for e in rv.log() if e["type"] == "reply"][-1]["edited"]

    def test_answer_edited_only_by_its_own_edit(self):
        rv = self.make("Alpha one.\n\nBeta two.\n", "Alpha ONE.\n\nBeta TWO.\n")
        p2 = self.changed(rv)[1]
        revert = lambda: rv.revert({"file": "f.tex", "passage": p2["id"], "hunk": 0})
        self.assertIs(self.run_answer(rv, [], revert), False)
        path = str(rv.repo / "f.tex")
        edit = [{"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": path}}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}]
        self.assertIs(self.run_answer(rv, edit, lambda: (rv.repo / "f.tex").write_text("Alpha 1.\n")), True)
        failed = [edit[0], {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "no match", "is_error": True}]}}]
        self.assertIs(self.run_answer(rv, failed, lambda: None), False)


class Server(Case):
    def request(self, rv, close):
        """GET /api/state on a socket pair; close: the page drops the request first."""
        srv, page = socket.socketpair()
        page.sendall(b"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n\r\n")
        page.shutdown(socket.SHUT_WR)
        if close:
            page.close()
        err, sys.stderr = sys.stderr, io.StringIO()
        try:
            review.handler(rv, 8765)(srv, ("127.0.0.1", 1), None)
            logged = sys.stderr.getvalue()
        finally:
            sys.stderr = err
            srv.close()
        reply = b"" if close else page.recv(65536)
        if not close:
            page.close()
        return reply.split(b"\r\n")[0], logged

    def test_aborted_request(self):
        rv = self.make("a\n", "b\n")
        self.assertEqual(self.request(rv, close=False), (b"HTTP/1.0 200 OK", ""))
        self.assertEqual(self.request(rv, close=True), (b"", ""))


# Random small paragraph edits for the 2 commit invariants of bug 3.
WORDS = ["the", "a", "group", "vote", "is", "not", "\\cite{x}", "$n$", ",", ".", "member", "%c", "\\emph{y}"]


def para(rng):
    return "\n".join(" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 5))) for _ in range(rng.randint(1, 3)))


def mutate(rng, text):
    toks = text.split(" ")
    for _ in range(rng.randint(1, 3)):
        r, i = rng.random(), rng.randrange(len(toks) + 1)
        if r < 0.3 and len(toks) > 1:
            del toks[min(i, len(toks) - 1)]
        elif r < 0.6:
            toks.insert(i, rng.choice(WORDS))
        elif r < 0.75:
            toks.insert(i, rng.choice(WORDS) + "\n" + rng.choice(WORDS))
        elif r < 0.85:
            toks.insert(i, rng.choice(WORDS) + "\n\n" + rng.choice(WORDS))
        else:
            toks[min(i, len(toks) - 1)] = rng.choice(WORDS)
    return " ".join(toks)


def edit(rng):
    """(base, work, splits): random paragraphs, some edited, deleted or added, and splits the page could log."""
    base = [para(rng) for _ in range(rng.randint(1, 4))]
    work = []
    for p in base:
        r = rng.random()
        if r < 0.1:
            continue
        if r < 0.2:
            work.append(para(rng))
        work.append(mutate(rng, p) if rng.random() < 0.7 else p)
    if rng.random() < 0.2:
        work.append(para(rng))
    base, work = "\n\n".join(base) + "\n", "\n\n".join(work) + "\n"
    splits = []
    for p in review.passages("f.tex", base, work):
        if p["kind"] == "changed" and newtext(p).strip().count("\n") and rng.random() < 0.5:
            line, text = page_split(p)
            splits.append({"type": "split", "passage": p["id"], "file": "f.tex", "line": line, "text": text})
    return base, work, splits


def unique_edit(rng):
    """(head, work): paragraphs of unique lines, edited, deleted, added, split or merged."""
    n = iter(range(10 ** 6))
    u = lambda: f"L{next(n)}"
    hp = [[u() for _ in range(rng.randint(1, 3))] for _ in range(rng.randint(1, 4))]
    wp, i = [], 0
    while i < len(hp):
        r, p = rng.random(), list(hp[i])
        if r < .15:
            i += 1
            continue
        if r < .3:
            wp.append([u() for _ in range(rng.randint(1, 2))])
        if r < .45 and len(p) > 1:
            k = rng.randrange(1, len(p))
            wp += [p[:k], p[k:]]
            i += 1
            continue
        if r < .55 and i + 1 < len(hp):
            wp.append(p + hp[i + 1])
            i += 2
            continue
        if r < .8:
            for _ in range(rng.randint(1, 2)):
                rr, j = rng.random(), rng.randrange(len(p) + 1)
                if rr < .33 and len(p) > 1:
                    del p[min(j, len(p) - 1)]
                elif rr < .66:
                    p.insert(j, u())
                else:
                    p[min(j, len(p) - 1)] = u()
        wp.append(p)
        i += 1
    return "\n\n".join("\n".join(p) for p in hp) + "\n", "\n\n".join("\n".join(p) for p in wp) + "\n"


def commit(head, work, base, splits, pid):
    """What approving passage pid commits on head (review.Review.commit without git)."""
    shown, ours = review.view("f.tex", base, head, work, splits)
    t = next(p for p in shown if p["id"] == pid)
    return review.staged(head, [u for u in ours if u["kind"] == "changed" and u["key"] == t["key"]])


class Invariants(unittest.TestCase):
    def test_commit_applies_exactly_what_the_passage_shows(self):
        """Approving a passage with HEAD at the base gives the work text with
        every other passage's hunks reverted the way the page reverts them."""
        rng = random.Random(1)
        for _ in range(400):
            base, work, splits = edit(rng)
            shown, _ = review.view("f.tex", base, base, work, splits)
            changed = [p for p in shown if p["kind"] == "changed"]
            for t in changed:
                want = work
                for q in reversed(changed):
                    if q is not t:
                        for s, e, old, new in reversed(review.hunks(q["segs"])):
                            want = want[:q["at"] + s] + old + want[q["at"] + e:]
                self.assertEqual(commit(base, work, base, splits, t["id"]), want, (base, work, splits, t["id"]))

    def test_committing_every_passage_in_any_order_gives_the_work_text(self):
        rng = random.Random(2)
        for _ in range(400):
            base, work, splits = edit(rng) if rng.random() < .5 else unique_edit(rng) + ([],)
            head, done = base, set()
            for _ in range(50):
                todo = [p["id"] for p in review.view("f.tex", base, head, work, splits)[0]
                        if p["kind"] == "changed" and p["id"] not in done]
                if not todo:
                    break
                pid = rng.choice(todo)
                head = commit(head, work, base, splits, pid)
                done.add(pid)
            self.assertEqual(head, work, (base, work, splits))

    def test_commit_keeps_lines_outside_the_passage(self):
        """Unique lines: a passage's commit adds the new lines it shows and no
        other, removes the lines it shows removed and no other, and leaves no
        empty paragraph."""
        rng = random.Random(3)
        for _ in range(400):
            head, work = unique_edit(rng)
            hl = set(head.split("\n")) - {""}
            for p in review.passages("f.tex", head, work):
                if p["kind"] != "changed":
                    continue
                got = commit(head, work, head, [], p["id"])
                gl = set(got.split("\n")) - {""}
                new = set(newtext(p).split("\n")) - {""}
                gone = set("".join(s[1] for s in p["segs"] if s[0] != "+").split("\n")) - new - {""}
                ctx = (head, work, p["segs"], got)
                self.assertEqual(gl - hl, new - hl, ctx)
                self.assertEqual(hl - gl, gone, ctx)
                self.assertNotIn("\n\n\n", got, ctx)
                self.assertFalse(got.startswith("\n"), ctx)


if __name__ == "__main__":
    unittest.main()
