#!/bin/bash
#
# check-branch-sync.sh — Session başlangıç branch freshness kontrolü.
#
# Kullanım (her kod değişikliği session başında):
#   bash .claude/scripts/check-branch-sync.sh
#
# Exit codes:
#   0 → branch fresh (main up-to-date VEYA kısa-ömürlü branch ≤5 commit behind)
#   1 → DUR: stale branch (>5 commit behind) — rebase/yeniden aç
#
# 2026-04-20 olay: claude/faz-c-master-plan 72 commit behind main iken
# Codex v3.2.0 → 4.0.0b1 jump yaptı, 11 minor release kaybedildi.
# Bu script bunu commit time'dan ÖNCE yakalar.

set -e

# Repo root'a in
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || {
  echo "✗ Not in a git repository"
  exit 2
}

branch=$(git branch --show-current)

# Detached HEAD
if [ -z "$branch" ]; then
  echo "⚠ Detached HEAD — feature branch aç:"
  echo "  git checkout -b <name> origin/main"
  exit 1
fi

# Forbidden long-lived branch patterns
if [[ "$branch" =~ ^(claude/|master-plan/|wip/) ]]; then
  echo "🚨 YASAK branch pattern: $branch"
  echo "  CLAUDE.md §17 — claude/*, master-plan/*, wip/* branch'leri stale üretir."
  echo "  Yeni short-lived branch aç from main:"
  echo "    git checkout -b feat/<topic> origin/main"
  exit 1
fi

# Backup branch — read-only, üstünde çalışılmaz
if [[ "$branch" =~ ^backup/ ]]; then
  echo "⚠ backup/ branch — bu read-only referans, üstünde çalışılmaz."
  echo "  Yeni branch aç from main:"
  echo "    git checkout -b feat/<topic> origin/main"
  exit 1
fi

primary_worktree=$(git worktree list --porcelain | awk '/^worktree / {print substr($0, 10); exit}')
repo_root=$(git rev-parse --show-toplevel)
if [ "$branch" != "main" ] && [ "$repo_root" = "$primary_worktree" ]; then
  echo "🚨 Primary checkout üstünde feature branch yasak: $branch"
  echo "  Ayrı worktree zorunlu:"
  echo "    git worktree add ../ao-kernel-<topic> -b codex/<topic> origin/main"
  echo "  Uncommitted değişiklik varsa önce commit/stash/archive ile koru; sonra branch/worktree değiştir."
  exit 1
fi

# Fetch main (silent, timeout 10s)
git fetch origin main --quiet --prune 2>/dev/null || {
  echo "⚠ origin/main fetch failed — offline?"
  echo "  Check connection and retry."
  exit 1
}

if [ "$branch" = "main" ]; then
  behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
  if [ "$behind" -gt 0 ]; then
    echo "⚠ main is $behind commits behind origin/main"
    echo "  Önce worktree clean olmalı; dirty ise commit/stash/archive ile koru."
    echo "  Clean ise: git merge --ff-only origin/main"
    exit 1
  fi
  echo "✓ main, up-to-date with origin/main"
  exit 0
fi

behind=$(git rev-list --count HEAD..origin/main)
ahead=$(git rev-list --count origin/main..HEAD)

echo "Branch: $branch"
echo "Ahead of main: $ahead"
echo "Behind main: $behind"

if [ "$behind" -gt 20 ]; then
  echo ""
  echo "🚨 BRANCH STALE: $behind commits behind — bu branch üstünde ÇALIŞMA"
  echo "  CLAUDE.md §17:"
  echo "    Opsiyon 1 (önerilen): git checkout -b <new> origin/main"
  echo "    Opsiyon 2: git rebase origin/main (yalnız worktree clean veya state korunmuşsa)"
  exit 1
elif [ "$behind" -gt 5 ]; then
  echo ""
  echo "⚠ WARN: branch $behind commits behind — rebase önerilir"
  echo "  Önce worktree clean olmalı; dirty ise commit/stash/archive ile koru."
  echo "  Clean ise: git rebase origin/main"
  exit 0
fi

echo "✓ Branch fresh"
exit 0
