from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/GPP-2D-5A-SMEE-RETIREMENT-EVIDENCE.md"


def test_gpp2d5a_records_external_check_run_collision_and_retirement() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "external GitHub App" in text
    assert "3800233" in text
    assert "ao-release-gate" in text
    assert "GitHub Actions" in text
    assert "smee-release.service" in text
    assert "inactive" in text
    assert "disabled" in text


def test_gpp2d5a_requires_source_pinned_github_actions_before_cutover() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Exactly one source may emit the reserved required-check name" in text
    assert "app_id:   15368" in text
    assert "app_slug: github-actions" in text
    assert "If `app_id=3800233` / `app_slug=ao-release-gate` appears again" in text
    assert "stop the cutover" in text


def test_gpp2d5a_keeps_hard_stops() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "No branch-protection / ruleset mutation." in text
    assert "No CODEOWNERS narrowing." in text
    assert "No auto-merge smoke." in text
    assert "No GPP-2 closeout." in text
    assert "No testai / smee active dependency reintroduced." in text
    assert "GPP-2 remains `blocked`" in text
