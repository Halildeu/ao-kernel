from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ao_kernel.cli import main as cli_main
from ao_kernel.pr_metadata import validate_pr_delivery_metadata_markdown
from ao_kernel.repo_intelligence import validate_repo_intelligence_product_onboarding


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=30)
    return completed.stdout.strip()


def _git_init_repo(repo: Path) -> str:
    _run(["git", "init", "--initial-branch=main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "test"])
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md", "src/a.py"])
    _run(["git", "-C", str(repo), "commit", "-m", "initial"])
    sha = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    _run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha])
    return sha


def _write_synthetic_ssot(repo: Path) -> None:
    (repo / "AGENTS.md").write_text("# AGENTS\nP5 product run-wrapper synthetic SSOT.\n", encoding="utf-8")
    plans_dir = repo / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "gpp_status.v1",
        "current_wp": {
            "id": "P5-run-wrapper-smoke",
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }
    (plans_dir / "gpp_status.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_repo_onboarding_template_is_valid_product_contract(capsys) -> None:
    rc = cli_main(["repo", "onboarding", "template", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    result = validate_repo_intelligence_product_onboarding(payload)
    assert result["status"] == "accepted"
    assert payload["setup"]["end_user_infrastructure"]["cloud_run_required"] is False
    assert payload["safety"]["live_adapter_execution"] is False


def test_repo_onboarding_init_config_and_doctor_ready(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    rc = cli_main(
        [
            "repo",
            "onboarding",
            "init-config",
            "--project-root",
            str(repo),
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    init_payload = json.loads(captured.out)
    assert init_payload["status"] == "written"
    assert (repo / ".ao" / "repo-intelligence.yml").is_file()

    rc = cli_main(
        [
            "repo",
            "onboarding",
            "doctor",
            "--project-root",
            str(repo),
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    doctor = json.loads(captured.out)
    assert doctor["status"] == "ready"
    assert doctor["workspace_exists"] is True
    assert doctor["onboarding"]["status"] == "accepted"
    assert doctor["live_adapter_execution_allowed"] is False


def test_pr_metadata_generate_and_fix_round_trip(tmp_path: Path, capsys) -> None:
    rc = cli_main(
        [
            "pr-metadata",
            "generate",
            "--work-package",
            "AO-MA-10",
            "--issue",
            "#123",
            "--reviewer-provider",
            "anthropic",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert validate_pr_delivery_metadata_markdown(captured.out).valid is True

    body_path = tmp_path / "body.md"
    body_path.write_text("## Summary\n\nProductized metadata UX.\n", encoding="utf-8")
    rc = cli_main(
        [
            "pr-metadata",
            "fix",
            "--body-file",
            str(body_path),
            "--write",
            "--output",
            "json",
            "--work-package",
            "AO-MA-10",
            "--issue",
            "#123",
            "--reviewer-provider",
            "anthropic",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    fix_payload = json.loads(captured.out)
    assert fix_payload["valid"] is True
    assert fix_payload["written"] is True
    assert validate_pr_delivery_metadata_markdown(body_path.read_text(encoding="utf-8")).valid is True


def test_pr_metadata_generate_supports_boundary_declarations(capsys) -> None:
    rc = cli_main(
        [
            "pr-metadata",
            "generate",
            "--work-package",
            "AO-MA-10",
            "--issue",
            "#123",
            "--boundary-credential-read",
            "--user-approval-evidence",
            "https://github.com/Halildeu/ao-kernel/pull/123#issuecomment-1",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    result = validate_pr_delivery_metadata_markdown(captured.out)
    assert result.valid is True
    assert result.metadata is not None
    boundary = result.metadata["boundary_declaration"]
    assert boundary["credential_read"] is True
    assert boundary["none_of_the_above"] is False
    assert boundary["user_approval_evidence"].startswith("https://github.com/")


def test_pr_metadata_generate_rejects_sensitive_boundary_without_evidence(capsys) -> None:
    rc = cli_main(
        [
            "pr-metadata",
            "generate",
            "--work-package",
            "AO-MA-10",
            "--issue",
            "#123",
            "--boundary-credential-read",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "pr-metadata generate failed" in captured.err
    assert "#123" not in captured.err


def test_orchestration_run_wrapper_dry_run_requires_declared_scope(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)

    rc = cli_main(
        [
            "orchestration",
            "run-wrapper",
            "--goal",
            "P5 dry-run wrapper smoke",
            "--repo-root",
            str(repo),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:P5 dry-run",
            "--dry-run",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert payload["worker_statuses"] == [{"task_id": "task-001", "status": "skipped_dry_run"}]
    assert payload["guard_flags"]["live_adapter_execution"] is False


def test_orchestration_run_wrapper_executes_pinned_local_fixture(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)

    rc = cli_main(
        [
            "orchestration",
            "run-wrapper",
            "--goal",
            "P5 execute wrapper smoke",
            "--repo-root",
            str(repo),
            "--worktree-base",
            str(tmp_path / "worktrees"),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:P5 execute",
            "--execute-local-fixture",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["mode"] == "execute_local_fixture"
    assert payload["worker_statuses"] == [{"task_id": "task-001", "status": "prepared"}]
    assert payload["invocation_report_path"] is not None
    assert Path(payload["manifest_path"]).is_file()
    assert Path(payload["runner_report_path"]).is_file()
    assert Path(payload["invocation_report_path"]).is_file()
