from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/AO-MA-10N-LIVE-ENFORCEMENT-CUTOVER.md"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_ao_ma10n_records_tracker_and_pr682_dependency() -> None:
    text = _doc_text()
    assert "https://github.com/Halildeu/ao-kernel/issues/683" in text
    assert "PR #682 must land first" in text
    assert "No live enforcement mutation should happen before #682 is" in text


def test_ao_ma10n_requires_dual_source_pinned_release_authority_checks() -> None:
    text = _doc_text()
    assert "ao-release-gate-technical" in text
    assert "ao-release-gate-review" in text
    assert "integration_id: 15368" in text
    assert "bypass_actors: []" in text
    assert "The legacy compatibility wrapper named `ao-release-gate` is not sufficient" in text


def test_ao_ma10n_keeps_classic_ci_requirements_and_hard_stops() -> None:
    text = _doc_text()
    for check in (
        "lint",
        "test (3.11)",
        "test (3.12)",
        "test (3.13)",
        "coverage",
        "typecheck",
        "packaging-smoke",
    ):
        assert f"- `{check}`" in text

    assert "No admin bypass." in text
    assert "No ruleset bypass actors." in text
    assert "No removal of classic CI requirements." in text
    assert "No support widening." in text
    assert "No production platform claim." in text
    assert "No live adapter execution." in text
    assert "No testai/smee/deployment-protection callback dependency." in text


def test_ao_ma10n_exposes_cc9_full_autonomy_gap() -> None:
    text = _doc_text()
    assert "CC-9 supersession gap" in text
    assert "operator-only" in text
    assert "Operator-bootstrap mode" in text
    assert "Full no-human bootstrap mode" in text
    assert "Until one of these modes is completed, full no-human autonomy is not proven." in text


def test_ao_ma10n_requires_positive_and_negative_smoke_before_activation() -> None:
    text = _doc_text()
    assert "High-risk smoke" in text
    assert "positive path" in text
    assert "negative path" in text
    assert "Low-risk direct merge smoke" in text
    assert "AO-MA-10m activation" in text
    assert "AO-MA-10N is complete only when:" in text
