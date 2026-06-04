"""V5 Epic 3 E-3-3 support-matrix-smoke advisory workflow invariants."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

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
    assert "--surface \"${{ matrix.surface_class }}\"" in text
    assert "--evidence-out \"support-matrix-smoke/${{ matrix.surface_class }}.support-widening-evidence.v1.json\"" in text
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
    protected_paths = [
        *_PROTECTED_WORKFLOW_PATHS,
        ".github/rulesets",
        ".github/branch-protection",
    ]
    assert _git_diff_names(protected_paths) == []


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
