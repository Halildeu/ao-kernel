from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/GPP-2D-6-AUTOMERGE-SMOKE-RUNBOOK.md"
CODEOWNERS = ROOT / ".github/CODEOWNERS"


def test_gpp2d6_records_codeowners_narrowing_and_remaining_review_blockers() -> None:
    doc = DOC.read_text(encoding="utf-8")
    codeowners = CODEOWNERS.read_text(encoding="utf-8")

    assert "* @Halildeu @gladyatore-lab" not in codeowners
    assert "/.github/ @Halildeu @gladyatore-lab" in codeowners
    assert "/.claude/ @Halildeu @gladyatore-lab" in codeowners
    assert "/ao_kernel/ao_release_gate*.py @Halildeu @gladyatore-lab" in codeowners
    assert "/scripts/local_gpp_gate*.py @Halildeu @gladyatore-lab" in codeowners
    assert "/deploy/ @Halildeu @gladyatore-lab" in codeowners
    assert "That default was safe but blocked the GPP-2D-6 low-risk auto-merge smoke" in doc
    assert "CODEOWNERS narrowing and `enforce_admins=true` tightening are" in doc
    assert "repository.autoMergeAllowed=false" in doc
    assert "legacy_branch_protection.enforce_admins = true" in doc
    assert "required_approving_review_count=1" in doc
    assert "necessary but still insufficient" in doc
    assert "GPP-2D-6b gate slice moves the high-risk human-review requirement" in doc
    assert "ao-release-gate requires a current-head non-author APPROVED GitHub review" in doc


def test_gpp2d6_requires_cutover_and_operator_review_model_before_smoke() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "GPP-2D-5 branch-protection / ruleset cutover" in doc
    assert "`ao-release-gate` required, source-pinned to GitHub Actions" in doc
    assert "admin bypass disallowed" in doc
    assert "GPP-2D-7 / AO-GATE-9 closeout records GPP-2 as closed. Done" in doc
    assert "CODEOWNERS narrowing lands and legacy `enforce_admins=true` is verified." in doc
    assert "`ao-release-gate` path-sensitive human-review enforcement lands" in doc
    assert "Operator enables GitHub-native auto-merge" in doc
    assert "Operator selects and applies the low-risk review model" in doc
    assert "Steps 1-6 are complete or in this hardening PR. Steps 7-9 remain" in doc


def test_gpp2d6_pins_low_risk_and_high_risk_smoke_acceptance() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "Low-risk auto-merge smoke" in doc
    assert "For low-risk paths, `ao-release-gate` must not require a human review" in doc
    assert "`ao-release-gate` records no high-risk changed paths." in doc
    assert "No non-author human review is required for the low-risk path." in doc
    assert "GitHub performs the merge after required checks pass." in doc
    assert "High-risk human-gate smoke" in doc
    assert "`ao-release-gate` fails with" in doc
    assert "ao_release_gate_high_risk_human_review_missing" in doc
    assert "current-head non-author `APPROVED` GitHub review" in doc
    assert "GitHub still reports a code-owner / required-review block" in doc
    assert "must not auto-merge the PR" in doc


def test_gpp2d6_keeps_hard_stops_and_gpp2_closeout_boundary() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "Admin bypass attempted: false" in doc
    assert "Support widening: false" in doc
    assert "Production platform claim: false" in doc
    assert "Live adapter execution: false" in doc
    assert "testai / smee dependency: false" in doc
    assert "Legacy branch-protection enforce_admins setting before smoke" in doc
    assert "Repository auto-merge is disabled." in doc
    assert "GPP-2 status after smoke: remains closed" in doc
    assert "Until then, GPP-2D-6 remains incomplete, but GPP-2 remains `closed`." in doc
