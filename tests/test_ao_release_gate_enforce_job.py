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


def test_enforce_job_triggers_on_pr_and_review_never_pull_request_target() -> None:
    block = _gate_job_block()
    workflow = _test_workflow_text()
    stripped = _strip_yaml_comments(block)
    assert "github.event_name == 'pull_request'" in block
    assert "github.event_name == 'pull_request_review'" in block
    assert "pull_request_review:" in workflow
    assert "pull_request_review:$EVENT_ACTION" in workflow
    assert "pull_request_target" not in stripped, "pull_request_target must not appear as a real trigger"
    assert "ao-release-gate only evaluates pull_request or pull_request_review events" in block


def test_enforce_job_permissions_are_minimal_with_checks_write() -> None:
    """The enforce job needs ``checks: write`` for the RG-CONCLUSION-
    SEMANTICS dual check-run publish (POST /repos/{owner}/{repo}/check-runs).
    Every other scope stays read-only. No long-lived secrets, no
    repository write, no PR write, no issue write, no actions write.
    """

    block = _gate_job_block()
    assert "contents: read" in block
    # RG-CONCLUSION-SEMANTICS C-prime: checks API publish needs `write`.
    # `checks: write` also subsumes `checks: read` for the upstream
    # check-runs lookup, so the prior read-only assertion is intentionally
    # superseded here.
    assert "checks: write" in block, "RG-CONCLUSION-SEMANTICS requires checks: write for dual publish"
    assert "pull-requests: read" in block
    for write_scope in (
        "contents: write",
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
    assert "always() && (" in block
    assert "github.event_name == 'pull_request'" in block
    assert "github.event_name == 'pull_request_review'" in block
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


def test_enforce_job_augments_payload_with_review_metadata_after_base_builder() -> None:
    block = _gate_job_block()
    assert 'gh pr view "$PR_NUMBER" --repo "$REPO_FULL" --json reviews,author > pr-reviews.json' in block
    assert "Augment release-gate payload with PR review metadata" in block
    assert 'review_payload = json.loads(Path("pr-reviews.json").read_text' in block
    assert 'payload["pr_author"] = pr_author' in block
    assert 'payload["human_reviews"] = reviews' in block
    assert 'payload["path_sensitive_human_review_enabled"] = True' in block


def test_enforce_job_reads_only_head_sha_free_raw_reviewer_evidence_from_pr_head() -> None:
    """C-prime/AO-MA-10j contract: PR-head inputs are only raw reviewer
    evidence files that carry no head_sha. Head-bound gate evidence and
    high-risk supersession evidence are generated at runtime from trusted
    base code, never read directly from PR head."""
    block = _gate_job_block()
    assert "head/local-ai-review-evidence.v1.json" in block
    assert "pr-files.json" in block
    assert "if not path.exists()" in block
    assert '"local-ai-review-evidence.v1.json" in paths' in block
    assert '[ "$REVIEW_CHANGED" = "true" ]' in block
    assert "head/ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json" in block
    assert "head/ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json" in block
    # Head-bound evidence files must NOT be read from PR head.
    assert "head/local-gpp-gate-evidence.v1.json" not in block
    assert "head/ao-ma-10-high-risk-supersession-evidence.v1.json" not in block


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
    # GOV-1 dynamic work_package binding: workflow no longer hardcodes "GPP-2";
    # it resolves the reviewer-declared work_package and passes it via env.
    assert '--work-package "$REVIEW_WORK_PACKAGE"' in block
    assert '--work-package "GPP-2"' not in block
    assert "Resolve reviewed work package from reviewer evidence" in block
    assert "REVIEW_EVIDENCE_PATH" in block
    assert "if not re.fullmatch" in block
    assert 'payload["reviewed_slice"] = os.environ["REVIEW_WORK_PACKAGE"]' in block
    # The step uses `if:` to skip when no reviewer evidence is committed.
    assert "if: ${{ steps.reviewer.outputs.path != '' }}" in block


def test_enforce_job_generates_high_risk_supersession_evidence_at_runtime() -> None:
    """AO-MA-10j: high-risk autonomous supersession evidence is not a
    committed head-bound artifact. The workflow locates two raw,
    head_sha-free reviewer evidence files and lets trusted base code bind
    them to the live PR SHA/diff before decision evaluation."""

    block = _gate_job_block()
    assert "Locate optional high-risk raw reviewer evidence on PR head" in block
    assert "working-directory: base" in block
    assert "payload.json" in block
    assert "_high_risk_paths(changed_paths)" in block
    assert '[ "$HIGH_RISK_CHANGED" != "true" ]' in block
    assert "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json" in block
    assert "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json" in block
    assert "high-risk supersession evidence requires both OpenAI and Anthropic raw reviewer files" in block
    assert "high-risk supersession raw reviews require root local-ai-review-evidence.v1.json" in block
    assert "Generate high-risk supersession evidence at runtime from raw reviewer evidence" in block
    assert "scripts/ao_ma10_high_risk_supersession_evidence.py" in block
    assert '--review-base-ref "refs/heads/$BASE_REF"' in block
    assert '--review-head-ref "refs/heads/$HEAD_REF"' in block
    assert '--diff-base-ref "$BASE_SHA"' in block
    assert '--diff-head-ref "$HEAD_SHA"' in block
    assert '--output high-risk-supersession-evidence.v1.json' in block


def test_enforce_job_patches_reviewed_slice_before_decision_core() -> None:
    """GOV-1 ordering invariant: the workflow must (a) resolve the
    reviewer-declared work_package, (b) patch payload.reviewed_slice,
    (c) invoke local_gpp_gate.py with the resolved work_package, and
    (d) invoke ao_release_gate_decision.py — strictly in that order.
    Otherwise decision-core's review_evidence.work_package ==
    payload.reviewed_slice binding falls back to the base-supplied
    GPP-2 default and fails any slice whose reviewer evidence declares
    a different work_package."""
    block = _gate_job_block()
    resolve_index = block.find("Resolve reviewed work package from reviewer evidence")
    patch_index = block.find('payload["reviewed_slice"] = os.environ["REVIEW_WORK_PACKAGE"]')
    local_gate_index = block.find("python scripts/local_gpp_gate.py")
    decision_index = block.find("python scripts/ao_release_gate_decision.py")
    assert resolve_index >= 0, "Resolve step must exist"
    assert patch_index >= 0, "reviewed_slice patch must exist"
    assert local_gate_index >= 0, "local_gpp_gate.py invocation must exist"
    assert decision_index >= 0, "ao_release_gate_decision.py invocation must exist"
    assert resolve_index < patch_index < local_gate_index < decision_index, (
        "ordering must be resolve -> patch -> local_gate -> decision_core"
    )


def test_enforce_job_binds_branch_labels_to_runtime_shas_before_invocation() -> None:
    """GPP-2D-3c trusted-base ref-binding (Codex iter-3+4 absorb):
    the base checkout is a detached HEAD at the PR base SHA with
    fetch-depth=1; branch names like 'main' and 'codex/...' are NOT
    guaranteed to exist as local refs. The legacy --base-ref /
    --head-ref alias path the base copy of local_gpp_gate.py uses
    resolves those names through `git diff <base_ref>...<head_ref>`
    and `git rev-parse <head_ref>`, so the names MUST be valid refs.

    The workflow must therefore (a) validate the API-reported branch
    labels with `git check-ref-format`, (b) bind those labels to the
    API-reported runtime SHAs via `git update-ref` BEFORE invoking
    local_gpp_gate.py, and (c) for each label the check-ref-format
    call must precede its update-ref call. Otherwise scope check and
    context_binding fall back to whatever refs happen to exist in
    the detached clone, which is an unstable contract.
    """
    block = _gate_job_block()
    # Both validation calls and both binding calls must exist.
    base_check_index = block.find('git check-ref-format "refs/heads/$BASE_REF"')
    head_check_index = block.find('git check-ref-format "refs/heads/$HEAD_REF"')
    base_update_index = block.find('git update-ref "refs/heads/$BASE_REF" "$BASE_SHA"')
    head_update_index = block.find('git update-ref "refs/heads/$HEAD_REF" "$HEAD_SHA"')
    invocation_index = block.find("python scripts/local_gpp_gate.py")

    assert base_check_index >= 0, "trusted-base ref-binding must validate $BASE_REF with git check-ref-format"
    assert head_check_index >= 0, "trusted-base ref-binding must validate $HEAD_REF with git check-ref-format"
    assert base_update_index >= 0, "trusted-base ref-binding must map $BASE_REF -> $BASE_SHA via git update-ref"
    assert head_update_index >= 0, "trusted-base ref-binding must map $HEAD_REF -> $HEAD_SHA via git update-ref"
    assert invocation_index >= 0, "no local_gpp_gate.py invocation found"

    # Per-label ordering: validate before binding, bind before invocation.
    assert base_check_index < base_update_index, "$BASE_REF check-ref-format must precede its update-ref"
    assert head_check_index < head_update_index, "$HEAD_REF check-ref-format must precede its update-ref"
    assert base_update_index < invocation_index, (
        "$BASE_REF update-ref must execute BEFORE the local_gpp_gate.py invocation"
    )
    assert head_update_index < invocation_index, (
        "$HEAD_REF update-ref must execute BEFORE the local_gpp_gate.py invocation"
    )


def test_enforce_job_passes_fully_qualified_refs_to_local_gpp_gate() -> None:
    """GPP-2D-3c bootstrap-safe ref contract (Codex iter-1+2+4 absorb):
    the workflow runs the base-ref copy of scripts/local_gpp_gate.py,
    which predates the dual-ref --review-* / --diff-* split. Passing
    the dual-ref flags there would parse-error on the base copy and
    silently fail the gate open. Instead the workflow MUST pass the
    fully-qualified local refs (refs/heads/$BASE_REF /
    refs/heads/$HEAD_REF) the previous step bound via `git update-ref`
    through the legacy --base-ref / --head-ref aliases. The base copy
    then:

      * matches scope check by string equality against the committed
        reviewer evidence's scope_reviewed.base_ref / head_ref, which
        also record the same fully-qualified refs/heads/* form (never
        SHAs — committing a SHA would re-introduce the head_sha
        self-reference fixed point this slice closes);
      * resolves the fully-qualified refs unambiguously through git's
        local ref database for `git diff <base>...<head>` and
        `git rev-parse <head>`. Unqualified labels are forbidden here
        because Git's revision-shorthand lookup can drift to a
        same-named tag or other object (iter-4 ambiguity drift).

    Passing $BASE_SHA / $HEAD_SHA into the legacy aliases would
    re-introduce the iter-1 SHA-vs-label string-equality mismatch
    that produced ao_release_gate_review_evidence_not_accepting on
    PR #599 b5ecf65. Passing unqualified $BASE_REF / $HEAD_REF would
    re-open the iter-4 unqualified-revision-lookup drift."""
    block = _gate_job_block()
    invocation_lines: list[str] = []
    current: list[str] = []
    collecting = False
    for line in block.splitlines():
        # Start collecting only at the actual `python scripts/local_gpp_gate.py`
        # command — comment lines that merely reference the script
        # (e.g. "# base/scripts/local_gpp_gate.py runs against ...")
        # must NOT trigger the collector, otherwise unrelated commands
        # higher up in the step (the build_payload invocation's
        # --base-ref / --head-ref) get swept into this slice.
        if line.lstrip().startswith("python scripts/local_gpp_gate.py"):
            collecting = True
        if collecting:
            current.append(line)
            if line.rstrip().endswith("> local-gpp-gate.stdout.log 2>&1 || true"):
                invocation_lines.append("\n".join(current))
                current = []
                collecting = False
    assert invocation_lines, "no local_gpp_gate.py invocation found in the gate job"
    for invocation in invocation_lines:
        assert '--base-ref "refs/heads/$BASE_REF"' in invocation, (
            "workflow must pass refs/heads/$BASE_REF (fully-qualified) into "
            "--base-ref, not $BASE_SHA or the unqualified label. invocation:\n" + invocation
        )
        assert '--head-ref "refs/heads/$HEAD_REF"' in invocation, (
            "workflow must pass refs/heads/$HEAD_REF (fully-qualified) into "
            "--head-ref, not $HEAD_SHA or the unqualified label. invocation:\n" + invocation
        )
        # The SHA env variables must NOT reach the legacy alias — iter-1 bug.
        assert '--base-ref "$BASE_SHA"' not in invocation, (
            "passing $BASE_SHA into --base-ref re-introduces the iter-1 "
            "scope-check string-equality mismatch.\n" + invocation
        )
        assert '--head-ref "$HEAD_SHA"' not in invocation, (
            "passing $HEAD_SHA into --head-ref re-introduces the iter-1 "
            "scope-check string-equality mismatch.\n" + invocation
        )
        # The unqualified label must NOT reach the legacy alias either —
        # iter-4 drift (Git unqualified revision lookup -> tag / object).
        assert '--base-ref "$BASE_REF"' not in invocation, (
            "passing unqualified $BASE_REF into --base-ref re-opens the iter-4 "
            "unqualified-revision-lookup drift; use refs/heads/$BASE_REF.\n" + invocation
        )
        assert '--head-ref "$HEAD_REF"' not in invocation, (
            "passing unqualified $HEAD_REF into --head-ref re-opens the iter-4 "
            "unqualified-revision-lookup drift; use refs/heads/$HEAD_REF.\n" + invocation
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
    runtime_invocations = [line for line in invocations if "--help" not in line]
    assert runtime_invocations, "decision-script runtime invocations missing (only --help probe found)"
    for invocation in runtime_invocations:
        assert "--conclusion-mode enforce" in invocation, (
            f"decision invocation missing --conclusion-mode enforce: {invocation}"
        )
    # RG-CONCLUSION-SEMANTICS C-prime: --wrapper-exit-code replaces
    # --fail-on-deny so a lone CODEOWNER-review-pending blocker maps to
    # exit 0 on the legacy compatibility wrapper. Real violations still
    # exit 1. The companion --emit-multi-check-runs writes the
    # ao-release-gate-{technical,review} artifacts consumed by the
    # publish step. Workflow is bootstrap-safe (RG-1 bootstrap PR runs
    # against a base that predates the new flags), so the new flag names
    # live in shell variable assignments and a legacy --fail-on-deny
    # fallback exists when the base script lacks --wrapper-exit-code.
    assert "--wrapper-exit-code" in block, (
        "RG-CONCLUSION-SEMANTICS C-prime requires --wrapper-exit-code in the enforce job"
    )
    assert "--emit-multi-check-runs check-runs" in block, (
        "RG-CONCLUSION-SEMANTICS dual publish requires --emit-multi-check-runs check-runs"
    )
    assert "--fail-on-deny" in block, "bootstrap-safe fallback for RG-1 base must keep --fail-on-deny available"
    assert "--help" in block and "grep" in block, (
        "bootstrap fallback must probe --help for --wrapper-exit-code support before invoking it"
    )
    has_runtime_evidence_invocation = any(
        "--review-evidence local-gpp-gate-evidence.v1.json" in line for line in runtime_invocations
    )
    assert has_runtime_evidence_invocation, (
        "decision script must consume the runtime-generated gate evidence "
        "(--review-evidence local-gpp-gate-evidence.v1.json), not a head-committed file"
    )
    assert "HIGH_RISK_FLAGS=(--high-risk-supersession-evidence high-risk-supersession-evidence.v1.json)" in block
    assert '"${HIGH_RISK_FLAGS[@]}"' in block
    # The dual check-run publisher runs after the decision step,
    # guarded by a missing-script tolerance for the RG-1 bootstrap path.
    assert "scripts/ao_release_gate_publish_check_runs.py" in block, (
        "RG-CONCLUSION-SEMANTICS C-prime requires the dual check-run publish step"
    )
    assert "--dir check-runs" in collapsed, "publisher must read artifacts from check-runs/"
    assert "ao_release_gate_publish_check_runs.py" in block and "exit 0" in block and "warning" in block.lower(), (
        "publish step must tolerate missing script on RG-1 bootstrap base (warning + exit 0)"
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
    assert "base/high-risk-supersession-evidence.v1.json" in block
