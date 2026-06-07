"""Doc-bound invariants for the v4.2.0 cross-repo dogfood evidence doc.

Keeps the evidence doc honest: it must label itself an operator-local
usage-model demo (NOT project-owned production evidence, per CLAUDE.md §21),
keep the three guard flags false, carry the reproducible transcript markers, and
carry an explicit "does NOT prove" scope so it cannot drift into a
production-platform overclaim.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "EVIDENCE-V4.2.0-CROSS-REPO-DOGFOOD.md"


def _normalized() -> str:
    cleaned: list[str] = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        while stripped.startswith(">"):
            stripped = stripped[1:].lstrip()
        cleaned.append(stripped)
    # Drop markdown emphasis markers so bold like ``**no**`` inside a phrase does
    # not break contiguous substring matching.
    text = " ".join(" ".join(cleaned).split()).lower()
    return text.replace("*", "")


def test_doc_present() -> None:
    assert DOC.is_file()


def test_doc_labels_itself_non_production_evidence() -> None:
    text = _normalized()
    # §21 evidence-class disclaimer must be explicit.
    assert "not project-owned production evidence" in text
    assert "operator-local usage-model demo" in text
    assert "§21" in text or "gpp contract" in text


def test_doc_keeps_guard_flags_false() -> None:
    text = _normalized()
    for flag in ("live_adapter_execution", "support_widening", "production_platform_claim"):
        assert flag in text
    assert "const false" in text
    assert "no provider api key" in text or "no api key" in text


def test_doc_carries_reproducible_transcript_markers() -> None:
    text = _normalized()
    assert "pip install ao-kernel==4.2.0" in text
    assert "from pypi" in text
    assert "fail-closed" in text
    assert "query_memory" in text


def test_doc_has_explicit_negative_scope() -> None:
    # Must say what it does NOT prove, and any production-platform mention must be
    # negated (no overclaim).
    text = _normalized()
    assert "does not prove" in text
    assert "no production-platform claim" in text or "confers no production-platform" in text
    # No bare affirmative production-platform claim.
    if "production platform" in text:
        idx = text.index("production platform")
        window = text[max(0, idx - 30) : idx]
        assert "no " in window or "not " in window, "production-platform mention must be negated"


def test_doc_does_not_conflate_canonical_store_with_jsonl_evidence_trail() -> None:
    # The dogfood writes the canonical decision store, NOT the separate JSONL
    # evidence trail. The doc must name the canonical store and explicitly mark
    # the JSONL evidence trail as a separate, non-exercised surface.
    text = _normalized()
    assert "canonical decision store" in text
    # JSONL evidence trail must be framed as separate / not exercised, never
    # claimed as proven by this demo.
    assert "jsonl evidence trail" in text
    assert "separate surface" in text
    # The reproduce snippet must match the transcript's bundled-policy line.
    assert "policy_cost_tracking" in text
