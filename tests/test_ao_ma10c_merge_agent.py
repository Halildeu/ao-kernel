from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10c_merge_agent.py"
DOC = ROOT / ".claude/plans/AO-MA-10C-MERGE-AGENT-EXECUTOR.md"
RECEIPT = ROOT / ".claude/plans/AO-MA-10C-MERGE-AGENT-EXECUTOR.v1.json"
READY_ELIGIBILITY = ROOT / "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.ready.valid.json"
DRY_RUN_FIXTURE = ROOT / "tests/fixtures/ao_ma_10c/merge_agent.ready_dry_run.valid.json"
BLOCKED_FIXTURE = ROOT / "tests/fixtures/ao_ma_10c/merge_agent.blocked_admin_actor.valid.json"
SCHEMA_NAME = "ao-ma-10c-merge-agent-result.schema.v1.json"
EXPECTED_ACTOR = "github-actions[bot]"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10c_merge_agent", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_snapshot(now: datetime) -> dict[str, Any]:
    return {
        "schema_version": "ao-ma-10-github-readiness-snapshot.v1",
        "artifact_kind": "ao_ma_10_github_readiness_snapshot",
        "repository": "Halildeu/ao-kernel",
        "branch": "main",
        "generated_at": (now - timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
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
            "login": EXPECTED_ACTOR,
            "permission": "write",
            "viewer_can_administer": False,
            "administration_write_absent_for_dedicated_actor": True,
        },
    }


def _ready_live_state() -> dict[str, Any]:
    return {
        "viewer": {"login": EXPECTED_ACTOR},
        "permission": {"permission": "write", "role_name": "write"},
        "pr_view": {
            "state": "OPEN",
            "isDraft": False,
            "baseRefName": "main",
            "headRefName": "codex/ao-ma10l-smoke-test",
            "headRefOid": "a" * 40,
            "isCrossRepository": False,
            "mergeStateStatus": "CLEAN",
        },
        "required_checks": [
            {"name": "ao-release-gate-technical", "bucket": "pass", "state": "SUCCESS"},
            {"name": "ao-release-gate-review", "bucket": "pass", "state": "SUCCESS"},
        ],
        "collection_errors": [],
    }


def _result(
    *,
    snapshot: dict[str, Any] | None = None,
    eligibility: dict[str, Any] | None = None,
    live_state: dict[str, Any] | None = None,
    execute: bool = False,
    confirmation: str | None = None,
    merge_exit_code: int | None = None,
    branch_delete_exit_code: int | None = None,
    branch_delete_stderr: str = "",
) -> dict[str, Any]:
    mod = _load_script_module()
    now = datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC)
    return cast(
        dict[str, Any],
        mod.build_result(
            repo="Halildeu/ao-kernel",
            pr_number=123,
            snapshot=snapshot or _ready_snapshot(now),
            eligibility=eligibility or _json(READY_ELIGIBILITY),
            live_state=live_state or _ready_live_state(),
            now=now,
            execute=execute,
            confirmation=confirmation,
            merge_exit_code=merge_exit_code,
            branch_delete_exit_code=branch_delete_exit_code,
            branch_delete_stderr=branch_delete_stderr,
        ),
    )


def test_ao_ma10c_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-10c-merge-agent-result:v1"


def test_ao_ma10c_receipt_and_doc_preserve_authority_boundary() -> None:
    receipt = _json(RECEIPT)
    text = DOC.read_text(encoding="utf-8")
    assert receipt["status"] == "implemented_fail_closed"
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    assert receipt["expected_actor"] == EXPECTED_ACTOR
    assert receipt["native_auto_merge_enablement"] is False
    assert "AI output remains evidence only." in text
    assert "Halildeu` with admin permission" in text


def test_ao_ma10c_fixtures_validate_against_schema() -> None:
    validator = Draft202012Validator(_schema())
    for fixture in (DRY_RUN_FIXTURE, BLOCKED_FIXTURE):
        payload = _json(fixture)
        validator.validate(payload)
        assert payload["schema_version"] == "ao-ma-10c-merge-agent-result.v1"


def test_ao_ma10c_ready_dry_run_does_not_attempt_merge() -> None:
    payload = _result()
    Draft202012Validator(_schema()).validate(payload)
    assert payload["decision"]["result"] == "ready_for_merge_dry_run"
    assert payload["dry_run"] is True
    assert payload["merge_command_attempted"] is False
    assert payload["mutations_performed"] is False
    assert payload["merge_command_argv"] == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/pulls/123/merge",
        "--method",
        "PUT",
        "-f",
        "merge_method=squash",
        "-f",
        f"sha={'a' * 40}",
    ]
    assert payload["branch_delete_command_argv"] == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/git/refs/heads/codex/ao-ma10l-smoke-test",
        "--method",
        "DELETE",
    ]
    assert "--admin" not in payload["merge_command_argv"]
    assert "--auto" not in payload["merge_command_argv"]


def test_ao_ma10c_execute_requires_explicit_confirmation() -> None:
    payload = _result(execute=True)
    assert payload["decision"]["result"] == "blocked"
    assert "execute_confirmation_missing" in payload["decision"]["blockers"]
    assert payload["merge_command_attempted"] is False


def test_ao_ma10c_execute_success_requires_all_gates() -> None:
    payload = _result(execute=True, confirmation="AO-MA-10C-EXECUTE", merge_exit_code=0)
    assert payload["decision"]["result"] == "merged"
    assert payload["merge_command_attempted"] is True
    assert payload["mutations_performed"] is True


def test_ao_ma10c_merge_command_failure_is_fail_closed() -> None:
    payload = _result(execute=True, confirmation="AO-MA-10C-EXECUTE", merge_exit_code=1)
    assert payload["decision"]["result"] == "blocked"
    assert "merge_command_failed" in payload["decision"]["blockers"]


def test_ao_ma10c_branch_delete_failure_warns_without_undoing_merge_result() -> None:
    payload = _result(
        execute=True,
        confirmation="AO-MA-10C-EXECUTE",
        merge_exit_code=0,
        branch_delete_exit_code=1,
        branch_delete_stderr="delete failed",
    )
    assert payload["decision"]["result"] == "merged"
    assert payload["branch_delete_attempted"] is True
    assert payload["branch_delete_error"] == "delete failed"
    assert "branch_delete_failed" in payload["decision"]["warnings"]


def test_ao_ma10c_execute_blocks_when_pr_head_sha_is_missing() -> None:
    live = _ready_live_state()
    live["pr_view"]["headRefOid"] = None
    payload = _result(live_state=live, execute=True, confirmation="AO-MA-10C-EXECUTE")

    assert payload["decision"]["result"] == "blocked"
    assert "pr_head_sha_missing" in payload["decision"]["blockers"]
    assert payload["merge_command_attempted"] is False


def test_ao_ma10c_execute_merge_uses_rest_merge_and_branch_delete(monkeypatch: Any) -> None:
    mod = _load_script_module()
    seen: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel/pulls/123/merge"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"merged": True}), "")
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel/git/refs/heads/codex/ao-ma10l-smoke-test"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run", fake_run)
    merge_exit, merge_error, delete_exit, delete_error, merge_argv, delete_argv = mod.execute_merge(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        pr_view=_ready_live_state()["pr_view"],
        base_ref="main",
        gh_bin="gh",
    )

    assert merge_exit == 0
    assert merge_error
    assert delete_exit == 0
    assert delete_error == ""
    assert merge_argv == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/pulls/123/merge",
        "--method",
        "PUT",
        "-f",
        "merge_method=squash",
        "-f",
        f"sha={'a' * 40}",
    ]
    assert delete_argv == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/git/refs/heads/codex/ao-ma10l-smoke-test",
        "--method",
        "DELETE",
    ]
    assert all("pr" not in command[:2] for command in seen)


def test_ao_ma10c_execute_merge_failure_does_not_delete_branch(monkeypatch: Any) -> None:
    mod = _load_script_module()
    seen: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel/pulls/123/merge"]:
            return subprocess.CompletedProcess(command, 1, "", "merge rejected")
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run", fake_run)
    merge_exit, merge_error, delete_exit, _delete_error, _merge_argv, delete_argv = mod.execute_merge(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        pr_view=_ready_live_state()["pr_view"],
        base_ref="main",
        gh_bin="gh",
    )

    assert merge_exit == 1
    assert merge_error == "merge rejected"
    assert delete_exit is None
    assert delete_argv == []
    assert len(seen) == 1


def test_ao_ma10c_skips_branch_delete_for_cross_repository_pr() -> None:
    live = _ready_live_state()
    live["pr_view"]["isCrossRepository"] = True
    payload = _result(
        live_state=live,
        execute=True,
        confirmation="AO-MA-10C-EXECUTE",
        merge_exit_code=0,
    )

    assert payload["decision"]["result"] == "merged"
    assert payload["branch_delete_command_argv"] == []
    assert "branch_delete_skipped_cross_repository" in payload["decision"]["warnings"]


def test_ao_ma10c_blocks_current_admin_actor() -> None:
    snapshot = _ready_snapshot(datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC))
    snapshot["merge_actor"]["login"] = "Halildeu"
    snapshot["merge_actor"]["permission"] = "admin"
    snapshot["merge_actor"]["viewer_can_administer"] = True
    snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] = False
    live = _ready_live_state()
    live["viewer"]["login"] = "Halildeu"
    live["permission"]["permission"] = "admin"
    live["permission"]["role_name"] = "admin"
    payload = _result(snapshot=snapshot, live_state=live)
    Draft202012Validator(_schema()).validate(payload)
    assert payload["decision"]["result"] == "blocked"
    assert "unexpected_merge_actor" in payload["decision"]["blockers"]
    assert "merge_actor_admin_permission_observed" in payload["decision"]["blockers"]
    assert "dedicated_merge_actor_not_confirmed" in payload["decision"]["blockers"]


def test_ao_ma10c_blocks_stale_snapshot() -> None:
    snapshot = _ready_snapshot(datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC))
    snapshot["generated_at"] = "2026-05-28T20:00:00Z"
    payload = _result(snapshot=snapshot)
    assert "readiness_snapshot_stale" in payload["decision"]["blockers"]
    assert payload["decision"]["result"] == "blocked"


def test_ao_ma10c_blocks_eligibility_not_ready() -> None:
    eligibility = copy.deepcopy(_json(READY_ELIGIBILITY))
    eligibility["decision"]["result"] = "blocked"
    eligibility["decision"]["blockers"] = ["changed_files_not_low_risk"]
    payload = _result(eligibility=eligibility)
    assert "eligibility_not_ready" in payload["decision"]["blockers"]


def test_ao_ma10c_blocks_failed_required_check() -> None:
    live = _ready_live_state()
    live["required_checks"][1]["bucket"] = "fail"
    payload = _result(live_state=live)
    assert "required_checks_not_passed" in payload["decision"]["blockers"]
    assert payload["required_checks"]["failing"][0]["name"] == "ao-release-gate-review"


def test_ao_ma10c_blocks_pr_not_ready() -> None:
    live = _ready_live_state()
    live["pr_view"]["isDraft"] = True
    live["pr_view"]["mergeStateStatus"] = "DIRTY"
    payload = _result(live_state=live)
    assert "pr_is_draft" in payload["decision"]["blockers"]
    assert "pr_merge_state_not_clean" in payload["decision"]["blockers"]


def test_ao_ma10c_blocks_guard_and_authority_drift() -> None:
    snapshot = _ready_snapshot(datetime(2026, 5, 28, 21, 0, 0, tzinfo=UTC))
    snapshot["guard_flags"]["support_widening"] = True
    eligibility = copy.deepcopy(_json(READY_ELIGIBILITY))
    eligibility["ai_output_release_authority"] = True
    payload = _result(snapshot=snapshot, eligibility=eligibility)
    assert "guard_flags_not_false" in payload["decision"]["blockers"]
    assert "ai_output_release_authority_observed" in payload["decision"]["blockers"]


def test_ao_ma10c_collect_live_state_reads_only() -> None:
    mod = _load_script_module()
    seen: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": "github-actions[bot]"}), "")
        if "/collaborators/" in command[2]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"permission": "write"}), "")
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["pr_view"]), "")
        if command[:3] == ["gh", "pr", "checks"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["required_checks"]), "")
        raise AssertionError(command)

    state = mod.collect_live_github_state(repo="Halildeu/ao-kernel", pr_number=123, gh_bin="gh", runner=fake_runner)
    assert state["collection_errors"] == []
    flat = " ".join(" ".join(command) for command in seen)
    assert " pr merge " not in flat
    assert " --method PATCH " not in flat
    assert " --method PUT " not in flat
    assert " --method POST " not in flat
    assert " --method DELETE " not in flat


def test_ao_ma10c_collect_live_state_falls_back_to_repo_permissions_when_collaborator_permission_403() -> None:
    mod = _load_script_module()

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": "github-actions[bot]"}), "")
        if len(command) >= 3 and "/collaborators/" in command[2]:
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "gh: Resource not accessible by personal access token (HTTP 403)",
            )
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"permissions": {"admin": False, "push": True, "pull": True}}),
                "",
            )
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["pr_view"]), "")
        if command[:3] == ["gh", "pr", "checks"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["required_checks"]), "")
        raise AssertionError(command)

    state = mod.collect_live_github_state(repo="Halildeu/ao-kernel", pr_number=123, gh_bin="gh", runner=fake_runner)

    assert state["collection_errors"] == []
    assert state["permission"]["permission"] == "write"
    assert state["permission"]["role_name"] == "write"


def test_ao_ma10c_collect_live_state_does_not_fallback_for_unexpected_permission_read_errors() -> None:
    mod = _load_script_module()
    repo_fallback_called = False

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal repo_fallback_called
        if command[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": "github-actions[bot]"}), "")
        if len(command) >= 3 and "/collaborators/" in command[2]:
            return subprocess.CompletedProcess(command, 1, "", "gh: server error (HTTP 500)")
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel"]:
            repo_fallback_called = True
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"permissions": {"admin": False, "push": True, "pull": True}}),
                "",
            )
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["pr_view"]), "")
        if command[:3] == ["gh", "pr", "checks"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["required_checks"]), "")
        raise AssertionError(command)

    state = mod.collect_live_github_state(repo="Halildeu/ao-kernel", pr_number=123, gh_bin="gh", runner=fake_runner)
    payload = _result(live_state=state)

    assert repo_fallback_called is False
    assert state["permission"] == {}
    assert any("HTTP 500" in error for error in state["collection_errors"])
    assert "github_api_read_failed" in payload["decision"]["blockers"]
    assert "merge_actor_not_write" in payload["decision"]["blockers"]


def test_ao_ma10c_collect_live_state_retries_transient_unstable_merge_state() -> None:
    mod = _load_script_module()
    pr_views = [
        {
            **_ready_live_state()["pr_view"],
            "mergeStateStatus": "UNSTABLE",
        },
        _ready_live_state()["pr_view"],
    ]

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": "github-actions[bot]"}), "")
        if len(command) >= 3 and "/collaborators/" in command[2]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"permission": "write"}), "")
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(pr_views.pop(0)), "")
        if command[:3] == ["gh", "pr", "checks"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["required_checks"]), "")
        raise AssertionError(command)

    state = mod.collect_live_github_state(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        gh_bin="gh",
        runner=fake_runner,
        merge_state_max_attempts=2,
        merge_state_poll_seconds=0,
    )

    assert state["collection_errors"] == []
    assert state["pr_view"]["mergeStateStatus"] == "CLEAN"
    assert pr_views == []


def test_ao_ma10c_collect_live_state_blocks_when_transient_merge_state_never_settles() -> None:
    mod = _load_script_module()
    seen_pr_views = 0

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal seen_pr_views
        if command[:3] == ["gh", "api", "user"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"login": "github-actions[bot]"}), "")
        if len(command) >= 3 and "/collaborators/" in command[2]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"permission": "write"}), "")
        if command[:3] == ["gh", "pr", "view"]:
            seen_pr_views += 1
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({**_ready_live_state()["pr_view"], "mergeStateStatus": "UNSTABLE"}),
                "",
            )
        if command[:3] == ["gh", "pr", "checks"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(_ready_live_state()["required_checks"]), "")
        raise AssertionError(command)

    state = mod.collect_live_github_state(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        gh_bin="gh",
        runner=fake_runner,
        merge_state_max_attempts=2,
        merge_state_poll_seconds=0,
    )
    payload = _result(live_state=state)

    assert seen_pr_views == 2
    assert state["pr_view"]["mergeStateStatus"] == "UNSTABLE"
    assert "pr_merge_state_not_clean" in payload["decision"]["blockers"]


def test_ao_ma10c_source_does_not_construct_admin_or_auto_merge() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--admin" not in source
    assert "--auto" not in source
    assert "enablePullRequestAutoMerge" not in source
    assert "mergePullRequest" not in source
    assert '"pr",\n        "merge"' not in source
