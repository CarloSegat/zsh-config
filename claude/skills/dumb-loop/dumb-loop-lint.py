#!/usr/bin/env python3
import collections
import os
import re
import subprocess
import sys

USAGE = "usage: dumb-loop-lint.sh <plan.md> <base>..<branch> [--wt <dir>]"


def die(msg, code=2):
    print(msg)
    sys.exit(code)


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def exists(rev, path):
    return subprocess.run(["git", "cat-file", "-e", f"{rev}:{path}"], capture_output=True).returncode == 0


def outside_string(code, idx):
    head = code[:idx]
    return head.count('"') % 2 == 0 and head.count("'") % 2 == 0


args = sys.argv[1:]
if len(args) not in (2, 4) or (len(args) == 4 and args[2] != "--wt") or ".." not in args[1]:
    die(USAGE)
plan_path, rng = args[0], args[1]
wt_dir = args[3] if len(args) == 4 else None
base, branch = rng.split("..", 1)
try:
    plan = open(plan_path).read()
except OSError as e:
    die(f"plan: {e}")

threads = []
for m in re.finditer(r"^## Thread (\d+):[^\n]*\n(.*?)(?=^## Thread |\Z)", plan, re.M | re.S):
    sec = m.group(2)
    fm = re.search(r"^files:\s*(.+)$", sec, re.M)
    files = [f for f in re.split(r"[,\s]+", fm.group(1).strip()) if f] if fm else []
    subs = re.findall(r'git commit -m "([^"]+)"', sec)
    threads.append((int(m.group(1)), files, subs))
if not threads:
    die("plan: no '## Thread N:' sections")
hm = re.search(r"^disjoint:\s*(\S+)", plan, re.M)
header = hm.group(1) if hm else ""

findings = []


def add(check, where, what):
    findings.append(f"{check} · {where} · {what}")


overlap = False
for i, (n1, f1, _) in enumerate(threads):
    for n2, f2, _ in threads[i + 1:]:
        for f in sorted(set(f1) & set(f2)):
            add("disjoint", f, f"in threads {n1} and {n2}")
            overlap = True
computed = "no" if overlap else "yes"
print(f"disjoint: {computed}")
if not overlap and header != "yes":
    add("disjoint", plan_path, f"header says '{header or 'nothing'}', computed yes")

if git("rev-list", "--count", rng).strip() == "0":
    print(f"range {rng} is empty: only disjoint checked")
else:
    listed = {f for _, fs, _ in threads for f in fs}
    for f in git("diff", "--name-only", rng).splitlines():
        if f and f not in listed and not (f.endswith(".uid") and f[:-4] in listed):
            add("outside", f, "not in any thread's files list")

    cur, ln, const_depth = None, 0, 0
    for line in git("diff", "-U0", rng, "--", "*.gd").splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else line[4:]
            const_depth = 0
            continue
        if line.startswith("@@"):
            ln = int(re.match(r"@@ -\S+ \+(\d+)", line).group(1))
            continue
        if not line.startswith("+"):
            continue
        code = line[1:]
        here = ln
        ln += 1
        stripped = code.lstrip()
        if stripped.startswith("#"):
            add("comment", f"{cur}:{here}", "full-line comment")
            continue
        i = code.find("#")
        while i != -1 and not outside_string(code, i):
            i = code.find("#", i + 1)
        if i != -1:
            add("comment", f"{cur}:{here}", "trailing comment")
        declares = re.match(r"\s*(const|@export|enum)\b", code) is not None
        if declares or const_depth > 0:
            const_depth = (const_depth if not declares else 0) + code.count("(") + code.count("[") + code.count("{") \
                - code.count(")") - code.count("]") - code.count("}")
            const_depth = max(const_depth, 0)
            continue
        for m in re.finditer(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?![A-Za-z0-9_.])", code):
            if m.group() in ("0", "1", "-1") or not outside_string(code, m.start()):
                continue
            add("magic", f"{cur}:{here}", m.group())
            break

    for line in git("diff", "--name-status", rng).splitlines():
        parts = line.split("\t")
        if parts[0].startswith("A") and parts[-1].endswith(".gd") and not exists(branch, parts[-1] + ".uid"):
            add("uid", parts[-1], "no committed .gd.uid")

    for f in git("diff", "--name-only", rng, "--", "*.tscn", "*.tres").splitlines():
        if not f or not exists(branch, f):
            continue
        for i, l in enumerate(git("show", f"{branch}:{f}").splitlines(), 1):
            if l.startswith("[ext_resource ") and 'uid="uid://' not in l:
                add("ext_resource", f"{f}:{i}", "no uid=")

    remaining = collections.Counter(git("log", "--format=%s", rng).splitlines())
    for n, _, subs in threads:
        if not subs:
            add("commit", f"thread {n}", "no git commit step in the plan")
            continue
        for subj in subs:
            if remaining[subj] > 0:
                remaining[subj] -= 1
            else:
                add("commit", f"thread {n}", f"subject not in {rng}: {subj}")

if wt_dir:
    if not os.path.isdir(wt_dir):
        die(f"--wt {wt_dir}: not a directory")
    for e in sorted(os.listdir(wt_dir)):
        p = os.path.join(wt_dir, e)
        if not os.path.isdir(p):
            continue
        r = subprocess.run(["git", "-C", p, "status", "--short"], capture_output=True, text=True)
        if r.returncode != 0:
            continue
        dirty = r.stdout.strip().splitlines()
        if dirty:
            more = f" (+{len(dirty) - 1})" if len(dirty) > 1 else ""
            add("wt", e, f"dirty: {dirty[0].strip()}{more}")

for f in findings:
    print(f)
print(f"lint: {len(findings)} findings")
sys.exit(1 if findings else 0)
