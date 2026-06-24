"""Invariants for the governed-control-plane v4.x release checklist."""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHECKLIST = _REPO_ROOT / "docs" / "V4-GOVERNED-CONTROL-PLANE-RELEASE-CHECKLIST.md"
_GAP_DOC = _REPO_ROOT / "docs" / "V5-GOVERNED-CONTROL-PLANE-READINESS-GAP.md"
_GPP_STATUS = _REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"


def _text(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_v4_release_checklist_exists_and_is_non_authority() -> None:
    text = _text(_CHECKLIST)

    assert text.startswith("# v4.x Governed Control-Plane Release Checklist")
    assert "not release authority" in text
    assert "not a v5.0.0 release plan" in text
    assert "Release authority remains the repo-owned `ao-release-gate`" in text
    assert "AI output is review evidence only" in text


def test_v4_release_checklist_preserves_guard_false_boundary() -> None:
    status = json.loads(_GPP_STATUS.read_text(encoding="utf-8"))
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False

    text = _text(_CHECKLIST)
    assert "| Guard flags | All remain `false` |" in text
    forbidden_claims = (
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "v5.0.0 tag/publish is authorized",
        "general-purpose production platform claim is authorized",
    )
    for phrase in forbidden_claims:
        assert phrase not in text


def test_v4_release_checklist_requires_release_engineering_evidence() -> None:
    text = _text(_CHECKLIST)
    required = (
        "PyPI trusted publishing",
        "twine check dist/*.whl dist/*.tar.gz",
        "CodeQL",
        "Trivy",
        "SBOM/license",
        "commit SHA",
        "workflow run URL",
        "artifact digest",
        "rollback",
        "pip install ao-kernel==<version>",
    )
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, missing


def test_v4_release_checklist_pins_high_risk_provider_blocker() -> None:
    text = _text(_CHECKLIST)

    assert "Issue `#985` / PR `#997`" in text
    assert "real MiniMax review evidence" in text
    assert "no synthetic MiniMax `AGREE` may be used" in text
    assert "weakening the provider quorum" in text


def test_v5_gap_doc_points_to_checklist_and_no_go_section() -> None:
    text = _text(_GAP_DOC)

    assert "docs/V4-GOVERNED-CONTROL-PLANE-RELEASE-CHECKLIST.md" in text
    assert "## v5.0.0 Release No-Go" in text
    assert "not** a v5.0.0 release/tag/publish plan" in text
    assert "Any workflow, PR, or release note that attempts to tag or publish v5.0.0" in text
    assert "out of scope for this plan" in text
