#!/usr/bin/env python3
"""Browser checks of page.html. Each test serves copies of review.py and page.html
on a throwaway git repo and drives the page in headless Chrome over CDP.

    python3 test_page.py [-k PATTERN]

Skips when Chrome or the websockets package is missing."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path

try:
    from websockets.sync.client import connect
except ImportError:
    connect = None

HERE = Path(__file__).resolve().parent
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
BASE = "\\section{Intro}\n\nAlpha paragraph stays the same here.\n\nOmega paragraph also stays.\n"
PARA = """Membership changes go through the governance group vote and take effect at once.
A member that leaves loses its rights immediately after the vote closes.
Revocation proper removes a credential from the registry for every verifier.
It applies to credentials that the group itself issued in the past.
By design the registry keeps a record of every revoked credential forever.
Verifiers read that record before accepting any credential at all."""
WORK = BASE.replace("Omega", PARA + "\n\nOmega")   # 1 inserted paragraph: 1 passage of 1 hunk
# 3 changed paragraphs: passages at lines 7, 9 and 11
BASE3 = BASE + "\nRevoked credentials are stored.\n\nEvery verifier checks them.\n\nThe end is near.\n"
WORK3 = BASE3.replace("are stored.", "are stored in the registry.").replace("checks them.", "checks them twice.") \
    .replace("is near.", "is here.")
# The page's first fetch matching `match` (JS on u, o) waits for window.__go(); window.__held once it waits.
HOLD = """(() => { const f = window.fetch; let once = true; window.fetch = async (u, o) => {
  const res = await f(u, o);
  if (once && (%s)) { once = false; window.__held = true; await new Promise(go => window.__go = go); }
  return res; }; })()"""
POSTED = "u === '/api/log' && o?.method === 'POST' && JSON.parse(o.body).type === '%s'"
CMDS = "[...document.querySelectorAll('.composer')].map(b => [b.closest('.card').passage.start, b.meta.line, $('textarea', b).value])"
CDP = TMP = chrome = None


def until(f, timeout=8):
    """f's first truthy value within timeout, else its last value."""
    end = time.time() + timeout
    while True:
        v = f()
        if v or time.time() > end:
            return v
        time.sleep(0.1)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def up(url):
    try:
        return urllib.request.urlopen(url).read()
    except OSError:
        return None


def setUpModule():
    global CDP, TMP, chrome
    if connect is None or not Path(CHROME).exists():
        raise unittest.SkipTest("needs Google Chrome and the websockets package")
    TMP = Path(tempfile.mkdtemp(prefix="review-page-"))
    # No API key: no claude -p, comments wait, commits take the fixed message.
    (TMP / "bin").mkdir()
    for name, code in (("security", 44), ("claude", 1)):
        (TMP / "bin" / name).write_text(f"#!/bin/sh\nexit {code}\n")
        (TMP / "bin" / name).chmod(0o755)
    CDP = free_port()
    chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={CDP}", f"--user-data-dir={TMP / 'chrome'}",
                               "--no-first-run", "--window-size=1400,1000", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not until(lambda: up(f"http://127.0.0.1:{CDP}/json/version"), 15):
        raise RuntimeError("Chrome did not start")


def tearDownModule():
    chrome.terminate()
    chrome.wait(10)
    shutil.rmtree(TMP, ignore_errors=True)


class Page:
    def __init__(self, url):
        req = urllib.request.Request(f"http://127.0.0.1:{CDP}/json/new?about:blank", method="PUT")
        t = json.loads(urllib.request.urlopen(req).read())
        self.tid, self.ws, self.n = t["id"], connect(t["webSocketDebuggerUrl"], max_size=2**26), 0
        self.cmd("Runtime.enable")
        self.cmd("Network.enable")
        self.cmd("Network.setBlockedURLs", urls=["*cdnjs.cloudflare.com*"])   # no KaTeX: offline and fast
        self.cmd("Page.navigate", url=url)
        until(lambda: self.js("typeof doc !== 'undefined' && !!doc", quiet=True))

    def cmd(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv(60))
            if m.get("method") == "Runtime.exceptionThrown":
                print("page exception:", m["params"]["exceptionDetails"].get("exception", {}).get("description"))
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]

    def js(self, expr, quiet=False):
        """expr's value, awaited; quiet: None while the page is (re)loading."""
        try:
            r = self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        except RuntimeError:
            if quiet:
                return None
            raise
        if "exceptionDetails" in r:
            if quiet:
                return None
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description"))
        return r["result"].get("value")

    def key(self, k, mods=0, repeat=False):
        d = dict(type="keyDown", key=k, modifiers=mods, autoRepeat=repeat)
        d.update(text=k, code=f"Key{k.upper()}", windowsVirtualKeyCode=ord(k.upper()))
        self.cmd("Input.dispatchKeyEvent", **d)
        d.pop("text")
        self.cmd("Input.dispatchKeyEvent", **{**d, "type": "keyUp"})

    def type(self, text):
        for k in text:
            self.key(k)

    def close(self):
        self.ws.close()
        up(urllib.request.Request(f"http://127.0.0.1:{CDP}/json/close/{self.tid}", method="PUT"))


class PageTest(unittest.TestCase):
    def start(self, base=BASE, work=WORK, check=None):
        d = Path(tempfile.mkdtemp(dir=TMP))
        self.repo, tool = d / "repo", d / "tool"
        tool.mkdir()
        for f in ("review.py", "page.html"):
            shutil.copy(HERE / f, tool)
        self.page_html = tool / "page.html"
        self.repo.mkdir()
        for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                  ["config", "commit.gpgsign", "false"]):
            self.git(*c)
        self.write(base)
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.git("tag", "base")
        self.write(work)
        env = {**os.environ, "PATH": f"{TMP / 'bin'}:{os.environ['PATH']}"}
        self.srv = subprocess.Popen([sys.executable, str(tool / "review.py"), "serve", "--base", "base", "--port", str(free_port()),
                                     *(["--check", check] if check else []), "doc.tex"],
                                    cwd=self.repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(self.stop, self.srv)
        self.url = self.srv.stdout.readline().split()[0]
        self.p = Page(self.url)
        self.addCleanup(self.p.close)
        return self.p

    def stop(self, srv):
        srv.terminate()
        srv.wait(10)

    def git(self, *a):
        return subprocess.run(["git", *a], cwd=self.repo, capture_output=True, text=True, check=True).stdout

    def write(self, text):
        (self.repo / "doc.tex").write_text(text)

    def log(self):
        return [json.loads(l) for l in (self.repo / ".review/log.jsonl").read_text().splitlines() if l.strip()]

    def append(self, entry):
        with open(self.repo / ".review/log.jsonl", "a") as f:
            f.write(json.dumps({"ts": "2026-11-10 10:00:00", **entry}) + "\n")

    def post(self, body):
        req = urllib.request.Request(self.url + "/api/log", data=json.dumps(body).encode(),
                                     headers={"X-Review": "1", "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    def types(self, n):
        return [e["type"] for e in self.log()[n:]]

    def committed(self, n):
        return until(lambda: "commit" in self.types(n) and self.types(n))

    def click(self, k, act="approve"):
        self.p.js(f"document.querySelectorAll('.card')[{k}].querySelector('[data-act={act}]').click()")

    def menu(self, k, h, act):
        self.p.js(f"document.querySelectorAll('.card')[{k}].querySelectorAll('.hunk')[{h}].click()")
        self.p.js(f"document.querySelector('#hmenu [data-h={act}]').click()")

    def buttons(self):
        return self.p.js("[...document.querySelectorAll('.card [data-act=approve]')].map(b => b.textContent)")

    def first_line(self):
        return self.p.js("newText(changed.find(p => newText(p).startsWith('Membership'))).split('\\n')[0]")

    # Bug 1: a passage approved hunk by hunk commits; its button never wipes approvals in 1 action.

    def test_hunk_by_hunk_approval_commits(self):
        p = self.start("\\section{Intro}\n\nThe quick brown fox jumps over the lazy dog near the river bank.\n",
                       "\\section{Intro}\n\nThe slow brown fox jumps over the lazy dog near the river shore.\n")
        self.assertEqual(p.js("changed[0].hs.length"), 2)
        n = len(self.log())
        self.menu(0, 0, "approve")
        time.sleep(1)
        self.assertEqual(self.types(n), ["approve_hunk"])
        self.assertEqual(self.buttons(), ["Approve"])
        self.menu(0, 1, "approve")
        self.assertEqual(self.committed(n), ["approve_hunk", "approve_hunk", "approve", "commit"])
        self.assertEqual(until(lambda: self.buttons()[0].startswith("Committed ")), True)

    def test_split_part_approved_from_its_menu_commits(self):
        p = self.start()
        self.click(0, "split")
        until(lambda: p.js("changed.length") == 2)
        n = len(self.log())
        self.menu(1, 0, "approve")
        self.assertEqual(self.committed(n), ["approve_hunk", "approve", "commit"])
        self.assertEqual(until(lambda: self.buttons()[1].startswith("Committed ")), True)

    def test_green_passage_without_approve_commits(self):
        p = self.start()
        for old, new in p.js("changed[0].hs.map(h => [h.old, h.neu])"):
            self.post({"type": "approve_hunk", "passage": p.js("changed[0].id"), "file": "doc.tex", "line": 5, "old": old, "new": new})
        p.js("loadDoc(true)")
        self.assertEqual(self.buttons(), ["Commit"])
        n = len(self.log())
        self.click(0)
        self.assertEqual(self.committed(n), ["approve", "commit"])

    def test_withdrawing_asks_first(self):
        p = self.start()
        self.click(0)
        self.committed(0)
        until(lambda: self.buttons()[0].startswith("Committed "))
        p.js("window.confirm = m => (window.__asked = m, window.__yes)")
        n = len(self.log())
        p.key("j")
        p.key("a")                       # the shortcut never withdraws
        time.sleep(1)
        self.assertEqual(self.types(n), [])
        self.click(0)                    # the button asks; "no" keeps everything
        time.sleep(1)
        self.assertEqual(self.types(n), [])
        self.assertEqual(p.js("window.__asked.startsWith('Withdraw the approval of doc.tex:5–10')"), True)
        p.js("window.__yes = true")
        self.click(0)
        self.assertEqual(until(lambda: self.types(n)), ["unapprove", "unapprove_hunk"])
        self.assertEqual(until(lambda: self.buttons() == ["Approve"]), True)

    # Bug 2: one approval per action, however fast the clicks or keys come.

    def test_double_click_and_key_repeat_approve_once(self):
        p = self.start()
        p.js("window.confirm = m => (window.__asked = m, false)")
        p.key("j")
        p.key("a", repeat=True)          # a held key's repeats are not shortcuts
        time.sleep(1)
        self.assertEqual(self.types(0), ["edit"])
        p.js("(async () => { const b = $('.card [data-act=approve]'); b.click(); await new Promise(r => setTimeout(r, 120)); b.click(); })()")
        time.sleep(2)
        self.assertEqual(self.types(0), ["edit", "approve_hunk", "approve", "commit"])

        p = self.start()
        self.assertEqual(p.js("(() => { const b = $('.card [data-act=approve]'); b.click(); const off = b.disabled; b.click(); return off; })()"), True)
        time.sleep(2)
        self.assertEqual(self.types(0), ["edit", "approve_hunk", "approve", "commit"])

    # Bug 3: drafts and focus survive re-renders; nothing sends twice.

    def test_rerender_keeps_focus_in_the_draft(self):
        p = self.start(BASE3, WORK3)
        self.click(1, "note")
        self.click(0, "note")            # opened last: focused
        p.js("document.querySelectorAll('.composer textarea')[1].value = 'second draft'")
        p.type("xy")
        self.write(WORK3.replace("Alpha paragraph", "Alpha para"))   # an edit re-renders the page
        until(lambda: p.js("changed.length") == 4)
        self.assertEqual(p.js("document.activeElement.value"), "xy")
        n = len(self.log())
        p.type("ac")
        time.sleep(1)
        self.assertEqual(self.types(n), [])
        self.assertEqual(p.js(CMDS), [[7, 7, "xyac"], [9, 9, "second draft"]])

    def test_comment_key_on_committed_card_opens_it(self):
        p = self.start()
        self.click(0)
        self.committed(0)
        until(lambda: p.js("$('.card').classList.contains('done')"))
        n = len(self.log())
        p.key("j")
        p.key("c")
        self.assertEqual(p.js("[!!$('.composer textarea').offsetParent, document.activeElement.tagName]"), [True, "TEXTAREA"])
        p.type("add")
        time.sleep(1)
        self.assertEqual(self.types(n), [])
        self.assertEqual(p.js("$('.composer textarea').value"), "add")

    def test_opening_a_composer_keeps_the_draft(self):
        p = self.start()
        self.click(0, "note")
        p.js("$('.composer textarea').value = 'keep me'")
        self.click(0, "note")            # the same (whole passage) comment: the draft comes back
        self.assertEqual(p.js(CMDS), [[5, 5, "keep me"]])
        self.menu(0, 0, "comment")       # a comment on a change opens beside it
        self.assertEqual(p.js(CMDS), [[5, 5, ""], [5, 5, "keep me"]])

    def test_draft_follows_its_line_when_its_passage_goes(self):
        p = self.start(BASE3, WORK3)
        self.click(0, "note")
        self.click(1, "note")
        p.js("document.querySelectorAll('.composer textarea')[0].value = 'D7'")
        p.js("document.querySelectorAll('.composer textarea')[1].value = 'D9'")
        # Line 7's change reverted and line 9's reworded: both passages' ids go.
        self.write(WORK3.replace("are stored in the registry.", "are stored.").replace("twice", "thrice"))
        until(lambda: p.js("changed.length") == 2)
        self.assertEqual(p.js(CMDS), [[9, 7, "D7"], [9, 9, "D9"]])

    def test_sent_comment_stays_sent_across_a_rerender(self):
        p = self.start()
        p.js(HOLD % (POSTED % "comment"))
        self.click(0, "note")
        p.js("$('.composer textarea').value = 'Tighten this'")
        p.js("$('.composer button.primary').click()")
        until(lambda: p.js("!!window.__held"))
        self.write(WORK.replace("Alpha paragraph", "Alpha para"))
        until(lambda: p.js("changed.length") == 2)
        p.js("window.__go()")
        time.sleep(0.5)
        self.assertEqual(p.js(CMDS), [])
        self.assertEqual(self.types(1), ["comment", "edit"])

    def test_cmd_enter_twice_sends_once(self):
        p = self.start()
        self.click(0, "note")
        p.js("""const ta = $('.composer textarea'); ta.value = 'Shorten this';
                for (const i of [1, 2]) ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', metaKey: true }))""")
        time.sleep(1)
        self.assertEqual(self.types(1), ["comment"])

    # Bug 4: the page shows the newest doc, and the doc follows the log.

    def test_older_load_never_renders_over_a_newer_one(self):
        p = self.start()
        p.js(HOLD % "u === '/api/refs'")
        self.write(WORK.replace("at once", "AT ONCE"))          # a poll's load starts and waits
        until(lambda: p.js("!!window.__held"))
        self.write(WORK.replace("at once", "IMMEDIATELY"))
        p.js("loadDoc(true)")                                    # a later load renders
        p.js("window.__go(); new Promise(r => setTimeout(r, 300))")   # the older one ends last
        self.assertEqual(self.first_line(), "Membership changes go through the governance group vote and take effect IMMEDIATELY.")

    def test_edit_during_a_load_shows(self):
        p = self.start()
        p.js(HOLD % "u === '/api/doc'")
        self.write(WORK.replace("at once", "AT ONCE"))
        until(lambda: p.js("!!window.__held"))
        self.write(WORK.replace("at once", "IMMEDIATELY"))      # after the doc, before the rest of the load
        p.js("window.__go()")
        until(lambda: "IMMEDIATELY" in self.first_line(), 6)
        self.assertEqual(self.first_line(), "Membership changes go through the governance group vote and take effect IMMEDIATELY.")

    def test_log_change_reloads_the_doc(self):
        base = BASE + "\nRevoked credentials are stored.\n\nEvery verifier checks them.\n"
        p = self.start(base, base.replace("are stored.", "are stored in the registry.")
                       .replace("checks them.", "checks them in the registry of record."))
        self.menu(0, 0, "approve")       # card 1 now shows its change since that approved text
        want = [["=", "Every verifier checks them"], ["=", " in the registry"], ["+", " of record", 0], ["=", "."]]
        self.assertEqual(until(lambda: p.js("changed[1].segs") == want and want, 5), want)

    def test_commit_shows_when_a_poll_synced_the_approve_first(self):
        go = TMP / f"go-{os.getpid()}"
        p = self.start(check=f"while [ ! -f {go} ]; do sleep 0.05; done")
        p.js(HOLD % (POSTED % "approve"))
        self.addCleanup(go.unlink, missing_ok=True)
        self.click(0)
        until(lambda: p.js("!!window.__held") and len(self.log()) == 3 and p.js("log.length") == 3)   # a poll fetched the approve
        p.js("window.__go()")
        go.touch()
        self.assertEqual(until(lambda: self.buttons()[0].startswith("Committed ")), True)

    # Bug 5: a failed request shows on the card and closes the menu.

    def test_failed_requests_show_on_the_card(self):
        p = self.start()
        self.stop(self.srv)
        for act in ("approve", "split"):
            p.js("document.querySelectorAll('.err').forEach(e => e.remove())")
            self.click(0, act)
            self.assertEqual(until(lambda: p.js("$('.card .err')?.textContent"), 3), "ErrorFailed to fetch", act)
        p.js("document.querySelectorAll('.err').forEach(e => e.remove())")
        self.menu(0, 0, "approve")
        self.assertEqual(until(lambda: p.js("$('.card .err')?.textContent"), 3), "ErrorFailed to fetch")
        self.assertEqual(p.js("[$('#hmenu').hidden, selecting()]"), [True, False])

    # Bug 6: new page code reloads the page, even within the first poll interval.

    def test_new_page_code_reloads_the_page(self):
        p = self.start()
        p.js("window.__marker = 1")
        os.utime(self.page_html)
        self.assertEqual(until(lambda: p.js("window.__marker === undefined && !!doc", quiet=True), 6), True)

    # Bug 7: a question from Claude stays in sight until dismissed.

    def test_question_on_committed_card_stays_visible(self):
        p = self.start()
        self.click(0)
        self.committed(0)
        until(lambda: p.js("$('.card').classList.contains('done')"))
        self.append({"id": "c1", "type": "comment", "passage": p.js("changed[0].id"), "file": "doc.tex", "line": 5, "quote": "", "text": "Name the registry"})
        self.append({"id": "r1", "type": "reply", "to": "c1", "text": "Which registry, the group's or the global one?", "edited": False})
        side = "$('#side').textContent.includes('Which registry, the group')"
        self.assertEqual(until(lambda: p.js(side), 5), True)
        self.assertEqual(p.js("[!!$('.card .note.reply').offsetParent, $('.card').classList.contains('done')]"), [True, False])
        p.js("$('[data-act=dismiss]').click()")
        self.assertEqual(until(lambda: p.js(f"!{side}"), 5), True)
        self.assertEqual(until(lambda: p.js("$('.card').classList.contains('done')"), 5), True)


if __name__ == "__main__":
    unittest.main()
