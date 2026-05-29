from __future__ import annotations

import base64
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10_github_readiness_snapshot.py"
SNAPSHOT = ROOT / ".claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json"
FIXTURE = ROOT / "tests/fixtures/ao_ma_10/github_readiness_snapshot.blocked.valid.json"
SCHEMA_NAME = "ao-ma-10-github-readiness-snapshot.schema.v1.json"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _snapshot() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SNAPSHOT.read_text(encoding="utf-8")))


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10_github_readiness_snapshot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_ready_inputs() -> dict[str, Any]:
    return {
        "repository": "Halildeu/ao-kernel",
        "branch": "main",
        "generated_at": "2026-05-27T19:30:00Z",
        "repo_info": {
            "autoMergeAllowed": False,
            "mergeCommitAllowed": True,
            "squashMergeAllowed": True,
            "rebaseMergeAllowed": True,
            "deleteBranchOnMerge": True,
            "viewerCanAdminister": False,
            "viewerPermission": "WRITE",
        },
        "viewer_login": "github-actions[bot]",
        "viewer_permission": "write",
        "branch_protection": {
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "required_approving_review_count": 0,
            },
            "enforce_admins": {"enabled": True},
            "required_status_checks": {
                "strict": True,
                "contexts": ["lint", "ao-release-gate-technical", "ao-release-gate-review"],
                "checks": [
                    {"context": "lint", "app_id": 15368},
                    {"context": "ao-release-gate-technical", "app_id": 15368},
                    {"context": "ao-release-gate-review", "app_id": 15368},
                ],
            },
        },
        "rulesets": [
            {
                "id": 16803733,
                "name": "Protect main",
                "target": "branch",
                "source_type": "Repository",
                "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "bypass_actors": [],
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
            }
        ],
        "branch_rules": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {"context": "ao-release-gate-technical", "integration_id": 15368},
                        {"context": "ao-release-gate-review", "integration_id": 15368},
                    ]
                },
            }
        ],
        "codeowners_text": """
/.github/ @Halildeu @gladyatore-lab
/AGENTS.md @Halildeu @gladyatore-lab
/CLAUDE.md @Halildeu @gladyatore-lab
/.claude/gpp_status.v1.json @Halildeu @gladyatore-lab
/ao_kernel/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/ao_release_gate*.py @Halildeu @gladyatore-lab
/scripts/local_gpp_gate*.py @Halildeu @gladyatore-lab
/deploy/ @Halildeu @gladyatore-lab
""",
    }


def test_ao_ma10a0_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:ao-ma-10-github-readiness-snapshot:v1"


def test_ao_ma10a0_fixture_and_live_snapshot_validate_against_schema() -> None:
    validator = Draft202012Validator(_schema())
    fixture = _fixture()
    snapshot = _snapshot()
    validator.validate(fixture)
    validator.validate(snapshot)
    assert fixture["schema_version"] == "ao-ma-10-github-readiness-snapshot.v1"
    assert snapshot["schema_version"] == "ao-ma-10-github-readiness-snapshot.v1"


def test_ao_ma10a0_live_snapshot_records_current_blockers_without_mutation() -> None:
    snapshot = _snapshot()
    assert snapshot["read_only"] is True
    assert snapshot["mutations_performed"] is False
    assert snapshot["release_authority"] == "ao-release-gate+github-ruleset"
    assert snapshot["ai_output_release_authority"] is False
    assert snapshot["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    assert snapshot["collection_errors"] == []
    blockers = set(snapshot["readiness"]["blockers"])
    assert "merge_actor_admin_permission_observed" in blockers
    assert "unexpected_merge_actor" in blockers
    assert "ao_release_gate_required_check_missing" not in blockers
    assert "legacy_required_review_blocks_low_risk_autonomy" not in blockers
    # Historical changelog/runbook wording does not count as a current SSOT
    # claim. AO-MA-10A0 should only report drift when the current status
    # section claims a live required-check shape that GitHub API contradicts.
    assert "ssot_live_required_check_drift_detected" not in blockers
    assert snapshot["ssot_cross_check"] == {
        "prior_required_check_claim_observed": False,
        "live_snapshot_conflicts_with_prior_claim": False,
        "prior_claim_source": ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md",
    }
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_ready_case_requires_source_pinned_release_gate_and_non_admin_actor() -> None:
    mod = _load_script_module()
    snapshot = mod.build_snapshot(**_valid_ready_inputs())
    Draft202012Validator(_schema()).validate(snapshot)
    assert snapshot["branch_protection"]["ao_release_gate_required_check_present"] is True
    assert snapshot["branch_protection"]["ao_release_gate_source_pinned_to_actions"] is True
    assert snapshot["rulesets"]["ao_release_gate_required_check_present"] is True
    assert snapshot["rulesets"]["ao_release_gate_source_pinned_to_actions"] is True
    assert snapshot["merge_actor"]["viewer_can_administer"] is False
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is True
    assert snapshot["readiness"]["decision"] == "ready_for_dry_run"
    assert snapshot["readiness"]["blockers"] == []
    assert "repository_auto_merge_disabled_merge_agent_direct_mode_required" in snapshot["readiness"]["warnings"]


def test_ao_ma10a0_blocks_wrong_non_admin_merge_actor() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["viewer_login"] = "some-other-writer"
    inputs["viewer_permission"] = "write"
    inputs["repo_info"]["viewerCanAdminister"] = False
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is False
    assert "unexpected_merge_actor" in snapshot["readiness"]["blockers"]
    assert "merge_actor_admin_permission_observed" not in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_wrong_source_pin_even_when_check_name_matches() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["branch_rules"][0]["parameters"]["required_status_checks"][1]["integration_id"] = 99999
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["rulesets"]["ao_release_gate_required_check_present"] is True
    assert snapshot["rulesets"]["ao_release_gate_source_pinned_to_actions"] is False
    assert "ao_release_gate_required_check_not_source_pinned" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_when_only_legacy_branch_protection_has_gate() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["branch_rules"] = []
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["branch_protection"]["ao_release_gate_required_check_present"] is True
    assert snapshot["rulesets"]["ao_release_gate_required_check_present"] is False
    assert "ao_release_gate_required_check_missing" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_ssot_live_required_check_drift() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["branch_rules"] = []
    inputs["ssot_required_check_claim_observed"] = True
    inputs["ssot_claim_source"] = ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md"
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["ssot_cross_check"] == {
        "prior_required_check_claim_observed": True,
        "live_snapshot_conflicts_with_prior_claim": True,
        "prior_claim_source": ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md",
    }
    assert "ssot_live_required_check_drift_detected" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_ssot_live_required_check_source_pin_drift() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["branch_rules"][0]["parameters"]["required_status_checks"][1]["integration_id"] = 99999
    inputs["ssot_required_check_claim_observed"] = True
    inputs["ssot_claim_source"] = ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md"
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["rulesets"]["ao_release_gate_required_check_present"] is True
    assert snapshot["rulesets"]["ao_release_gate_source_pinned_to_actions"] is False
    assert snapshot["ssot_cross_check"] == {
        "prior_required_check_claim_observed": True,
        "live_snapshot_conflicts_with_prior_claim": True,
        "prior_claim_source": ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md",
    }
    assert "ao_release_gate_required_check_not_source_pinned" in snapshot["readiness"]["blockers"]
    assert "ssot_live_required_check_drift_detected" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_ruleset_bypass_actors() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["rulesets"][0]["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["rulesets"]["bypass_actors_empty"] is False
    assert "ruleset_bypass_actors_present" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_all_branch_ruleset_bypass_actors() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["rulesets"][0]["conditions"] = {"ref_name": {"include": ["~ALL"], "exclude": []}}
    inputs["rulesets"][0]["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["rulesets"]["bypass_actors_empty"] is False
    assert "ruleset_bypass_actors_present" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_ignores_all_branch_ruleset_excluding_main() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["rulesets"][0]["conditions"] = {"ref_name": {"include": ["~ALL"], "exclude": ["refs/heads/main"]}}
    inputs["rulesets"][0]["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["rulesets"]["bypass_actors_empty"] is True
    assert "ruleset_bypass_actors_present" not in snapshot["readiness"]["blockers"]


def test_ao_ma10a0_blocks_global_required_review_for_low_risk_autonomy() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["branch_protection"]["required_pull_request_reviews"]["required_approving_review_count"] = 1
    snapshot = mod.build_snapshot(**inputs)
    assert "legacy_required_review_blocks_low_risk_autonomy" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_admin_merge_actor() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["repo_info"]["viewerCanAdminister"] = True
    inputs["viewer_permission"] = "admin"
    snapshot = mod.build_snapshot(**inputs)
    assert "merge_actor_admin_permission_observed" in snapshot["readiness"]["blockers"]
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is False
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_broad_codeowners_default() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["codeowners_text"] = "* @Halildeu\n" + inputs["codeowners_text"]
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["codeowners"]["broad_default_owner_present"] is True
    assert "codeowners_broad_default_owner_present" in snapshot["readiness"]["blockers"]


def test_ao_ma10a0_blocks_missing_governance_codeowners() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["codeowners_text"] = "tests/ @Halildeu\n"
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["codeowners"]["governance_paths_owned"] is False
    assert "codeowners_governance_paths_not_fully_owned" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_collection_errors_fail_closed() -> None:
    mod = _load_script_module()
    inputs = _valid_ready_inputs()
    inputs["collection_errors"] = ["rulesets: command failed with exit 1"]
    snapshot = mod.build_snapshot(**inputs)
    assert snapshot["collection_errors"] == ["rulesets: command failed with exit 1"]
    assert "github_api_read_failed" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_collect_live_snapshot_records_repo_and_viewer_read_errors(monkeypatch: Any) -> None:
    mod = _load_script_module()
    codeowners_text = _valid_ready_inputs()["codeowners_text"]
    encoded_codeowners = base64.b64encode(codeowners_text.encode("utf-8")).decode("utf-8")

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {}, "repository: command failed with exit 1"
        if label == "viewer_login":
            return {}, "viewer_login: command failed with exit 1"
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot("Halildeu/ao-kernel", "main", "gh")

    assert snapshot["collection_errors"] == [
        "repository: command failed with exit 1",
        "viewer_login: command failed with exit 1",
    ]
    assert "github_api_read_failed" in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_accepts_github_actions_integration_user_endpoint_shape(monkeypatch: Any) -> None:
    mod = _load_script_module()
    codeowners_text = _valid_ready_inputs()["codeowners_text"]
    encoded_codeowners = base64.b64encode(codeowners_text.encode("utf-8")).decode("utf-8")

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {"data": {"repository": _valid_ready_inputs()["repo_info"]}}, None
        if label == "viewer_login":
            return {}, "viewer_login: gh: Resource not accessible by integration (HTTP 403)"
        if label == "viewer_permission":
            return {}, "viewer_permission: gh: Not Found (HTTP 404)"
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot(
        "Halildeu/ao-kernel",
        "main",
        "gh-governance",
        dedicated_merge_actor="github-actions[bot]",
        actor_gh_bin="gh-dedicated",
    )

    Draft202012Validator(_schema()).validate(snapshot)
    assert snapshot["collection_errors"] == []
    assert snapshot["merge_actor"] == {
        "login": "github-actions[bot]",
        "permission": "write",
        "viewer_can_administer": False,
        "administration_write_absent_for_dedicated_actor": True,
    }
    assert "github_user_endpoint_unavailable_for_integration_token" in snapshot["readiness"]["warnings"]
    assert "github_api_read_failed" not in snapshot["readiness"]["blockers"]
    assert "unexpected_merge_actor" not in snapshot["readiness"]["blockers"]
    assert snapshot["readiness"]["decision"] == "ready_for_dry_run"


def test_ao_ma10a0_infers_actions_integration_write_from_pull_request_read(monkeypatch: Any) -> None:
    mod = _load_script_module()
    encoded_codeowners = base64.b64encode(_valid_ready_inputs()["codeowners_text"].encode("utf-8")).decode("ascii")
    repo_info = copy.deepcopy(_valid_ready_inputs()["repo_info"])
    repo_info.pop("viewerPermission")

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {"data": {"repository": repo_info}}, None
        if label == "viewer_login":
            return {}, "viewer_login: gh: Resource not accessible by integration (HTTP 403)"
        if label == "viewer_permission":
            return {}, "viewer_permission: gh: Not Found (HTTP 404)"
        if label == "pulls":
            return [], None
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot(
        "Halildeu/ao-kernel",
        "main",
        "gh-governance",
        dedicated_merge_actor="github-actions[bot]",
        actor_gh_bin="gh-dedicated",
    )

    Draft202012Validator(_schema()).validate(snapshot)
    assert snapshot["collection_errors"] == []
    assert snapshot["merge_actor"]["login"] == "github-actions[bot]"
    assert snapshot["merge_actor"]["permission"] == "write"
    assert snapshot["merge_actor"]["viewer_can_administer"] is False
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is True
    assert snapshot["readiness"]["decision"] == "ready_for_dry_run"


def test_ao_ma10a0_infers_actions_integration_write_when_permission_endpoint_returns_read(
    monkeypatch: Any,
) -> None:
    mod = _load_script_module()
    encoded_codeowners = base64.b64encode(_valid_ready_inputs()["codeowners_text"].encode("utf-8")).decode("ascii")
    repo_info = copy.deepcopy(_valid_ready_inputs()["repo_info"])
    repo_info["viewerPermission"] = "READ"

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {"data": {"repository": repo_info}}, None
        if label == "viewer_login":
            return {}, "viewer_login: gh: Resource not accessible by integration (HTTP 403)"
        if label == "viewer_permission":
            return {"permission": "read"}, None
        if label == "pulls":
            return [], None
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot(
        "Halildeu/ao-kernel",
        "main",
        "gh-governance",
        dedicated_merge_actor="github-actions[bot]",
        actor_gh_bin="gh-dedicated",
    )

    Draft202012Validator(_schema()).validate(snapshot)
    assert snapshot["collection_errors"] == []
    assert snapshot["merge_actor"]["login"] == "github-actions[bot]"
    assert snapshot["merge_actor"]["permission"] == "write"
    assert snapshot["merge_actor"]["viewer_can_administer"] is False
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is True
    assert snapshot["readiness"]["decision"] == "ready_for_dry_run"


def test_ao_ma10a0_blocks_actions_integration_when_pull_request_read_fails(monkeypatch: Any) -> None:
    mod = _load_script_module()
    encoded_codeowners = base64.b64encode(_valid_ready_inputs()["codeowners_text"].encode("utf-8")).decode("ascii")
    repo_info = copy.deepcopy(_valid_ready_inputs()["repo_info"])
    repo_info.pop("viewerPermission")

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {"data": {"repository": repo_info}}, None
        if label == "viewer_login":
            return {}, "viewer_login: gh: Resource not accessible by integration (HTTP 403)"
        if label == "viewer_permission":
            return {}, "viewer_permission: gh: Not Found (HTTP 404)"
        if label == "pulls":
            return {}, "pulls: gh: Resource not accessible by integration (HTTP 403)"
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot(
        "Halildeu/ao-kernel",
        "main",
        "gh-governance",
        dedicated_merge_actor="github-actions[bot]",
        actor_gh_bin="gh-dedicated",
    )

    Draft202012Validator(_schema()).validate(snapshot)
    assert "github_api_read_failed" in snapshot["readiness"]["blockers"]
    assert snapshot["merge_actor"]["permission"] is None
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is False
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_blocks_actions_integration_read_permission_when_pull_probe_fails(
    monkeypatch: Any,
) -> None:
    mod = _load_script_module()
    encoded_codeowners = base64.b64encode(_valid_ready_inputs()["codeowners_text"].encode("utf-8")).decode("ascii")
    repo_info = copy.deepcopy(_valid_ready_inputs()["repo_info"])
    repo_info["viewerPermission"] = "READ"

    def fake_run_json_with_error(command: list[str], label: str) -> tuple[dict[str, Any] | list[Any], str | None]:
        del command
        if label == "repository":
            return {"data": {"repository": repo_info}}, None
        if label == "viewer_login":
            return {}, "viewer_login: gh: Resource not accessible by integration (HTTP 403)"
        if label == "viewer_permission":
            return {"permission": "read"}, None
        if label == "pulls":
            return {}, "pulls: gh: Resource not accessible by integration (HTTP 403)"
        if label == "branch_protection":
            return _valid_ready_inputs()["branch_protection"], None
        if label == "rulesets":
            return _valid_ready_inputs()["rulesets"], None
        if label == "ruleset:16803733":
            return _valid_ready_inputs()["rulesets"][0], None
        if label == "branch_rules":
            return _valid_ready_inputs()["branch_rules"], None
        if label == "codeowners":
            return {"content": encoded_codeowners}, None
        raise AssertionError(f"unexpected label: {label}")

    monkeypatch.setattr(mod, "_run_json_with_error", fake_run_json_with_error)
    snapshot = mod.collect_live_snapshot(
        "Halildeu/ao-kernel",
        "main",
        "gh-governance",
        dedicated_merge_actor="github-actions[bot]",
        actor_gh_bin="gh-dedicated",
    )

    Draft202012Validator(_schema()).validate(snapshot)
    assert "github_api_read_failed" in snapshot["readiness"]["blockers"]
    assert snapshot["merge_actor"]["permission"] == "read"
    assert snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] is False
    assert snapshot["readiness"]["decision"] == "blocked"


def test_ao_ma10a0_script_is_read_only_and_has_no_write_api_methods() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden_tokens = [
        "--method PATCH",
        "--method PUT",
        "--method POST",
        "--method DELETE",
        "gh pr merge",
        "enablePullRequestAutoMerge",
        "updateBranchProtectionRule",
        "updateRepositoryRuleset",
        "createRepositoryRuleset",
        "deleteRepositoryRuleset",
    ]
    for token in forbidden_tokens:
        assert token not in source


def test_ao_ma10a0_fixture_rejects_guard_or_authority_widening() -> None:
    validator = Draft202012Validator(_schema())
    payload = _fixture()

    widened = copy.deepcopy(payload)
    widened["guard_flags"]["support_widening"] = True
    assert list(validator.iter_errors(widened))

    ai_authority = copy.deepcopy(payload)
    ai_authority["ai_output_release_authority"] = True
    assert list(validator.iter_errors(ai_authority))

    mutated = copy.deepcopy(payload)
    mutated["mutations_performed"] = True
    assert list(validator.iter_errors(mutated))
