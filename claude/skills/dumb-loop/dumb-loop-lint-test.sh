#!/bin/bash
set -u
here="$(cd "$(dirname "$0")" && pwd)"
lint="$here/dumb-loop-lint.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/repo" "$tmp/plans" "$tmp/wt"
cd "$tmp/repo"
git init -q && git config user.email t@t && git config user.name t
mkdir -p stages
printf 'extends Node\n\nconst SPEED: float = 2.0\n' > stages/a.gd
printf '[gd_scene]\n\n[ext_resource type="Script" uid="uid://c1abc2def3ghi" path="res://stages/a.gd" id="1_a"]\n\n[node name="root" type="Node2D"]\n' > stages/scene.tscn
printf '[resource]\n' > stages/label.tres
git add -A && git commit -qm base

cat > "$tmp/plans/good.md" <<'EOF'
task: fixture
disjoint: yes

## Thread 1: scripts
files: stages/a.gd, stages/b.gd
depends_on: none
steps:
1. edit.
2. Run exactly: git add -A && git commit -m "feat(good one)" -m "t" -m "b"

## Thread 2: scene
files: stages/scene.tscn stages/label.tres
depends_on: none
steps:
1. edit.
2. Run exactly: git add -A && git commit -m "feat(good two)" -m "t" -m "b"
EOF
cat > "$tmp/plans/bad.md" <<'EOF'
task: fixture
disjoint: yes

## Thread 1: scripts
files: stages/a.gd, stages/c.gd, stages/scene.tscn
depends_on: none
steps:
1. edit.
2. Run exactly: git add -A && git commit -m "feat(t1)" -m "t" -m "b"

## Thread 2: scene
files: stages/scene.tscn, stages/label.tres
depends_on: none
steps:
1. edit.
2. Run exactly: git add -A && git commit -m "feat(t2)" -m "t" -m "b"
EOF
cat > "$tmp/plans/multi.md" <<'EOF'
task: fixture
disjoint: yes

## Thread 1: multi
files: stages/a.gd, stages/b.gd
depends_on: none
steps:
1. edit.
1c. Run: git add -A && git commit -m "feat(multi one)" -m "t" -m "b"
2. edit.
2c. Run: git add -A && git commit -m "feat(multi two)" -m "t" -m "b"
EOF
cat > "$tmp/plans/multi-bad.md" <<'EOF'
task: fixture
disjoint: yes

## Thread 1: multi
files: stages/a.gd, stages/b.gd
depends_on: none
steps:
1. edit.
1c. Run: git add -A && git commit -m "feat(multi one)" -m "t" -m "b"
2. edit.
2c. Run: git add -A && git commit -m "feat(multi missing)" -m "t" -m "b"
EOF

git checkout -qb good
printf 'extends Node\n\nconst SPEED: float = 2.0\nconst COURSE: PackedVector2Array = [\n\tVector2(336, -5),\n\tVector2(239, 340),\n]\n\n\nfunc _ready() -> void:\n\tvar label := "#not a comment"\n\tprint(label, COURSE[0])\n' > stages/a.gd
printf 'extends Node\n\n\nfunc foo() -> void:\n\tpass\n' > stages/b.gd
printf 'uid://b2xyz3uvw4rst\n' > stages/b.gd.uid
git add -A && git commit -qm "feat(good one)" -m t -m b
sed 's/c1abc2def3ghi/d4new5uid6xyz/' stages/scene.tscn > s.tmp && mv s.tmp stages/scene.tscn
printf '[resource]\nx = 1\n' > stages/label.tres
git add -A && git commit -qm "feat(good two)" -m t -m b

git checkout -q main && git checkout -qb bad
printf 'extends Node\n\nconst SPEED: float = 2.0\n\n\nfunc _process(_d: float) -> void:\n\t# note\n\tposition.x += 30.0\n' > stages/a.gd
printf 'extends Node\n\n\nfunc foo() -> void:\n\tpass\n' > stages/c.gd
printf '[gd_scene]\n\n[ext_resource type="Script" path="res://stages/a.gd" id="1_a"]\n\n[node name="root" type="Node2D"]\n' > stages/scene.tscn
printf 'stray\n' > stray.txt
git add -A && git commit -qm "feat(t2)" -m t -m b
git worktree add -q "$tmp/wt/dirty" -b wt-dirty main && printf 'junk\n' > "$tmp/wt/dirty/junk"
git worktree add -q "$tmp/wt/clean" -b wt-clean main

git checkout -q main && git checkout -qb multi
printf 'extends Node\n\nconst SPEED: float = 2.0\n\n\nfunc _ready() -> void:\n\tprint(SPEED)\n' > stages/a.gd
git add -A && git commit -qm "feat(multi one)" -m t -m b
printf 'extends Node\n\n\nfunc foo() -> void:\n\tpass\n' > stages/b.gd
printf 'uid://e5new6uvw7xyz\n' > stages/b.gd.uid
git add -A && git commit -qm "feat(multi two)" -m t -m b
git checkout -q main

fail=0
run() { out=$("$lint" "$@" 2>&1); rc=$?; }

echo "## good"; run "$tmp/plans/good.md" main..good --wt "$tmp/wt/clean_only_dir_missing" ; echo "$out"
run "$tmp/plans/good.md" main..good; echo "$out"
[[ $rc -eq 0 && "$out" == *"lint: 0 findings"* && "$out" == *"disjoint: yes"* ]] || { echo "FAIL good"; fail=1; }

echo "## bad"; run "$tmp/plans/bad.md" main..bad --wt "$tmp/wt"; echo "$out"
names=$(echo "$out" | grep ' · ' | cut -d' ' -f1 | sort | tr '\n' ' ')
[[ $rc -eq 1 && "$names" == "comment commit disjoint ext_resource magic outside uid wt " && "$out" == *"lint: 8 findings"* ]] || { echo "FAIL bad: got [$names] rc=$rc"; fail=1; }

echo "## multi"; run "$tmp/plans/multi.md" main..multi; echo "$out"
[[ $rc -eq 0 && "$out" == *"lint: 0 findings"* ]] || { echo "FAIL multi"; fail=1; }

echo "## multi-bad"; run "$tmp/plans/multi-bad.md" main..multi; echo "$out"
names=$(echo "$out" | grep ' · ' | cut -d' ' -f1 | sort | tr '\n' ' ')
[[ $rc -eq 1 && "$names" == "commit " && "$out" == *"lint: 1 findings"* ]] || { echo "FAIL multi-bad: got [$names] rc=$rc"; fail=1; }

echo "## empty range"; run "$tmp/plans/good.md" main..main; echo "$out"
[[ $rc -eq 0 && "$out" == *"is empty"* ]] || { echo "FAIL empty"; fail=1; }

echo "## bad args"; run "$tmp/plans/good.md" main; [[ $rc -eq 2 ]] || { echo "FAIL args rc=$rc"; fail=1; }

real=~/REPOS/emoji-management/client/plans/WATER-EMOJI.md
if [[ -f "$real" && -d ~/REPOS/emoji-godot ]]; then
  echo "## real plan, empty range"; (cd ~/REPOS/emoji-godot && "$lint" "$real" main..main); rc=$?
  [[ $rc -eq 0 ]] || { echo "FAIL real rc=$rc"; fail=1; }
fi
[[ $fail -eq 0 ]] && echo PASS || echo FAIL
exit $fail
