"""AO-MA-11E-2b workflow YAML invariants.

Pins:
- workflow_dispatch only (no schedule, no push) — Codex iter-1 §4
- 4 inputs: dry_run + allow_apply + confirmation + accepted_dry_run_report_digest
- Apply job 7-condition compound `if:` gate
- environment: ao-ma-mirror-sync set for apply job
- Environment preflight step before any write
- Post-drift verification after apply
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ao-ma-11e-2b-mirror-sync.yml"


def _read() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_exists() -> None:
    assert _WORKFLOW_PATH.is_file()


def test_workflow_dispatch_only_trigger() -> None:
    """Only workflow_dispatch trigger; no schedule/push to prevent autonomous run."""
    content = _read()
    assert "workflow_dispatch:" in content
    # No schedule
    assert "schedule:" not in content
    # No push trigger (write workflow should not auto-fire on commits)
    push_in_on = re.search(r"^on:\s*\n(?:\s*[a-z_]+:.*\n)*\s*push:", content, re.MULTILINE)
    assert push_in_on is None


def test_workflow_has_all_4_required_inputs() -> None:
    content = _read()
    for inp in ("dry_run", "allow_apply", "confirmation", "accepted_dry_run_report_digest"):
        assert re.search(rf"^\s*{inp}:", content, re.MULTILINE), f"missing input: {inp}"


def test_workflow_dry_run_default_is_true() -> None:
    """Codex iter-1 §B: dry_run default true (fail-closed)."""
    content = _read()
    assert re.search(
        r"dry_run:[\s\S]{0,200}?default:\s*['\"]?true['\"]?",
        content,
    ), "dry_run default MUST be 'true' (fail-closed)"


def test_workflow_allow_apply_default_is_false() -> None:
    """Codex iter-1 §B: allow_apply default false."""
    content = _read()
    assert re.search(
        r"allow_apply:[\s\S]{0,200}?default:\s*['\"]?false['\"]?",
        content,
    )


def test_workflow_apply_job_has_7_condition_compound_gate() -> None:
    """Codex iter-1 §4 absorb: 7-condition compound apply gate."""
    content = _read()
    # Find the apply job's `if:` block
    apply_if = re.search(
        r"apply:[\s\S]{0,2000}?if:\s*\|([\s\S]{0,1500}?)runs-on:",
        content,
    )
    assert apply_if, "apply job missing compound `if:` block"
    if_text = apply_if.group(1)
    required_conditions = [
        "github.ref == 'refs/heads/main'",
        "github.event_name == 'workflow_dispatch'",
        "github.run_attempt == 1",
        "inputs.dry_run == 'false'",
        "inputs.allow_apply == 'true'",
        "inputs.confirmation == 'AO-MA-11E-2B-APPLY'",
        "inputs.accepted_dry_run_report_digest != ''",
    ]
    for cond in required_conditions:
        assert cond in if_text, f"apply gate missing condition: {cond}"


def test_workflow_apply_job_uses_environment() -> None:
    """Codex iter-1 §5 absorb: environment: ao-ma-mirror-sync for apply protection."""
    content = _read()
    assert re.search(
        r"apply:[\s\S]{0,3000}?environment:\s*ao-ma-mirror-sync",
        content,
    ), "apply job MUST use `environment: ao-ma-mirror-sync` protection gate"


def test_workflow_apply_has_environment_preflight_step() -> None:
    """Codex iter-1 §5 absorb: env preflight verifies required_reviewers > 0."""
    content = _read()
    has_preflight = re.search(
        r"Environment preflight verify",
        content,
    )
    assert has_preflight, "apply job MUST have environment preflight verify step"
    assert "required_reviewers" in content
    assert "REVIEWER_COUNT" in content


def test_workflow_preflight_counts_actual_reviewers_not_rules() -> None:
    """Codex iter-2 §G/iter-1 §3 absorb: counter MUST count reviewers inside the
    rule (`.reviewers[]?`), not the number of rules.
    """
    content = _read()
    # The jq expression must dereference into .reviewers[?] within a
    # required_reviewers rule selection.
    assert re.search(
        r"\.reviewers\[\?\]",
        content,
    ) or re.search(
        r"select\(\.type ==.*required_reviewers.*\) *\| *\.reviewers",
        content,
    ), "preflight MUST count actual reviewers inside required_reviewers rule, not the number of rules"


def test_workflow_apply_generates_fresh_dry_run_inside_same_run() -> None:
    """Codex iter-1 §1 absorb: apply job MUST NOT depend on cross-run artifact.
    Apply runs a fresh dry-run, then digest-verifies operator input against it.
    """
    content = _read()
    assert re.search(
        r"Generate fresh dry-run inside apply job",
        content,
    ), "apply job MUST run a fresh dry-run inside the same workflow run"
    assert re.search(
        r"Verify operator digest matches fresh dry-run",
        content,
    ), "apply job MUST verify operator digest against the fresh dry-run report"


def test_workflow_apply_runs_post_drift_verification() -> None:
    """Post-apply: re-run 11E-2a drift checker to confirm synced."""
    content = _read()
    assert re.search(r"Post-drift verification", content)
    assert "ao_ma11e2_v5_mirror_drift.py" in content


def test_workflow_uploads_artifacts() -> None:
    """Reports MUST be uploaded as artifacts (audit trail)."""
    content = _read()
    assert "actions/upload-artifact" in content
    assert "sync_report" in content
    assert "apply_report" in content
    assert "post_drift_report" in content


def test_workflow_no_admin_bypass_or_force_push() -> None:
    """No admin operations / force operations in workflow."""
    content = _read()
    assert "--admin" not in content
    assert "--force" not in content
    assert "ruleset" not in content.lower()


def test_workflow_dry_run_job_no_environment() -> None:
    """Dry-run job MUST NOT require environment (operator can preview safely)."""
    content = _read()
    dry_run_block = re.search(
        r"dry_run:[\s\S]*?(?=^\s*apply:|\Z)",
        content,
        re.MULTILINE,
    )
    assert dry_run_block
    # Dry-run block should not contain `environment:` (any production env protection)
    dry_run_text = dry_run_block.group(0)
    assert "environment:" not in dry_run_text


def test_workflow_apply_install_uses_repo_pip_install() -> None:
    """Apply job installs from repo (idempotent + reproducible)."""
    content = _read()
    apply_block = re.search(r"apply:[\s\S]*", content)
    assert apply_block
    apply_text = apply_block.group(0)
    assert "pip install" in apply_text
