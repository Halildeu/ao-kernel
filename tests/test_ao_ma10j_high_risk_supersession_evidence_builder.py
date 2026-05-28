"""AO-MA-10j runtime high-risk supersession evidence builder tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from scripts.ao_ma10_high_risk_supersession_evidence import (
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
) -> dict[str, Any]:
    return {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": "Halildeu/ao-kernel",
        "work_package": "AO-MA-10j",
        "implementer": {"agent": "implementer-agent", "provider": "google"},
        "reviewer": {"agent": agent, "provider": provider, "verdict": verdict},
        "scope_reviewed": {
            "base_ref": "refs/heads/main",
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


@pytest.fixture()
def high_risk_repo(tmp_path: Path) -> tuple[Path, list[Path], list[str]]:
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


def test_build_high_risk_supersession_rejects_missing_required_provider(
    high_risk_repo: tuple[Path, list[Path], list[str]],
) -> None:
    repo, review_paths, changed_files = high_risk_repo
    second = json.loads(review_paths[1].read_text(encoding="utf-8"))
    second["reviewer"]["provider"] = "openai"
    second["reviewer"]["agent"] = "second-openai-reviewer"
    review_paths[1].write_text(json.dumps(second), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly OpenAI and Anthropic"):
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
