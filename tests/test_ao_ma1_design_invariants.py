from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md"
STATUS = ROOT / ".claude/plans/gpp_status.v1.json"
AGENTS = ROOT / "AGENTS.md"


def test_ao_ma1_keeps_release_authority_in_ao_release_gate() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "AO-MA execution layer" in text
    assert "GPP-2D merge / release authority layer" in text
    assert "Agent outputs are evidence, not authority." in text
    assert (
        "Release authority = the repo-owned `ao-release-gate` required check plus GitHub branch-protection enforcement."
        in text
    )
    assert "Claude MCP consultation is advisory review only, not release authority." in text
    assert "No treating Codex, Claude, or any other model output as release authority." in text


def test_ao_ma1_pins_agent_roles_parallel_worktrees_and_claim_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")

    for required_role in (
        "Planner Agent",
        "Explorer Agent",
        "Worker / Implementation Agent",
        "Reviewer Agent",
        "Verifier Agent",
        "Integrator",
        "Release Gate",
    ):
        assert required_role in text

    assert "parallel AI agents with disjoint write scopes" in text
    assert "Every worker uses a separate worktree and short-lived branch." in text
    assert "No two workers may edit the same file" in text
    assert "claim-required coordination set" in text
    assert "one-agent-one-worktree semantics" in text


def test_ao_ma1_is_docs_only_and_keeps_gpp2_guards_closed() -> None:
    text = DOC.read_text(encoding="utf-8")
    status = json.loads(STATUS.read_text(encoding="utf-8"))

    assert "AO-MA-1 is a design/docs-only slice" in text
    assert "GPP-2 stays `blocked`" in text
    assert "support_widening=false" in text
    assert "production_platform_claim=false" in text
    assert "live_adapter_execution=false" in text
    assert "No admin bypass" in text
    assert "No branch-protection/ruleset mutation by the agent." in text
    assert (
        "No testai.acik.com/ao-gate, smee.io, GitHub App webhook, or deployment-protection callback work in AO-MA-1."
        in text
    )
    # GPP-2 closeout (AO-GATE-9) is recorded in completed_wps; AO-MA-1 stays
    # docs-only and does not change the three guard flags. The active slice
    # at this point in the program is GPP-3a (Faz 1 of GPP-3) which migrated
    # current_wp away from GPP-2.
    gpp2_entries = [item for item in status["completed_wps"] if item.get("id") == "GPP-2"]
    assert len(gpp2_entries) == 1
    assert "closed_at" in gpp2_entries[0]
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False


def test_agents_contract_names_active_gpp2d_and_ao_ma1_context() -> None:
    text = AGENTS.read_text(encoding="utf-8")

    assert "GPP-2 - Protected Live-Adapter Gate Runtime Binding (closed)" in text
    assert "GPP-2D - Autonomous Required-Check Lane" in text
    assert "GPP-2D-3 enforce job" in text
    assert "GPP-2D-5 branch-protection ruleset cutover" in text
    assert "GPP-2D-7 AO-GATE-9 GPP-2 closeout" in text
    assert "AO-MA-1 - Multi-Agent Orchestration Design" in text
    assert "GPP-2C - testai / smee / webhook callback integration" in text
    assert "Deferred, not an active blocker" in text
    assert "AI agent output is evidence, not release authority." in text
    assert "Release authority is the repo-owned ao-release-gate required check plus" in text
