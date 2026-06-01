"""AO-MA-11A-2 workflow YAML invariants."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ao-ma-11a-plan-approval.yml"


def _read() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_exists():
    assert _WORKFLOW_PATH.is_file()


def test_workflow_dispatch_only():
    content = _read()
    assert "workflow_dispatch:" in content
    assert "schedule:" not in content
    # No push trigger
    assert not re.search(r"^on:\s*\n\s*push:", content, re.MULTILINE)


def test_workflow_has_all_7_required_inputs():
    content = _read()
    inputs = (
        "confirmation",
        "plan_path",
        "consensus_bundle_path",
        "approval_request_path",
        "plan_digest",
        "consensus_bundle_sha256",
        "approval_request_sha256",
    )
    for inp in inputs:
        assert re.search(rf"^\s*{inp}:", content, re.MULTILINE), f"missing input: {inp}"


def test_workflow_all_inputs_required_true():
    content = _read()
    inputs = (
        "confirmation",
        "plan_path",
        "consensus_bundle_path",
        "approval_request_path",
        "plan_digest",
        "consensus_bundle_sha256",
        "approval_request_sha256",
    )
    for inp in inputs:
        pattern = rf"{inp}:[\s\S]{{0,300}}?required:\s*true"
        assert re.search(pattern, content), f"input {inp} not required:true"


def test_workflow_permissions_no_contents_write():
    """Codex iter-2 Binding 3 absorb: artifact-only emission; no contents:write."""
    content = _read()
    perms_block = re.search(r"permissions:\s*\n([\s\S]+?)\njobs:", content)
    assert perms_block, "missing permissions block"
    perms_text = perms_block.group(1)
    assert "contents: read" in perms_text
    assert "actions: read" in perms_text
    assert "deployments: read" in perms_text
    assert "contents: write" not in perms_text


def test_workflow_two_jobs_validate_and_approve():
    content = _read()
    assert re.search(r"^\s*validate:", content, re.MULTILINE)
    assert re.search(r"^\s*approve:", content, re.MULTILINE)


def test_workflow_approve_needs_validate():
    content = _read()
    assert re.search(r"approve:[\s\S]{0,200}?needs:\s*validate", content)


def test_workflow_approve_environment_set():
    content = _read()
    assert re.search(
        r"approve:[\s\S]{0,1500}?environment:\s*ao-ma-plan-approval",
        content,
    )


def test_workflow_approve_has_10_condition_compound_gate():
    """Codex iter-2 Blocker 1 absorb: 10-condition compound apply gate."""
    content = _read()
    apply_if = re.search(
        r"approve:[\s\S]{0,2500}?if:\s*\|([\s\S]{0,2000}?)runs-on:",
        content,
    )
    assert apply_if, "approve job missing compound if: block"
    if_text = apply_if.group(1)
    required = [
        "github.ref == 'refs/heads/main'",
        "github.event_name == 'workflow_dispatch'",
        "github.run_attempt == 1",
        "inputs.confirmation == 'AO-MA-11A-2-APPROVE'",
        "inputs.plan_path != ''",
        "inputs.consensus_bundle_path != ''",
        "inputs.approval_request_path != ''",
        "inputs.plan_digest != ''",
        "inputs.consensus_bundle_sha256 != ''",
        "inputs.approval_request_sha256 != ''",
    ]
    for cond in required:
        assert cond in if_text, f"missing condition: {cond}"


def test_workflow_approve_has_environment_preflight():
    content = _read()
    assert re.search(r"Environment preflight verify", content)
    assert "required_reviewers" in content
    assert ".reviewers[?]" in content or "reviewers[]?" in content


def test_workflow_uploads_artifacts():
    content = _read()
    assert "actions/upload-artifact" in content
    assert "validate_report" in content
    assert "plan_approval_gate" in content


def test_workflow_no_admin_or_ruleset_mutation():
    content = _read()
    assert "--admin" not in content
    assert "ruleset" not in content.lower()
    assert "force-push" not in content.lower()
