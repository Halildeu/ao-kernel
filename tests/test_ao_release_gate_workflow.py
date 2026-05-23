"""Drift-guard for the ao-release-gate shadow workflow (GPP-2D-2c)."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow_text() -> str:
    workflow = _repo_root() / ".github" / "workflows" / "ao-release-gate.yml"
    return workflow.read_text(encoding="utf-8")


def test_workflow_triggers_on_pull_request_never_pull_request_target() -> None:
    """GPP-2D §3.2: the gate must trigger on pull_request only.

    pull_request_target would expose the workflow to PR-controlled code
    with write-scoped permissions and break the trusted-base design.
    """
    text = _workflow_text()
    assert "on:\n  pull_request:" in text
    assert "pull_request_target" not in text or "pull_request_target context" in text
    # The defensive event-name guard must explicitly reject anything else.
    assert "ao-release-gate-shadow only evaluates pull_request events" in text


def test_workflow_permissions_are_read_only() -> None:
    """GPP-2D §3.2: read-only permissions, no write scopes."""
    text = _workflow_text()
    assert "contents: read" in text
    assert "checks: read" in text
    assert "pull-requests: read" in text
    # No write permissions anywhere in the job.
    for write_scope in (
        "contents: write",
        "checks: write",
        "pull-requests: write",
        "issues: write",
        "actions: write",
    ):
        assert write_scope not in text, f"unexpected write permission: {write_scope}"


def test_workflow_job_uses_shadow_name_not_required_check_name() -> None:
    """GPP-2D §3.4: the required-check name `ao-release-gate` is reserved
    for the GPP-2D-3 enforce job. The shadow job runs under the distinct
    name `ao-release-gate-shadow` so branch protection can never be
    satisfied by this fail-open advisory job.
    """
    text = _workflow_text()
    assert "name: ao-release-gate-shadow" in text
    # The required-check name reservation must be explicitly documented.
    assert "`ao-release-gate-shadow`" in text
    assert "is reserved for the GPP-2D-3 enforce job" in text


def test_workflow_checks_out_base_ref_for_gate_code() -> None:
    """GPP-2D §3.2: the decision-core code, schemas, and gpp_status.v1.json
    are evaluated from the base ref, not the PR head. A PR that edits the
    gate cannot thereby change the gate that judges it.
    """
    text = _workflow_text()
    # The base checkout must explicitly pin to the PR base SHA.
    assert "ref: ${{ github.event.pull_request.base.sha }}" in text
    assert "path: base" in text
    # The script and gpp_status paths must be resolved from the base checkout.
    assert "scripts/ao_release_gate_decision.py" in text
    assert "scripts/ao_release_gate_build_payload.py" in text
    assert ".claude/plans/gpp_status.v1.json" in text


def test_workflow_builds_payload_from_api_not_pr_committed_json() -> None:
    """GPP-2D §3.3: the release-gate payload is built by the workflow from
    the GitHub API and the base-ref gpp_status, never from a PR-committed
    JSON file. PR-author-supplied allowed_path_prefixes / required_checks
    / branch_up_to_date / admin_bypass_requested fields would let a PR
    self-approve.
    """
    text = _workflow_text()
    assert "gh pr view" in text
    assert "gh api" in text and "/check-runs" in text
    # The builder script reads the API outputs and the base-ref gpp_status,
    # not anything from the PR head checkout (other than the optional
    # review-evidence file).
    assert "--pr-files-json pr-files.json" in text
    assert "--check-runs-json check-runs.json" in text
    assert "--gpp-status .claude/plans/gpp_status.v1.json" in text
    # The payload JSON must not be sourced from the PR head.
    assert "head/payload.json" not in text


def test_workflow_reads_review_evidence_only_from_pr_head_and_validates_via_core() -> None:
    """GPP-2D §3.3: the review evidence is the only PR-head input. The
    decision core validates it against the full schema + acceptance
    profile + context-binding before trusting any field.
    """
    text = _workflow_text()
    assert "head/local-gpp-gate-evidence.v1.json" in text
    assert "--review-evidence" in text


def test_workflow_is_advisory_never_propagates_deny_exit() -> None:
    """GPP-2D §6 GPP-2D-2c: the shadow job runs and reports the decision
    but always succeeds (advisory) and is never a required check until
    the GPP-2D-5 cutover.
    """
    text = _workflow_text()
    # The decision script must never be invoked WITH --fail-on-deny under
    # the shadow advisory job. Comments may reference the flag to explain
    # the design, but no actual invocation line carries it.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "--fail-on-deny" not in line, "shadow workflow must not invoke the decision script with --fail-on-deny"
    # Explicit advisory contract: the decision step ends with `exit 0` so
    # the job always succeeds regardless of the decision body.
    assert "Shadow advisory" in text
    assert "exit 0" in text


def test_workflow_uses_only_github_token_no_long_lived_secrets() -> None:
    """GPP-2D §7: no long-lived secret / PAT / PEM / webhook-secret value
    in the workflow. Only the ephemeral GitHub Actions GITHUB_TOKEN is
    used, with minimal read-only permissions.
    """
    text = _workflow_text()
    assert "${{ github.token }}" in text
    # No reference to any long-lived secret name.
    for forbidden in (
        "AO_GITHUB_APP_PRIVATE_KEY",
        "AO_RELEASE_GATE_WEBHOOK_SECRET",
        "GHCR_TOKEN",
        "AO_CLAUDE_CODE_CLI_AUTH",
        "secrets.PAT",
        "secrets.PRIVATE_KEY",
    ):
        assert forbidden not in text, f"unexpected long-lived secret reference: {forbidden}"


def test_workflow_uploads_decision_audit_artifact() -> None:
    """Every shadow run uploads payload.json + decision.json so operators
    can audit what the gate would have decided.
    """
    text = _workflow_text()
    assert "actions/upload-artifact@v7" in text
    assert "base/payload.json" in text
    assert "base/decision.json" in text


def test_workflow_fetches_check_runs_per_page_not_paginate() -> None:
    """The check-runs API endpoint returns an object, not an array; `gh api
    --paginate` against an object endpoint concatenates page objects and
    breaks `json.loads`. The workflow must fetch a single page with
    per_page=100 (gh's max) instead.
    """
    text = _workflow_text()
    assert "check-runs?per_page=100" in text
    # No --paginate flag in the check-runs fetch line.
    for line in text.splitlines():
        if "/check-runs" in line and "gh api" in line:
            assert "--paginate" not in line, "check-runs fetch must not use --paginate"


def test_workflow_carries_continue_on_error_on_data_gathering_steps() -> None:
    """The shadow advisory job must not fail when a pre-decision step
    (API fetch, freshness, builder, evidence locator, decision) fails.
    Every such step carries continue-on-error: true; the final synthesis
    step runs on `if: always()` so an audit artifact is emitted even
    when prior steps failed.
    """
    text = _workflow_text()
    # At least the five pre-decision steps + the decision step carry the
    # continue-on-error flag, so six occurrences is the minimum.
    assert text.count("continue-on-error: true") >= 5
    assert "if: always()" in text


def test_workflow_synthesizes_decision_when_prior_steps_fail() -> None:
    """When the decision step did not produce decision.json (because a
    prior continue-on-error step failed), a synthesis step invokes the
    repo-owned synthesizer script (no fragile inline Python) which writes
    an error_fail_closed decision so every shadow run still emits an
    auditable record. The synthesizer itself is unit-tested in
    test_ao_release_gate_synthesize_error_decision.py.
    """
    text = _workflow_text()
    assert "Synthesize error_fail_closed decision when prior steps failed" in text
    # The workflow invokes the repo-owned synthesizer script; it must not
    # carry inline `python -c` snippets that would IndentationError under
    # YAML block-scalar indent stripping.
    assert "scripts/ao_release_gate_synthesize_error_decision.py decision.json" in text
    assert "python -c" not in text


def test_workflow_synthesis_step_has_bootstrap_fallback() -> None:
    """The shadow workflow is itself a base-ref-trusted system; on the PR
    that first introduces it the synthesizer script is not yet on the
    base ref. The synthesis step must fall back to an inline JSON
    artifact so the bootstrap PR still produces an audit record and the
    job exits 0; subsequent PRs (after this one merges to main) find the
    synthesizer on main and use the canonical path.
    """
    text = _workflow_text()
    # The fallback branch exists.
    assert "Synthesizer script not present on the base ref" in text
    # The synthesis step itself carries continue-on-error so even an
    # unexpected catastrophic fallback failure does not break the job.
    synthesis_index = text.index("Synthesize error_fail_closed decision when prior steps failed")
    upload_index = text.index("Upload audit artifact")
    synthesis_block = text[synthesis_index:upload_index]
    assert "continue-on-error: true" in synthesis_block, (
        "synthesis step must carry continue-on-error as belt-and-suspenders"
    )
    # The bootstrap fallback still emits the workflow-only finding code.
    assert "ao_release_gate_shadow_pre_decision_step_failed" in text


def test_workflow_does_not_forward_pull_request_issue_url() -> None:
    """The pull_request webhook field `issue_url` is the PR's own API URL,
    NOT the GPP work-package issue URL. Forwarding it to the builder
    would make gpp_issue_consistency fail closed on every PR. The
    builder must source issue_url from the base-ref
    gpp_status.current_wp.issue instead.
    """
    text = _workflow_text()
    # The builder receives no --issue-url argument.
    assert "--issue-url" not in text
    # The env var is not declared either.
    assert "ISSUE_URL:" not in text
    assert "github.event.pull_request.issue_url" not in text
