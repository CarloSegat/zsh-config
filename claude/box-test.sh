#!/usr/bin/env bash
# box-test.sh <emoji-godot ref> [make target and vars...]
# Runs an emoji-godot make target (default: test) on the box from detached
# worktrees of origin/<ref> and of emoji-gs origin/${GS_REF:-main}, streams the
# output, exits with make's code, and removes both worktrees.
# Box unreachable: exits 75 and runs nothing; tests never fall back to the Mac.
#   box-test.sh fix/my-branch
#   box-test.sh fix/my-branch unit UNIT=rocket
#   GS_REF=feat/gs-branch box-test.sh main test
set -euo pipefail
BOX=${BOX:-car-ms-7885}
[ $# -ge 1 ] || { sed -n 2,9p "$0" >&2; exit 2; }
ref=$1; shift
[ $# -ge 1 ] || set -- test
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$BOX" true 2>/dev/null; then
	echo "box-test: $BOX unreachable; no tests on the Mac (owner rule, 2026-11-23)" >&2
	exit 75
fi
ssh "$BOX" bash -s -- "$ref" "${GS_REF:-main}" "$@" <<'REMOTE'
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
ref=$1 gs_ref=$2; shift 2
resolve() { git -C "$1" rev-parse --verify -q "origin/$2^{commit}" || git -C "$1" rev-parse --verify "$2^{commit}"; }
g=~/REPOS/emoji-godot s=~/REPOS/emoji-gs
git -C "$g" fetch -q origin && git -C "$s" fetch -q origin
tag=$(printf '%s' "$ref" | tr '/' '-')-$$
wt=~/REPOS/emoji-godot-wt/box-test-$tag gwt=~/REPOS/emoji-gs-wt/box-test-$tag
cleanup() { git -C "$g" worktree remove --force "$wt" 2>/dev/null; git -C "$s" worktree remove --force "$gwt" 2>/dev/null; true; }
trap cleanup EXIT
git -C "$g" worktree add -q --detach "$wt" "$(resolve "$g" "$ref")"
git -C "$s" worktree add -q --detach "$gwt" "$(resolve "$s" "$gs_ref")"
echo "box-test: emoji-godot $ref @ $(git -C "$wt" rev-parse --short=8 HEAD), emoji-gs $gs_ref @ $(git -C "$gwt" rev-parse --short=7 HEAD): make $*"
cd "$wt"
# a fresh worktree has no .godot cache; the gates (menu-census) need one
godot --headless --path . --import > .box-test-import.log 2>&1 || { tail -20 .box-test-import.log; exit 1; }
make --no-print-directory "$@" GS_REPO="$gwt"
REMOTE
