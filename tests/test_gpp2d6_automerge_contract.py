from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/GPP-2D-6-AUTOMERGE-SMOKE-RUNBOOK.md"
CODEOWNERS = ROOT / ".github/CODEOWNERS"


def test_gpp2d6_records_current_broad_codeowners_as_blocking_low_risk_automerge() -> None:
    doc = DOC.read_text(encoding="utf-8")
    codeowners = CODEOWNERS.read_text(encoding="utf-8")

    assert "* @Halildeu @gladyatore-lab" in codeowners
    assert "safe but blocks the GPP-2D-6 low-risk auto-merge smoke" in doc
    assert "This runbook intentionally does not change CODEOWNERS." in doc
    assert "Weakening reviewer coverage before `ao-release-gate` is source-pinned" in doc


def test_gpp2d6_requires_cutover_before_codeowners_narrowing() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "GPP-2D-5 branch-protection / ruleset cutover" in doc
    assert "`ao-release-gate` required, source-pinned to GitHub Actions" in doc
    assert "admin bypass disallowed" in doc
    assert "Steps 1-3 must complete before any CODEOWNERS narrowing." in doc


def test_gpp2d6_pins_low_risk_and_high_risk_smoke_acceptance() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "Low-risk auto-merge smoke" in doc
    assert "No non-author human review is required for the low-risk path." in doc
    assert "GitHub performs the merge after required checks pass." in doc
    assert "High-risk human-gate smoke" in doc
    assert "GitHub still reports a code-owner / required-review block." in doc
    assert "must not auto-merge the PR" in doc


def test_gpp2d6_keeps_hard_stops_and_gpp2_closeout_boundary() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "Admin bypass attempted: false" in doc
    assert "Support widening: false" in doc
    assert "Production platform claim: false" in doc
    assert "Live adapter execution: false" in doc
    assert "testai / smee dependency: false" in doc
    assert "Until then, GPP-2 remains `blocked`." in doc
