---
name: pr-open
description: Run tests + lint, craft commit, push, and open a GitHub PR. Use when impl is finished and the user says "PR aç", "pull request aç", "merge için hazırla", or explicitly invokes /pr-open.
when_to_use: Trigger after implementation + local verification is complete AND the user wants the branch shipped as a PR. Also valid when user explicitly types /pr-open <title>.
argument-hint: <pr-title>
allowed-tools: Bash(pytest:*), Bash(ruff:*), Bash(mypy:*), Bash(git:*), Bash(gh:*), Read
---

# pr-open — local gate + commit + PR

End-to-end PR open workflow mirroring ao-kernel conventions: tests → lint → typecheck → commit → push → gh pr create.

## Steps

1. **Dirty-tree check**: `git status --short`. If clean, abort with "no changes to ship".
2. **Fast test**: `pytest tests/ -x -q` — abort on failure. Surface the first failing test name + 5 lines of traceback. Ask user: fix-forward or abort?
3. **Lint**: `ruff check ao_kernel/ tests/ --output-format=concise`. Abort on new errors; ignore if already-existing (compare HEAD if in doubt).
4. **Format check**: `ruff format --check ao_kernel/ tests/`. If it fails, run `ruff format` + re-stage.
5. **Typecheck**: `mypy ao_kernel/ --ignore-missing-imports`. Abort on new errors.
6. **Stage + commit** (unless already committed):
   - Prefer explicit file names over `git add -A`.
   - Commit message style (match recent history):
     - `feat(pr-bN): <what>` for new feature
     - `test(pr-bN): <what>` for test-only
     - `docs(faz-x): <what>` for docs
     - `fix(pr-bN): <what>` for bug fix
   - Include trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
   - Use HEREDOC for multiline messages.
7. **Branch + push**:
   - If on `main`: create `claude/<kebab-slug-of-title>` branch first.
   - `git push -u origin <branch>`.
8. **Draft PR body** via HEREDOC (Türkçe başlık / İngilizce body, repo style):
   ```markdown
   ## Summary
   - <bullet 1>
   - <bullet 2>

   ## Test plan
   - [x] pytest tests/ -x (all green, <N> passed)
   - [x] ruff check + format
   - [x] mypy clean
   - [ ] CI green (pending push)

   ## Evidence
   - CNS: <ids if any>
   - Related plan: .claude/plans/<file>.md

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```
9. **Open PR**: `gh pr create --title "<title>" --body "$(cat <<'EOF' ... EOF)"`.
10. **Return PR URL** to the user and ask: "CI izleyeyim mi?" (follow-up per `feedback_ci_monitoring.md`).

## Guardrails

- **No `--no-verify`** unless user explicitly requests. Pre-commit hooks must pass.
- **No force-push** to `main`. If branch needs rewrite, ask first.
- **Don't commit .env / credentials** — skip any file ending with `.env`, `credentials.json`, or `*secret*`.
- If tests are currently red **before** the skill runs (pre-existing breakage), abort with a clear message — don't mask the red state.
- **CI monitoring is separate**: this skill stops at PR open; CI lifecycle ownership is covered by the `feedback_ci_monitoring.md` rule (auto-merge after green + approval).

## Notes

- If the user wants `gh pr merge --admin` after CI green, that's the `feedback_ci_monitoring.md` path, not this skill.
- Branch naming: `claude/<slug>` for ongoing work, `claude/pr-<id>-<slug>` for numbered PRs.
- PR body language: body in English (aligns with CLAUDE.md §16 — docs Türkçe, code+commit English; PR body is a GitHub-facing artifact so English is idiomatic).
