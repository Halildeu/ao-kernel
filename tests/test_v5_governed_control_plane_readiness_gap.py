"""Invariants for the V5 governed control-plane readiness gap note."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC_PATH = _REPO_ROOT / "docs" / "V5-GOVERNED-CONTROL-PLANE-READINESS-GAP.md"
_RI7_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_v5_gap_note_distinguishes_default_blocked_from_manifest_ready() -> None:
    """The note must not collapse default fail-closed output into current RI-7 state."""
    text = _read(_DOC_PATH)

    assert "Without an evidence manifest" in text
    assert "blocked_operator_bound_evidence_required" in text
    assert "--evidence-manifest .claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json" in text
    assert "ready_for_operator_promotion_decision" in text
    assert "overall_status: ready_for_operator_decision" in text
    assert "promotion_blockers: []" in text


def test_v5_gap_manifest_ready_claim_matches_readiness_tool() -> None:
    """The manifest-backed ready wording must match the actual readiness CLI."""
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/repo_intelligence_tier_promotion_readiness.py",
            "--output",
            "json",
            "--evidence-manifest",
            str(_RI7_MANIFEST_PATH),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["decision"] == "ready_for_operator_promotion_decision"
    assert report["overall_status"] == "ready_for_operator_decision"
    assert report["promotion_blockers"] == []
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["live_adapter_execution"] is False


def test_v5_gap_note_does_not_reopen_completed_ri7_agent_rows() -> None:
    """When the RI-7 manifest is all true, completed evidence rows must not reappear as next work."""
    manifest = json.loads(_read(_RI7_MANIFEST_PATH))
    evidence_keys = {
        key: value
        for key, value in manifest.items()
        if key not in {"schema_version", "artifact_kind"}
    }
    assert evidence_keys, "expected at least one RI-7 evidence key"
    assert all(value is True for value in evidence_keys.values()), evidence_keys

    text = _read(_DOC_PATH)
    assert "No agent-only RI-7 evidence rows remain open in this document." in text
    for key in evidence_keys:
        assert f"`{key}`" in text
    stale_next_work_phrases = (
        "docs(readiness): record guardrail hardening matrix evidence plan",
        "test(readiness): add wheel-installed scan/index/query smoke harness",
        "| 2 | Guardrail hardening matrix evidence |",
        "| 3 | Vector backend E2E evidence |",
        "| 4 | Wheel-installed scan/index/query smoke |",
        "| 5 | Cross-lane production matrix gap inventory |",
        "| 6 | GP-5.9 reclassification + support-boundary transition draft |",
    )
    for phrase in stale_next_work_phrases:
        assert phrase not in text, phrase
