"""Drift-guards for the ao-release-gate enforce job (GPP-2D-3c).

GPP-2D-2c stood up an advisory shadow workflow at
``.github/workflows/ao-release-gate.yml``. PR #594 observed it on a
real PR. GPP-2D-3c retires that file in favor of a single enforce job
inside ``.github/workflows/test.yml`` under the reserved required-check
name ``ao-release-gate``.

Codex C-prime (cross-AI strategic consult, thread ``019e59f7``)
extends the enforce contract with **runtime gate-evidence generation**:
the PR head commits only the raw reviewer evidence
(``local-ai-review-evidence.v1.json``, no ``head_sha`` field), and the
workflow's trusted-base checkout runs
``base/scripts/local_gpp_gate.py`` at CI time to produce the
head-bound ``local-gpp-gate-evidence.v1.json``. This avoids the
``head_sha`` self-reference fixed point that a head-committed gate
evidence file would create.

These tests pin the enforce contract so the shadow's fail-open behavior
cannot regress and the runtime generation step cannot be silently
removed.
"""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _test_workflow_text() -> str:
    return (_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")


def _strip_yaml_comments(text: str) -> str:
    """Return only the non-comment YAML content from ``text``.

    The drift-guards forbid certain tokens (``pull_request_target``,
    ``continue-on-error: true``, etc.) as YAML keys / shell flags, but
    those tokens may legitimately appear in defensive comments that
    explain why the workflow rejects them. This helper strips
    comment-only lines so the forbid-checks operate on real YAML
    structure.
    """

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            in_string = False
            cut = None
            for index, char in enumerate(line):
                if char in ("'", '"'):
                    in_string = not in_string
                elif char == "#" and not in_string:
                    cut = index
                    break
            if cut is not None:
                line = line[:cut].rstrip()
        lines.append(line)
    return "\n".join(lines)


def _gate_job_block() -> str:
    """Slice the ``ao-release-gate:`` job definition out of test.yml."""

    text = _test_workflow_text()
    anchor = text.index("\n  ao-release-gate:\n")
    after = text[anchor + 1 :]
    next_job = re.search(r"\n  [a-z][a-z0-9-]*:\n", after[len("  ao-release-gate:\n") :])
    if next_job is None:
        return after
    return after[: len("  ao-release-gate:\n") + next_job.start()]


def test_shadow_workflow_file_is_retired() -> None:
    """The GPP-2D-2c advisory shadow workflow is retired in this slice;
    only the test.yml-resident enforce job remains."""
    assert not (_repo_root() / ".github" / "workflows" / "ao-release-gate.yml").exists()


def test_enforce_job_is_present_under_reserved_required_check_name() -> None:
    """The enforce job lives inside test.yml under the stable
    required-check name ``ao-release-gate``."""
    block = _gate_job_block()
    assert "name: ao-release-gate\n" in block
    assert "name: ao-release-gate-shadow" not in _test_workflow_text()


def test_enforce_job_triggers_only_on_pull_request_never_pull_request_target() -> None:
    block = _gate_job_block()
    stripped = _strip_yaml_comments(block)
    assert "github.event_name == 'pull_request'" in block
    assert "pull_request_target" not in stripped, "pull_request_target must not appear as a real trigger"
    assert "ao-release-gate only evaluates pull_request events" in block


def test_enforce_job_permissions_are_read_only() -> None:
    block = _gate_job_block()
    assert "contents: read" in block
    assert "checks: read" in block
    assert "pull-requests: read" in block
    for write_scope in (
        "contents: write",
        "checks: write",
        "pull-requests: write",
        "issues: write",
        "actions: write",
    ):
        assert write_scope not in block, f"unexpected write permission: {write_scope}"


def test_enforce_job_uses_only_github_token_no_long_lived_secrets() -> None:
    block = _gate_job_block()
    assert "${{ github.token }}" in block
    for forbidden in (
        "AO_GITHUB_APP_PRIVATE_KEY",
        "AO_RELEASE_GATE_WEBHOOK_SECRET",
        "GHCR_TOKEN",
        "AO_CLAUDE_CODE_CLI_AUTH",
        "secrets.PAT",
        "secrets.PRIVATE_KEY",
    ):
        assert forbidden not in block, f"unexpected long-lived secret: {forbidden}"


def test_enforce_job_carries_no_continue_on_error() -> None:
    """The enforce contract removes the shadow's advisory fail-open
    behavior: no `continue-on-error: true` anywhere in the job."""
    block = _gate_job_block()
    stripped = _strip_yaml_comments(block)
    assert "continue-on-error: true" not in stripped


def test_enforce_job_runs_with_fail_closed_needs_short_circuit() -> None:
    """`if: always()` + (should_run OR event-gate result != success)
    plus an early step that inspects every required `needs.*.result`
    and exits 1 with a fail-closed audit artifact when any one is not
    `success`."""
    block = _gate_job_block()
    assert "always() && github.event_name == 'pull_request'" in block
    assert "needs.event-gate.outputs.should_run == 'true'" in block
    assert "needs.event-gate.result != 'success'" in block
    assert "Fail closed if any required CI job did not succeed" in block
    for needed in (
        "needs.event-gate.result",
        "needs.lint.result",
        "needs.typecheck.result",
        "needs.test.result",
        "needs.coverage.result",
        "needs.packaging-smoke.result",
        "needs.policy-container-smoke.result",
        "needs.release-gate-container-smoke.result",
    ):
        assert needed in block, f"fail-closed needs short-circuit missing {needed}"
    assert "ao_release_gate_upstream_required_check_failed" in block
    assert "exit 1" in block


def test_enforce_job_checks_out_protected_base_ref() -> None:
    block = _gate_job_block()
    assert "ref: ${{ github.event.pull_request.base.sha }}" in block
    assert "path: base" in block
    assert "scripts/ao_release_gate_decision.py" in block
    assert "scripts/ao_release_gate_build_payload.py" in block
    assert ".claude/plans/gpp_status.v1.json" in block


def test_enforce_job_builds_payload_from_api_not_pr_committed_json() -> None:
    block = _gate_job_block()
    assert "gh pr view" in block
    assert "gh api" in block and "/check-runs" in block
    assert "--pr-files-json pr-files.json" in block
    assert "--check-runs-json check-runs.json" in block
    assert "--gpp-status .claude/plans/gpp_status.v1.json" in block
    assert "head/payload.json" not in block


def test_enforce_job_reads_only_raw_reviewer_evidence_from_pr_head() -> None:
    """C-prime contract: the only PR-head input is the raw reviewer
    evidence file `local-ai-review-evidence.v1.json`. The
    head-bound gate evidence file (`local-gpp-gate-evidence.v1.json`)
    is NEVER read from the PR head — it would create the head_sha
    self-reference problem."""
    block = _gate_job_block()
    assert "head/local-ai-review-evidence.v1.json" in block
    # The head-bound gate evidence file must NOT be read from PR head.
    assert "head/local-gpp-gate-evidence.v1.json" not in block


def test_enforce_job_generates_gate_evidence_at_runtime_from_reviewer_evidence() -> None:
    """C-prime contract: a workflow step runs
    `base/scripts/local_gpp_gate.py` at CI time to produce the
    head-bound `local-gpp-gate-evidence.v1.json` from the untrusted
    PR-head reviewer evidence + the actual git diff. The output lives
    under `base/` (so the decision script's working directory finds
    it), is generated with the runtime resolved head SHA, and is
    therefore binding-equality consistent with the API-derived
    payload."""
    block = _gate_job_block()
    assert "Generate local-gpp-gate evidence at runtime from reviewer evidence" in block
    assert "scripts/local_gpp_gate.py" in block
    assert "--review-evidence" in block and "local-ai-review-evidence.v1.json" in block
    assert "--output local-gpp-gate-evidence.v1.json" in block
    assert '--work-package "GPP-2"' in block
    # The step uses `if:` to skip when no reviewer evidence is committed.
    assert "if: ${{ steps.reviewer.outputs.path != '' }}" in block


def test_enforce_job_passes_dual_ref_split_to_local_gpp_gate() -> None:
    """GPP-2D-3c dual-ref contract (Codex iter-1 absorb): the workflow
    must pass --review-base-ref / --review-head-ref using the PR base /
    head BRANCH NAMES (matched against committed reviewer evidence
    scope_reviewed.base_ref / head_ref), and --diff-base-ref /
    --diff-head-ref using the runtime base / head SHAs (drive git diff
    + context_binding.head_sha). Mixing them re-creates the head_sha
    self-reference fixed point or a scope-check mismatch."""
    block = _gate_job_block()
    assert '--review-base-ref "$BASE_REF"' in block, "workflow must pass the PR base BRANCH NAME as --review-base-ref"
    assert '--review-head-ref "$HEAD_REF"' in block, "workflow must pass the PR head BRANCH NAME as --review-head-ref"
    assert '--diff-base-ref "$BASE_SHA"' in block, "workflow must pass the runtime base SHA as --diff-base-ref"
    assert '--diff-head-ref "$HEAD_SHA"' in block, "workflow must pass the runtime head SHA as --diff-head-ref"
    # The legacy single-ref alias must NOT be passed alongside the dual
    # split for the local_gpp_gate.py invocation in this gate. The
    # legacy alias would make the script default review-* and diff-*
    # to the same value, re-introducing the original bug.
    invocation_lines: list[str] = []
    current: list[str] = []
    collecting = False
    for line in block.splitlines():
        if "scripts/local_gpp_gate.py" in line:
            collecting = True
        if collecting:
            current.append(line)
            if line.rstrip().endswith("> local-gpp-gate.stdout.log 2>&1 || true"):
                invocation_lines.append("\n".join(current))
                current = []
                collecting = False
    assert invocation_lines, "no local_gpp_gate.py invocation found in the gate job"
    for invocation in invocation_lines:
        assert '--base-ref "$BASE_SHA"' not in invocation, (
            "legacy --base-ref alias must not be used inside the dual-ref invocation"
        )
        assert '--head-ref "$HEAD_SHA"' not in invocation, (
            "legacy --head-ref alias must not be used inside the dual-ref invocation"
        )


def test_enforce_job_uses_per_page_check_runs_not_paginate() -> None:
    block = _gate_job_block()
    assert "check-runs?per_page=100" in block
    for line in block.splitlines():
        if "/check-runs" in line and "gh api" in line:
            assert "--paginate" not in line, "check-runs fetch must not use --paginate"


def test_enforce_job_passes_explicit_required_check_allowlist_to_builder() -> None:
    block = _gate_job_block()
    for required in (
        "--required-check lint",
        "--required-check typecheck",
        '--required-check "test (3.11)"',
        '--required-check "test (3.12)"',
        '--required-check "test (3.13)"',
        "--required-check coverage",
        "--required-check packaging-smoke",
        "--required-check policy-container-smoke",
        "--required-check release-gate-container-smoke",
    ):
        assert required in block, f"builder allowlist missing {required}"


def test_enforce_job_passes_runtime_generated_evidence_to_decision_script() -> None:
    """The decision script reads the **runtime-generated** gate
    evidence file (base/local-gpp-gate-evidence.v1.json), not a
    PR-head-committed gate evidence file. Pinning this prevents a
    future regression that flips back to the head_sha self-reference
    pattern."""
    block = _gate_job_block()
    collapsed = re.sub(r"\\\n\s+", " ", block)
    invocations = [line for line in collapsed.splitlines() if "scripts/ao_release_gate_decision.py" in line]
    assert invocations, "no decision-script invocations found"
    for invocation in invocations:
        assert "--conclusion-mode enforce" in invocation, (
            f"decision invocation missing --conclusion-mode enforce: {invocation}"
        )
        assert "--fail-on-deny" in invocation, f"decision invocation missing --fail-on-deny: {invocation}"
    has_runtime_evidence_invocation = any(
        "--review-evidence local-gpp-gate-evidence.v1.json" in line for line in invocations
    )
    assert has_runtime_evidence_invocation, (
        "decision script must consume the runtime-generated gate evidence "
        "(--review-evidence local-gpp-gate-evidence.v1.json), not a head-committed file"
    )


def test_enforce_job_uses_synthesizer_only_for_pre_decision_crash_path() -> None:
    block = _gate_job_block()
    assert "Synthesize error_fail_closed audit artifact if pre-decision step crashed" in block
    assert "if [ ! -f decision.json ]" in block
    assert "ao_release_gate_synthesize_error_decision.py decision.json" in block
    anchor = block.index("Synthesize error_fail_closed audit artifact if pre-decision step crashed")
    after = block[anchor:]
    next_step = after.find("\n      - name:", 1)
    synth_block = after[: next_step if next_step != -1 else len(after)]
    assert "\n          exit 0" not in synth_block, (
        "synthesizer step must not exit 0 — the prior failed step is what fails the job"
    )


def test_enforce_job_uploads_decision_audit_artifact() -> None:
    """Every enforce run uploads payload.json + decision.json plus the
    runtime-generated gate evidence and the local-gpp-gate stdout log
    so operators can audit the full chain after the fact."""
    block = _gate_job_block()
    assert "actions/upload-artifact@v7" in block
    assert "base/payload.json" in block
    assert "base/decision.json" in block
    assert "base/local-gpp-gate-evidence.v1.json" in block
    assert "base/local-gpp-gate.stdout.log" in block
