# Product Quickstart — Local Governed Workflow

This guide takes a fresh install from zero to the first local evidence
artifacts for the productized `ao-kernel` workflow:

1. repo-intelligence onboarding,
2. PR delivery metadata,
3. bounded multi-agent local orchestration.

It is intentionally local and fail-closed. It does **not** configure GitHub
Apps, Vault, webhooks, branch protection, Cloud Run, live adapters, support
widening, or a production-platform claim.

## 1. Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ao-kernel==4.3.1
ao-kernel version
```

For a checkout smoke before publishing, use:

```bash
python scripts/fresh_install_product_smoke.py --mode both
```

The smoke builds the checkout, installs the wheel and sdist into separate
clean virtualenvs, and writes evidence under:

```text
build/fresh-install-product-smoke/
```

## 2. Prepare A Project

Run these commands from the repository you want to onboard.

```bash
ao-kernel init
ao-kernel repo onboarding init-config \
  --project-root . \
  --path .ao/repo-intelligence.yml
ao-kernel repo onboarding doctor --project-root . --output json
```

Expected boundary:

- `status` should become `ready` once the `.ao` workspace and onboarding
  config are present.
- The generated config records GitHub App installation and repository
  selection as the user-managed setup boundary.
- End users are not asked to host `ao-release-gate`, Vault, Cloud Run,
  deployment-protection callbacks, or webhooks.

## 3. Add PR Delivery Metadata

Generate a metadata block:

```bash
ao-kernel pr-metadata generate \
  --work-package PRODUCT-SLICE-1 \
  --issue '#123' \
  --reviewer-provider anthropic > /tmp/pr-metadata.md
```

Insert or update it in a PR body:

```bash
ao-kernel pr-metadata fix \
  --body-file pr-body.md \
  --write \
  --work-package PRODUCT-SLICE-1 \
  --issue '#123' \
  --reviewer-provider anthropic

ao-kernel pr-metadata validate --body-file pr-body.md --output json
```

The PR metadata block is a structured declaration. It is not release authority.
Release authority remains the repo-owned `ao-release-gate` required check plus
GitHub branch protection.

## 4. Run A Bounded Local Multi-Agent Wrapper

Dry-run one declared write scope:

```bash
BASE_SHA="$(git rev-parse origin/main)"

ao-kernel orchestration run-wrapper \
  --goal "bounded local slice" \
  --repo-root . \
  --base-sha "$BASE_SHA" \
  --repo Halildeu/ao-kernel \
  --declared-spec task-001:src/example.py:"bounded local change" \
  --dry-run \
  --format json
```

Run multiple deterministic local worker fixtures concurrently:

```bash
ao-kernel orchestration run-wrapper-async \
  --goal "bounded parallel local slice" \
  --repo-root . \
  --worktree-base ../ao-kernel-workers \
  --base-sha "$BASE_SHA" \
  --repo Halildeu/ao-kernel \
  --declared-spec task-001:src/a.py:"worker one" \
  --declared-spec task-002:src/b.py:"worker two" \
  --execute-local-fixture \
  --max-workers 2 \
  --format json
```

The async wrapper:

- emits one task graph for all declared specs,
- prepares one worker worktree per declared task,
- invokes the pinned deterministic local worker fixture concurrently,
- collects `manifest.v1.json`, `runner_report.v1.json`, and
  `worker_invocation_report.v1.json`,
- reports review and verification phases as external evidence required rather
  than fabricating AI review or verifier approval.

## 5. Collect Cross-Provider Review Evidence

High-risk review evidence is collected through explicit provider commands. Each
command receives a no-secret JSON review request on stdin and returns JSON on
stdout:

```json
{
  "agent": "short-reviewer-label",
  "verdict": "AGREE",
  "checks_considered": [
    {"name": "tests", "status": "pass"},
    {"name": "secret_scan", "status": "pass"}
  ],
  "findings": ["review clean"]
}
```

Collect raw evidence for the reviewer providers required after excluding the
implementer provider:

```bash
export AO_MA10_OPENAI_REVIEW_CMD="python3 -m ao_kernel.ai_review_provider_wrappers codex"
export AO_MA10_ANTHROPIC_REVIEW_CMD="python3 -m ao_kernel.ai_review_provider_wrappers claude"
export AO_MA10_MINIMAX_REVIEW_CMD="python3 -m ao_kernel.ai_review_provider_wrappers mavis"
export AO_MA10_MAVIS_BIN="mavis"  # Optional; set to ~/.mavis/bin/mavis if not on PATH.

ao-kernel ai-review collect \
  --work-package AO-MA-10X \
  --base-ref origin/main \
  --head-ref HEAD \
  --repo-root . \
  --implementer-provider openai \
  --output-dir .ao/ai-review \
  --format json
```

Run bounded ping-pong until unanimous `AGREE`, or fail closed when the maximum
round count is exhausted:

```bash
ao-kernel ai-review consensus \
  --work-package AO-MA-10X \
  --base-ref origin/main \
  --head-ref HEAD \
  --repo-root . \
  --implementer-provider openai \
  --max-rounds 3 \
  --output-dir .ao/ai-review \
  --format json
```

The bundled provider wrappers are the recommended command form:

| Provider | Env command | Runtime notes |
|---|---|---|
| OpenAI/Codex | `python3 -m ao_kernel.ai_review_provider_wrappers codex` | Uses `codex exec --sandbox read-only --output-last-message`; stdout/stderr noise is not trusted as evidence. |
| Anthropic/Claude | `python3 -m ao_kernel.ai_review_provider_wrappers claude` | Uses `claude -p` and extracts fenced or plain JSON. |
| MiniMax/Mavis | `python3 -m ao_kernel.ai_review_provider_wrappers mavis` | Opens a fresh one-shot `mavis` session by default; persistent communication mode is optional via `AO_MA10_MAVIS_MODE=communication` plus explicit session IDs. Fails closed on timeout, stale message, or non-JSON response. |

Each collection/consensus artifact records:

- `command_argv_sha256`,
- redacted command argv,
- `prompt_sha256`,
- context binding (`head_sha`, changed-files digest, changed-file count),
- guard flags fixed to false.

The CLI `--format json` output is deliberately a safe status/provider summary.
Read the durable files under `--output-dir` for full path and provenance data.

## 6. High-Risk Dry-Run Gate Check

After raw reviewer evidence exists, dry-run the high-risk `ao-release-gate`
acceptance path locally:

```bash
ao-kernel ai-review high-risk-dry-run \
  --work-package AO-MA-10X \
  --base-ref origin/main \
  --head-ref HEAD \
  --repo-root . \
  --implementer-provider openai \
  --review-evidence .ao/ai-review/anthropic.local-ai-review-evidence.v1.json \
  --review-evidence .ao/ai-review/minimax.local-ai-review-evidence.v1.json \
  --output-dir .ao/ai-review \
  --format json
```

This writes:

- `high_risk_supersession_evidence.v1.json`,
- `local_gpp_gate_review_evidence.v1.json`,
- `ao_release_gate_decision.v1.json`,
- `ai_review_high_risk_dry_run.v1.json`.

The dry-run proves the local decision-core path. It does not post GitHub
check-runs or attempt a merge; GitHub merge authority remains the repo-owned
required check plus branch ruleset.

## 7. Acceptance Boundary

This quickstart proves the local governed-control-plane workflow is installed
and operational. It does not prove or claim:

- support widening,
- production-platform readiness,
- live adapter execution,
- GitHub ruleset mutation,
- webhook callback delivery,
- cloud hosting,
- provider API execution.

Those remain separate operator-bound supersession decisions.
