"""Drift-guards for the ao-release-gate enforce job (GPP-2D-3b).

GPP-2D-2c stood up an advisory shadow workflow in
``.github/workflows/ao-release-gate.yml``. PR #594 observed it on a
real PR. GPP-2D-3 retires that file in favor of a single enforce job
inside ``.github/workflows/test.yml`` under the reserved required-check
name ``ao-release-gate``. These tests pin the enforce contract so the
shadow-style fail-open behavior cannot regress.
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
    # The job block runs from `  ao-release-gate:` to either the next
    # top-level job (`  <name>:` at column 2) or end-of-file.
    next_job = re.search(r"\n  [a-z][a-z0-9-]*:\n", after[len("  ao-release-gate:\n") :])
    if next_job is None:
        return after
    return after[: len("  ao-release-gate:\n") + next_job.start()]


def test_shadow_workflow_file_is_retired() -> None:
    """The GPP-2D-2c advisory shadow workflow is retired in this slice;
    only the test.yml-resident enforce job remains."""
    assert not (_repo_root() / ".github" / "workflows" / "ao-release-gate.yml").exists()


def test_synthesizer_script_is_enforce_aware_not_retired() -> None:
    """The synthesizer survives as an enforce-aware audit safety net.
    Default conclusion mode is ``shadow`` (backward compat for any
    legacy advisory caller); the enforce workflow steps pass
    ``--conclusion-mode enforce`` explicitly."""
    script = _repo_root() / "scripts" / "ao_release_gate_synthesize_error_decision.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "--conclusion-mode" in text
    assert "--reason" in text
    assert "--finding-code" in text
    # Default kept shadow so a legacy advisory caller doesn't accidentally
    # flip to enforce semantics; the enforce workflow opts in explicitly.
    assert 'default="shadow"' in text


def test_enforce_job_is_present_under_reserved_required_check_name() -> None:
    """The enforce job lives inside test.yml under the stable
    required-check name ``ao-release-gate``."""
    block = _gate_job_block()
    assert "name: ao-release-gate\n" in block
    # Belt-and-suspenders: no advisory `ao-release-gate-shadow` alias
    # is reintroduced in the same file.
    assert "name: ao-release-gate-shadow" not in _test_workflow_text()


def test_enforce_job_triggers_only_on_pull_request_never_pull_request_target() -> None:
    """The enforce job is restricted to pull_request events; the
    pull_request_target unsafe variant is rejected by the defensive
    event guard."""
    block = _gate_job_block()
    stripped = _strip_yaml_comments(block)
    assert "github.event_name == 'pull_request'" in block
    assert "pull_request_target" not in stripped, "pull_request_target must not appear as a real trigger"
    assert "ao-release-gate only evaluates pull_request events" in block


def test_enforce_job_permissions_are_read_only() -> None:
    """The enforce job runs with read-only permissions only."""
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
    """The enforce job uses only the ephemeral GITHUB_TOKEN; no
    long-lived secret (PAT / PEM / webhook secret) is referenced."""
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
    """The job runs under `if: always()` so a red `needs:` matrix
    cannot silently skip it. An early step inspects every required
    `needs.*.result` and short-circuits with a fail-closed audit
    artifact + exit 1 when any one is not `success`. event-gate is
    included so an event-gate failure also produces failure, not skip.
    """
    block = _gate_job_block()
    assert "if: always() && needs.event-gate.outputs.should_run == 'true'" in block
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
    # The short-circuit step exits 1 explicitly so the job posts
    # `failure`, not `skipped`.
    assert "exit 1" in block


def test_enforce_job_checks_out_protected_base_ref() -> None:
    """Trusted-base gate (design §3.2): the decision-core code,
    schemas, and gpp_status.v1.json come from the PR base SHA, never
    the PR head."""
    block = _gate_job_block()
    assert "ref: ${{ github.event.pull_request.base.sha }}" in block
    assert "path: base" in block
    assert "scripts/ao_release_gate_decision.py" in block
    assert "scripts/ao_release_gate_build_payload.py" in block
    assert ".claude/plans/gpp_status.v1.json" in block


def test_enforce_job_builds_payload_from_api_not_pr_committed_json() -> None:
    """Untrusted PR input (design §3.3): the payload is built from the
    GitHub API + base-ref gpp_status, never from a PR-committed JSON
    file."""
    block = _gate_job_block()
    assert "gh pr view" in block
    assert "gh api" in block and "/check-runs" in block
    assert "--pr-files-json pr-files.json" in block
    assert "--check-runs-json check-runs.json" in block
    assert "--gpp-status .claude/plans/gpp_status.v1.json" in block
    assert "head/payload.json" not in block


def test_enforce_job_reads_review_evidence_only_from_pr_head() -> None:
    """The review evidence is the only PR-head input; the decision core
    validates it hard against the bundled schema + acceptance profile."""
    block = _gate_job_block()
    assert "head/local-gpp-gate-evidence.v1.json" in block
    assert "--review-evidence" in block


def test_enforce_job_uses_per_page_check_runs_not_paginate() -> None:
    """The check-runs API endpoint returns an object; `--paginate`
    against an object endpoint concatenates page objects and breaks
    json.loads. Single-page per_page=100 (gh's max) is the correct
    pattern."""
    block = _gate_job_block()
    assert "check-runs?per_page=100" in block
    for line in block.splitlines():
        if "/check-runs" in line and "gh api" in line:
            assert "--paginate" not in line, "check-runs fetch must not use --paginate"


def test_enforce_job_passes_explicit_required_check_allowlist_to_builder() -> None:
    """GPP-2D-3 + observation (b): the builder is invoked with an
    explicit ``--required-check`` allowlist matching the job's
    `needs:` graph. Advisory / non-blocking jobs (extras-install,
    benchmark-fast, scorecard) are not on this list and therefore
    cannot block the gate via their pending or failing state."""
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


def test_enforce_job_passes_conclusion_mode_enforce_and_fail_on_deny_to_decision() -> None:
    """The decision script is invoked with both --conclusion-mode
    enforce (so the artifact body's github_check_run.conclusion is
    `failure` on deny/error) AND --fail-on-deny (so the script exits 1
    and the job posts `failure`)."""
    block = _gate_job_block()
    collapsed = re.sub(r"\\\n\s+", " ", block)
    invocations = [line for line in collapsed.splitlines() if "scripts/ao_release_gate_decision.py" in line]
    assert invocations, "no decision-script invocations found"
    for invocation in invocations:
        assert "--conclusion-mode enforce" in invocation, (
            f"decision invocation missing --conclusion-mode enforce: {invocation}"
        )
        assert "--fail-on-deny" in invocation, f"decision invocation missing --fail-on-deny: {invocation}"


def test_enforce_job_uses_synthesizer_only_for_pre_decision_crash_path() -> None:
    """The synthesizer step is reachable on `if: always()` and writes a
    fail-CLOSED artifact only when ``decision.json`` is missing — i.e.
    a pre-decision step crashed before the decision script ran. It
    does NOT alter the job exit code; any earlier step's failure
    already marks the job failed."""
    block = _gate_job_block()
    assert "Synthesize error_fail_closed audit artifact if pre-decision step crashed" in block
    assert "if [ ! -f decision.json ]" in block
    assert "ao_release_gate_synthesize_error_decision.py decision.json" in block
    # The synthesizer step body explicitly does NOT carry an `exit 0`
    # that would mask the prior step's failure.
    anchor = block.index("Synthesize error_fail_closed audit artifact if pre-decision step crashed")
    after = block[anchor:]
    next_step = after.find("\n      - name:", 1)
    synth_block = after[: next_step if next_step != -1 else len(after)]
    assert "\n          exit 0" not in synth_block, (
        "synthesizer step must not exit 0 — the prior failed step is what fails the job"
    )


def test_enforce_job_uploads_decision_audit_artifact() -> None:
    """Every enforce run uploads payload.json + decision.json so
    operators can audit the gate decision after the fact."""
    block = _gate_job_block()
    assert "actions/upload-artifact@v7" in block
    assert "base/payload.json" in block
    assert "base/decision.json" in block
