# E-3-3 — Advisory CI Matrix Workflow

> V5 Epic 3 support-widening matrix infrastructure slice. This record is
> advisory-only infrastructure and does not widen support, claim production
> readiness, execute live adapters, mutate required workflows, or mutate GitHub
> rulesets.

## Status

- **Work package:** E-3-3
- **Issue:** #855
- **Branch:** `codex/epic3-e3-ci-matrix`
- **Risk:** medium
- **Authority:** `.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md`
- **Guard flags:** unchanged:
  - `support_widening_allowed=false`
  - `production_platform_claim_allowed=false`
  - `live_adapter_execution_allowed=false`

## Added Surface

E-3-3 adds `.github/workflows/support-matrix-smoke.yml`, an opt-in advisory
workflow that runs the E-3-2 stub-only smoke harness across all five E-3-1
surface classes:

- `provider`
- `python_version`
- `os_platform`
- `db_backend`
- `deployment_topology`

The workflow can run in two ways only:

1. `workflow_dispatch` manual operator opt-in.
2. `pull_request` events when the PR carries the `support-matrix-smoke` label.

The workflow writes per-surface `support_widening_evidence.v1` artifacts as
GitHub Actions artifacts and writes an advisory job summary. On labeled PR runs,
it also posts a top-level PR review comment through `pulls.createReview` using
only `pull-requests: write`.

## Non-Authority Boundary

This workflow is explicitly not a release gate:

- It is not added to branch protection.
- It is not a required check.
- It uses `continue-on-error: true`.
- It emits simulated-only evidence from the E-3-2 stub harness.
- It does not use secrets, environments, provider credentials, or live network
  calls.
- It cannot flip any guard flag.

Epic 9 remains the only place where support widening can be authorized, and that
future path requires an operator-bound supersession PR plus the E-3-6
recompute-not-trust validator.

## Machine Invariants

`tests/test_support_matrix_smoke_workflow.py` pins the E-3-3 contract:

- Trigger shape is exactly `pull_request` types
  `[opened, labeled, synchronize, reopened]` plus `workflow_dispatch`.
- No `push`, `repository_dispatch`, `schedule`, `pull_request_target`, or
  trigger-level label filter exists.
- Every job contains the combined dispatch/label gate:
  `github.event_name == 'workflow_dispatch' ||
  contains(github.event.pull_request.labels.*.name, 'support-matrix-smoke')`.
- The matrix matches `SURFACE_CLASSES`.
- The workflow invokes `scripts/run_support_smoke.py --surface ... --evidence-out ...`.
- Permissions are exactly `contents: read` and `pull-requests: write`.
- No `secrets.` expression or `environment:` binding exists.
- No guard-flag true literal exists.
- Existing required workflows and ruleset files are not modified.
- Workflow and job names do not collide with existing required workflow names.
- When GitHub API auth is available, live ruleset required contexts are checked
  for `support-matrix-smoke` collisions.

## Validation Plan

Minimum local validation before merge:

```bash
python3 -m json.tool local-ai-review-evidence.v1.json
pytest tests/test_support_matrix_smoke_workflow.py -q
ruff check tests/test_support_matrix_smoke_workflow.py
mypy tests/test_support_matrix_smoke_workflow.py
git diff --check origin/main...HEAD
python3 scripts/gpp_next.py
```

Cross-provider review evidence must confirm that E-3-3 remains advisory and
does not mutate protected workflows or rulesets.
