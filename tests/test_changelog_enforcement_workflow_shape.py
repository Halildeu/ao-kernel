"""V5 Epic 1 E-1-3 invariants: changelog enforcement CI workflow shape.

Workflow YAML is high-risk path (.github/workflows/). Structural
invariants only; the workflow's runtime semantics are exercised by
GitHub Actions on real PR events. Tests verify discipline:

- Binding to the canonical `ao-kernel quality check-changelog` CLI
  (ADR-0005 SSOT) — NOT a YAML-duplicated decision contract
- Read-only token + pull_request (not _target) + no secrets/admin
- Env-routed PR labels + base ref (no inline expression injection)
- ZERO TOUCH governance + only one new workflow under `.github/workflows/`
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "changelog-enforcement.yml"
LOCAL_HOOK_PATH = REPO_ROOT / ".claude" / "scripts" / "pre-commit-changelog-gate.sh"

_ALLOWED_ACTION_VERSION_LINE = re.compile(
    r"^[+-]\s*(?:-\s+)?uses:\s+(?:"
    r"actions/checkout@v[67]|"
    r"github/codeql-action/(?:init|analyze|upload-sarif)@v[34]|"
    r"google-github-actions/deploy-cloudrun@v[23]"
    r")$"
)


def _workflow_diff_is_dependency_only(paths: list[str]) -> bool:
    proc = subprocess.run(
        ["git", "diff", "--unified=0", "origin/main...HEAD", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False
    changed_lines = [
        line
        for line in proc.stdout.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    return bool(changed_lines) and all(_ALLOWED_ACTION_VERSION_LINE.fullmatch(line) for line in changed_lines)


def _load_workflow() -> dict[Any, Any]:
    if yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    loaded = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert isinstance(loaded, dict)
    return loaded


# ---- 1. Presence + structure (5) ----------------------------------------


def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_workflow_has_name_and_pull_request_trigger() -> None:
    wf = _load_workflow()
    assert wf["name"] == "Changelog Enforcement"
    on_block = wf.get("on") if "on" in wf else wf.get(True)
    assert isinstance(on_block, dict)
    assert "pull_request" in on_block
    pr = on_block["pull_request"]
    assert "main" in pr["branches"]
    # `edited` is required because the CLI inspects PR labels which
    # change via the `edited` event
    assert "edited" in pr["types"]
    assert "synchronize" in pr["types"]


def test_workflow_uses_pull_request_not_target() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "pull_request_target" not in text


def test_workflow_concurrency_cancels_in_progress() -> None:
    wf = _load_workflow()
    concurrency = wf["concurrency"]
    assert concurrency.get("cancel-in-progress") is True
    assert "changelog-enforcement-" in concurrency["group"]


def test_workflow_has_single_enforce_job() -> None:
    wf = _load_workflow()
    assert "enforce-changelog" in wf["jobs"]
    job = wf["jobs"]["enforce-changelog"]
    assert job.get("timeout-minutes", 0) > 0
    assert job["runs-on"] == "ubuntu-latest"


# ---- 2. Permissions + token discipline (3) ------------------------------


def test_workflow_uses_minimum_permissions() -> None:
    wf = _load_workflow()
    perms = wf["permissions"]
    assert perms.get("contents") == "read"
    assert perms.get("pull-requests") == "read"
    forbidden = {
        "id-token",
        "packages",
        "checks",
        "deployments",
        "pages",
        "issues",
        "discussions",
        "statuses",
        "actions",
        "security-events",
    }
    for key in forbidden:
        value = perms.get(key)
        assert value != "write", f"workflow must not grant {key}:write"


def test_workflow_persist_credentials_false() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "persist-credentials: false" in text


def test_workflow_routes_dynamic_inputs_via_env() -> None:
    """BASE_REF and PR_LABELS_JSON MUST be routed through env: (not
    embedded directly in run: ${{ }}) to avoid command injection."""
    text = WORKFLOW_PATH.read_text()
    assert "BASE_REF: ${{ github.event.pull_request.base.ref }}" in text
    assert "PR_LABELS_JSON: ${{ toJSON(github.event.pull_request.labels) }}" in text


# ---- 3. Binds to ao-kernel CLI (NOT YAML-duplicated contract) (4) -------


def test_workflow_invokes_ao_kernel_quality_check_changelog() -> None:
    """E-1-3 Codex iter-1 F1 absorb: SSOT must remain in the CLI, not
    drift into the workflow YAML. Workflow MUST call
    `ao-kernel quality check-changelog`."""
    text = WORKFLOW_PATH.read_text()
    assert "ao-kernel quality check-changelog" in text


def test_workflow_installs_ao_kernel_core_only() -> None:
    """Core install is sufficient; do not pull live LLM provider
    extras into the changelog gate runner."""
    text = WORKFLOW_PATH.read_text()
    assert "pip install -e ." in text
    forbidden = ("[llm]", "[otel]", "anthropic", "openai")
    for token in forbidden:
        assert token not in text, f"workflow must not install live provider extras: {token!r}"


def test_workflow_passes_base_and_labels_to_cli() -> None:
    """CLI MUST receive the current signature so behavior is bound to
    the SSOT validator (no YAML drift). The CLI requires
    --base-changelog, --head-changelog, --out; optional --diff-path /
    --chore-no-changelog / --chore-rationale. Labels are still env-
    routed via PR_LABELS_JSON, parsed inline (the CLI does not accept
    a --labels-json flag)."""
    text = WORKFLOW_PATH.read_text()
    assert "--base-changelog base-changelog.md" in text
    assert "--head-changelog CHANGELOG.md" in text
    assert "--out changelog-verdict.json" in text
    assert "PR_LABELS_JSON" in text
    assert "chore-no-changelog" in text


def test_workflow_actionable_error_cites_adr_0005_paths() -> None:
    """Failure message MUST guide reporters to the two valid recovery
    paths defined by ADR-0005: (a) bullet under [Unreleased], OR
    (b) chore-no-changelog label + >=10-char rationale."""
    text = WORKFLOW_PATH.read_text()
    assert "[Unreleased]" in text
    assert "chore-no-changelog" in text
    assert "rationale" in text


# ---- 4. Coexistence with local hook (2) ---------------------------------


def test_local_hook_optional_skip_if_absent() -> None:
    """E-1-3 is the canonical CI gate; E-1-4 local hook is UX ergonomic
    shortcut. Hook may or may not be present on this base."""
    if not LOCAL_HOOK_PATH.exists():
        pytest.skip(
            "local hook (E-1-4) not yet present in this base ref; this is a non-blocking skip because CI is the SSOT"
        )
    assert LOCAL_HOOK_PATH.exists()


def test_workflow_documents_relationship_to_local_hook() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "E-1-4" in text
    assert "pre-commit-changelog-gate.sh" in text


# ---- 5. SSOT binding + drift avoidance (2) ------------------------------


def test_workflow_does_not_duplicate_adr_0005_decision_in_yaml() -> None:
    """F1 absorb: workflow MUST NOT re-implement the decision logic in
    YAML. The 8-prefix Conventional Commit set + the [Unreleased]
    bullet check + the rationale length check belong inside the CLI
    (quality_profile.py), NOT in the workflow run: body. Detect the
    main drift signal: an inline allowed-prefix regex.
    """
    text = WORKFLOW_PATH.read_text()
    # An inline prefix regex like `(chore|docs|test|ci|style|refactor|build|perf)`
    # is the drift smell — the canonical set lives in ADR-0005 + CLI.
    drift_signal = "(chore|docs|test|ci|style|refactor|build|perf)"
    assert drift_signal not in text, (
        "workflow must not duplicate ADR-0005 prefix decision in YAML; "
        "delegate to `ao-kernel quality check-changelog` CLI"
    )


def test_workflow_disclaims_required_check_wiring_is_separate_slice() -> None:
    """F2 absorb: 'non-bypassable' overclaim removed. The header must
    NOT claim non-bypassable status; required-check ruleset wiring is
    a separate operator-bound slice."""
    text = WORKFLOW_PATH.read_text().lower()
    # The header must NOT advertise non-bypassable
    assert "non-bypassable" not in text
    # And the header must reference E-1-4 as ergonomic local mirror
    assert "ergonomic" in text or "ux shortcut" in text or "ux helper" in text or "local pre-commit" in text


# ---- 6. Governance ZERO TOUCH (3) ---------------------------------------


def test_only_one_workflow_file_changed() -> None:
    """When E-1-3 edits the changelog workflow, it must be the only
    workflow file changed. Other PRs exercise the already-landed workflow
    shape tests above without inheriting the E-1-3 diff-shape invariant."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = proc.stdout.split()
    if not changed:
        pytest.skip(
            "no committed diff vs origin/main yet (untracked-only state); CI run on the PR will exercise this invariant"
        )
    workflow_path = ".github/workflows/changelog-enforcement.yml"
    if workflow_path not in changed:
        pytest.skip("E-1-3 workflow diff-shape invariant applies only when the changelog workflow is changed")
    workflow_changes = [p for p in changed if p.startswith(".github/workflows/")]
    if _workflow_diff_is_dependency_only(workflow_changes):
        return
    assert workflow_changes == [workflow_path], (
        f"E-1-3 must add exactly one workflow; got: {workflow_changes}"
    )


def test_no_codeowners_or_ruleset_diff() -> None:
    """E-1-3 zero-touch invariant is slice-scoped.

    Only enforce the governance-file diff guard when the changelog workflow is
    part of the PR diff. Other governance PRs, such as the PR template delivery
    metadata contract, have their own scoped tests.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = set(proc.stdout.split())
    if ".github/workflows/changelog-enforcement.yml" not in changed:
        pytest.skip("E-1-3 governance zero-touch invariant applies only when changelog workflow is changed")
    forbidden = {
        ".github/CODEOWNERS",
        ".github/REPO-GOVERNANCE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
    }
    overlap = forbidden & changed
    assert not overlap, f"E-1-3 must not touch governance files: {overlap}"


def test_workflow_no_secret_or_admin_surface() -> None:
    text = WORKFLOW_PATH.read_text()
    forbidden_tokens = (
        "secrets.GITHUB_TOKEN_WRITE",
        "--admin",
        "ADMIN_TOKEN",
        "PAT_TOKEN",
        "secrets.PAT",
        "id-token: write",
    )
    for token in forbidden_tokens:
        assert token not in text, f"workflow must not expose secret/admin: {token!r}"
    # The CLI install + invocation does not require any secrets.* reference
    assert "secrets." not in text
