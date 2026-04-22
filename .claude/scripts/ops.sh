#!/bin/bash
#
# ops.sh — WP-6 operasyon dispatcher'ı.
#
# İlk yüzeyler:
# - `preflight`
#   - branch freshness (`check-branch-sync.sh`)
#   - current worktree dirtiness
#   - upstream divergence visibility
#   - other attached worktree snapshot
# - `overlap-check`
#   - attached worktree'lerin changed-path setlerini karşılaştırır
#   - exact file overlap ve paylaşılan top-level alan sinyali üretir
# - `close-worktree`
#   - clean non-current worktree'yi güvenli biçimde kapatır
#   - dirty veya current target için fail-closed davranır
#
# Kullanım:
#   bash .claude/scripts/ops.sh preflight
#   bash .claude/scripts/ops.sh overlap-check
#   bash .claude/scripts/ops.sh close-worktree <path>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  bash .claude/scripts/ops.sh preflight
  bash .claude/scripts/ops.sh overlap-check
  bash .claude/scripts/ops.sh close-worktree <path>

Available commands:
  preflight       Session başlangıcı için branch/worktree sağlık özeti
  overlap-check   Attached worktree'ler arası path-overlap riski görünürlüğü
  close-worktree  Clean non-current worktree kapatma yüzeyi
EOF
}

count_lines() {
  awk 'NF {count += 1} END {print count + 0}'
}

run_preflight() {
  local sync_output=""
  local sync_status=0
  local repo_root=""
  local branch=""
  local upstream=""
  local upstream_state=""
  local staged=0
  local unstaged=0
  local untracked=0
  local warnings=0
  local current_dirty=0
  local other_count=0
  local other_dirty=0
  local block_path=""
  local block_branch=""
  local block_detached=0

  set +e
  sync_output="$("$SCRIPT_DIR/check-branch-sync.sh" 2>&1)"
  sync_status=$?
  set -e

  printf '== ops preflight ==\n'
  printf '%s\n' "$sync_output"

  if [ "$sync_status" -ne 0 ]; then
    return "$sync_status"
  fi

  repo_root="$(git rev-parse --show-toplevel)"
  branch="$(git branch --show-current)"

  if upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
    upstream_state="ahead $(git rev-list --count "${upstream}..HEAD"), behind $(git rev-list --count "HEAD..${upstream}")"
  else
    upstream="(none)"
    upstream_state="not pushed yet"
    if [ "$branch" != "main" ]; then
      warnings=$((warnings + 1))
    fi
  fi

  staged="$(git diff --cached --name-only | count_lines)"
  unstaged="$(git diff --name-only | count_lines)"
  untracked="$(git ls-files --others --exclude-standard | count_lines)"
  if [ "$staged" -gt 0 ] || [ "$unstaged" -gt 0 ] || [ "$untracked" -gt 0 ]; then
    current_dirty=1
    warnings=$((warnings + 1))
  fi

  printf '\nRepo: %s\n' "$repo_root"
  printf 'Branch: %s\n' "$branch"
  printf 'Upstream: %s (%s)\n' "$upstream" "$upstream_state"
  if [ "$current_dirty" -eq 1 ]; then
    printf 'Current worktree: dirty (staged=%s, unstaged=%s, untracked=%s)\n' "$staged" "$unstaged" "$untracked"
  else
    printf 'Current worktree: clean\n'
  fi

  printf 'Other worktrees:\n'
  while IFS= read -r line || [ -n "$line" ]; do
    if [ -z "$line" ]; then
      if [ -n "$block_path" ] && [ "$block_path" != "$repo_root" ]; then
        local wt_status="clean"
        local wt_lines=""
        other_count=$((other_count + 1))
        wt_lines="$(git -C "$block_path" status --short --untracked-files=normal 2>/dev/null || true)"
        if [ -n "$wt_lines" ]; then
          wt_status="dirty"
          other_dirty=$((other_dirty + 1))
          warnings=$((warnings + 1))
        fi
        if [ "$block_detached" -eq 1 ] && [ -z "$block_branch" ]; then
          block_branch="(detached)"
        fi
        printf '  - %s [%s] %s\n' "$block_path" "${block_branch:-unknown}" "$wt_status"
      fi
      block_path=""
      block_branch=""
      block_detached=0
      continue
    fi

    case "$line" in
      worktree\ *)
        block_path="${line#worktree }"
        ;;
      branch\ refs/heads/*)
        block_branch="${line#branch refs/heads/}"
        ;;
      detached)
        block_detached=1
        ;;
    esac
  done < <(git worktree list --porcelain)

  if [ "$other_count" -eq 0 ]; then
    printf '  - none\n'
  fi

  printf '\nSummary:\n'
  if [ "$warnings" -eq 0 ]; then
    printf '✓ Preflight clean\n'
  else
    printf '⚠ Preflight completed with warnings\n'
    if [ "$current_dirty" -eq 1 ]; then
      printf '  - current worktree dirty\n'
    fi
    if [ "$upstream" = "(none)" ] && [ "$branch" != "main" ]; then
      printf '  - branch has no upstream yet\n'
    fi
    if [ "$other_dirty" -gt 0 ]; then
      printf '  - %s other worktree(s) dirty\n' "$other_dirty"
    fi
  fi
}

run_overlap_check() {
  python3 "$SCRIPT_DIR/ops_overlap_check.py"
}

run_close_worktree() {
  python3 "$SCRIPT_DIR/ops_close_worktree.py" "$@"
}

main() {
  local command="${1:-}"
  case "$command" in
    preflight)
      run_preflight
      ;;
    overlap-check)
      run_overlap_check
      ;;
    close-worktree)
      shift
      run_close_worktree "$@"
      ;;
    ""|-h|--help|help)
      usage
      ;;
    *)
      printf 'Unknown command: %s\n\n' "$command" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
