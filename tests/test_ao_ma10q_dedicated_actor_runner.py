from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10q_dedicated_actor_runner.py"
DOC = ROOT / ".claude/plans/AO-MA-10Q-DEDICATED-ACTOR-RUNNER.md"
RECEIPT = ROOT / ".claude/plans/AO-MA-10Q-DEDICATED-ACTOR-RUNNER.v1.json"
SCHEMA_NAME = "ao-ma-10q-dedicated-actor-runner-result.schema.v1.json"
TOKEN_ENV = "GLADYATORE_LAB_GH_TOKEN"
GOVERNANCE_TOKEN_ENV = "AO_GOVERNANCE_GH_TOKEN"
TOKEN_VALUE = "VALUE_NOT_IN_ARTIFACT"
GOVERNANCE_TOKEN_VALUE = "GOVERNANCE_VALUE_NOT_IN_ARTIFACT"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10q_dedicated_actor_runner", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _smoke_payload(
    *,
    result: str = "merged",
    blocker: str | None = None,
    mutated: bool = True,
    producer_role: str = "merge_actor",
    producer_same_as_merge_actor: bool = True,
    producer_release_authority: bool = False,
    producer_allowed_operations: list[str] | None = None,
) -> dict[str, Any]:
    blockers = [blocker] if blocker else []
    return {
        "schema_version": "ao-ma-10l-autonomous-smoke-result.v1",
        "artifact_kind": "ao_ma_10l_autonomous_smoke_result",
        "mutations_performed": mutated,
        "pr_producer": {
            "role": producer_role,
            "same_as_merge_actor": producer_same_as_merge_actor,
            "release_authority": producer_release_authority,
            "allowed_operations": producer_allowed_operations
            if producer_allowed_operations is not None
            else ["base_ref_read", "branch_create", "file_create", "pr_create"],
        },
        "decision": {
            "result": result,
            "blockers": blockers,
            "warnings": [],
            "next_required_slice": "record AO-MA-10l result",
        },
    }


class FakeSmokeRunner:
    def __init__(self, payload: dict[str, Any], *, returncode: int = 0) -> None:
        self.payload = payload
        self.returncode = returncode
        self.commands: list[list[str]] = []
        self.timeouts: list[int] = []
        self.wrapper_path: str | None = None
        self.wrapper_mode: int | None = None
        self.wrapper_contents: str | None = None

    def __call__(self, command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.timeouts.append(timeout)
        assert command[0]
        assert command[1].endswith("ao_ma10l_autonomous_smoke.py")
        assert "--gh-bin" in command
        assert "--output" in command
        wrapper = Path(command[command.index("--gh-bin") + 1])
        output = Path(command[command.index("--output") + 1])
        self.wrapper_path = str(wrapper)
        self.wrapper_mode = stat.S_IMODE(wrapper.stat().st_mode)
        self.wrapper_contents = wrapper.read_text(encoding="utf-8")
        output.write_text(json.dumps(self.payload), encoding="utf-8")
        return subprocess.CompletedProcess(command, self.returncode, json.dumps(self.payload), "")


class TimeoutSmokeRunner:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        self.commands: list[list[str]] = []
        self.timeouts: list[int] = []

    def __call__(self, command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.timeouts.append(timeout)
        raise subprocess.TimeoutExpired(command, timeout=self.timeout)


def test_ao_ma10q_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-10q-dedicated-actor-runner-result:v1"


def test_ao_ma10q_doc_and_receipt_preserve_no_secret_authority_boundary() -> None:
    receipt = cast(dict[str, Any], json.loads(RECEIPT.read_text(encoding="utf-8")))
    text = DOC.read_text(encoding="utf-8")
    assert receipt["status"] == "implemented_fail_closed"
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    assert receipt["token_value_recorded"] is False
    assert receipt["wrapper_path_recorded"] is False
    assert receipt["default_token_env"] == TOKEN_ENV
    assert "never accepts token values on CLI arguments" in text
    assert "AI provider output remains evidence only." in text


def test_ao_ma10q_missing_token_env_blocks_before_smoke_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(_smoke_payload())

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=False,
            confirmation=None,
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert output.exists()
    assert runner.commands == []
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["dedicated_actor_token_env_missing"]
    assert result["mutations_performed"] is False
    assert result["token_value_recorded"] is False
    assert result["wrapper"] == {"created": False, "mode": None, "path_recorded": False}
    assert result["producer_wrapper"] == {
        "created": False,
        "mode": None,
        "path_recorded": False,
        "same_as_merge_actor_wrapper": True,
    }
    assert result["producer_token_env"] == TOKEN_ENV


def test_ao_ma10q_rejects_invalid_token_env_name(tmp_path: Path) -> None:
    mod = _load_script_module()
    with pytest.raises(ValueError, match="token env name"):
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env="bad-token-env",
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=tmp_path / "ao-ma10q.json",
            execute=False,
            confirmation=None,
            timeout_seconds=0,
            poll_seconds=1,
            runner=FakeSmokeRunner(_smoke_payload()),
        )


def test_ao_ma10q_execute_uses_temporary_gh_wrapper_without_recording_secret_or_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    monkeypatch.delenv(GOVERNANCE_TOKEN_ENV, raising=False)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(_smoke_payload(result="merged", mutated=True))

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert runner.commands
    assert runner.wrapper_path is not None
    assert runner.wrapper_mode == 0o700
    assert runner.wrapper_contents is not None
    assert TOKEN_ENV in runner.wrapper_contents
    assert TOKEN_VALUE not in runner.wrapper_contents
    github_token_var = "GH_" + "TOKEN"
    assert f'{github_token_var}="${{{TOKEN_ENV}}}" exec gh "$@"' in runner.wrapper_contents
    assert "--governance-gh-bin" not in runner.commands[0]
    assert "--execute" in runner.commands[0]
    assert runner.commands[0][runner.commands[0].index("--confirmation") + 1] == "AO-MA-10L-EXECUTE"

    artifact_text = output.read_text(encoding="utf-8")
    assert TOKEN_VALUE not in artifact_text
    assert runner.wrapper_path not in artifact_text
    assert result["smoke_command"][result["smoke_command"].index("--gh-bin") + 1] == "<temporary-gh-wrapper>"
    assert result["smoke_command"][result["smoke_command"].index("--output") + 1] == "<temporary-smoke-output>"
    assert result["wrapper"] == {"created": True, "mode": "0700", "path_recorded": False}
    assert result["producer_wrapper"] == {
        "created": False,
        "mode": None,
        "path_recorded": False,
        "same_as_merge_actor_wrapper": True,
    }
    assert result["producer_token_env"] == TOKEN_ENV
    assert result["token_value_recorded"] is False
    assert result["decision"]["result"] == "merged"
    assert runner.timeouts == [180]
    assert result["mutations_performed"] is True


def test_ao_ma10q_uses_optional_governance_wrapper_without_recording_secret_or_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    monkeypatch.setenv(GOVERNANCE_TOKEN_ENV, GOVERNANCE_TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(_smoke_payload(result="merged", mutated=True))

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert "--governance-gh-bin" in runner.commands[0]
    assert "--producer-gh-bin" in runner.commands[0]
    assert runner.commands[0][runner.commands[0].index("--governance-gh-bin") + 1].startswith("/tmp/")
    assert runner.commands[0][runner.commands[0].index("--producer-gh-bin") + 1].startswith("/tmp/")
    assert (
        runner.commands[0][runner.commands[0].index("--producer-gh-bin") + 1]
        == runner.commands[0][runner.commands[0].index("--governance-gh-bin") + 1]
    )
    artifact_text = output.read_text(encoding="utf-8")
    assert TOKEN_VALUE not in artifact_text
    assert GOVERNANCE_TOKEN_VALUE not in artifact_text
    assert result["smoke_command"].count("<temporary-gh-wrapper>") == 3
    assert result["producer_token_env"] == GOVERNANCE_TOKEN_ENV
    assert result["producer_wrapper"] == {
        "created": True,
        "mode": "0700",
        "path_recorded": False,
        "same_as_merge_actor_wrapper": False,
    }
    assert result["decision"]["result"] == "merged"
    assert runner.timeouts == [180]


def test_ao_ma10q_accepts_bounded_governance_producer_without_release_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    monkeypatch.setenv(GOVERNANCE_TOKEN_ENV, GOVERNANCE_TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(
        _smoke_payload(
            result="merged",
            mutated=True,
            producer_role="governance_producer",
            producer_same_as_merge_actor=False,
        )
    )

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert "--producer-gh-bin" in runner.commands[0]
    assert result["decision"]["result"] == "merged"
    assert result["decision"]["blockers"] == []
    assert result["mutations_performed"] is True


def test_ao_ma10q_blocks_if_split_producer_claims_release_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    monkeypatch.setenv(GOVERNANCE_TOKEN_ENV, GOVERNANCE_TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(
        _smoke_payload(
            result="merged",
            mutated=True,
            producer_role="governance_producer",
            producer_same_as_merge_actor=False,
            producer_release_authority=True,
        )
    )

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["producer_release_authority_observed"]
    assert result["mutations_performed"] is True


def test_ao_ma10q_default_subprocess_timeout_exceeds_inner_smoke_window() -> None:
    mod = _load_script_module()
    assert mod._smoke_process_timeout(timeout_seconds=900, poll_seconds=15) == 960
    assert mod._smoke_process_timeout(timeout_seconds=60, poll_seconds=30) == 180
    assert mod._smoke_process_timeout(timeout_seconds=0, poll_seconds=1) == 180


def test_ao_ma10q_catches_smoke_command_timeout_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = TimeoutSmokeRunner(timeout=321)

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=900,
            poll_seconds=15,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert output.exists()
    assert runner.commands
    assert runner.timeouts == [960]
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["smoke_command_timeout: 321s"]
    assert result["smoke_result"] is None
    assert result["mutations_performed"] is False
    assert result["token_value_recorded"] is False


def test_ao_ma10q_default_runner_applies_aligned_subprocess_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    observed: dict[str, Any] = {}

    def fake_subprocess_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["capture_output"] = capture_output
        observed["text"] = text
        observed["timeout"] = timeout
        raise subprocess.TimeoutExpired(command, timeout=timeout)

    monkeypatch.setattr(mod.subprocess, "run", fake_subprocess_run)

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=900,
            poll_seconds=15,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert observed["timeout"] == 960
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["smoke_command_timeout: 960s"]


def test_ao_ma10q_propagates_smoke_blockers_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN_VALUE)
    mod = _load_script_module()
    output = tmp_path / "ao-ma10q.json"
    runner = FakeSmokeRunner(
        _smoke_payload(result="blocked", blocker="unexpected_merge_actor", mutated=False),
        returncode=1,
    )

    result = cast(
        dict[str, Any],
        mod.run(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="gladyatore-lab",
            token_env=TOKEN_ENV,
            governance_token_env=GOVERNANCE_TOKEN_ENV,
            base_gh_bin="gh",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=runner,
        ),
    )

    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert result["decision"]["blockers"] == ["unexpected_merge_actor"]
    assert result["mutations_performed"] is False
    assert result["smoke_result"]["decision"]["result"] == "blocked"
