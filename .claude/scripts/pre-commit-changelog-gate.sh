#!/bin/bash
#
# pre-commit-changelog-gate.sh — Block code commits that forget to
# update CHANGELOG.md per the Keep-a-Changelog discipline.
#
# Pattern: when staged files include any *.py / pyproject.toml /
# ao_kernel/defaults/*.json change, the commit MUST also stage a
# CHANGELOG.md edit OR carry an explicit `chore:` / `docs:` / `test:` /
# `ci:` / `style:` Conventional Commit prefix that signals "no
# user-visible change". This is the lightweight local mirror of the
# upcoming E-1-3 CI changelog enforcement workflow.
#
# Install (combined with the version-gate hook):
#   cat .claude/scripts/pre-commit-version-gate.sh \
#       .claude/scripts/pre-commit-changelog-gate.sh \
#       > .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Override (rare, justify in commit message):
#   git commit --no-verify
#
# E-1-4 V5 Epic 1 slice. Aligned with ADR-0005 (Keep-a-Changelog
# discipline). Does NOT flip any guard flag.

set -e

# 1. What's staged?
code_changed=$(git diff --cached --name-only \
  | grep -E "^(ao_kernel/.*\.py|pyproject\.toml|ao_kernel/defaults/.*\.json|scripts/.*\.py)$" \
  | grep -v '/tests/' || true)
changelog_changed=$(git diff --cached --name-only \
  | grep -E "^CHANGELOG\.md$" || true)

# 2. No code change -> nothing to enforce
if [ -z "$code_changed" ]; then
  exit 0
fi

# 3. Code change with CHANGELOG.md edit -> pass
if [ -n "$changelog_changed" ]; then
  exit 0
fi

# 4. Code change without CHANGELOG edit -> check the commit message
#    for a non-user-visible prefix. The message is in
#    .git/COMMIT_EDITMSG when this hook runs.
msg_file=".git/COMMIT_EDITMSG"
if [ ! -f "$msg_file" ]; then
  # Fallback: best-effort, allow if we can't introspect the message
  exit 0
fi

first_line=$(head -n1 "$msg_file" | tr -d '\r')
# Allowed prefixes for "no CHANGELOG required"
allowed_re='^(chore|docs|test|ci|style|refactor|build|perf)(\(.*\))?(!)?:'

if echo "$first_line" | grep -Eq "$allowed_re"; then
  exit 0
fi

# 5. Code change + no CHANGELOG + no allowed prefix -> block
cat <<'EOF' >&2
ao-kernel pre-commit: CHANGELOG.md update is missing.

Staged code changes detected but CHANGELOG.md is not staged. Either:
  a) Add a CHANGELOG.md entry under ## [Unreleased] and stage it, OR
  b) Use a non-user-visible Conventional Commit prefix in your message
     (chore: / docs: / test: / ci: / style: / refactor: / build: / perf:)

To override (rare; justify in message):
  git commit --no-verify

E-1-4 V5 Epic 1 — local mirror of the upcoming E-1-3 CI workflow.
EOF
exit 1
