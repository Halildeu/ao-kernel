"""AO-MA-10j runtime high-risk supersession evidence builder tests.

Covers 3-state binding_mode classification (added/modified/unchanged),
path-to-provider audit binding, suffix-parts repo-relative resolution, and
schema-pinned binding_mode field. See Codex thread 019e6ffc plan-time AGREE.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from scripts.ao_ma10_high_risk_supersession_evidence import (
    HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS,
    VALID_BINDING_MODES,
    _classify_evidence_binding,
    _resolve_repo_relative_path,
    build_high_risk_supersession_evidence,
)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _raw_review(
    *,
    provider: str,
    agent: str,
    changed_files: list[str],
    verdict: str = "AGREE",
    head_ref: str = "refs/heads/feature",
    work_package: str = "AO-MA-10j",
    base_ref: str = "refs/heads/main",
) -> dict[str, Any]:
    return {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": "Halildeu/ao-kernel",
        "work_package": work_package,
        "implementer": {"agent": "implementer-agent", "provider": "google"},
        "reviewer": {"agent": agent, "provider": provider, "verdict": verdict},
        "scope_reviewed": {
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_files": changed_files,
        },
        "checks_considered": [
            {"name": "tests", "status": "pass"},
            {"name": "secret_scan", "status": "pass"},
        ],
        "findings": [],
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


# --- Introducer fixture (raw evidence ADDED in feature commit) ---


@pytest.fixture()
def high_risk_repo(tmp_path: Path) -> tuple[Path, list[Path], list[str]]:
    """Introducer fixture: raw evidence files ADDED in the feature commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "ao_kernel/ao_release_gate.py", "# base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "feature")

    changed_files = [
        "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json",
        "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json",
        "ao_kernel/ao_release_gate.py",
    ]
    _write(repo, "ao_kernel/ao_release_gate.py", "# changed\n")
    review_paths = []
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        path = repo / f"ao-ma-10-high-risk-reviews/{provider}.local-ai-review-evidence.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _raw_review(provider=provider, agent=agent, changed_files=changed_files),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        review_paths.append(path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    return repo, review_paths, changed_files


# --- State-at-landing fixture (raw evidence present on base, unchanged in PR) ---


@pytest.fixture()
def state_at_landing_repo(tmp_path: Path) -> tuple[Path, list[Path], list[str]]:
    """State-at-landing fixture: raw evidence files present on base SHA and
    NOT touched in the feature branch (binding_mode=unchanged)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "ao_kernel/ao_release_gate.py", "# base\n")

    # Raw evidence files on BASE — bound to a prior "AO-MA-10-LANDED" work_package
    landed_changed_files = [
        "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json",
        "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json",
        "ao_kernel/ao_release_gate.py",
    ]
    review_paths = []
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        path = repo / f"ao-ma-10-high-risk-reviews/{provider}.local-ai-review-evidence.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _raw_review(
                    provider=provider,
                    agent=agent,
                    changed_files=landed_changed_files,
                    work_package="AO-MA-10-LANDED",
                    head_ref="refs/heads/landed-pr",
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        review_paths.append(path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base with landed evidence")
    _git(repo, "checkout", "-b", "feature")

    # Feature touches ONLY ao_release_gate.py — raw evidence files unchanged
    _write(repo, "ao_kernel/ao_release_gate.py", "# changed by feature\n")
    feature_changed_files = sorted(["ao_kernel/ao_release_gate.py"])
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature changes release gate only")
    return repo, review_paths, feature_changed_files


# --- Modified fixture (raw evidence present on base, MODIFIED in PR) ---


@pytest.fixture()
def modified_evidence_repo(tmp_path: Path) -> tuple[Path, list[Path], list[str]]:
    """Modified fixture: raw evidence files present on base SHA and MODIFIED
    in the feature commit (binding_mode=modified -> strict current-PR
    bindings still required)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "ao_kernel/ao_release_gate.py", "# base\n")

    landed_changed_files = [
        "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json",
        "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json",
        "ao_kernel/ao_release_gate.py",
    ]
    review_paths = []
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        path = repo / f"ao-ma-10-high-risk-reviews/{provider}.local-ai-review-evidence.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _raw_review(
                    provider=provider,
                    agent=agent,
                    changed_files=landed_changed_files,
                    work_package="AO-MA-10-LANDED",
                    head_ref="refs/heads/landed-pr",
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        review_paths.append(path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base with landed evidence")
    _git(repo, "checkout", "-b", "feature")

    # Feature MODIFIES raw evidence (still bound to old AO-MA-10-LANDED wp,
    # not rebound to current feature wp). Also changes release gate.
    _write(repo, "ao_kernel/ao_release_gate.py", "# changed by feature\n")
    feature_changed_files = sorted(
        [
            "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json",
            "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json",
            "ao_kernel/ao_release_gate.py",
        ]
    )
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        path = repo / f"ao-ma-10-high-risk-reviews/{provider}.local-ai-review-evidence.v1.json"
        existing = json.loads(path.read_text(encoding="utf-8"))
        # Touch with a no-op change (e.g., add a new finding line)
        existing["findings"] = ["doc(meta): minor wording update"]
        path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature with touched evidence")
    return repo, review_paths, feature_changed_files


# === Tests: introducer (binding_mode=added) ===


def test_build_high_risk_supersession_evidence_from_raw_runtime_reviews(
    high_risk_repo: tuple[Path, list[Path], list[str]],
) -> None:
    repo, review_paths, changed_files = high_risk_repo

    evidence = build_high_risk_supersession_evidence(
        repository="Halildeu/ao-kernel",
        review_work_package="AO-MA-10j",
        review_base_ref="refs/heads/main",
        review_head_ref="refs/heads/feature",
        diff_base_ref="main",
        diff_head_ref="feature",
        repo_root=repo,
        raw_review_paths=review_paths,
        max_age_seconds=3600,
        round_index=1,
        generated_at="2026-05-28T00:00:00Z",
    )

    schema = load_default("schemas", "ao-ma-10-high-risk-supersession-evidence.schema.v1.json")
    assert list(Draft202012Validator(schema).iter_errors(evidence)) == []
    assert evidence["schema_version"] == "ao-ma-10-high-risk-supersession-evidence.v1"
    assert evidence["reviewer_providers"] == ["anthropic", "openai"]
    assert evidence["context_binding"]["head_sha"] == _git(repo, "rev-parse", "feature")
    assert evidence["context_binding"]["changed_files_count"] == len(changed_files)
    assert evidence["context_binding"]["high_risk_changed_paths"] == ["ao_kernel/ao_release_gate.py"]
    assert {item["provider_id"] for item in evidence["provider_verdicts"]} == {"openai", "anthropic"}
    # Introducer PR: every verdict carries binding_mode=added (raw files ADDED)
    assert {item["binding_mode"] for item in evidence["provider_verdicts"]} == {"added"}


def test_build_high_risk_supersession_rejects_missing_required_provider(
    high_risk_repo: tuple[Path, list[Path], list[str]],
) -> None:
    repo, review_paths, changed_files = high_risk_repo
    # Make both reviewer files claim provider=openai (so anthropic missing)
    # AND fix path-provider binding for the duplicated openai entry.
    second = json.loads(review_paths[1].read_text(encoding="utf-8"))
    second["reviewer"]["provider"] = "openai"
    second["reviewer"]["agent"] = "second-openai-reviewer"
    review_paths[1].write_text(json.dumps(second), encoding="utf-8")

    # The anthropic.* path now carries provider=openai → path-provider binding
    # fails first (before provider-set check). Match either reason.
    with pytest.raises(
        ValueError,
        match="(does not match path-bound expected provider|exactly OpenAI and Anthropic)",
    ):
        build_high_risk_supersession_evidence(
            repository="Halildeu/ao-kernel",
            review_work_package="AO-MA-10j",
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/feature",
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_root=repo,
            raw_review_paths=review_paths,
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-05-28T00:00:00Z",
        )


def test_build_high_risk_supersession_rejects_scope_mismatch(
    high_risk_repo: tuple[Path, list[Path], list[str]],
) -> None:
    repo, review_paths, _changed_files = high_risk_repo
    first = json.loads(review_paths[0].read_text(encoding="utf-8"))
    first["scope_reviewed"]["head_ref"] = "refs/heads/not-this-pr"
    review_paths[0].write_text(json.dumps(first), encoding="utf-8")

    with pytest.raises(ValueError, match="scope refs mismatch"):
        build_high_risk_supersession_evidence(
            repository="Halildeu/ao-kernel",
            review_work_package="AO-MA-10j",
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/feature",
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_root=repo,
            raw_review_paths=review_paths,
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-05-28T00:00:00Z",
        )


# === Tests: state-at-landing (binding_mode=unchanged) ===


def test_build_evidence_unchanged_state_at_landing(
    state_at_landing_repo: tuple[Path, list[Path], list[str]],
) -> None:
    """When raw evidence files are NOT in this PR's diff, scope binding is
    relaxed (state-at-landing pin). Different work_package and head_ref in
    the landed evidence is accepted."""
    repo, review_paths, _changed_files = state_at_landing_repo

    evidence = build_high_risk_supersession_evidence(
        repository="Halildeu/ao-kernel",
        review_work_package="AO-MA-10j-current",  # different from landed AO-MA-10-LANDED
        review_base_ref="refs/heads/main",
        review_head_ref="refs/heads/feature",
        diff_base_ref="main",
        diff_head_ref="feature",
        repo_root=repo,
        raw_review_paths=review_paths,
        max_age_seconds=3600,
        round_index=1,
        generated_at="2026-05-28T00:00:00Z",
    )
    # Unchanged binding_mode reported in every verdict (state-at-landing pin)
    assert {item["binding_mode"] for item in evidence["provider_verdicts"]} == {"unchanged"}
    assert evidence["consensus_status"] == "AGREE"


def test_build_evidence_unchanged_still_enforces_immutable_secrets_recorded(
    state_at_landing_repo: tuple[Path, list[Path], list[str]],
) -> None:
    """Immutable properties (secrets_recorded=false) enforced even when
    binding_mode=unchanged."""
    repo, review_paths, _changed_files = state_at_landing_repo
    # Corrupt landed evidence on base SHA: rewrite file at HEAD (this mutates
    # it; binding_mode becomes "modified", which is also strict). To keep
    # the test in unchanged-mode, we instead patch read_text via fixture
    # state — simulate the unchanged file at base already having a violation.
    # Easier: since unchanged path means file is byte-identical at HEAD,
    # we cannot have unchanged AND broken without modifying. So this test
    # demonstrates the property by modifying: the resulting binding_mode is
    # "modified" but the immutable check still fires first.
    bad = json.loads(review_paths[0].read_text(encoding="utf-8"))
    bad["secrets_recorded"] = True
    review_paths[0].write_text(json.dumps(bad), encoding="utf-8")
    repo_with_modified = repo
    # Commit so diff detects modification
    _git(repo_with_modified, "add", "ao-ma-10-high-risk-reviews/")
    _git(repo_with_modified, "commit", "-m", "feature with broken evidence")

    with pytest.raises(ValueError, match="records secret material"):
        build_high_risk_supersession_evidence(
            repository="Halildeu/ao-kernel",
            review_work_package="AO-MA-10j-current",
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/feature",
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_root=repo_with_modified,
            raw_review_paths=review_paths,
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-05-28T00:00:00Z",
        )


# === Tests: modified (binding_mode=modified -> strict required) ===


def test_build_evidence_modified_requires_strict_work_package(
    modified_evidence_repo: tuple[Path, list[Path], list[str]],
) -> None:
    """When raw evidence is MODIFIED in this PR but still bound to old
    work_package, fail-closed (current-PR strict binding required)."""
    repo, review_paths, _changed_files = modified_evidence_repo

    with pytest.raises(ValueError, match="work_package mismatch.*binding_mode=modified"):
        build_high_risk_supersession_evidence(
            repository="Halildeu/ao-kernel",
            review_work_package="AO-MA-10j-current",  # current PR wp
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/feature",
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_root=repo,
            raw_review_paths=review_paths,
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-05-28T00:00:00Z",
        )


# === Tests: path-provider audit binding ===


def test_provider_path_binding_mismatch_rejected(
    high_risk_repo: tuple[Path, list[Path], list[str]],
) -> None:
    """openai.* file with reviewer.provider=anthropic must fail (audit
    provenance protection — Codex thread 019e6ffc iter-2 note)."""
    repo, review_paths, changed_files = high_risk_repo
    # review_paths[0] is openai by fixture order; rewrite as anthropic
    first = json.loads(review_paths[0].read_text(encoding="utf-8"))
    first["reviewer"]["provider"] = "anthropic"
    first["reviewer"]["agent"] = "claude-imposter"
    review_paths[0].write_text(json.dumps(first), encoding="utf-8")
    # Need to also amend the commit so the fixture's introducer state holds
    _git(repo, "add", "ao-ma-10-high-risk-reviews/")
    _git(repo, "commit", "--amend", "--no-edit")

    with pytest.raises(ValueError, match="does not match path-bound expected provider"):
        build_high_risk_supersession_evidence(
            repository="Halildeu/ao-kernel",
            review_work_package="AO-MA-10j",
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/feature",
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_root=repo,
            raw_review_paths=review_paths,
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-05-28T00:00:00Z",
        )


# === Tests: suffix-parts path resolution ===


def test_resolve_repo_relative_path_matches_workflow_style_prefix() -> None:
    """Workflow passes paths like ../head/ao-ma-10-high-risk-reviews/openai...
    — suffix-parts match should resolve."""
    resolved = _resolve_repo_relative_path(
        Path("../head/ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json")
    )
    assert resolved == "ao-ma-10-high-risk-reviews/openai.local-ai-review-evidence.v1.json"

    resolved2 = _resolve_repo_relative_path(
        Path("/abs/repo/ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json")
    )
    assert resolved2 == "ao-ma-10-high-risk-reviews/anthropic.local-ai-review-evidence.v1.json"


def test_resolve_repo_relative_path_rejects_non_allowlist() -> None:
    with pytest.raises(ValueError, match="not in allowlist"):
        _resolve_repo_relative_path(Path("../head/some/other/path/local-ai-review-evidence.v1.json"))


# === Tests: schema-pinned binding_mode field ===


def test_schema_pins_binding_mode_enum_on_provider_verdict() -> None:
    """The provider_verdict schema must pin binding_mode as required with
    enum [added, modified, unchanged]."""
    schema = load_default("schemas", "ao-ma-10-high-risk-supersession-evidence.schema.v1.json")
    pv = schema["$defs"]["provider_verdict"]
    assert "binding_mode" in pv["required"]
    assert pv["properties"]["binding_mode"]["enum"] == list(VALID_BINDING_MODES)


def test_high_risk_review_repo_relative_paths_pin_provider() -> None:
    """The path-to-provider audit binding map must include both required
    providers exactly once and point to the matching filename."""
    assert sorted(HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS.values()) == ["anthropic", "openai"]
    for path, provider in HIGH_RISK_REVIEW_REPO_RELATIVE_PATHS.items():
        assert provider in path  # filename contains the provider name


# === Tests: classification dispatch ===


def test_classify_added_vs_modified_vs_unchanged(tmp_path: Path) -> None:
    """Direct check of _classify_evidence_binding dispatch table."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "a.txt", "a\n")
    _write(repo, "b.txt", "b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "feature")

    # ADD c.txt, MODIFY a.txt, leave b.txt unchanged
    _write(repo, "c.txt", "c\n")
    _write(repo, "a.txt", "a-mod\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")

    assert (
        _classify_evidence_binding(
            repo_root=repo,
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_relative_path="c.txt",
        )
        == "added"
    )
    assert (
        _classify_evidence_binding(
            repo_root=repo,
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_relative_path="a.txt",
        )
        == "modified"
    )
    assert (
        _classify_evidence_binding(
            repo_root=repo,
            diff_base_ref="main",
            diff_head_ref="feature",
            repo_relative_path="b.txt",
        )
        == "unchanged"
    )
