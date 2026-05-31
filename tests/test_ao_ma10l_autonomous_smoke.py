from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10l_autonomous_smoke.py"
DOC = ROOT / ".claude/plans/AO-MA-10L-POSITIVE-AUTONOMOUS-SMOKE.md"
RECEIPT = ROOT / ".claude/plans/AO-MA-10L-POSITIVE-AUTONOMOUS-SMOKE.v1.json"
SCHEMA_NAME = "ao-ma-10l-autonomous-smoke-result.schema.v1.json"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10l_autonomous_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_snapshot() -> dict[str, Any]:
    return {
        "schema_version": "ao-ma-10-github-readiness-snapshot.v1",
        "artifact_kind": "ao_ma_10_github_readiness_snapshot",
        "repository": "Halildeu/ao-kernel",
        "branch": "main",
        "generated_at": "2026-05-28T21:00:00Z",
        "read_only": True,
        "mutations_performed": False,
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "readiness": {"decision": "ready_for_dry_run", "blockers": [], "warnings": []},
        "merge_actor": {
            "login": "github-actions[bot]",
            "permission": "write",
            "viewer_can_administer": False,
            "administration_write_absent_for_dedicated_actor": True,
        },
    }


def _blocked_snapshot() -> dict[str, Any]:
    snapshot = _ready_snapshot()
    snapshot["readiness"] = {
        "decision": "blocked",
        "blockers": [
            "unexpected_merge_actor",
            "merge_actor_admin_permission_observed",
            "dedicated_merge_actor_not_confirmed",
        ],
        "warnings": [],
    }
    snapshot["merge_actor"] = {
        "login": "Halildeu",
        "permission": "admin",
        "viewer_can_administer": True,
        "administration_write_absent_for_dedicated_actor": False,
    }
    return snapshot


def _ready_eligibility(changed_file: str) -> dict[str, Any]:
    return {
        "schema_version": "ao-ma-10-autonomous-merge-eligibility.v1",
        "artifact_kind": "ao_ma_10_autonomous_merge_eligibility",
        "generated_at": "2026-05-28T21:00:00Z",
        "read_only": True,
        "mutations_performed": False,
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "candidate_changed_files": {
            "files": [changed_file],
            "files_count": 1,
            "low_risk": True,
            "invalid_paths": [],
            "not_allowed": [],
            "prohibited_matches": [],
            "release_gate_high_risk_matches": [],
        },
        "decision": {
            "result": "ready_for_low_risk_dry_run",
            "blockers": [],
            "warnings": [],
            "next_required_slice": "AO-MA-10c merge-agent dry-run",
        },
    }


def _blocked_eligibility(changed_file: str) -> dict[str, Any]:
    payload = _ready_eligibility(changed_file)
    payload["decision"] = {
        "result": "blocked",
        "blockers": ["unexpected_merge_actor"],
        "warnings": [],
        "next_required_slice": "resolve_live_github_enforcement_blockers_before_AO-MA-10k_or_merge_agent_activation",
    }
    return payload


def _merge_agent_merged() -> dict[str, Any]:
    return {
        "schema_version": "ao-ma-10c-merge-agent-result.v1",
        "artifact_kind": "ao_ma_10c_merge_agent_result",
        "decision": {"result": "merged", "blockers": [], "warnings": [], "next_required_slice": "record evidence"},
    }


class FakeRunner:
    def __init__(
        self,
        *,
        ready: bool = True,
        checks_pass: bool = True,
        checks_transient_failures: int = 0,
        checks_transient_error: str = "no checks reported on the 'codex/ao-ma10l-smoke-example' branch",
        gh_bin: str = "gh",
        producer_gh_bin: str | None = None,
    ) -> None:
        self.ready = ready
        self.checks_pass = checks_pass
        self.checks_transient_failures = checks_transient_failures
        self.checks_transient_error = checks_transient_error
        self.gh_bin = gh_bin
        self.producer_gh_bin = producer_gh_bin or gh_bin
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if len(command) > 1 and command[1].endswith("ao_ma10_github_readiness_snapshot.py"):
            output = Path(command[command.index("--output") + 1])
            output.write_text(json.dumps(_ready_snapshot() if self.ready else _blocked_snapshot()), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        if len(command) > 1 and command[1].endswith("ao_ma10_autonomous_merge_eligibility.py"):
            output = Path(command[command.index("--output") + 1])
            changed_file = command[command.index("--changed-file") + 1]
            payload = _ready_eligibility(changed_file) if self.ready else _blocked_eligibility(changed_file)
            output.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0 if self.ready else 1, json.dumps(payload), "")
        if command[:3] == [self.producer_gh_bin, "api", "repos/Halildeu/ao-kernel/git/ref/heads/main"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"object": {"sha": "a" * 40}}), "")
        if command[:3] == [self.producer_gh_bin, "api", "repos/Halildeu/ao-kernel/git/refs"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"ref": "refs/heads/example"}), "")
        if len(command) >= 3 and command[:2] == [self.producer_gh_bin, "api"] and "/contents/" in command[2]:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"content": {"path": "docs/evidence/example.md"}}), ""
            )
        if command[:3] == [self.producer_gh_bin, "pr", "create"]:
            return subprocess.CompletedProcess(command, 0, "https://github.com/Halildeu/ao-kernel/pull/999\n", "")
        if command[:3] == [self.gh_bin, "pr", "checks"]:
            if self.checks_transient_failures > 0:
                self.checks_transient_failures -= 1
                return subprocess.CompletedProcess(
                    command,
                    1,
                    "",
                    self.checks_transient_error,
                )
            checks = (
                [
                    {"name": "ao-release-gate-technical", "bucket": "pass", "state": "SUCCESS"},
                    {"name": "ao-release-gate-review", "bucket": "pass", "state": "SUCCESS"},
                ]
                if self.checks_pass
                else [
                    {"name": "ao-release-gate-technical", "bucket": "pass", "state": "SUCCESS"},
                    {"name": "ao-release-gate-review", "bucket": "fail", "state": "FAILURE"},
                ]
            )
            return subprocess.CompletedProcess(command, 0, json.dumps(checks), "")
        if len(command) > 1 and command[1].endswith("ao_ma10c_merge_agent.py"):
            output = Path(command[command.index("--output") + 1])
            output.write_text(json.dumps(_merge_agent_merged()), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, json.dumps(_merge_agent_merged()), "")
        raise AssertionError(command)


def _run_with_fake(
    tmp_path: Path,
    fake: FakeRunner,
    *,
    execute: bool = False,
    confirmation: str | None = None,
    gh_bin: str = "gh",
    governance_gh_bin: str | None = None,
    producer_gh_bin: str | None = None,
) -> dict[str, Any]:
    mod = _load_script_module()
    output = tmp_path / "result.json"
    return cast(
        dict[str, Any],
        mod.run_smoke(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="github-actions[bot]",
            gh_bin=gh_bin,
            governance_gh_bin=governance_gh_bin,
            producer_gh_bin=producer_gh_bin,
            smoke_root="docs/evidence/ao-ma-10l-autonomous-smoke",
            output=output,
            execute=execute,
            confirmation=confirmation,
            timeout_seconds=0,
            poll_seconds=1,
            runner=fake,
            now=datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC),
        ),
    )


def test_ao_ma10l_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-10l-autonomous-smoke-result:v1"


def test_ao_ma10l_doc_and_receipt_preserve_authority_boundary() -> None:
    receipt = _json(RECEIPT)
    text = DOC.read_text(encoding="utf-8")
    assert receipt["status"] == "implemented_fail_closed"
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    assert receipt["expected_actor"] == "github-actions[bot]"
    assert "AI provider output remains evidence only." in text
    assert "AO-MA-10c merge-agent" in text


def test_ao_ma10l_current_admin_actor_blocks_before_github_write(tmp_path: Path) -> None:
    fake = FakeRunner(ready=False)
    result = _run_with_fake(tmp_path, fake)
    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "blocked"
    assert "unexpected_merge_actor" in result["decision"]["blockers"]
    assert "merge_actor_admin_permission_observed" in result["decision"]["blockers"]
    assert result["mutations_performed"] is False
    assert not any(command[:2] == ["gh", "api"] and "/git/refs" in command[2] for command in fake.commands)
    assert not any(command[:3] == ["gh", "pr", "create"] for command in fake.commands)


def test_ao_ma10l_execute_requires_confirmation_before_writes(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True)
    result = _run_with_fake(tmp_path, fake, execute=True)
    assert result["decision"]["result"] == "blocked"
    assert "execute_confirmation_missing" in result["decision"]["blockers"]
    assert result["mutations_performed"] is False
    assert not any(command[:3] == ["gh", "pr", "create"] for command in fake.commands)


def test_ao_ma10l_ready_dry_run_has_no_mutations(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True)
    result = _run_with_fake(tmp_path, fake)
    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "ready_for_smoke_dry_run"
    assert result["execute_requested"] is False
    assert result["mutations_performed"] is False
    assert result["smoke_path"].startswith("docs/evidence/ao-ma-10l-autonomous-smoke/")
    assert result["pr_producer"] == {
        "role": "merge_actor",
        "same_as_merge_actor": True,
        "release_authority": False,
        "allowed_operations": ["base_ref_read", "branch_create", "file_create", "pr_create"],
    }


def test_ao_ma10l_execute_success_creates_pr_and_delegates_merge_agent(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True)
    result = _run_with_fake(tmp_path, fake, execute=True, confirmation="AO-MA-10L-EXECUTE")
    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "merged"
    assert result["mutations_performed"] is True
    assert result["created_pr"]["number"] == 999
    assert result["required_checks"]["all_passed"] is True
    assert result["merge_agent_result"]["decision"]["result"] == "merged"
    assert any(command[:3] == ["gh", "pr", "create"] for command in fake.commands)
    merge_agent_commands = [
        command for command in fake.commands if len(command) > 1 and command[1].endswith("ao_ma10c_merge_agent.py")
    ]
    assert merge_agent_commands
    assert "--execute" in merge_agent_commands[0]
    assert "--admin" not in merge_agent_commands[0]


def test_ao_ma10l_propagates_custom_gh_bin_to_all_live_github_calls(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True, gh_bin="gh-dedicated")
    result = _run_with_fake(
        tmp_path,
        fake,
        execute=True,
        confirmation="AO-MA-10L-EXECUTE",
        gh_bin="gh-dedicated",
    )
    assert result["decision"]["result"] == "merged"

    readiness_commands = [
        command
        for command in fake.commands
        if len(command) > 1 and command[1].endswith("ao_ma10_github_readiness_snapshot.py")
    ]
    assert len(readiness_commands) == 2
    assert all(command[command.index("--gh-bin") + 1] == "gh-dedicated" for command in readiness_commands)

    live_gh_commands = [command for command in fake.commands if len(command) > 1 and command[1] in {"api", "pr"}]
    assert live_gh_commands
    assert all(command[0] == "gh-dedicated" for command in live_gh_commands)

    merge_agent_commands = [
        command for command in fake.commands if len(command) > 1 and command[1].endswith("ao_ma10c_merge_agent.py")
    ]
    assert merge_agent_commands
    assert merge_agent_commands[0][merge_agent_commands[0].index("--gh-bin") + 1] == "gh-dedicated"


def test_ao_ma10l_uses_governance_gh_bin_only_for_readiness_snapshots(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True, gh_bin="gh-dedicated")
    mod = _load_script_module()
    output = tmp_path / "result.json"
    result = cast(
        dict[str, Any],
        mod.run_smoke(
            repo="Halildeu/ao-kernel",
            base_ref="main",
            expected_actor="github-actions[bot]",
            gh_bin="gh-dedicated",
            governance_gh_bin="gh-governance",
            producer_gh_bin=None,
            smoke_root="docs/evidence/ao-ma-10l-autonomous-smoke",
            output=output,
            execute=True,
            confirmation="AO-MA-10L-EXECUTE",
            timeout_seconds=0,
            poll_seconds=1,
            runner=fake,
            now=datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC),
        ),
    )
    assert result["decision"]["result"] == "merged"

    readiness_commands = [
        command
        for command in fake.commands
        if len(command) > 1 and command[1].endswith("ao_ma10_github_readiness_snapshot.py")
    ]
    assert len(readiness_commands) == 2
    assert all(command[command.index("--gh-bin") + 1] == "gh-governance" for command in readiness_commands)
    assert all(command[command.index("--actor-gh-bin") + 1] == "gh-dedicated" for command in readiness_commands)

    live_gh_commands = [command for command in fake.commands if len(command) > 1 and command[1] in {"api", "pr"}]
    assert live_gh_commands
    assert all(command[0] == "gh-dedicated" for command in live_gh_commands)


def test_ao_ma10l_can_split_disposable_pr_producer_from_merge_actor(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True, gh_bin="gh-dedicated", producer_gh_bin="gh-producer")
    result = _run_with_fake(
        tmp_path,
        fake,
        execute=True,
        confirmation="AO-MA-10L-EXECUTE",
        gh_bin="gh-dedicated",
        governance_gh_bin="gh-governance",
        producer_gh_bin="gh-producer",
    )
    Draft202012Validator(_schema()).validate(result)
    assert result["decision"]["result"] == "merged"
    assert result["pr_producer"]["role"] == "governance_producer"
    assert result["pr_producer"]["same_as_merge_actor"] is False
    assert result["pr_producer"]["release_authority"] is False

    producer_commands = [
        command
        for command in fake.commands
        if len(command) > 1
        and command[0] == "gh-producer"
        and (command[1] == "api" or command[:3] == ["gh-producer", "pr", "create"])
    ]
    assert producer_commands
    assert all(
        command[0] == "gh-producer"
        for command in producer_commands
        if command[1] == "api" or command[:3] == ["gh-producer", "pr", "create"]
    )

    check_commands = [command for command in fake.commands if command[:3] == ["gh-dedicated", "pr", "checks"]]
    assert check_commands
    merge_agent_commands = [
        command for command in fake.commands if len(command) > 1 and command[1].endswith("ao_ma10c_merge_agent.py")
    ]
    assert merge_agent_commands
    assert merge_agent_commands[0][merge_agent_commands[0].index("--gh-bin") + 1] == "gh-dedicated"


@pytest.mark.parametrize(
    "transient_error",
    [
        "no checks reported on the 'codex/ao-ma10l-smoke-example' branch",
        "no required checks reported on the 'codex/ao-ma10l-smoke-example' branch",
    ],
)
def test_ao_ma10l_waits_for_initial_required_checks_to_appear(tmp_path: Path, transient_error: str) -> None:
    fake = FakeRunner(ready=True, checks_transient_failures=1, checks_transient_error=transient_error)
    mod = _load_script_module()
    monkeypatch_sleep = mod.time.sleep
    mod.time.sleep = lambda _seconds: None
    try:
        result = cast(
            dict[str, Any],
            mod.run_smoke(
                repo="Halildeu/ao-kernel",
                base_ref="main",
                expected_actor="github-actions[bot]",
                gh_bin="gh",
                governance_gh_bin=None,
                producer_gh_bin=None,
                smoke_root="docs/evidence/ao-ma-10l-autonomous-smoke",
                output=tmp_path / "result.json",
                execute=True,
                confirmation="AO-MA-10L-EXECUTE",
                timeout_seconds=5,
                poll_seconds=1,
                runner=fake,
                now=datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC),
            ),
        )
    finally:
        mod.time.sleep = monkeypatch_sleep

    assert result["decision"]["result"] == "merged"
    check_commands = [command for command in fake.commands if command[:3] == ["gh", "pr", "checks"]]
    assert len(check_commands) == 2


def test_ao_ma10l_required_check_failure_blocks_before_merge_agent(tmp_path: Path) -> None:
    fake = FakeRunner(ready=True, checks_pass=False)
    result = _run_with_fake(tmp_path, fake, execute=True, confirmation="AO-MA-10L-EXECUTE")
    assert result["decision"]["result"] == "blocked"
    assert "required_checks_not_passed" in result["decision"]["blockers"]
    assert result["mutations_performed"] is True
    assert result["created_pr"]["number"] == 999
    assert not any(len(command) > 1 and command[1].endswith("ao_ma10c_merge_agent.py") for command in fake.commands)
