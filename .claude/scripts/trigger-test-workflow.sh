#!/bin/bash
#
# trigger-test-workflow.sh — Test workflow'unu mevcut branch için manuel tetikle.
#
# Özellikle stacked PR retarget sonrası GitHub otomatik check üretmezse
# kullanılır. Branch push'u normalde codex/* için CI üretir; bu script
# manuel fallback'tir.
#
# Kullanım:
#   bash .claude/scripts/trigger-test-workflow.sh
#   bash .claude/scripts/trigger-test-workflow.sh <branch>
#   bash .claude/scripts/trigger-test-workflow.sh <branch> --watch

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" 2>/dev/null || {
  echo "✗ Not in a git repository"
  exit 2
}

if ! command -v gh >/dev/null 2>&1; then
  echo "✗ gh CLI bulunamadı"
  exit 1
fi

branch="${1:-$(git branch --show-current)}"
watch_flag="${2:-}"

if [ -z "$branch" ]; then
  echo "✗ Detached HEAD — branch adı ver:"
  echo "  bash .claude/scripts/trigger-test-workflow.sh <branch>"
  exit 1
fi

if ! git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  echo "✗ origin/$branch bulunamadı — önce push et:"
  echo "  git push -u origin $branch"
  exit 1
fi

echo "→ Test workflow tetikleniyor: branch=$branch"
gh workflow run test.yml --ref "$branch" -f reason="manual-retarget-check"

sleep 3
run_id=$(gh run list \
  --workflow test.yml \
  --branch "$branch" \
  --event workflow_dispatch \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')

if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
  echo "⚠ Run kuyruğu doğrulanamadı. Şunu izle:"
  echo "  gh run list --workflow test.yml --branch $branch --limit 5"
  exit 0
fi

echo "✓ Queued run id: $run_id"
echo "  İzlemek için:"
echo "    gh run watch $run_id"

if [ "$watch_flag" = "--watch" ]; then
  gh run watch "$run_id"
fi
