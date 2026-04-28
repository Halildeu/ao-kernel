from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "gpp_next.py"
    spec = importlib.util.spec_from_file_location("gpp_next", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "gpp_status.v1.json"


def test_gpp_status_contract_keeps_support_widening_closed() -> None:
    payload = json.loads(_status_path().read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1"
    assert payload["program_id"] == "general-purpose-production-promotion"
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/547"
    assert (
        payload["current_wp"]["exit_decision"]
        == "ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped"
    )
    assert any(item["id"] == "GPP-1b" for item in payload["completed_wps"])
    assert any(
        item["id"] == "GPP-2a" and item["decision"] == "still_blocked_protected_prerequisites_missing"
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2d"
        and item["decision"] == "repeatable_attestation_available_current_gate_still_blocked"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/487"
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2e"
        and item["decision"] == "decision_recorded_not_approved_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/489"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2f"
        and item["decision"] == "independent_release_gate_required_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/491"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2g"
        and item["decision"] == "github_native_release_authority_selected_claude_mcp_advisory_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/493"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2h"
        and item["decision"] == "github_app_deployment_protection_rule_selected_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/495"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2i"
        and item["decision"] == "deployment_protection_attestation_supported_gate_still_blocked"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/497"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2k"
        and item["decision"] == "protected_live_gate_provisioning_runbook_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/517"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2l"
        and item["decision"] == "protected_live_gate_prerequisites_ready_runtime_binding_not_started"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/519"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2m"
        and item["decision"] == "protected_workflow_bound_live_execution_still_disabled"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/521"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2n"
        and item["decision"] == "protected_workflow_evidence_fail_closed_policy_response_missing"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/523"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2o"
        and item["decision"] == "policy_decision_core_ready_service_not_deployed"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/525"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2p"
        and item["decision"] == "policy_webhook_service_scaffold_ready_service_not_deployed"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/527"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2q"
        and item["decision"] == "policy_webhook_runtime_ready_service_not_deployed"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/529"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2r"
        and item["decision"] == "policy_webhook_container_ready_service_not_hosted"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/531"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2s"
        and item["decision"] == "policy_container_publish_path_ready_service_not_hosted"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/533"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2u"
        and item["decision"] == "autonomous_github_app_release_gate_selected_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/537"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2v"
        and item["decision"] == "ao_release_gate_dry_run_scaffold_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/539"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2w"
        and item["decision"] == "ao_release_gate_check_run_service_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/541"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2x"
        and item["decision"] == "ao_release_gate_container_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/543"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2y"
        and item["decision"] == "ao_release_gate_publish_path_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/545"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2aa"
        and item["decision"] == "ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/547"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    assert payload["pending_external_actions"] == [
        "bootstrap the ao-release-gate Cloud Run deploy trust path and run the trusted deploy workflow from main without treating health evidence as check-run evidence",
        "configure the ao-release-gate GitHub App webhook URL to the hosted /github/ao-release-gate endpoint with runtime webhook secret and GitHub App authentication outside the repo",
        "collect dry-run ao-release-gate check-run evidence on real PRs before granting merge authority or changing branch protection",
        "validate whether GitHub App pull request approvals count for the current branch protection; if not, cut over to a required ao-release-gate status check",
        "deploy or configure the ao-kernel-live-adapter-gate GitHub App deployment-protection policy service/webhook using the repo-owned GHCR image or container package with webhook secret verification and GitHub App auth so it posts deployment callback reviews",
        "rerun the protected workflow evidence slice from main after the policy service can approve_contract_gate, reject, or fail explicitly",
    ]
    assert payload["blocked_wps"] == [
        {
            "id": "GPP-2",
            "reason": (
                "repo-owned policy webhook container image publish path, ao-release-gate dry-run decision "
                "scaffold, check-run service surface, release-gate container package, release-gate "
                "image publish path, and release-gate autonomous deploy path are ready, but neither the "
                "release-gate service nor the deployment-protection service is publicly hosted/configured "
                "with webhook evidence or cut over with protected evidence"
            ),
        }
    ]
    assert any("python3 scripts/gpp_next.py" == item["command"] for item in payload["required_startup_checks"])
    assert any(
        action
        == "bootstrap and run the ao-release-gate Cloud Run deploy workflow from main before collecting real PR evidence"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "deploy or host the ao-release-gate check-run service in dry-run mode and collect real PR evidence before any branch protection cutover"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "collect ao-release-gate dry-run check-run evidence on real PRs before any branch protection cutover"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "validate GitHub App review-counting only as a spike; use required status check as the durable enforcement path unless proven otherwise"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "keep the single-admin equivalent release gate not approved unless issue #489 is explicitly superseded"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "use --equivalent-release-gate-approved while GPP-2e remains not_approved"
        for action in payload["forbidden_actions"]
    )
    assert any(action == "treat a product end-user account as release authority" for action in payload["forbidden_actions"])
    assert any(action == "treat a PAT-backed bot user as release authority" for action in payload["forbidden_actions"])
    assert any(action == "use admin bypass to merge GPP program PRs" for action in payload["forbidden_actions"])
    assert any(action == "treat Codex or Claude output as release authority" for action in payload["forbidden_actions"])
    assert any(
        action
        == "deploy or configure the deployment-protection policy service using the repo-owned GHCR image or container package before any further live-adapter runtime work"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "do not repeatedly dispatch .github/workflows/live-adapter-gate.yml until the ao-kernel-live-adapter-gate policy service is active"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/live_adapter_gate_policy_service_smoke.py only for local webhook/callback artifact validation, not live callback posting"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/live_adapter_gate_policy_decision.py only for policy callback decision evaluation, not live adapter execution"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/live_adapter_gate_policy_container_smoke.py only for no-secret local container health validation, not live callback posting"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/ao_release_gate_container_smoke.py only for no-secret local container health validation, not check-run posting"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "publish or pull ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service only as a deploy artifact, not hosted service evidence"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "publish or pull ghcr.io/halildeu/ao-kernel-ao-release-gate-service only as a deploy artifact, not hosted service evidence"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "configure ao_kernel.ao_release_gate_runtime:application only with runtime secret manager values, never committed or echoed secret material"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "configure ao_kernel.live_adapter_gate_policy_runtime:application only with runtime secret manager values, never committed or echoed secret material"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "do not reference AO_CLAUDE_CODE_CLI_AUTH through secrets context until a later live execution slice explicitly permits it"
        for action in payload["next_allowed_actions"]
    )
    assert any(action == "treat Claude MCP consultation as release authority" for action in payload["forbidden_actions"])
    assert any(
        action == "use ao_memory_write or ao_llm_call during Claude MCP consultation"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "use Claude MCP consultation only as advisory review, not release authority"
        for action in payload["next_allowed_actions"]
    )


def test_gpp2e_equivalent_gate_decision_defaults_to_not_approved() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2e-SINGLE-ADMIN-EQUIVALENT-GATE-DECISION.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `not_approved`" in decision
    assert "does not approve that equivalent gate" in decision
    assert "--equivalent-release-gate-approved" in decision
    assert "must not be used for production prerequisite attestation" in decision


def test_gpp2f_independent_release_gate_replaces_end_user_reviewer_model() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2f-INDEPENDENT-RELEASE-GATE-ARCHITECTURE.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `independent_release_gate_required`" in decision
    assert "not a product end-user account" in decision
    assert "GitHub-native release authority" in decision
    assert "GitHub App deployment protection rule" in decision
    assert "OIDC-backed external secret broker" in decision
    assert "Product end-user accounts must not be treated as release authority" in decision


def test_gpp2g_claude_mcp_consultation_is_advisory_only() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2g-GITHUB-NATIVE-RELEASE-AUTHORITY-AND-CLAUDE-MCP-CONSULTATION.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `github_native_release_authority_selected_claude_mcp_advisory`" in decision
    assert "GitHub-native release authority" in decision
    assert "It is not an application end-user account." in decision
    assert "The consultation path is advisory only." in decision
    assert "**Provisioning path superseded by:** `GPP-2h`" in decision
    assert "mcp__ao-kernel__ao_workspace_status" in decision
    assert "mcp__ao-kernel__ao_quality_gate" in decision
    assert "mcp__ao-kernel__ao_memory_write" in decision
    assert "mcp__ao-kernel__ao_llm_call" in decision
    assert "does not unblock `GPP-2`" in decision


def test_gpp2h_selects_deployment_protection_bot_not_bot_user() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2h-DEPLOYMENT-PROTECTION-BOT-GATE-DECISION.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `github_app_deployment_protection_rule_selected`" in decision
    assert "supersedes the first provisioning path selected in `GPP-2g`" in decision
    assert "GitHub App deployment protection rule" in decision
    assert "The model is a policy bot, not a user-like reviewer account." in decision
    assert "PAT-backed bot account listed as required reviewer" in decision
    assert "GPP-2i - deployment protection attestation support" in decision
    assert "does not unblock `GPP-2`" in decision
    assert "does not widen support" in decision


def test_gpp2i_attestation_support_keeps_gate_blocked() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2i-DEPLOYMENT-PROTECTION-ATTESTATION-SUPPORT.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `deployment_protection_attestation_supported_gate_still_blocked`" in decision
    assert "`release_gate_model = github_app_deployment_protection_rule`" in decision
    assert "`required_deployment_protection_app_slug = ao-kernel-live-adapter-gate`" in decision
    assert "deployment_protection_gate: blocked (live_gate_deployment_protection_missing)" in decision
    assert "`--equivalent-release-gate-approved` does not satisfy" in decision
    assert "does not unblock `GPP-2`" in decision
    assert "does not widen support" in decision


def test_gpp2u_selects_autonomous_github_app_release_gate_not_admin_bypass() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2u-AUTONOMOUS-GITHUB-APP-RELEASE-GATE.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `autonomous_github_app_release_gate_selected_no_support_widening`" in decision
    assert "GitHub App release gate" in decision
    assert "`ao-release-gate`" in decision
    assert "required status check" in decision
    assert "PAT-backed bot" in decision
    assert "Admin bypass is rejected." in decision
    assert "Claude/Codex release authority is rejected." in decision
    assert "dry-run" in decision
    assert "does not unblock GPP-2" in decision
    assert "does not widen support" in decision


def test_gpp2v_adds_dry_run_release_gate_scaffold_without_merge_authority() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `ao_release_gate_dry_run_scaffold_ready_no_support_widening`" in decision
    assert "`ao-release-gate`" in decision
    assert "`ao_kernel/ao_release_gate.py`" in decision
    assert "`scripts/ao_release_gate_decision.py`" in decision
    assert "`merge_authority_enabled=false`" in decision
    assert "No check-run POST to GitHub." in decision
    assert "No branch protection/ruleset change." in decision
    assert "No admin bypass." in decision
    assert "No PAT-backed bot." in decision
    assert "No Claude/Codex release authority." in decision


def test_gpp2w_wires_check_run_service_without_merge_authority() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2w-AO-RELEASE-GATE-CHECK-RUN-SERVICE.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `ao_release_gate_check_run_service_ready_no_support_widening`" in decision
    assert "`ao-release-gate`" in decision
    assert "`ao_kernel/ao_release_gate_service.py`" in decision
    assert "`ao_kernel/ao_release_gate_runtime.py`" in decision
    assert "check-run" in decision
    assert "`dry_run=true`" in decision
    assert "`merge_authority_enabled=false`" in decision
    assert "No branch protection/ruleset change." in decision
    assert "No admin bypass." in decision
    assert "No PAT-backed bot user." in decision
    assert "No Claude/Codex release authority." in decision
    assert "The `ao-release-gate` service is not yet publicly hosted." in decision
    assert "does not unblock GPP-2" in decision
    assert "authorize human-free merges yet" in decision


def test_gpp2x_packages_release_gate_container_without_hosting_or_merge_authority() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2x-AO-RELEASE-GATE-CONTAINER.md").read_text(
        encoding="utf-8"
    )

    assert "**Decision:** `ao_release_gate_container_ready_no_support_widening`" in decision
    assert "`ao-release-gate`" in decision
    assert "`deploy/ao-release-gate-service/Dockerfile`" in decision
    assert "`scripts/ao_release_gate_container_smoke.py`" in decision
    assert "no-secret health smoke" in decision
    assert "does not publish the image" in decision
    assert "post a check-run to GitHub" in decision
    assert "change branch protection" in decision
    assert "does not unblock GPP-2" in decision
    assert "does not authorize human-free merges" in decision
    assert "AO_CLAUDE_CODE_CLI_AUTH" in decision


def test_gpp2y_adds_release_gate_publish_path_without_hosting_or_merge_authority() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2y-AO-RELEASE-GATE-CONTAINER-PUBLISH.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `ao_release_gate_publish_path_ready_no_support_widening`" in decision
    assert "`ao-release-gate`" in decision
    assert "`.github/workflows/ao-release-gate-container-publish.yml`" in decision
    assert "`ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>`" in decision
    assert "no-secret `/healthz` smoke" in decision
    assert "does not host the service" in decision
    assert "post check-runs" in decision
    assert "change branch protection" in decision
    assert "does not unblock GPP-2" in decision
    assert "does not authorize human-free merges" in decision
    assert "AO_CLAUDE_CODE_CLI_AUTH" in decision


def test_gpp2aa_adds_release_gate_deploy_path_without_cutover_or_merge_authority() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2aa-AO-RELEASE-GATE-AUTONOMOUS-DEPLOY.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped`" in decision
    assert "`ao-release-gate`" in decision
    assert "`.github/workflows/ao-release-gate-deploy-cloud-run.yml`" in decision
    assert "`ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>`" in decision
    assert "GitHub OIDC" in decision
    assert "Secret Manager" in decision
    assert "check_run_post=false" in decision
    assert "branch_protection_cutover=false" in decision
    assert "merge_authority_enabled=false" in decision
    assert "post check-runs" in decision
    assert "change branch" in decision
    assert "AO_CLAUDE_CODE_CLI_AUTH" in decision


def test_gpp_next_load_status_validates_required_guards() -> None:
    mod = _module()

    payload = mod.load_status(_status_path())

    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/547"
    assert payload["blocked_wps"][0]["id"] == "GPP-2"
    assert (
        payload["current_wp"]["exit_decision"]
        == "ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped"
    )
    assert payload["support_widening_allowed"] is False


def test_gpp_next_rejects_fake_support_widening(tmp_path: Path) -> None:
    mod = _module()
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    payload["support_widening_allowed"] = True
    status_path = tmp_path / "gpp_status.v1.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        mod.load_status(status_path)
    except mod.GppStatusError as exc:
        assert "support_widening_allowed must be false" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("expected GppStatusError for fake support widening")


def test_gpp_next_text_output_names_current_and_blocked_work() -> None:
    mod = _module()
    payload = mod.load_status(_status_path())

    rendered = mod.render_text(payload, git_summary={"status": "## main...origin/main", "divergence": "0\t0"})

    assert "Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding" in rendered
    assert "Current status: blocked" in rendered
    assert "Support widening allowed: false" in rendered
    assert "Production platform claim allowed: false" in rendered
    assert "Live adapter execution allowed: false" in rendered
    assert "Blocked work packages:\n- GPP-2: repo-owned policy webhook container image publish path" in rendered
    assert "divergence: 0\t0" in rendered


def test_gpp_next_cli_json_output(capsys: Any) -> None:
    mod = _module()

    result = mod.main(["--status-path", str(_status_path()), "--output", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["blocked_wps"][0]["id"] == "GPP-2"
