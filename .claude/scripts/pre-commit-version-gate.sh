#!/bin/bash
#
# pre-commit-version-gate.sh — Stale base'de version bump'ı engelle.
#
# Install:
#   cp .claude/scripts/pre-commit-version-gate.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# 2026-04-20 olay: Codex stale branch'te version 3.2.0 → 4.0.0b1 bump
# yaptı, 11 minor release kaybı tehlikesi doğurdu. Bu hook aynı hatayı
# commit time'da yakalar.
#
# Override (gerçekten gerekliyse):
#   git commit --no-verify

set -e

# Hangi dosyalar staged?
version_changed=$(git diff --cached --name-only \
  | grep -E "^(pyproject\.toml|ao_kernel/__init__\.py)$" || true)

if [ -z "$version_changed" ]; then
  # Version dosyası değişmiyor, check atla
  exit 0
fi

# origin/main ile merge-base yaşını hesapla
git fetch origin main --quiet 2>/dev/null || {
  echo "⚠ pre-commit: origin/main fetch failed, skipping staleness check"
  exit 0
}

base_sha=$(git merge-base HEAD origin/main 2>/dev/null)
if [ -z "$base_sha" ]; then
  echo "⚠ pre-commit: no merge-base with origin/main, skipping"
  exit 0
fi

base_ts=$(git log -1 --format=%ct "$base_sha" 2>/dev/null || echo 0)
now=$(date +%s)
age_hours=$(( (now - base_ts) / 3600 ))

if [ "$age_hours" -gt 24 ]; then
  echo ""
  echo "✗ PRE-COMMIT BLOCK: version bump on stale base"
  echo "  Branch: $(git branch --show-current)"
  echo "  Merge-base age: ${age_hours} hours old (limit: 24h)"
  echo "  Files triggering check:"
  echo "$version_changed" | sed 's/^/    /'
  echo ""
  echo "  CLAUDE.md §18: Version bump stale base'de yasak."
  echo "  Fix:"
  echo "    git rebase origin/main"
  echo "    git add <version files>"
  echo "    git commit"
  echo ""
  echo "  Override (risk kabul ederek):"
  echo "    git commit --no-verify"
  exit 1
fi

echo "✓ pre-commit: version bump OK (base $age_hours hours old, ≤24h limit)"
exit 0
