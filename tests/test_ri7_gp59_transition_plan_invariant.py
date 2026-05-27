"""Doc invariant test for RI-7.7 GP-5.9 reclassification + support-boundary
transition plan evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.7-GP59-RECLASSIFICATION-SUPPORT-BOUNDARY-TRANSITION-PLAN.md"
_EVIDENCE_PATH = (
    _REPO_ROOT / ".claude" / "plans" / "RI-7.7-GP59-RECLASSIFICATION-SUPPORT-BOUNDARY-TRANSITION-PLAN.v1.json"
)
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-gp59-transition-plan-evidence.schema.v1.json"
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri77_plan_doc_records_bc_baseline_and_boundary_surfaces() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    for bc in ("BC-1", "BC-2", "BC-3", "BC-4", "BC-5", "BC-6", "BC-7", "BC-8", "BC-9", "BC-10"):
        assert bc in flat, bc
    for surface in (
        "docs/PUBLIC-BETA.md",
        "docs/SUPPORT-BOUNDARY.md",
        "docs/KNOWN-BUGS.md",
    ):
        assert surface in flat, surface
    assert "ri7_gp59_transition_plan_ready" in flat
    assert "No production platform claim" in flat
    assert "No live adapter execution" in flat
    assert "Forbidden-Change Audit" in text


def test_ri77_evidence_artifact_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri77_evidence_records_frozen_baseline_decisions() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_gp59_reclassification_support_boundary_transition_plan_evidence"
    assert evidence["decision"] == "ri7_gp59_transition_plan_ready"
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False

    bc_by_id = {bc["id"]: bc for bc in evidence["bc_baseline"]}
    assert set(bc_by_id) == {
        "BC-1",
        "BC-2",
        "BC-3",
        "BC-4",
        "BC-5",
        "BC-6",
        "BC-7",
        "BC-8",
        "BC-9",
        "BC-10",
    }
    # BC-1 + BC-10 retained as blockers; the rest retained as covered.
    assert bc_by_id["BC-1"]["current_status"] == "blocked"
    assert bc_by_id["BC-1"]["ri77_reclassification_decision"] == "retain_as_blocker"
    assert bc_by_id["BC-10"]["current_status"] == "blocked"
    assert bc_by_id["BC-10"]["ri77_reclassification_decision"] == "retain_as_blocker"
    for bc_id in (
        "BC-2",
        "BC-3",
        "BC-4",
        "BC-5",
        "BC-6",
        "BC-7",
        "BC-8",
        "BC-9",
    ):
        assert bc_by_id[bc_id]["current_status"] == "covered", bc_id
        assert bc_by_id[bc_id]["ri77_reclassification_decision"] == "retain_as_covered", bc_id

    # All three boundary surfaces stay unchanged at this slice; only the
    # contract is recorded.
    paths = {s["path"] for s in evidence["boundary_surfaces"]}
    assert paths == {"docs/PUBLIC-BETA.md", "docs/SUPPORT-BOUNDARY.md", "docs/KNOWN-BUGS.md"}
    for surface in evidence["boundary_surfaces"]:
        assert surface["ri77_edit_decision"] == "unchanged_record_contract_only"


def test_ri77_manifest_flips_both_gp59_and_support_boundary_keys() -> None:
    """The RI-7 evidence manifest committed with this slice flips
    both `gp59_reclassification_plan` and `support_boundary_transition_plan`
    to true. Other RI-7.x evidence keys are owned by their own slices and
    may flip true independently; this test only pins the operator-bound
    flags as false because no docs-only slice can legitimately flip those.
    """
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["gp59_reclassification_plan"] is True
    assert manifest["support_boundary_transition_plan"] is True
    # Only the operator-bound flags are pinned False here — the
    # remaining RI-7.x evidence keys are owned by their own slices
    # (e.g. RI-7.3 vector_backend_e2e_evidence, RI-7.4
    # scan_index_query_packaging_smoke, RI-7.6 cross_lane) and may
    # legitimately be True once those slices have also landed.
    for key in (
        "explicit_operator_authorization",
        "general_purpose_platform_claim_authorization",
        "operator_verified_runtime_semantics",
    ):
        assert manifest[key] is False, key


def test_ri77_public_boundary_surfaces_actually_exist() -> None:
    """The plan references docs/PUBLIC-BETA.md, SUPPORT-BOUNDARY.md, and
    KNOWN-BUGS.md as untouched. The files must exist in the repo today so
    the contract is grounded in real source.
    """
    for surface in (
        _REPO_ROOT / "docs" / "PUBLIC-BETA.md",
        _REPO_ROOT / "docs" / "SUPPORT-BOUNDARY.md",
        _REPO_ROOT / "docs" / "KNOWN-BUGS.md",
    ):
        assert surface.exists(), f"missing boundary surface: {surface}"
