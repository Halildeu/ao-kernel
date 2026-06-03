# V5 Epic 1 E-1-4: Pre-commit Changelog Hook

> **Risk class:** conservative low-risk (local script only; opt-in install)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Local pre-commit shell hook that enforces ADR-0005 Keep-a-Changelog
discipline at commit time. Aligned with the existing
`pre-commit-version-gate.sh` install pattern (CLAUDE.md §17). E-1-3
will provide the matching CI workflow; this slice is the lightweight
local mirror.

**In scope:**
- `.claude/scripts/pre-commit-changelog-gate.sh` (shell hook)
- 15 invariant tests (presence/structure + decision contract +
  coexistence with version-gate + ADR-0005/CHANGELOG presence +
  governance)

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*` (E-1-3 covers CI)
- ADR-0005 content (referenced, not modified)
- CHANGELOG.md content (referenced, not modified)
- `.git/hooks/pre-commit` (operator-owned install path; documented)
- Any guard flag flip

## 2. Decision Contract

| Staged | Commit message prefix | Hook decision |
|---|---|---|
| No code | any | PASS |
| Code + CHANGELOG.md | any | PASS |
| Code, no CHANGELOG | `chore:` / `docs:` / `test:` / `ci:` / `style:` / `refactor:` / `build:` / `perf:` | PASS (non-user-visible) |
| Code, no CHANGELOG | `feat:` / `fix:` / other | BLOCK (exit 1) with actionable message |
| `--no-verify` | any | bypass (rare; justify in message) |

The hook reads `.git/COMMIT_EDITMSG` to introspect the commit prefix.
"Code" = `ao_kernel/**/*.py` + `pyproject.toml` + `ao_kernel/defaults/**/*.json` + `scripts/**/*.py` (excluding `/tests/`).

## 3. Test Sections (15 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Presence/structure | 6 | Hook file + executable bit + bash shebang + `set -e` + CHANGELOG.md reference + Keep-a-Changelog/ADR-0005 citation |
| 2. Allowed-prefix contract | 4 | 5 prefixes listed + `feat:` without CHANGELOG → exit 1 + `chore:` without CHANGELOG → exit 0 + `feat:` with CHANGELOG → exit 0 |
| 3. Coexistence | 2 | Version-gate hook still present + install instruction composes both |
| 4. ADR + governance | 3 | ADR-0005 exists + CHANGELOG.md exists + ZERO TOUCH `.github/workflows/` |

Decision contract tests run the hook in a temp git repo (no global git
side effects).

## 4. Install (operator action; CLAUDE.md §17 pattern)

```bash
cat .claude/scripts/pre-commit-version-gate.sh \
    .claude/scripts/pre-commit-changelog-gate.sh \
    > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Hook is operator-installed (not auto-installed) per existing repo
convention. The CI workflow (E-1-3) provides the non-bypassable mirror.

## 5. References

- ADR-0005 Keep-a-Changelog discipline
- `.claude/scripts/pre-commit-version-gate.sh` (existing co-pattern)
- CHANGELOG.md
- E-1-3 future slice: CI changelog enforcement workflow
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
