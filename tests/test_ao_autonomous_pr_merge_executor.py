from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_autonomous_pr_merge_executor.py"


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_autonomous_pr_merge_executor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_live_state() -> dict[str, Any]:
    return {
        "viewer": {"login": "github-actions[bot]"},
        "permission": {"permission": "write", "role_name": "write"},
        "pr_view": {
            "state": "OPEN",
            "isDraft": False,
            "baseRefName": "main",
            "headRefName": "codex/example",
            "headRefOid": "a" * 40,
            "isCrossRepository": False,
            "mergeStateStatus": "CLEAN",
            "mergedAt": None,
            "url": "https://github.com/Halildeu/ao-kernel/pull/123",
        },
        "required_checks": [
            {"name": "lint", "bucket": "pass", "state": "SUCCESS"},
            {"name": "ao-release-gate-technical", "bucket": "pass", "state": "SUCCESS"},
            {"name": "ao-release-gate-review", "bucket": "pass", "state": "SUCCESS"},
        ],
        "check_runs": {
            "check_runs": [
                {
                    "name": "ao-release-gate-technical",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"id": 15368, "slug": "github-actions"},
                    "details_url": "https://github.example/technical",
                },
                {
                    "name": "ao-release-gate-review",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"id": 15368, "slug": "github-actions"},
                    "details_url": "https://github.example/review",
                },
            ]
        },
        "collection_errors": [],
        "collection_warnings": [],
    }


def _result(
    live_state: dict[str, Any] | None = None,
    *,
    execute: bool = True,
    confirmation: str | None = "AO-AUTONOMOUS-MERGE-EXECUTE",
    event_head_sha: str | None = "a" * 40,
    merge_exit_code: int | None = None,
) -> dict[str, Any]:
    mod = _load_script_module()
    return mod.build_result(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        live_state=live_state or _ready_live_state(),
        expected_actor="github-actions[bot]",
        base_ref="main",
        event_head_sha=event_head_sha,
        execute=execute,
        confirmation=confirmation,
        merge_exit_code=merge_exit_code,
    )


def test_ready_executor_is_ready_to_merge_without_claiming_authority() -> None:
    payload = _result()

    assert payload["decision"]["result"] == "ready_to_merge"
    assert payload["release_authority"] == "ao-release-gate+github-ruleset"
    assert payload["ai_output_release_authority"] is False
    assert payload["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    assert payload["source_pinned_release_gate_checks"]["all_passed"] is True
    assert "--admin" not in payload["merge_command_argv"]
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


def test_successful_merge_records_mutation_and_branch_delete_command() -> None:
    payload = _result(merge_exit_code=0)

    assert payload["decision"]["result"] == "merged"
    assert payload["mutations_performed"] is True
    assert payload["branch_delete_command_argv"] == [
        "gh",
        "api",
        "repos/Halildeu/ao-kernel/git/refs/heads/codex/example",
        "--method",
        "DELETE",
    ]


def test_missing_source_pinned_release_gate_check_blocks() -> None:
    live = _ready_live_state()
    live["check_runs"]["check_runs"] = [
        item for item in live["check_runs"]["check_runs"] if item["name"] != "ao-release-gate-review"
    ]

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "source_pinned_ao_release_gate_checks_not_success" in payload["decision"]["blockers"]


def test_wrong_release_gate_app_blocks_even_when_check_name_matches() -> None:
    live = _ready_live_state()
    live["check_runs"]["check_runs"][1]["app"] = {"id": 999999, "slug": "some-other-app"}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "source_pinned_ao_release_gate_checks_not_success" in payload["decision"]["blockers"]


def test_required_check_failure_blocks() -> None:
    live = _ready_live_state()
    live["required_checks"][0] = {"name": "lint", "bucket": "fail", "state": "FAILURE"}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "required_checks_not_passed" in payload["decision"]["blockers"]


def test_duplicate_required_checks_allow_pass_over_stale_pending_and_skipped() -> None:
    live = _ready_live_state()
    live["required_checks"] = [
        {"name": "lint", "bucket": "skipping", "state": "SKIPPED", "link": "stale"},
        {"name": "lint", "bucket": "pass", "state": "SUCCESS", "link": "current"},
        {"name": "test (3.11)", "bucket": "pending", "state": "IN_PROGRESS", "link": "old-run"},
        {"name": "test (3.11)", "bucket": "pass", "state": "SUCCESS", "link": "new-run"},
        {"name": "ao-release-gate", "bucket": "skipping", "state": "SKIPPED", "link": "event-gate-only"},
    ]

    payload = _result(live)

    assert payload["decision"]["result"] == "ready_to_merge"
    assert payload["required_checks"]["all_passed"] is True
    assert payload["required_checks"]["failing"] == []


def test_pending_required_check_without_pass_still_blocks() -> None:
    live = _ready_live_state()
    live["required_checks"].append(
        {"name": "test (3.13)", "bucket": "pending", "state": "IN_PROGRESS", "link": "current"}
    )

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "required_checks_not_passed" in payload["decision"]["blockers"]
    assert payload["required_checks"]["failing"][0]["name"] == "test (3.13)"


def test_github_actions_integration_token_permission_gap_does_not_block() -> None:
    live = _ready_live_state()
    live["permission"] = {}
    live["collection_warnings"] = ["github_user_endpoint_unavailable_for_integration_token"]
    live["repo_owned_actions_token"] = {"verified": True, "failures": []}

    payload = _result(live)

    assert payload["decision"]["result"] == "ready_to_merge"
    assert "merge_actor_not_write" not in payload["decision"]["blockers"]
    assert "github_actions_integration_token_permission_unobservable" in payload["decision"]["warnings"]
    assert payload["repo_owned_actions_token"]["verified"] is True


def test_integration_token_permission_gap_without_repo_owned_proof_blocks() -> None:
    live = _ready_live_state()
    live["permission"] = {}
    live["collection_warnings"] = ["github_user_endpoint_unavailable_for_integration_token"]
    live["repo_owned_actions_token"] = {"verified": False, "failures": ["workflow_ref"]}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "merge_actor_permission_unobservable" in payload["decision"]["blockers"]
    assert "merge_actor_identity_unverified" in payload["decision"]["blockers"]
    assert "merge_actor_not_write" not in payload["decision"]["blockers"]


def test_integration_token_with_write_permission_still_requires_repo_owned_proof() -> None:
    live = _ready_live_state()
    live["permission"] = {"permission": "write", "role_name": "write"}
    live["collection_warnings"] = ["github_user_endpoint_unavailable_for_integration_token"]
    live["repo_owned_actions_token"] = {"verified": False, "failures": ["workflow_ref"]}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "merge_actor_identity_unverified" in payload["decision"]["blockers"]
    assert "merge_actor_not_write" not in payload["decision"]["blockers"]


def test_required_check_failure_with_missing_state_blocks_without_type_error() -> None:
    live = _ready_live_state()
    live["required_checks"][0] = {"name": "lint", "bucket": "fail", "link": "failure-without-state"}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "required_checks_not_passed" in payload["decision"]["blockers"]


def test_stale_workflow_run_head_sha_blocks() -> None:
    payload = _result(event_head_sha="b" * 40)

    assert payload["decision"]["result"] == "blocked"
    assert "event_head_sha_stale" in payload["decision"]["blockers"]


def test_admin_or_wrong_actor_blocks() -> None:
    live = _ready_live_state()
    live["viewer"] = {"login": "Halildeu"}
    live["permission"] = {"permission": "admin", "role_name": "admin"}

    payload = _result(live)

    assert payload["decision"]["result"] == "blocked"
    assert "unexpected_merge_actor" in payload["decision"]["blockers"]
    assert "merge_actor_admin_permission_observed" in payload["decision"]["blockers"]


def test_already_merged_pr_is_successful_noop() -> None:
    live = _ready_live_state()
    live["pr_view"]["state"] = "MERGED"
    live["pr_view"]["mergedAt"] = "2026-05-29T14:00:00Z"
    live["collection_errors"] = ["viewer: transient API failure"]

    payload = _result(live)

    assert payload["decision"]["result"] == "noop_already_merged"
    assert payload["decision"]["blockers"] == []
    assert "pr_already_merged_noop" in payload["decision"]["warnings"]
    assert "noop_collection_error:viewer: transient API failure" in payload["decision"]["warnings"]
    assert payload["mutations_performed"] is False


def test_execute_merge_uses_rest_merge_and_safe_branch_delete() -> None:
    mod = _load_script_module()
    seen: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel/pulls/123/merge"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"merged": True}), "")
        if command[:3] == ["gh", "api", "repos/Halildeu/ao-kernel/git/refs/heads/codex/example"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(command)

    merge_exit, merge_error, delete_exit, delete_error, merge_argv, delete_argv = mod.execute_merge(
        repo="Halildeu/ao-kernel",
        pr_number=123,
        pr_view=_ready_live_state()["pr_view"],
        base_ref="main",
        gh_bin="gh",
        runner=fake_run,
    )

    assert merge_exit == 0
    assert merge_error
    assert delete_exit == 0
    assert delete_error == ""
    assert merge_argv in seen
    assert delete_argv in seen
    assert "--admin" not in merge_argv
