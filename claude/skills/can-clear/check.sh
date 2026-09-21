#!/usr/bin/env bash
# Git-side blockers for /can-clear. One "BLOCK:" line per problem, "GIT: clean" when none.
set -u
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "GIT: not a repo, skipped"; exit 0; }
root=$(git rev-parse --show-toplevel); cd "$root" || exit 1
main=$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
[ -n "$main" ] || { git show-ref -q refs/heads/main && main=main || main=master; }
cur=$(git branch --show-current)
b() { echo "BLOCK: $*"; }

checks() {
  [ -z "$(git status --porcelain)" ] || b "uncommitted changes in $root ($(git status --porcelain | wc -l | tr -d ' ') paths)"
  [ "$cur" = "$main" ] || b "on branch '$cur', not $main"
  git worktree list --porcelain | awk -v root="$root" '/^worktree /{w=$2} /^branch /{sub("refs/heads/","",$2); if (w!=root) print w" "$2}' \
    | while read -r w br; do b "extra worktree $w ($br): git worktree remove $w"; done
  git branch --format='%(refname:short)' | grep -vx "$main" | while read -r br; do
    if git merge-base --is-ancestor "$br" "$main"; then b "merged branch '$br' not deleted: git branch -d $br"
    else b "branch '$br' not merged into $main"; fi
  done
  if git rev-parse -q --verify "origin/$main" >/dev/null 2>&1; then
    n=$(git rev-list --count "origin/$main..$main"); [ "$n" = 0 ] || b "$main is $n commit(s) ahead of origin/$main: git push"
  fi
  [ -z "$(git stash list)" ] || b "$(git stash list | wc -l | tr -d ' ') stash(es): git stash list"
  if command -v gh >/dev/null && git remote get-url origin 2>/dev/null | grep -q github; then
    gh pr list --author @me --state open --json number,title,headRefName \
      -q '.[] | "#\(.number) \(.headRefName): \(.title)"' 2>/dev/null | while read -r p; do b "open PR $p"; done
  fi
}
out=$(checks)
[ -n "$out" ] && echo "$out" || echo "GIT: clean"
