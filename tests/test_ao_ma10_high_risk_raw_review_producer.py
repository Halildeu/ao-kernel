from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from scripts import ao_ma10_high_risk_raw_review_producer as producer


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _repo_with_high_risk_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    workflow = repo / ".github" / "workflows" / "test.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: test\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature")
    workflow.write_text("name: test\n# high-risk change\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    return repo


def _repo_with_low_risk_change(tmp_path: Path) -> Path:
    repo = tmp_path / "low"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    doc = repo / "docs"
    doc.mkdir()
    (doc / "note.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature")
    (doc / "note.md").write_text("base\nchange\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    return repo


def _fake_provider(tmp_path: Path, *, verdict: str = "AGREE", secret: bool = False) -> Path:
    script = tmp_path / f"fake_{verdict.lower()}_{'secret' if secret else 'clean'}.py"
    finding_expr = (
        "'contains ' + 'token' + '=' + 'abcdefghijklmnopqrstuvwxyz'"
        if secret
        else "'review clean'"
    )
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "request = json.load(sys.stdin)",
                "provider = sys.argv[1]",
                "json.dump({",
                "  'agent': provider + '-fake-reviewer',",
                f"  'verdict': {verdict!r},",
                "  'checks_considered': [",
                "    {'name': 'tests', 'status': 'pass'},",
                "    {'name': 'secret_scan', 'status': 'pass'},",
                "  ],",
                f"  'findings': [{finding_expr}, 'files=' + str(len(request['context']['changed_files']))],",
                "}, sys.stdout)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script


def _provider_commands(
    tmp_path: Path,
    *,
    verdict: str = "AGREE",
    secret: bool = False,
) -> dict[str, producer.ProviderCommand]:
    fake = _fake_provider(tmp_path, verdict=verdict, secret=secret)
    return {
        provider_id: producer.ProviderCommand(
            provider=provider_id,
            command=(sys.executable, str(fake), provider_id),
        )
        for provider_id in producer.PROVIDER_REVIEW_POOL
    }


def test_producer_writes_schema_valid_default_openai_and_anthropic_raw_reviews(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    output_dir = tmp_path / "reviews"

    paths = producer.produce_raw_reviews(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10K",
        implementer={"agent": "codex", "provider": "google"},
        base_ref="main",
        head_ref="feature",
        repo_root=repo,
        output_dir=output_dir,
        provider_commands=_provider_commands(tmp_path),
        max_diff_bytes=200_000,
        timeout_seconds=30,
    )

    schema = load_default("schemas", producer.RAW_REVIEW_SCHEMA)
    for provider_id, path in paths.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)
        assert path.name == f"{provider_id}.local-ai-review-evidence.v1.json"
        assert payload["reviewer"]["provider"] == provider_id
        assert payload["reviewer"]["verdict"] == "AGREE"
        assert payload["scope_reviewed"]["changed_files"] == [".github/workflows/test.yml"]
        assert payload["secrets_recorded"] is False
        assert payload["support_widening"] is False
        assert payload["production_platform_claim"] is False
        assert payload["live_adapter_execution"] is False


def test_producer_excludes_implementer_provider_from_required_reviewers(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    output_dir = tmp_path / "reviews"

    paths = producer.produce_raw_reviews(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10K",
        implementer={"agent": "codex", "provider": "openai"},
        base_ref="main",
        head_ref="feature",
        repo_root=repo,
        output_dir=output_dir,
        provider_commands=_provider_commands(tmp_path),
        max_diff_bytes=200_000,
        timeout_seconds=30,
    )

    assert set(paths) == {"anthropic", "minimax"}
    assert "openai" not in paths


def test_producer_requires_both_provider_commands() -> None:
    with pytest.raises(ValueError, match="missing required provider command"):
        producer._parse_provider_specs(["openai=echo {}"])


def test_producer_fails_closed_when_provider_verdict_is_not_agree(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)

    with pytest.raises(ValueError, match="verdict is not AGREE"):
        producer.produce_raw_reviews(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10K",
            implementer={"agent": "codex", "provider": "openai"},
            base_ref="main",
            head_ref="feature",
            repo_root=repo,
            output_dir=tmp_path / "reviews",
            provider_commands=_provider_commands(tmp_path, verdict="REVISE"),
            max_diff_bytes=200_000,
            timeout_seconds=30,
        )


def test_producer_fails_closed_on_secret_like_provider_output(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)

    with pytest.raises(ValueError, match="secret-like"):
        producer.produce_raw_reviews(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10K",
            implementer={"agent": "codex", "provider": "openai"},
            base_ref="main",
            head_ref="feature",
            repo_root=repo,
            output_dir=tmp_path / "reviews",
            provider_commands=_provider_commands(tmp_path, secret=True),
            max_diff_bytes=200_000,
            timeout_seconds=30,
        )


def test_producer_refuses_low_risk_changes(tmp_path: Path) -> None:
    repo = _repo_with_low_risk_change(tmp_path)

    with pytest.raises(ValueError, match="no high-risk changed paths"):
        producer.produce_raw_reviews(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10K",
            implementer={"agent": "codex", "provider": "openai"},
            base_ref="main",
            head_ref="feature",
            repo_root=repo,
            output_dir=tmp_path / "reviews",
            provider_commands=_provider_commands(tmp_path),
            max_diff_bytes=200_000,
            timeout_seconds=30,
        )


def test_provider_specs_can_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AO_MA10_OPENAI_REVIEW_CMD", "python openai.py")
    monkeypatch.setenv("AO_MA10_ANTHROPIC_REVIEW_CMD", "python anthropic.py")

    commands = producer._parse_provider_specs([])

    assert commands["openai"].command == ("python", "openai.py")
    assert commands["anthropic"].command == ("python", "anthropic.py")


def test_cli_outputs_paths_without_secret_values(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path)
    output_dir = tmp_path / "reviews"

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/ao_ma10_high_risk_raw_review_producer.py",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10K",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--provider",
            f"openai={sys.executable} {fake} openai",
            "--provider",
            f"anthropic={sys.executable} {fake} anthropic",
            "--implementer-provider",
            "google",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )

    assert proc.returncode == 0, proc.stderr
    assert "openai:" in proc.stdout
    assert "anthropic:" in proc.stdout
    assert "token=" not in proc.stdout
    assert (output_dir / "openai.local-ai-review-evidence.v1.json").exists()
    assert (output_dir / "anthropic.local-ai-review-evidence.v1.json").exists()
