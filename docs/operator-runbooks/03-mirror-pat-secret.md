# Runbook 03 — Mirror-Sync PAT Secret (AO-MA-11E-2b)

> **Agent-prepared only.** This runbook directs the operator to seed the
> repository secret `REPO_GH_PAT_PROJECTS_RW` used by the
> `.github/workflows/ao-ma-11e-2b-mirror-sync.yml` workflow. The agent
> NEVER commits a PAT and NEVER seeds the secret itself.

## Prerequisites

- Repository admin permissions on `Halildeu/ao-kernel`
- Decision: classic PAT vs fine-grained PAT (see Sections A and B)
- `gh` CLI authenticated with an account that owns the PAT

## Section A — Classic PAT (recommended for Projects v2)

Classic PATs support Projects v2 natively today.

### Scopes (minimal)

- `project` — full Projects v2 read/write
- `public_repo` — issue/PR write on public repos
- **NEVER set `repo` full scope** (over-privileged; covers private repo
  contents, security events, deployments)
- **NEVER set `workflow`** (not needed; workflow reads use `GITHUB_TOKEN`)
- **NEVER set `admin:*`**

### Expiration

- Set expiration to 90 days
- Schedule a 60-day rotation reminder
- Document the owner + revoke contact in an operator-private location
  (NOT in this repo)

## Section B — Fine-grained PAT (minimal-scope alternative)

Fine-grained PATs are repo-scoped and use distinct permission categories.

### Repository access

- Select repositories: V5 mirror repo (exact list)

### Permissions

- **Issues**: Read + Write
- **Metadata**: Read (default)
- **Pull requests**: Read (NOT Write; the mirror workflow uses
  `pull-requests: read`)
- **Projects**: operator-verified support (GitHub fine-grained PAT
  Projects v2 support varies; verify against the repo's project type)

### NEVER grant

- **Contents**: Write (not needed; workflow writes are issue/project)
- **Workflows**: Write
- **Administration**

### Expiration

- Set expiration to 90 days; same rotation cadence as Section A

## Steps (common seed flow for both PAT types)

Use the stdin pipe pattern (HARD RULE D43) — never `--body`, never `echo`.

1. Create the PAT in the GitHub UI per Section A or B.
2. Copy the token to the clipboard.
3. Open a terminal and clear shell history for the next command:
   ```bash
   set +o history
   ```
4. Seed the secret via stdin pipe:
   ```bash
   read -s TOKEN
   # paste the PAT and press Enter; nothing is echoed
   printf '%s' "$TOKEN" | \
       gh secret set REPO_GH_PAT_PROJECTS_RW \
           --repo Halildeu/ao-kernel \
           --body-file -
   unset TOKEN
   set -o history
   ```
5. Confirm the secret exists:
   ```bash
   gh secret list --repo Halildeu/ao-kernel | grep REPO_GH_PAT_PROJECTS_RW
   ```

## Verification

- The secret `REPO_GH_PAT_PROJECTS_RW` appears in
  Settings → Secrets and variables → Actions
- The PAT does NOT appear in any committed file (run a manual
  `git grep ghp_` or `git grep github_pat_` to confirm)
- The PAT does NOT appear in any shell history transcript

## Rollback

- Revoke the PAT from the GitHub UI (Settings → Developer settings →
  Personal access tokens)
- Delete the repo secret: `gh secret delete REPO_GH_PAT_PROJECTS_RW --repo Halildeu/ao-kernel`

## Stop and contact owner if

- The proposed PAT requires `repo` full scope (classic) or
  `Contents: Write` (fine-grained); escalate, do NOT silently grant
- The repo is private and the fine-grained PAT does not support
  Projects v2; switch to classic or escalate
- The PAT value was accidentally echoed to the terminal, logged, or
  pasted into a chat — revoke immediately and re-seed
- The secret name is not exactly `REPO_GH_PAT_PROJECTS_RW` (typo)

## Notes

- The repo and CI MUST NEVER see the PAT value. The stdin pipe pattern
  ensures the token never reaches the shell command line, never enters
  shell history, and never appears in `gh` debug output.
- **Forbidden seeding patterns** (do NOT use any of these):
  - `gh secret set REPO_GH_PAT_PROJECTS_RW --body "ghp_..."` (token on
    command line; visible in process list and shell history)
  - `echo "ghp_..." | gh secret set ...` (token in shell history)
  - Pasting the token into a Markdown PR description or chat

## References

- `.github/workflows/ao-ma-11e-2b-mirror-sync.yml`
- HARD RULE D43 stdin-pipe secret handling
- Codex thread `019e84c6`
