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
    # GPP-8 (M6 Faz 2) is the current slice in closed state. M5 milestone
    # is done (GPP-6 chain), M4 milestone done (GPP-4 chain). GPP-2
    # closeout + GPP-3 + GPP-4 + GPP-6 chains + GPP-6c are all preserved
    # in completed_wps as historical audit trace. GPP-7 itself is
    # intentionally NOT in completed_wps this slice (current-closed
    # accounting per program convention); the next M6 slice (GPP-8)
    # migrates GPP-7. M6 milestone closure is reserved for GPP-9.
    assert payload["current_wp"]["id"] == "GPP-8"
    assert payload["current_wp"]["status"] == "closed"
    # CC-13 issue anchor is opened during commit; allow null in this slice.
    assert payload["current_wp"].get("issue") in (
        None,
        "",
    ) or payload["current_wp"]["issue"].startswith("https://github.com/Halildeu/ao-kernel/issues/")
    assert (
        payload["current_wp"]["exit_decision"]
        == "gpp8_keep_sandbox_only_authoritative_no_remote_pr_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim"
    )
    assert payload["current_wp"]["record"] == ".claude/plans/GPP-8-REMOTE-PR-SANDBOX-DECISION.md"
    assert (_repo_root() / payload["current_wp"]["record"]).exists()
    assert payload["current_wp"]["evidence_collected"] == []
    # GPP-8 absence from completed_wps is invariant for this slice; the next
    # M6 closeout slice (GPP-9) migrates it. GPP-7 was migrated as part of
    # GPP-8 opener; GPP-7 is the most recent completed_wps entry from the
    # M6 chain.
    assert not any(item["id"] == "GPP-8" for item in payload["completed_wps"])
    gpp7_entries = [item for item in payload["completed_wps"] if item["id"] == "GPP-7"]
    assert len(gpp7_entries) == 1
    assert (
        gpp7_entries[0]["decision"]
        == "gpp7_keep_rehearsal_only_authoritative_no_write_side_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim"
    )
    assert gpp7_entries[0]["record"] == ".claude/plans/GPP-7-WRITE-CANDIDATE-DECISION.md"
    assert gpp7_entries[0]["pr"] == "https://github.com/Halildeu/ao-kernel/pull/632"
    assert gpp7_entries[0]["closed_at"] == "2026-05-26T00:22:00Z"
    # GPP-6c is still preserved in completed_wps from the prior slice migration.
    gpp6c_entries = [item for item in payload["completed_wps"] if item["id"] == "GPP-6c"]
    assert len(gpp6c_entries) == 1
    assert gpp6c_entries[0]["pr"] == "https://github.com/Halildeu/ao-kernel/pull/630"
    # GPP-3a closure is preserved in completed_wps with the schema-ready
    # decision string.
    gpp3a_entries = [item for item in payload["completed_wps"] if item["id"] == "GPP-3a"]
    assert len(gpp3a_entries) == 1
    assert gpp3a_entries[0]["decision"] == "real_adapter_usage_cost_schema_ready_live_run_pending_no_support_widening"
    assert gpp3a_entries[0]["record"] == ".claude/plans/GPP-3a-USAGE-COST-EVIDENCE-SCHEMA.md"
    # GPP-2 closeout is preserved in completed_wps with the full closeout
    # decision string + closeout record + closed_at timestamp.
    from datetime import datetime

    gpp2_entries = [item for item in payload["completed_wps"] if item["id"] == "GPP-2"]
    assert len(gpp2_entries) == 1, "exactly one GPP-2 entry in completed_wps"
    gpp2 = gpp2_entries[0]
    assert (
        gpp2["decision"]
        == "gpp2_closed_no_testai_release_governance_required_check_enforced_callback_deferred_no_support_widening_no_production_claim_no_live_adapter_execution"
    )
    assert gpp2["record"] == ".claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md"
    assert (_repo_root() / gpp2["record"]).exists()
    datetime.fromisoformat(gpp2["closed_at"].replace("Z", "+00:00"))
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
        "defer deployment-protection callback review evidence and the protected-workflow callback rerun; no protected workflow dispatch or callback evidence is required for the no-testai GPP-2B path under the GPP-2 closeout decision",
        "defer policy App slug reconciliation ('ao-kernel-live-adapter-gate-policy' vs 'ao-kernel-live-adapter-gate') with the deferred deployment-protection callback initiative; it is not a near-term active blocker under the GPP-2 closeout decision",
        "preserve local_gpp_gate as operator-controlled local/process evidence only; do not treat it as support widening, live adapter execution approval, production platform readiness, or release authority",
        "keep end-user repo-intelligence onboarding independent from GPP-2 gate hosting by requiring at most GitHub App installation, repository selection, and explicit opt-in configuration",
    ]
    # GPP-2 stays blocked. The blocker narrative is synced to the
    # no-testai near-term model (GPP-2C plan, PR #585): the
    # deployment-protection callback path is deferred optional future
    # infrastructure; GPP-2 remains blocked pending ao-release-gate
    # enforce-mode evidence, the required-check cutover, and the
    # AO-GATE-9 closeout. Guard flags stay false.
    assert payload["blocked_wps"] == []
    assert any("python3 scripts/gpp_next.py" == item["command"] for item in payload["required_startup_checks"])
    assert any(
        action
        == "continue operating the no-testai local/operator release-governance model with ao-release-gate enforced via GitHub ruleset as the recorded GPP-2 closeout outcome: cross-provider AI review, non-author GitHub approval, local_gpp_gate evidence, and ao-release-gate required-check enforcement"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "treat testai.acik.com/ao-gate, smee.io delivery, deployment-protection callback evidence, and policy App slug reconciliation as deferred GPP-2C infrastructure, not active blockers under the GPP-2 closeout decision"
        for action in payload["next_allowed_actions"]
    )
    # Closeout-anchored required-check operational rules (3 new):
    assert any(
        action
        == "operate ao-release-gate as the active required check enforced by the GitHub branch ruleset; do not regress to shadow conclusion-mode without explicit GPP supersession"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "keep the ao-release-gate ruleset bypass_actors list empty; do not add bypass actors without explicit GPP supersession"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "preserve the legacy main branch protection enforce_admins surface separately from the ao-release-gate ruleset; tightening that surface is an optional later hardening slice"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "do not repoint GitHub App webhooks to testai.acik.com/ao-gate under the GPP-2 closeout decision"
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
        == "use the local AI review evidence gate as operator-controlled trust evidence only; it does not execute live adapters, widen support, claim production readiness, or replace the ao-release-gate required check"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "prioritize repo-intelligence onboarding as a read-only product workflow that requires GitHub App installation and repository selection, not Cloud Run, vault, webhook, or private-key setup by each user"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action
        == "use GPP-6a read-only E2E preflight evidence for preparation only, while GPP-6 execution remains blocked until GPP-4 read-only adapter decision is ready and support_widening_allowed=false and production_platform_claim_allowed=false"
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
    # GPP-2D-7 / AO-GATE-9 closeout forbidden_actions: seven new supersession lines
    # that protect the terminal release-governance state.
    assert any(
        action
        == "treat GPP-2 closeout as support widening, production platform claim, or live adapter execution approval"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action
        == "reopen testai.acik.com/ao-gate, smee.io delivery, or deployment-protection callback topology without explicit GPP supersession of the deferred GPP-2C decision"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "regress ao-release-gate to shadow conclusion-mode without explicit GPP supersession"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "remove ao-release-gate from the GitHub ruleset required-check list without explicit GPP supersession"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action == "add bypass_actors to the ao-release-gate ruleset without explicit GPP supersession"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action
        == "treat GPP-2 closeout as completion of low-risk auto-merge smoke or CODEOWNERS narrowing without an explicit later GPP-2D-6/hardening record"
        for action in payload["forbidden_actions"]
    )
    assert any(
        action
        == "treat any same-name external ao-release-gate check-run as satisfying the required-check source pin without explicit ruleset/API verification"
        for action in payload["forbidden_actions"]
    )
    # Closeout negative guards: stale "blocked" wording must not return.
    joined = " ".join(
        payload["pending_external_actions"] + payload["next_allowed_actions"] + payload["current_wp"]["allowed_scope"]
    ).lower()
    assert "gpp-2 stays blocked" not in joined
    assert "cutover pending" not in joined
    assert "collect ao-release-gate enforce-mode success and failure evidence" not in joined
    assert "before branch-protection cutover" not in joined


def test_active_doc_surfaces_do_not_carry_stale_blocked_wording() -> None:
    """GPP-2D-7 / AO-GATE-9 closeout drift guard.

    After GPP-2 is closed, active human-readable and schema/source surfaces
    must not advertise the pre-closeout 'still blocked / cutover pending /
    future check / no service wiring' model. Historical change-log /
    tracking-log sections are excluded because they record the timeline of
    past slices.
    """

    repo = _repo_root()

    def _active_surface(path: str, *, timeline_header: str | None = None) -> str:
        text = (repo / path).read_text(encoding="utf-8")
        if timeline_header is not None and timeline_header in text:
            text = text.split(timeline_header, 1)[0]
        return text

    # Active surfaces — STATUS.md and AO-GATE roadmap are split on the
    # timeline / change-log header so historical entries do not trip the
    # guard. The schemas and the script module docstring are scanned in
    # full.
    surfaces = {
        # Active narrative: header + §1 Purpose + §1a 2026-05-22 Scope Correction
        # + §1b 2026-05-24 Autonomous Orchestration Alignment. §2 Current
        # Baseline onward records historical baseline + past-slice narratives.
        ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md": _active_surface(
            ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md",
            timeline_header="## 2. Current Baseline",
        ),
        # Active surface: header + How To Use + Guardrails + Roadmap Board up
        # to the per-slice historical AO-GATE-N narrative sections (which
        # describe each slice's at-merge state).
        ".claude/plans/AO-GATE-ROADMAP-TODO.md": _active_surface(
            ".claude/plans/AO-GATE-ROADMAP-TODO.md",
            timeline_header="## AO-GATE-1:",
        ),
        "ao_kernel/defaults/schemas/ao-release-gate-review-evidence-input.schema.v1.json": _active_surface(
            "ao_kernel/defaults/schemas/ao-release-gate-review-evidence-input.schema.v1.json",
        ),
        "ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json": _active_surface(
            "ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json",
        ),
        "scripts/local_gpp_gate.py": _active_surface("scripts/local_gpp_gate.py"),
        "AGENTS.md": _active_surface("AGENTS.md"),
    }

    stale_strings = (
        "GPP-2 stays blocked",
        "GPP-2 remains blocked",
        "GPP-2 remains fail-closed until",
        "GPP-2 stays `blocked`",
        "branch protection is unchanged",
        "No service wiring exists",
        "GPP-2 - Protected Live-Adapter Gate Runtime Binding (blocked)",
    )

    failures: list[str] = []
    for surface_path, body in surfaces.items():
        for stale in stale_strings:
            if stale in body:
                failures.append(f"{surface_path}: still carries stale '{stale}'")

    assert failures == [], "stale pre-closeout wording on active surfaces:\n" + "\n".join(failures)


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

    assert payload["current_wp"]["id"] == "GPP-8"
    assert payload["current_wp"]["status"] == "closed"
    issue = payload["current_wp"].get("issue")
    assert issue in (None, "") or issue.startswith("https://github.com/Halildeu/ao-kernel/issues/")
    assert payload["blocked_wps"] == []
    assert (
        payload["current_wp"]["exit_decision"]
        == "gpp8_keep_sandbox_only_authoritative_no_remote_pr_production_candidate_no_live_adapter_execution_no_support_widening_no_production_claim"
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

    # Renderer switches "Active" → "Current" prefix when current_wp.status is closed.
    assert "Current WP: GPP-8 - Remote PR Sandbox-Only Decision (M6 Faz 2)" in rendered
    assert "Current status: closed" in rendered
    assert "Support widening allowed: false" in rendered
    assert "Production platform claim allowed: false" in rendered
    assert "Live adapter execution allowed: false" in rendered
    assert "Blocked work packages:\n- none" in rendered
    # GPP-2 closeout already landed; GPP-6c is closed-current (M5 done), so no
    # "remains blocked pending" wording should leak.
    assert "remains blocked pending" not in rendered.lower()
    # Deferred GPP-2C wording must still be visible because the callback path stays
    # deferred. render_text() prints next_allowed_actions; the "deferred GPP-2C
    # infrastructure" line is the rendered anchor.
    assert "deferred GPP-2C infrastructure" in rendered
    assert "divergence: 0\t0" in rendered


def test_gpp_next_cli_json_output(capsys: Any) -> None:
    mod = _module()

    result = mod.main(["--status-path", str(_status_path()), "--output", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert payload["current_wp"]["id"] == "GPP-8"
    assert payload["current_wp"]["status"] == "closed"
    assert payload["blocked_wps"] == []


def test_allowed_scope_reflects_gpp8_keep_sandbox_only_decision() -> None:
    """current_wp.allowed_scope describes the GPP-8 closed slice scope
    (M6 Faz 2; remote PR keep_sandbox_only decision + docs sync +
    SSOT migration) and must not regress to earlier-slice wording."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    allowed_scope = payload["current_wp"]["allowed_scope"]
    assert isinstance(allowed_scope, list) and allowed_scope
    joined = " ".join(allowed_scope).lower()

    # Pre-no-testai active hosting scope must not return.
    for stale in (
        "deploy or configure the ao-kernel-live-adapter-gate github app policy service",
        "deploy or configure the ao-release-gate github app check-run service",
        "no-paid-cloud default host bundle",
        "internal_gate_host_health_probe",
        "configure hosted gate runtimes",
        "design or implement a local ai review evidence gate",
        "repeat protected workflow evidence collection",
    ):
        assert stale not in joined, f"stale active hosting scope re-entered allowed_scope: {stale}"

    # GPP-8 decision anchors must be present.
    assert any("keep_sandbox_only" in item.lower() and "authoritative" in item.lower() for item in allowed_scope)
    assert any("remote_pr_candidate_ready" in item.lower() for item in allowed_scope)
    assert any("option x" in item.lower() and "operator-bound" in item.lower() for item in allowed_scope)
    assert any("option z" in item.lower() and "reject" in item.lower() for item in allowed_scope)
    assert any("m6 milestone closure is reserved for gpp-9" in item.lower() for item in allowed_scope)
    assert any("docs/support-boundary.md" in item.lower() for item in allowed_scope)
    assert any("docs/public-beta.md" in item.lower() for item in allowed_scope)
    assert any("docs/known-bugs.md" in item.lower() for item in allowed_scope)
    # No aggregate map entry under GPP-8 (deferred to GPP-9 milestone closure)
    assert any("do not extend _aggregate_completion_sources" in item.lower() for item in allowed_scope)
    # GPP-8 is decision authority only; no live execution wording leak
    assert any("no live claude-code-cli adapter execution" in item.lower() for item in allowed_scope)
    # GPP-8 specific: non-sandbox repo live-write must be explicitly forbidden
    assert any("non-sandbox repo live-write" in item.lower() for item in allowed_scope)
    # Stale wording from prior slices must NOT appear in the active slice
    assert "gpp-2 stays blocked" not in joined
    assert "remains blocked pending" not in joined


# ---------------------------------------------------------------------------
# GOV-1: milestones + progress drift guards
# ---------------------------------------------------------------------------


# Aggregate-aware completion sources for milestone consistency. Each entry
# names how a GPP slot is considered "completed" for milestone purposes:
# - "current_wp": the slot lives in current_wp with the given status
# - "evidence_refs": milestone's evidence_refs must include this path
# - "completed_children": the listed children must all appear in completed_wps
_AGGREGATE_COMPLETION_SOURCES = {
    # GPP-2 closeout moved into completed_wps as part of GPP-3a; the default
    # branch in _slot_is_satisfied (slot in completed_ids) handles it from
    # there. GPP-2D, GPP-3, GPP-4, GPP-5 and GPP-6 remain aggregate (lane /
    # parent-with-children). GPP-4 closes under the keep_operator_beta
    # authority across three Faz records (GPP-4a + GPP-4b + GPP-4c). GPP-6
    # closes under the keep_rehearsal_only authority across three Faz
    # records (GPP-6a + GPP-6b + GPP-6c).
    "GPP-2D": {"evidence_refs": [".claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md"]},
    "GPP-3": {
        "evidence_refs": [
            ".claude/plans/GPP-3a-USAGE-COST-EVIDENCE-SCHEMA.md",
            ".claude/plans/GPP-3b-BC10-CLOSURE-PATH-DECISION.md",
            ".claude/plans/GPP-3c-BC10-EXCEPTION-INFAZ.md",
        ]
    },
    "GPP-4": {
        "evidence_refs": [
            ".claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md",
            ".claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md",
            ".claude/plans/GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md",
        ]
    },
    "GPP-5": {"completed_children": {"GPP-5a", "GPP-5b", "GPP-5c", "GPP-5d"}},
    "GPP-6": {
        "evidence_refs": [
            ".claude/plans/GPP-6a-READ-ONLY-E2E-PREFLIGHT.md",
            ".claude/plans/GPP-6b-READ-ONLY-E2E-DECISION.md",
            ".claude/plans/GPP-6c-KEEP-REHEARSAL-ONLY-INFAZ.md",
        ]
    },
}


def _slot_is_satisfied(slot: str, payload: dict[str, object], milestone: dict[str, object]) -> bool:
    """True if a GPP slot is satisfied for milestone completion."""
    completed_ids = {item["id"] for item in payload.get("completed_wps", []) if isinstance(item, dict)}
    current_wp = payload.get("current_wp", {}) or {}
    aggregate = _AGGREGATE_COMPLETION_SOURCES.get(slot)
    # Aggregate / lane IDs (GPP-2, GPP-2D, GPP-3, GPP-4, GPP-5, GPP-6) need explicit handling.
    if aggregate is not None:
        if "current_wp" in aggregate:
            return current_wp.get("id") == slot and current_wp.get("status") == aggregate["current_wp"]
        if "evidence_refs" in aggregate:
            evidence_refs = milestone.get("evidence_refs", [])
            return all(ref in evidence_refs for ref in aggregate["evidence_refs"])
        if "completed_children" in aggregate:
            return aggregate["completed_children"] <= completed_ids
    # Default: slot must appear in completed_wps.
    return slot in completed_ids


def test_gpp_status_milestones_contract() -> None:
    """milestones[] presence, structure, and seven-milestone invariant."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    milestones = payload["milestones"]
    assert isinstance(milestones, list) and len(milestones) == 7
    ids = [m["id"] for m in milestones]
    assert ids == ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
    for m in milestones:
        assert set(m.keys()) >= {"id", "title", "gpp_slots", "status", "closed_at", "evidence_refs"}
        assert isinstance(m["gpp_slots"], list) and m["gpp_slots"]
        assert m["status"] in ("done", "pending")
        assert isinstance(m["evidence_refs"], list)
        if m["status"] == "pending":
            assert m["closed_at"] is None
            assert m["evidence_refs"] == []


def test_gpp_status_done_milestones_have_evidence_refs() -> None:
    """Every done milestone has at least one evidence_refs path that exists."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    done_milestones = [m for m in payload["milestones"] if m["status"] == "done"]
    assert len(done_milestones) == 6
    for m in done_milestones:
        assert m["evidence_refs"], f"done milestone {m['id']} has empty evidence_refs"
        for ref in m["evidence_refs"]:
            assert (_repo_root() / ref).exists(), f"missing evidence_refs path {ref} for {m['id']}"
        # closed_at must be ISO-parseable.
        from datetime import datetime

        datetime.fromisoformat(m["closed_at"].replace("Z", "+00:00"))


def test_gpp_status_m4_done_three_evidence_refs() -> None:
    """M4 done state carries exactly the three GPP-4 Faz record paths."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    m4 = next(m for m in payload["milestones"] if m["id"] == "M4")
    assert m4["status"] == "done"
    assert set(m4["evidence_refs"]) == {
        ".claude/plans/GPP-4a-FAILURE-MATRIX-SCHEMA.md",
        ".claude/plans/GPP-4b-KEEP-OPERATOR-BETA-DECISION.md",
        ".claude/plans/GPP-4c-KEEP-OPERATOR-BETA-INFAZ.md",
    }
    assert len(m4["evidence_refs"]) == 3


def test_gpp_status_m5_done_three_evidence_refs() -> None:
    """M5 done state carries exactly the three GPP-6 Faz record paths."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    m5 = next(m for m in payload["milestones"] if m["id"] == "M5")
    assert m5["status"] == "done"
    assert set(m5["evidence_refs"]) == {
        ".claude/plans/GPP-6a-READ-ONLY-E2E-PREFLIGHT.md",
        ".claude/plans/GPP-6b-READ-ONLY-E2E-DECISION.md",
        ".claude/plans/GPP-6c-KEEP-REHEARSAL-ONLY-INFAZ.md",
    }
    assert len(m5["evidence_refs"]) == 3


def test_gpp_status_done_milestones_are_consistent_with_completion_sources() -> None:
    """Aggregate-aware: each done milestone's slots are satisfied by
    completed_wps, closed current_wp, or explicit aggregate completion mapping."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    for m in payload["milestones"]:
        if m["status"] != "done":
            continue
        for slot in m["gpp_slots"]:
            assert _slot_is_satisfied(slot, payload, m), (
                f"done milestone {m['id']} slot {slot} not satisfied by completed_wps, current_wp, or aggregate map"
            )


def test_gpp_status_progress_estimates_present() -> None:
    """progress_estimates contains both milestone-based and wp-weighted blocks."""
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    pe = payload["progress_estimates"]
    assert set(pe.keys()) >= {"milestones", "wp_weighted"}
    ms = pe["milestones"]
    assert ms["done_count"] == 6
    assert ms["total_count"] == 7
    assert ms["percent"] == 86
    assert ms["next_milestone_id"] == "M6"
    wp = pe["wp_weighted"]
    # GPP-8 M6 Faz 2 opener accounting (current-closed convention):
    #   completed_wps_count=47 (46 prior + GPP-7 migrated into completed_wps),
    #   closed_current_wp_count=1 (GPP-8 current closed; M6 still pending),
    #   completed_or_closed_count=48 = 47 + 1.
    assert wp["completed_wps_count"] == 47
    assert wp["closed_current_wp_count"] == 1
    assert wp["completed_or_closed_count"] == 48
    assert wp["estimated_total_wps"] == 50
    assert wp["percent"] == 96
    assert wp["estimated"] is True


def test_gpp_next_progress_output_renders_milestones(capsys: Any) -> None:
    """`--output progress` lists all seven milestones and the headline."""
    mod = _module()
    result = mod.main(["--status-path", str(_status_path()), "--output", "progress"])
    captured = capsys.readouterr()
    assert result == 0
    out = captured.out
    assert "Milestones: 6/7 done (86%; next M6 - Production matrix + final claim)" in out
    assert "WP-weighted estimate: 48/50 (96%; estimated)" in out
    for mid in ("M0", "M1", "M2", "M3", "M4", "M5", "M6"):
        assert f"- {mid} [" in out


def test_gpp_next_text_output_renders_milestone_summary() -> None:
    """Default text output carries the two-line milestone summary."""
    mod = _module()
    payload = mod.load_status(_status_path())
    rendered = mod.render_text(payload, git_summary={"status": "## main", "divergence": "0\t0"})
    assert "Milestones: 6/7 done (86%; next M6 - Production matrix + final claim)" in rendered
    assert "WP-weighted estimate: 48/50 (96%; estimated)" in rendered


def test_status_md_milestones_section_is_timeline_free() -> None:
    """STATUS.md §0 Milestones must exist and must not duplicate the global
    `**Date:** YYYY-MM-DD` header inside the milestone section (Codex iter-1
    hardening)."""
    status_md = (_repo_root() / ".claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md").read_text(
        encoding="utf-8"
    )
    assert "## 0. Milestones" in status_md
    section_start = status_md.index("## 0. Milestones")
    section_end = status_md.index("## 1. Purpose")
    section = status_md[section_start:section_end]
    # The section must reference the seven canonical milestone IDs.
    for mid in ("M0", "M1", "M2", "M3", "M4", "M5", "M6"):
        assert f"| {mid} |" in section, f"milestone row for {mid} missing in §0"
    # And must NOT carry a `**Date:**` line of its own (date drift).
    assert "**Date:**" not in section
    # GPP-2 reference is required in the slot column for M1.
    assert "GPP-2" in section
    # Pre-closeout stale wording for GPP-2 must NOT appear in the active §0
    # (case-insensitive sharp check; covers `blocked` / `Blocked`).
    assert "gpp-2 blocked" not in section.lower()
    assert "gpp-2 stays blocked" not in section.lower()
    assert "gpp-2 remains blocked" not in section.lower()
