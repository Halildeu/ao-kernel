from __future__ import annotations

import json
import subprocess
import importlib.util
from collections.abc import Mapping
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ao_ma10t_configure_dedicated_actor_secret.py"
SPEC = importlib.util.spec_from_file_location("ao_ma10t_configure_dedicated_actor_secret", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(
        self,
        command: list[str],
        env: Mapping[str, str],
        stdin: str | None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(command), stdin))
        assert "token-secret-value" not in command
        if command[:3] == ["gh", "secret", "set"]:
            assert command == [
                "gh",
                "secret",
                "set",
                "GLADYATORE_LAB_GH_TOKEN",
                "--repo",
                "Halildeu/ao-kernel",
            ]
            assert stdin == "token-secret-value"
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "name": "GLADYATORE_LAB_GH_TOKEN",
                        "created_at": "2026-05-29T00:00:00Z",
                        "updated_at": "2026-05-29T00:00:00Z",
                    }
                ),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_source_token_env_fails_closed_without_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLADYATORE_LAB_GH_TOKEN", raising=False)
    output = tmp_path / "result.json"
    runner = FakeRunner()

    result = bootstrap.run(
        repo="Halildeu/ao-kernel",
        secret_name="GLADYATORE_LAB_GH_TOKEN",
        source_token_env="GLADYATORE_LAB_GH_TOKEN",
        gh_bin="gh",
        output=output,
        execute=True,
        confirmation=bootstrap.EXECUTE_CONFIRMATION,
        runner=runner,
    )

    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["source_token_env_missing"]
    assert result["mutations_performed"] is False
    assert result["token_value_recorded"] is False
    assert runner.calls == []
    assert read_json(output)["decision"]["result"] == "blocked"


def test_source_token_without_execute_is_ready_to_configure_no_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GLADYATORE_LAB_GH_TOKEN", "token-secret-value")
    output = tmp_path / "result.json"
    runner = FakeRunner()

    result = bootstrap.run(
        repo="Halildeu/ao-kernel",
        secret_name="GLADYATORE_LAB_GH_TOKEN",
        source_token_env="GLADYATORE_LAB_GH_TOKEN",
        gh_bin="gh",
        output=output,
        execute=False,
        confirmation=None,
        runner=runner,
    )

    assert result["decision"]["result"] == "ready_to_configure"
    assert result["mutations_performed"] is False
    assert runner.calls == []


def test_execute_requires_literal_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLADYATORE_LAB_GH_TOKEN", "token-secret-value")
    output = tmp_path / "result.json"
    runner = FakeRunner()

    result = bootstrap.run(
        repo="Halildeu/ao-kernel",
        secret_name="GLADYATORE_LAB_GH_TOKEN",
        source_token_env="GLADYATORE_LAB_GH_TOKEN",
        gh_bin="gh",
        output=output,
        execute=True,
        confirmation="wrong",
        runner=runner,
    )

    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["execute_confirmation_missing"]
    assert result["mutations_performed"] is False
    assert runner.calls == []


def test_execute_sets_secret_via_stdin_and_records_metadata_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GLADYATORE_LAB_GH_TOKEN", "token-secret-value")
    output = tmp_path / "result.json"
    runner = FakeRunner()

    result = bootstrap.run(
        repo="Halildeu/ao-kernel",
        secret_name="GLADYATORE_LAB_GH_TOKEN",
        source_token_env="GLADYATORE_LAB_GH_TOKEN",
        gh_bin="gh",
        output=output,
        execute=True,
        confirmation=bootstrap.EXECUTE_CONFIRMATION,
        runner=runner,
    )

    assert result["decision"]["result"] == "secret_configured"
    assert result["mutations_performed"] is True
    assert result["token_value_recorded"] is False
    assert result["secret_value_recorded"] is False
    assert result["secret_metadata"] == {
        "name": "GLADYATORE_LAB_GH_TOKEN",
        "created_at_present": True,
        "updated_at_present": True,
    }
    serialized = output.read_text(encoding="utf-8")
    assert "token-secret-value" not in serialized
    assert runner.calls[0][0] == [
        "gh",
        "secret",
        "set",
        "GLADYATORE_LAB_GH_TOKEN",
        "--repo",
        "Halildeu/ao-kernel",
    ]
    assert runner.calls[0][1] == "token-secret-value"
    assert runner.calls[1][0] == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/actions/secrets/GLADYATORE_LAB_GH_TOKEN",
    ]


def test_invalid_env_names_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        bootstrap.run(
            repo="Halildeu/ao-kernel",
            secret_name="BAD-NAME",
            source_token_env="GLADYATORE_LAB_GH_TOKEN",
            gh_bin="gh",
            output=tmp_path / "result.json",
            execute=False,
            confirmation=None,
        )
