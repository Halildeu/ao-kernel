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
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/567"
    assert (
        payload["current_wp"]["exit_decision"]
        == "no_testai_near_term_release_governance_selected_enforce_mode_and_required_check_cutover_pending_callback_deferred_no_support_widening"
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
        item["id"] == "GPP-2t"
        and item["decision"] == "policy_service_autonomous_deploy_path_ready_service_not_bootstrapped"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/535"
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
    assert any(
        item["id"] == "GPP-2ab"
        and item["decision"] == "policy_cloud_run_bootstrap_attestation_tool_ready_variables_missing"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/549"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2ac"
        and item["decision"] == "operator_owned_gate_end_user_onboarding_boundary_recorded_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/551"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2ad"
        and item["decision"] == "internal_vault_gate_secret_contract_ready_service_not_hosted_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/563"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2ae"
        and item["decision"] == "internal_operator_host_bundle_ready_service_not_hosted_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/565"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2af"
        and item["decision"]
        == "internal_gate_host_health_probe_ready_hosting_evidence_not_collected_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/567"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-5a"
        and item["decision"] == "repo_intelligence_product_onboarding_contract_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/553"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-5b"
        and item["decision"] == "repo_intelligence_explicit_workflow_context_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/555"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-5c"
        and item["decision"] == "repo_intelligence_read_only_workflow_surface_ready_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/557"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-5d"
        and item["decision"] == "repo_intelligence_read_only_workflow_surface_closed_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/559"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-6a"
        and item["decision"] == "read_only_e2e_preflight_ready_execution_blocked_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/561"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    # The no-testai near-term decision (GPP-2C plan, PR #585) is synced
    # into the machine-readable SSOT. Deployment-protection callback
    # topology (testai.acik.com/ao-gate, smee.io), callback review
    # evidence, and policy App slug reconciliation are reframed as a
    # deferred optional GPP-2C initiative; the active near-term path is
    # ao-release-gate enforce-mode evidence plus the required-check
    # cutover. GPP-2 stays blocked.
    assert payload["pending_external_actions"] == [
        "defer production-suitable deployment-protection callback topology, including any testai.acik.com/ao-gate or smee.io path, to an optional future GPP-2C infrastructure initiative",
        "defer deployment-protection callback review evidence and the protected-workflow callback rerun; no protected workflow dispatch or callback evidence is required for the no-testai GPP-2B near-term path",
        "defer policy App slug reconciliation ('ao-kernel-live-adapter-gate-policy' vs 'ao-kernel-live-adapter-gate') with the deferred deployment-protection callback initiative; it is not a near-term GPP-2B blocker",
        "before branch-protection cutover, switch ao-release-gate to enforce mode and demonstrate one positive success path plus one negative failure path on real pull requests",
        "cut branch protection/ruleset over to require ao-release-gate only after enforce-mode evidence is captured; admin bypass YASAK",
        "preserve local_gpp_gate as operator-controlled local/process evidence only; do not treat it as GPP-2 closure, support widening, live adapter execution approval, or production platform readiness",
        "keep end-user repo-intelligence onboarding independent from GPP-2 gate hosting by requiring at most GitHub App installation, repository selection, and explicit opt-in configuration",
    ]
    # GPP-2 stays blocked. The blocker narrative is synced to the
    # no-testai near-term model (GPP-2C plan, PR #585): the
    # deployment-protection callback path is deferred optional future
    # infrastructure; GPP-2 remains blocked pending ao-release-gate
    # enforce-mode evidence, the required-check cutover, and the
    # AO-GATE-9 closeout. Guard flags stay false.
    assert payload["blocked_wps"] == [
        {
            "id": "GPP-2",
            "reason": "the no-testai near-term release-governance model is selected and recorded: cross-provider AI review, non-author GitHub approval, local_gpp_gate operator evidence, and the ao-release-gate required-check mapping plus conclusion-mode matrix are the active GPP-2B path; repo-owned policy and ao-release-gate decision cores, container packages, GHCR publish paths, internal operator host bundle, hosted health evidence, webhook delivery chain evidence, and ao-release-gate shadow dry-run check-run evidence are collected; GPP-2 remains blocked pending ao-release-gate enforce-mode success and failure evidence on real pull requests, branch-protection/ruleset cutover that makes ao-release-gate a required status check with admin bypass disallowed, and the final AO-GATE-9/GPP status closeout; deployment-protection callback topology and callback review evidence, including any testai.acik.com/ao-gate or smee.io path, are deferred optional future infrastructure and are not active GPP-2B blockers",
        }
    ]
    assert any("python3 scripts/gpp_next.py" == item["command"] for item in payload["required_startup_checks"])
    assert any(
        action
        == "use the no-testai local/operator release-governance model as the active GPP-2 path: cross-provider AI review, non-author GitHub approval, local_gpp_gate evidence, and ao-release-gate required-check mapping"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "treat testai.acik.com/ao-gate, smee.io delivery, deployment-protection callback evidence, and policy App slug reconciliation as deferred GPP-2C infrastructure, not active GPP-2B blockers"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "collect ao-release-gate enforce-mode success and failure evidence on real pull requests before any branch-protection cutover"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "cut branch protection/ruleset over to require the ao-release-gate status check only after enforce-mode evidence is captured; admin bypass remains disallowed"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "do not repoint GitHub App webhooks to testai.acik.com/ao-gate in the no-testai GPP-2B path"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "keep the single-admin equivalent release gate not approved unless issue #489 is explicitly superseded"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "use --equivalent-release-gate-approved while GPP-2e remains not_approved"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "treat a product end-user account as release authority" for action in payload["forbidden_actions"]
    )
    assert any(
        action
        == "require product end users to self-host the GPP-2 deployment-protection policy service, vault, webhook secret, GitHub App private key, or Cloud Run project"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action
        == "require product end users to self-host the ao-release-gate check-run service, webhook, or branch-protection cutover"
        for action in payload["forbidden_actions"]
    )
    assert any(action == "treat a PAT-backed bot user as release authority" for action in payload["forbidden_actions"])
    assert any(action == "use admin bypass to merge GPP program PRs" for action in payload["forbidden_actions"])
    assert any(action == "treat Codex or Claude output as release authority" for action in payload["forbidden_actions"])
    assert any(
        action
        == "use the local AI review evidence gate as operator-controlled trust evidence only; it does not close GPP-2, change branch protection, execute live adapters, widen support, or claim production readiness"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "prioritize repo-intelligence onboarding as a read-only product workflow that requires GitHub App installation and repository selection, not Cloud Run, vault, webhook, or private-key setup by each user"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use GPP-6a read-only E2E preflight evidence for preparation only, while GPP-6 execution remains blocked until GPP-2 protected gate and GPP-4 read-only adapter decision are ready and support_widening_allowed=false and production_platform_claim_allowed=false"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "configure ao_kernel.live_adapter_gate_policy_runtime:application with internal vault secret ids or direct runtime secret manager values, never committed or echoed secret material"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "configure ao_kernel.ao_release_gate_runtime:application with internal vault secret ids or direct runtime secret manager values, never committed or echoed secret material"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "do not repeatedly dispatch .github/workflows/live-adapter-gate.yml while deployment-protection callback topology is deferred"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/live_adapter_gate_policy_service_smoke.py only for local webhook/callback artifact validation, not live callback posting"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use scripts/live_adapter_gate_policy_decision.py only for policy decision evaluation, not live callback posting or live adapter execution"
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
        == "do not reference AO_CLAUDE_CODE_CLI_AUTH through secrets context until a later live execution slice explicitly permits it"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "treat Claude MCP consultation as release authority" for action in payload["forbidden_actions"]
    )
    assert any(
        action == "use ao_memory_write or ao_llm_call during Claude MCP consultation"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "use Claude MCP consultation only as advisory review, not release authority"
        for action in payload["next_allowed_actions"]
    )


def test_gpp2e_equivalent_gate_decision_defaults_to_not_approved() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2e-SINGLE-ADMIN-EQUIVALENT-GATE-DECISION.md").read_text(
        encoding="utf-8"
    )

    assert "**Decision:** `not_approved`" in decision
    assert "does not approve that equivalent gate" in decision
    assert "--equivalent-release-gate-approved" in decision
    assert "must not be used for production prerequisite attestation" in decision


def test_gpp2f_independent_release_gate_replaces_end_user_reviewer_model() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2f-INDEPENDENT-RELEASE-GATE-ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )

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
    decision = (_repo_root() / ".claude/plans/GPP-2h-DEPLOYMENT-PROTECTION-BOT-GATE-DECISION.md").read_text(
        encoding="utf-8"
    )

    assert "**Decision:** `github_app_deployment_protection_rule_selected`" in decision
    assert "supersedes the first provisioning path selected in `GPP-2g`" in decision
    assert "GitHub App deployment protection rule" in decision
    assert "The model is a policy bot, not a user-like reviewer account." in decision
    assert "PAT-backed bot account listed as required reviewer" in decision
    assert "GPP-2i - deployment protection attestation support" in decision
    assert "does not unblock `GPP-2`" in decision
    assert "does not widen support" in decision


def test_gpp2i_attestation_support_keeps_gate_blocked() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2i-DEPLOYMENT-PROTECTION-ATTESTATION-SUPPORT.md").read_text(
        encoding="utf-8"
    )

    assert "**Decision:** `deployment_protection_attestation_supported_gate_still_blocked`" in decision
    assert "`release_gate_model = github_app_deployment_protection_rule`" in decision
    assert "`required_deployment_protection_app_slug = ao-kernel-live-adapter-gate`" in decision
    assert "deployment_protection_gate: blocked (live_gate_deployment_protection_missing)" in decision
    assert "`--equivalent-release-gate-approved` does not satisfy" in decision
    assert "does not unblock `GPP-2`" in decision
    assert "does not widen support" in decision


def test_gpp2u_selects_autonomous_github_app_release_gate_not_admin_bypass() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2u-AUTONOMOUS-GITHUB-APP-RELEASE-GATE.md").read_text(encoding="utf-8")

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
    decision = (_repo_root() / ".claude/plans/GPP-2v-AO-RELEASE-GATE-DRY-RUN-SCAFFOLD.md").read_text(encoding="utf-8")

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
    decision = (_repo_root() / ".claude/plans/GPP-2w-AO-RELEASE-GATE-CHECK-RUN-SERVICE.md").read_text(encoding="utf-8")

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
    decision = (_repo_root() / ".claude/plans/GPP-2x-AO-RELEASE-GATE-CONTAINER.md").read_text(encoding="utf-8")

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
    decision = (_repo_root() / ".claude/plans/GPP-2y-AO-RELEASE-GATE-CONTAINER-PUBLISH.md").read_text(encoding="utf-8")

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
    decision = (_repo_root() / ".claude/plans/GPP-2aa-AO-RELEASE-GATE-AUTONOMOUS-DEPLOY.md").read_text(encoding="utf-8")

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


def test_gpp2ab_policy_cloud_run_bootstrap_attestation_is_metadata_only() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2ab-POLICY-CLOUD-RUN-BOOTSTRAP-ATTESTATION.md").read_text(
        encoding="utf-8"
    )

    assert "policy_cloud_run_bootstrap_attestation_tool_ready_variables_missing" in decision
    assert "gh variable list --json name,updatedAt" in decision
    assert "A `metadata_ready` attestation means only" in decision
    assert "Google Cloud OIDC trust is not proven" in decision
    assert "Cloud Run deployment" in decision
    assert "AO_CLAUDE_CODE_CLI_AUTH" in decision
    assert "`live_execution_allowed=false`" in decision
    assert "`support_widening=false`" in decision
    assert "`production_platform_claim=false`" in decision


def test_gpp2ac_keeps_gate_operator_owned_and_end_user_onboarding_simple() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2ac-OPERATOR-GATE-END-USER-BOUNDARY.md").read_text(encoding="utf-8")

    assert "operator_owned_gate_end_user_onboarding_boundary_recorded_no_support_widening" in decision
    assert "self-host them to use the product" in decision
    assert "Operator-owned platform infrastructure" in decision
    assert "GitHub App private-key storage" in decision
    assert "`ao-release-gate` GitHub App check-run service hosting" in decision
    assert "real PR dry-run check-run evidence" in decision
    assert "install the product's GitHub App" in decision
    assert "select repositories" in decision
    assert "repo-intelligence" in decision
    assert "GitHub is not bypassed" in decision
    assert "`live_execution_allowed=false`" in decision
    assert "`support_widening=false`" in decision
    assert "`production_platform_claim=false`" in decision


def test_gpp2ad_records_internal_vault_gate_secret_contract() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2ad-INTERNAL-VAULT-GATE-SECRET-CONTRACT.md").read_text(
        encoding="utf-8"
    )

    assert "internal_vault_gate_secret_contract_ready_service_not_hosted_no_support_widening" in decision
    assert "internal host plus vault-backed runtime" in decision
    assert "secret contract" in decision
    assert "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID" in decision
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET_ID" in decision
    assert "AO_GITHUB_APP_PRIVATE_KEY_PEM_ID" in decision
    assert "End users must not be" in decision
    assert "asked to" in decision
    assert "self-host the policy service" in decision
    assert "public `/healthz` evidence" in decision
    assert "`live_execution_allowed=false`" in decision
    assert "`support_widening=false`" in decision
    assert "`production_platform_claim=false`" in decision


def test_gpp2ae_records_internal_operator_host_bundle() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2ae-INTERNAL-OPERATOR-HOST-BUNDLE.md").read_text(encoding="utf-8")

    assert "internal_operator_host_bundle_ready_service_not_hosted_no_support_widening" in decision
    assert "deploy/internal-gate-host/" in decision
    assert "ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service" in decision
    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service" in decision
    assert "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID" in decision
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET_ID" in decision
    assert "AO_GITHUB_APP_PRIVATE_KEY_PEM_ID" in decision
    assert "End users must not be asked" in decision
    assert "python3 scripts/internal_gate_host_bootstrap_attest.py" in decision
    assert "does not" in decision
    assert "`live_execution_allowed=false`" in decision
    assert "`support_widening=false`" in decision
    assert "`production_platform_claim=false`" in decision


def test_gpp2af_records_internal_gate_host_health_probe() -> None:
    decision = (_repo_root() / ".claude/plans/GPP-2af-INTERNAL-GATE-HOST-HEALTH-PROBE.md").read_text(encoding="utf-8")

    assert "internal_gate_host_health_probe_ready_hosting_evidence_not_collected_no_support_widening" in decision
    assert "scripts/internal_gate_host_health_probe.py" in decision
    assert "https://<AO_GATE_HOSTNAME>/policy/healthz" in decision
    assert "https://<AO_GATE_HOSTNAME>/release-gate/healthz" in decision
    assert "program_id=GPP-2q" in decision
    assert "program_id=GPP-2w" in decision
    assert "local_health_ready" in decision
    assert "secret_value_readback=false" in decision
    assert "github_webhook_configured=false" in decision
    assert "github_callback_post=false" in decision
    assert "github_check_run_post=false" in decision
    assert "branch_protection_cutover=false" in decision
    assert "protected_workflow_dispatch=false" in decision
    assert "live_adapter_execution=false" in decision
    assert "support_widening=false" in decision
    assert "production_platform_claim=false" in decision


def test_gpp_next_load_status_validates_required_guards() -> None:
    mod = _module()

    payload = mod.load_status(_status_path())

    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/567"
    assert payload["blocked_wps"][0]["id"] == "GPP-2"
    assert (
        payload["current_wp"]["exit_decision"]
        == "no_testai_near_term_release_governance_selected_enforce_mode_and_required_check_cutover_pending_callback_deferred_no_support_widening"
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
    assert "the no-testai near-term release-governance model is selected and recorded" in rendered
    assert "internal operator host bundle" in rendered
    assert "GPP-2 remains blocked pending ao-release-gate enforce-mode" in rendered
    assert "deferred optional future infrastructure" in rendered
    assert "are not active GPP-2B blockers" in rendered
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
