"""Doc invariant test for RI-7.6 cross-lane production matrix evidence."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.6-CROSS-LANE-PRODUCTION-MATRIX-EVIDENCE.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.6-CROSS-LANE-PRODUCTION-MATRIX-EVIDENCE.v1.json"
_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-cross-lane-production-matrix-evidence.schema.v1.json"
)
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri76_plan_doc_records_seven_lanes_and_exit_decision() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    for lane in (
        "read_only_e2e",
        "controlled_write_side",
        "remote_pr_write",
        "rollback_operations",
        "cost_telemetry",
        "release_governance",
        "real_adapter_live_execution",
    ):
        assert lane in flat, lane
    assert "ri7_cross_lane_production_matrix_ready" in flat
    assert "operator-bound deferred" in flat or "operator_bound_deferred" in flat
    assert "No production platform claim" in flat
    assert "No live adapter execution" in flat


def test_ri76_evidence_artifact_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri76_evidence_artifact_records_closed_boundary_and_seven_lanes() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_cross_lane_production_matrix_evidence"
    assert evidence["decision"] == "ri7_cross_lane_production_matrix_ready"
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False
    ids = {lane["id"] for lane in evidence["lanes"]}
    assert ids == {
        "read_only_e2e",
        "controlled_write_side",
        "remote_pr_write",
        "rollback_operations",
        "cost_telemetry",
        "release_governance",
        "real_adapter_live_execution",
    }
    by_id = {lane["id"]: lane for lane in evidence["lanes"]}
    # Real-adapter lane MUST remain operator-bound deferred so the live
    # boundary is auditable. All other lanes must be 'covered'.
    assert by_id["real_adapter_live_execution"]["status"] == "operator_bound_deferred"
    for lane_id in ids - {"real_adapter_live_execution"}:
        assert by_id[lane_id]["status"] == "covered", lane_id


def test_ri76_evidence_test_refs_cite_real_paths() -> None:
    """Every evidence_ref in the artifact must point at a path that
    actually exists in the repo today; the audit catches stale refs.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    for lane in evidence["lanes"]:
        for ref in lane["evidence_refs"]:
            ref_path = _REPO_ROOT / ref
            assert ref_path.exists(), f"missing evidence ref: {ref}"


def test_ri76_manifest_records_cross_lane_true_and_operator_bound_false() -> None:
    """The RI-7 evidence manifest committed with this slice flips
    `cross_lane_production_matrix_evidence` to true. Other RI-7.x
    evidence keys are owned by their own slices and may flip true
    independently; this test only pins the operator-bound flags as
    false because no docs-only slice can legitimately flip those.
    """
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["cross_lane_production_matrix_evidence"] is True
    # Only the operator-bound flags are pinned False here — the
    # remaining RI-7.x evidence keys are owned by their own slices
    # (e.g. RI-7.3 vector_backend_e2e_evidence, RI-7.4
    # scan_index_query_packaging_smoke, RI-7.7 gp59/support_boundary)
    # and may legitimately be True once those slices have also landed.
    for key in (
        "explicit_operator_authorization",
        "general_purpose_platform_claim_authorization",
        "operator_verified_runtime_semantics",
    ):
        assert manifest[key] is False, key
