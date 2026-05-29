from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10r_dedicated_actor_credential_doctor.py"
DOC = ROOT / ".claude/plans/AO-MA-10R-DEDICATED-ACTOR-CREDENTIAL-DOCTOR.md"
RECEIPT = ROOT / ".claude/plans/AO-MA-10R-DEDICATED-ACTOR-CREDENTIAL-DOCTOR.v1.json"
SCHEMA_NAME = "ao-ma-10r-dedicated-actor-credential-doctor-result.schema.v1.json"
TOKEN_ENV = "GLADYATORE_LAB_GH_TOKEN"
TOKEN_VALUE = "VALUE_NOT_IN_ARTIFACT"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10r_dedicated_actor_credential_doctor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGitHubRunner:
    def __init__(
        self,
        *,
        login: str = "gladyatore-lab",
        actor_id: int = 12345,
        permissions: dict[str, bool] | None = None,
        pulls: list[dict[str, Any]] | None = None,
        fail_command_contains: str | None = None,
    ) -> None:
        self.login = login
        self.actor_id = actor_id
        self.permissions = permissions if permissions is not None else {"pull": True, "push": True, "admin": False}
        self.pulls = [] if pulls is None else pulls
        self.fail_command_contains = fail_command_contains
        self.commands: list[list[str]] = []
        self.envs: list[dict[str, str]] = []

    def __call__(self, command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.envs.append(dict(env))
        joined = " ".join(command)
        if self.fail_command_contains and self.fail_command_contains in joined:
            return subprocess.CompletedProcess(command, 1, "", "forced failure")
        if command == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": self.login, "id": self.actor_id}), "")
        if command == ["gh", "api", "repos/Halildeu/ao-kernel"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"permissions": self.permissions}), "")
        if command == ["gh", "api", "repos/Halildeu/ao-kernel/pulls?state=open&per_page=1"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.pulls), "")
        return subprocess.CompletedProcess(command, 1, "", f"unexpected command: {joined}")


def _run_doctor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: FakeGitHubRunner,
    *,
    token_value: str | None = TOKEN_VALUE,
    expected_actor: str = "gladyatore-lab",
) -> dict[str, Any]:
    if token_value is None:
        monkeypatch.delenv(TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(TOKEN_ENV, token_value)
    mod = _load_script_module()
    return cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            expected_actor=expected_actor,
            token_env=TOKEN_ENV,
            gh_bin="gh",
            output=tmp_path / "ao-ma10r.json",
            runner=runner,
        ),
    )


def test_ao_ma10r_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-10r-dedicated-actor-credential-doctor-result:v1"


def test_ao_ma10r_doc_and_receipt_preserve_no_secret_authority_boundary() -> None:
    receipt = cast(dict[str, Any], json.loads(RECEIPT.read_text(encoding="utf-8")))
    text = DOC.read_text(encoding="utf-8")
    assert receipt["status"] == "implemented_fail_closed"
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    assert receipt["token_value_recorded"] is False
    assert receipt["default_token_env"] == TOKEN_ENV
    assert "never accepts token values as CLI arguments" in text
    assert "Release authority remains the repo-owned" in text


def test_ao_ma10r_missing_token_env_blocks_before_github_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeGitHubRunner()
    result = _run_doctor(tmp_path, monkeypatch, runner, token_value=None)

    Draft202012Validator(_schema()).validate(result)
    assert runner.commands == []
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["dedicated_actor_token_env_missing"]
    assert result["token_value_recorded"] is False
    assert result["mutations_performed"] is False


def test_ao_ma10r_rejects_invalid_token_env_name(tmp_path: Path) -> None:
    mod = _load_script_module()
    with pytest.raises(ValueError, match="token env name"):
        mod.run(
            repo="Halildeu/ao-kernel",
            expected_actor="gladyatore-lab",
            token_env="bad-token-env",
            gh_bin="gh",
            output=tmp_path / "ao-ma10r.json",
            runner=FakeGitHubRunner(),
        )


def test_ao_ma10r_happy_path_ready_without_recording_secret_or_mutating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FakeGitHubRunner()
    result = _run_doctor(tmp_path, monkeypatch, runner)

    Draft202012Validator(_schema()).validate(result)
    artifact_text = (tmp_path / "ao-ma10r.json").read_text(encoding="utf-8")
    assert TOKEN_VALUE not in artifact_text
    assert all(env.get("GH_TOKEN") == TOKEN_VALUE for env in runner.envs)
    assert result["decision"]["result"] == "credential_ready"
    assert result["decision"]["blockers"] == []
    assert result["actor"] == {"login": "gladyatore-lab", "id": 12345, "matches_expected": True}
    assert result["repository_access"]["permission_level"] == "write"
    assert result["repository_access"]["can_merge_without_admin"] is True
    assert result["repository_access"]["admin_permission_observed"] is False
    assert result["repository_access"]["can_read_pull_requests"] is True
    assert result["token_value_recorded"] is False
    assert result["mutations_performed"] is False
    assert result["commands"] == [
        ["gh", "api", "user"],
        ["gh", "api", "repos/Halildeu/ao-kernel"],
        ["gh", "api", "repos/Halildeu/ao-kernel/pulls?state=open&per_page=1"],
    ]


def test_ao_ma10r_accepts_maintain_as_non_admin_merge_capable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(permissions={"pull": True, "push": False, "maintain": True, "admin": False}),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "credential_ready"
    assert result["repository_access"]["permission_level"] == "maintain"
    assert result["repository_access"]["can_merge_without_admin"] is True
    assert result["repository_access"]["admin_permission_observed"] is False


def test_ao_ma10r_blocks_wrong_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(tmp_path, monkeypatch, FakeGitHubRunner(login="Halildeu"))

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "unexpected_merge_actor" in result["decision"]["blockers"]
    assert result["actor"]["matches_expected"] is False


def test_ao_ma10r_blocks_admin_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(permissions={"pull": True, "push": True, "admin": True}),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "merge_actor_admin_permission_observed" in result["decision"]["blockers"]
    assert result["repository_access"]["permission_level"] == "admin"


def test_ao_ma10r_blocks_read_only_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(permissions={"pull": True, "push": False, "admin": False}),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "merge_actor_not_write_capable" in result["decision"]["blockers"]
    assert result["repository_access"]["permission_level"] == "read"


def test_ao_ma10r_blocks_github_api_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(fail_command_contains="pulls?state=open"),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "pull_request_read_failed" in result["decision"]["blockers"]
    assert result["collection_errors"]
    assert TOKEN_VALUE not in (tmp_path / "ao-ma10r.json").read_text(encoding="utf-8")


def test_ao_ma10r_blocks_user_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(fail_command_contains=" api user"),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "github_user_read_failed" in result["decision"]["blockers"]
    assert "unexpected_merge_actor" in result["decision"]["blockers"]
    assert any(item.startswith("user:") for item in result["collection_errors"])


def test_ao_ma10r_blocks_repository_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_doctor(
        tmp_path,
        monkeypatch,
        FakeGitHubRunner(fail_command_contains="repos/Halildeu/ao-kernel"),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "github_repository_read_failed" in result["decision"]["blockers"]
    assert "repository_read_permission_missing" in result["decision"]["blockers"]
    assert "merge_actor_not_write_capable" in result["decision"]["blockers"]
    assert any(item.startswith("repository:") for item in result["collection_errors"])
