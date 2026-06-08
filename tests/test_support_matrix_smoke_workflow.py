"""V5 Epic 3 E-3-3 support-matrix-smoke advisory workflow invariants."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from ao_kernel._internal.support_widening.harnesses.runner import SURFACE_CLASSES

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is available in dev/CI
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "support-matrix-smoke.yml"

_LABEL_GATE = "contains(github.event.pull_request.labels.*.name, 'support-matrix-smoke')"
_DISPATCH_GATE = "github.event_name == 'workflow_dispatch'"

_PROTECTED_WORKFLOW_PATHS = [
    ".github/workflows/test.yml",
    ".github/workflows/ao-autonomous-merge-executor.yml",
    ".github/workflows/ao-release-gate-container-publish.yml",
    ".github/workflows/ao-release-gate-deploy-cloud-run.yml",
    ".github/workflows/bc1-protected-live-adapter-attestation.yml",
    ".github/workflows/bc10-real-adapter-usage-cost.yml",
    ".github/workflows/live-adapter-gate.yml",
    ".github/workflows/publish.yml",
    ".github/workflows/ao-ma-11a-plan-approval.yml",
    ".github/workflows/ao-ma-11e-2b-mirror-sync.yml",
    ".github/workflows/policy-container-publish.yml",
    ".github/workflows/policy-service-deploy-cloud-run.yml",
    ".github/workflows/ao-ma10q-dedicated-actor-smoke.yml",
]

# Protected-workflow authorization model (Codex thread 019ea61b, issue #983).
# A change to a _PROTECTED_WORKFLOW_PATHS entry is allowed past the drift guard
# ONLY when this per-PR, schema-valid, fresh, narrow authorization artifact lists
# exactly the protected workflow paths changed. This is independent
# defense-in-depth; the real high-risk merge authority remains ao-release-gate.
_AUTHORIZATION_REL_PATH = ".github/protected-workflow-authorization.v1.json"
_AUTHORIZATION_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "protected-workflow-authorization.schema.v1.json"
)

_COLLISION_WORKFLOW_PATHS = [
    *_PROTECTED_WORKFLOW_PATHS,
    ".github/workflows/live-adapter-evidence-emit.yml",
    ".github/workflows/changelog-enforcement.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/trivy.yml",
]


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[Any, Any]:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _load_workflow() -> dict[Any, Any]:
    return _load_yaml(_WORKFLOW_PATH)


def _on_block(workflow: dict[Any, Any]) -> dict[Any, Any]:
    on_block = workflow.get("on") if "on" in workflow else workflow.get(True)
    assert isinstance(on_block, dict)
    return on_block


def _job_names(path: Path) -> set[str]:
    workflow = _load_yaml(path)
    names: set[str] = set()
    top_name = workflow.get("name")
    if isinstance(top_name, str):
        names.add(top_name)
    jobs = workflow.get("jobs")
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            if isinstance(job_id, str):
                names.add(job_id)
            if isinstance(job, dict) and isinstance(job.get("name"), str):
                names.add(job["name"])
    return names


def _git_diff_names(paths: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", *paths],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _git_diff_name_status(paths: list[str]) -> list[tuple[str, str]]:
    """Return ``(status, path)`` pairs for ``paths`` over origin/main...HEAD.

    Status-aware (``--name-status --no-renames``) so the protected-workflow
    drift guard can fail closed on deletions/renames (a rename surfaces as a
    ``D`` of the old path plus an ``A`` of the new path) while authorizing only
    additions/modifications. Path-filtered (BLK-005 safe).
    """
    proc = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", "origin/main...HEAD", "--", *paths],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    pairs: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()[:1]
        path = parts[-1].strip()
        if status and path:
            pairs.append((status, path))
    return pairs


def _authorization_schema() -> dict[Any, Any]:
    return json.loads(_AUTHORIZATION_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_authorization_or_none() -> dict[str, Any] | None:
    """Load + schema-validate the protected-workflow authorization artifact.

    Returns ``None`` (== "no valid authorization") when the file is absent,
    unreadable, not JSON, or fails schema validation. A deleted or unparseable
    artifact therefore fails closed when a protected workflow is touched.
    Freshness (the artifact being added/modified in *this* PR's diff) is checked
    separately by the caller.
    """
    path = _REPO_ROOT / _AUTHORIZATION_REL_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        jsonschema.Draft202012Validator(_authorization_schema()).validate(data)
    except jsonschema.ValidationError:
        return None
    return data if isinstance(data, dict) else None


def _evaluate_protected_workflow_drift(
    *,
    protected_workflow_changes: list[tuple[str, str]],
    rulesets_bp_changes: list[tuple[str, str]],
    authorization: dict[str, Any] | None,
    authorization_in_diff: bool,
) -> list[str]:
    """Pure decision core for the protected-workflow drift guard.

    Returns a list of violation messages (empty == no drift / authorized).
    Kept git-free so it is unit-testable with synthetic inputs.
    """
    violations: list[str] = []

    # Rulesets / branch-protection are NEVER authorizable via this guard.
    if rulesets_bp_changes:
        paths = sorted({path for _, path in rulesets_bp_changes})
        violations.append(f"ruleset/branch-protection paths changed (never authorizable via this guard): {paths}")

    # Deletions/renames of a protected workflow are unconditionally fail-closed.
    destructive = sorted({path for status, path in protected_workflow_changes if status not in ("A", "M")})
    if destructive:
        violations.append(f"protected workflow deleted/renamed (fail-closed; not authorizable): {destructive}")

    addmod = sorted({path for status, path in protected_workflow_changes if status in ("A", "M")})
    if not addmod:
        return violations

    # A protected workflow was added/modified -> require fresh, narrow, valid authorization.
    if authorization is None:
        violations.append(
            f"protected workflow(s) {addmod} changed without a valid authorization artifact "
            f"({_AUTHORIZATION_REL_PATH}); add a fresh schema-valid authorization listing exactly these paths"
        )
        return violations
    if not authorization_in_diff:
        violations.append(
            "protected-workflow authorization artifact is stale (not added/modified in this PR's diff); "
            "a fresh per-PR authorization is required for a protected-workflow change"
        )

    authorized = {p for p in authorization.get("authorized_paths", []) if isinstance(p, str)}
    unknown = sorted(authorized - set(_PROTECTED_WORKFLOW_PATHS))
    if unknown:
        violations.append(f"authorization lists paths that are not protected workflows: {unknown}")
    missing = sorted(set(addmod) - authorized)
    if missing:
        violations.append(f"protected workflow(s) changed but not authorized: {missing}")
    extra = sorted(authorized - set(addmod))
    if extra:
        violations.append(f"authorization lists protected workflow(s) not changed in this PR (over-broad): {extra}")
    return violations


def _ruleset_required_contexts() -> set[str]:
    """Return live ruleset required contexts when GitHub API auth is available.

    The invariant is still enforced in CI/local runs that can reach the API; if
    the API is unavailable, the static job-name collision tests below keep the
    PR fail-closed against known repo-owned required-check names.
    """

    if shutil.which("gh") is None:
        pytest.skip("gh CLI not available for live ruleset collision check")
    if "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ:
        auth = subprocess.run(
            ["gh", "auth", "status"],
            cwd=_REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if auth.returncode != 0:
            pytest.skip("gh API auth unavailable for live ruleset collision check")

    listing = subprocess.run(
        ["gh", "api", "repos/Halildeu/ao-kernel/rulesets", "--paginate"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if listing.returncode != 0:
        pytest.skip(f"ruleset list API unavailable: {listing.stderr.strip()}")
    rulesets = json.loads(listing.stdout or "[]")
    contexts: set[str] = set()
    for item in rulesets:
        ruleset_id = item.get("id")
        if not ruleset_id:
            continue
        detail = subprocess.run(
            ["gh", "api", f"repos/Halildeu/ao-kernel/rulesets/{ruleset_id}"],
            cwd=_REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert detail.returncode == 0, detail.stderr
        payload = json.loads(detail.stdout)
        for rule in payload.get("rules", []):
            if rule.get("type") != "required_status_checks":
                continue
            parameters = rule.get("parameters") or {}
            for check in parameters.get("required_status_checks", []):
                context = check.get("context")
                if isinstance(context, str):
                    contexts.add(context)
            for context in parameters.get("contexts", []):
                if isinstance(context, str):
                    contexts.add(context)
    return contexts


def test_workflow_exists_at_canonical_path() -> None:
    assert _WORKFLOW_PATH.exists()


def test_trigger_shape_is_label_or_dispatch_only() -> None:
    workflow = _load_workflow()
    on_block = _on_block(workflow)

    assert sorted(on_block) == ["pull_request", "workflow_dispatch"]
    assert on_block["pull_request"] == {"types": ["opened", "labeled", "synchronize", "reopened"]}
    assert on_block["workflow_dispatch"] is None

    text = _workflow_text()
    for forbidden in ("push:", "repository_dispatch:", "schedule:", "pull_request_target:", "labels:"):
        assert forbidden not in text, f"unexpected trigger surface: {forbidden}"


def test_all_jobs_are_opt_in_and_dispatch_path_is_viable() -> None:
    jobs = _load_workflow()["jobs"]
    assert isinstance(jobs, dict)
    for job_id, job in jobs.items():
        assert isinstance(job, dict)
        expression = str(job.get("if", ""))
        assert _DISPATCH_GATE in expression, job_id
        assert _LABEL_GATE in expression, job_id

    def gate_allows(event_name: str, labels: list[str]) -> bool:
        return event_name == "workflow_dispatch" or "support-matrix-smoke" in labels

    assert gate_allows("workflow_dispatch", []) is True
    assert gate_allows("pull_request", ["support-matrix-smoke"]) is True
    assert gate_allows("pull_request", []) is False


def test_permissions_are_minimal_and_no_secret_or_environment_surface() -> None:
    workflow = _load_workflow()
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "write"}

    text = _workflow_text()
    for forbidden in (
        "write-all",
        "actions: write",
        "checks: write",
        "contents: write",
        "deployments: write",
        "id-token: write",
        "issues: write",
        "packages: write",
        "secrets.",
        "environment:",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AO_CLAUDE_CODE_CLI_AUTH",
    ):
        assert forbidden not in text, f"unexpected advisory workflow surface: {forbidden}"


def test_matrix_matches_surface_registry_and_invokes_smoke_runner() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["support-matrix-smoke-advisory"]

    assert job["continue-on-error"] is True
    assert job["strategy"]["fail-fast"] is False
    assert tuple(job["strategy"]["matrix"]["surface_class"]) == SURFACE_CLASSES

    text = _workflow_text()
    assert "scripts/run_support_smoke.py" in text
    assert '--surface "${{ matrix.surface_class }}"' in text
    assert '--evidence-out "support-matrix-smoke/${{ matrix.surface_class }}.support-widening-evidence.v1.json"' in text
    assert "actions/upload-artifact@v7" in text
    assert "if-no-files-found: error" in text
    assert "required_check: false" in text


def test_workflow_does_not_flip_guard_flags() -> None:
    text = _workflow_text()
    for forbidden in (
        "support_widening: true",
        "production_platform_claim: true",
        "live_adapter_execution: true",
        "support_widening_allowed: true",
        "production_platform_claim_allowed: true",
        "live_adapter_execution_allowed: true",
    ):
        assert forbidden not in text
    for required_false in (
        "support_widening: false",
        "production_platform_claim: false",
        "live_adapter_execution: false",
    ):
        assert required_false in text


def test_protected_workflows_and_ruleset_files_are_not_modified_by_slice() -> None:
    """Protected workflows / rulesets must not drift unless explicitly authorized.

    Codex thread 019ea61b / issue #983: the old guard rejected ANY protected
    workflow change unconditionally, which blocked even an authorized,
    cross-provider-reviewed change (e.g. re-landing #979's pull_request_review
    CI carve-out). It now recognizes a narrow per-PR authorization artifact:

    * rulesets / branch-protection: any change is drift (not authorizable here),
    * protected-workflow deletion/rename: fail-closed (not authorizable),
    * protected-workflow add/modify: requires a fresh (in this PR's diff),
      schema-valid authorization listing exactly the changed protected paths,
    * an unauthorized or stale protected-workflow change still fails closed.

    The real high-risk merge authority remains ao-release-gate
    (HIGH_RISK_PATH_PATTERNS + supersession / non-author review); this guard is
    independent defense-in-depth against accidental drift.
    """
    protected_workflow_changes = _git_diff_name_status(_PROTECTED_WORKFLOW_PATHS)
    rulesets_bp_changes = _git_diff_name_status([".github/rulesets", ".github/branch-protection"])

    authorization: dict[str, Any] | None = None
    authorization_in_diff = False
    if any(status in ("A", "M") for status, _ in protected_workflow_changes):
        authorization = _load_authorization_or_none()
        if authorization is not None:
            authorization_in_diff = any(
                status in ("A", "M") and path == _AUTHORIZATION_REL_PATH
                for status, path in _git_diff_name_status([_AUTHORIZATION_REL_PATH])
            )

    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=protected_workflow_changes,
        rulesets_bp_changes=rulesets_bp_changes,
        authorization=authorization,
        authorization_in_diff=authorization_in_diff,
    )
    assert not violations, "; ".join(violations)


def test_job_names_do_not_collide_with_required_workflow_names() -> None:
    new_names = _job_names(_WORKFLOW_PATH)
    existing_names: set[str] = set()
    for relative in _COLLISION_WORKFLOW_PATHS:
        path = _REPO_ROOT / relative
        if path.exists():
            existing_names.update(_job_names(path))

    for new_name in new_names:
        for existing_name in existing_names:
            assert new_name != existing_name
            assert new_name not in existing_name
            assert existing_name not in new_name


def test_live_ruleset_required_contexts_do_not_reference_support_matrix_smoke() -> None:
    contexts = _ruleset_required_contexts()
    forbidden_contexts = _job_names(_WORKFLOW_PATH)
    forbidden_contexts.add("support-matrix-smoke")

    assert forbidden_contexts.isdisjoint(contexts)


def test_slice_diff_only_adds_expected_workflow_supporting_artifacts() -> None:
    changed = set(_git_diff_names(["."]))
    if ".github/workflows/support-matrix-smoke.yml" not in changed:
        pytest.skip("support-matrix-smoke workflow not changed by this PR")

    expected = {
        ".github/workflows/support-matrix-smoke.yml",
        ".claude/plans/EPIC-3-E-3-3-CI-MATRIX.md",
        "CHANGELOG.md",
        "local-ai-review-evidence.v1.json",
        "tests/test_cost_ceiling.py",
        "tests/test_support_matrix_smoke_workflow.py",
    }
    unexpected = changed - expected
    assert not unexpected


# ── protected-workflow authorization model (issue #983, Codex 019ea61b) ──


def _synthetic_authorization(authorized_paths: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "protected-workflow-authorization.v1",
        "artifact_kind": "protected_workflow_authorization",
        "repo": "Halildeu/ao-kernel",
        "work_package": "AO-MA-TEST",
        "reason": "unit-test synthetic authorization (>=10 chars)",
        "authorized_paths": list(authorized_paths),
        "review_evidence_refs": ["local-ai-review-evidence.v1.json"],
    }


def test_drift_core_passes_when_no_protected_path_touched() -> None:
    assert (
        _evaluate_protected_workflow_drift(
            protected_workflow_changes=[],
            rulesets_bp_changes=[],
            authorization=None,
            authorization_in_diff=False,
        )
        == []
    )


def test_drift_core_passes_with_fresh_narrow_authorization() -> None:
    assert (
        _evaluate_protected_workflow_drift(
            protected_workflow_changes=[("M", ".github/workflows/test.yml")],
            rulesets_bp_changes=[],
            authorization=_synthetic_authorization([".github/workflows/test.yml"]),
            authorization_in_diff=True,
        )
        == []
    )


def test_drift_core_blocks_unauthorized_protected_change() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[("M", ".github/workflows/test.yml")],
        rulesets_bp_changes=[],
        authorization=None,
        authorization_in_diff=False,
    )
    assert any("without a valid authorization" in m for m in violations)


def test_drift_core_blocks_stale_authorization() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[("M", ".github/workflows/test.yml")],
        rulesets_bp_changes=[],
        authorization=_synthetic_authorization([".github/workflows/test.yml"]),
        authorization_in_diff=False,
    )
    assert any("stale" in m for m in violations)


def test_drift_core_blocks_missing_authorized_path() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[
            ("M", ".github/workflows/test.yml"),
            ("M", ".github/workflows/publish.yml"),
        ],
        rulesets_bp_changes=[],
        authorization=_synthetic_authorization([".github/workflows/test.yml"]),
        authorization_in_diff=True,
    )
    assert any("not authorized" in m for m in violations)


def test_drift_core_blocks_overbroad_authorization() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[("M", ".github/workflows/test.yml")],
        rulesets_bp_changes=[],
        authorization=_synthetic_authorization([".github/workflows/test.yml", ".github/workflows/publish.yml"]),
        authorization_in_diff=True,
    )
    assert any("over-broad" in m for m in violations)


def test_drift_core_blocks_unknown_non_protected_path() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[("M", ".github/workflows/test.yml")],
        rulesets_bp_changes=[],
        authorization=_synthetic_authorization([".github/workflows/test.yml", ".github/workflows/not-protected.yml"]),
        authorization_in_diff=True,
    )
    assert any("not protected workflows" in m for m in violations)


def test_drift_core_blocks_protected_workflow_deletion() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[("D", ".github/workflows/test.yml")],
        rulesets_bp_changes=[],
        authorization=_synthetic_authorization([".github/workflows/test.yml"]),
        authorization_in_diff=True,
    )
    assert any("deleted/renamed" in m for m in violations)


def test_drift_core_blocks_ruleset_change() -> None:
    violations = _evaluate_protected_workflow_drift(
        protected_workflow_changes=[],
        rulesets_bp_changes=[("M", ".github/rulesets/protect-main.json")],
        authorization=_synthetic_authorization([".github/workflows/test.yml"]),
        authorization_in_diff=True,
    )
    assert any("ruleset/branch-protection" in m for m in violations)


def test_authorization_schema_is_valid_draft2020() -> None:
    schema = _authorization_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:protected-workflow-authorization:v1"
    assert schema["additionalProperties"] is False


def test_real_authorization_artifact_is_schema_valid_and_narrow() -> None:
    path = _REPO_ROOT / _AUTHORIZATION_REL_PATH
    if not path.is_file():
        pytest.skip("no protected-workflow authorization artifact present")
    data = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(_authorization_schema()).validate(data)
    assert set(data["authorized_paths"]).issubset(set(_PROTECTED_WORKFLOW_PATHS)), (
        "authorization may only list known protected workflows"
    )


def test_authorization_schema_rejects_additional_properties() -> None:
    bad = _synthetic_authorization([".github/workflows/test.yml"])
    bad["unexpected"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_authorization_schema()).validate(bad)


def test_authorization_schema_rejects_non_workflow_authorized_path() -> None:
    bad = _synthetic_authorization(["ao_kernel/ao_release_gate.py"])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_authorization_schema()).validate(bad)


def test_authorization_schema_requires_authorized_paths() -> None:
    bad = _synthetic_authorization([".github/workflows/test.yml"])
    del bad["authorized_paths"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_authorization_schema()).validate(bad)
