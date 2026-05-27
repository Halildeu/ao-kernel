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
    """B-path absorb (Codex thread 019e691b iter-2+iter-3): the BC
    baseline now splits the previous `current_status` field into
    `current_gp59_status` (source truth from
    gp5_platform_claim_decision.py, using the script's own enum
    `pass|blocked|exception` exactly) and `promotion_readiness_status`
    (whether the criterion still blocks a general-purpose production
    platform claim). BC-10's GP-5.9 status is `exception` per GPP-3c
    (deliberate-policy exception); it remains a promotion-blocker
    until live usage/cost evidence lands. BC-1's GP-5.9 status is
    `blocked`; it remains a promotion-blocker until protected
    live-adapter gate attestation lands. BC-2..BC-9 are `pass` on
    both axes (the previous RI-7.7-internal alias `covered` is
    retired).
    """
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

    # BC-1: GP-5.9 status blocked; readiness blocked on protected gate attestation.
    assert bc_by_id["BC-1"]["current_gp59_status"] == "blocked"
    assert bc_by_id["BC-1"]["ri77_reclassification_decision"] == "retain_as_blocker"
    assert bc_by_id["BC-1"]["promotion_readiness_status"] == "blocked_until_protected_live_adapter_gate_attestation"
    assert bc_by_id["BC-1"]["required_evidence_class"] == "live"
    assert bc_by_id["BC-1"]["target_promotion_readiness_status_after_successful_supersession"] == "pass"

    # BC-10: GP-5.9 status exception (NOT blocked — GPP-3c policy exception);
    # readiness blocked on live usage/cost evidence.
    assert bc_by_id["BC-10"]["current_gp59_status"] == "exception"
    assert bc_by_id["BC-10"]["ri77_reclassification_decision"] == "retain_as_promotion_blocker"
    assert bc_by_id["BC-10"]["promotion_readiness_status"] == "blocked_until_live_usage_cost_evidence"
    assert bc_by_id["BC-10"]["required_evidence_class"] == "live"
    assert bc_by_id["BC-10"]["target_promotion_readiness_status_after_successful_supersession"] == "pass"

    # BC-1: also carries the new helper fields.
    assert bc_by_id["BC-1"]["target_promotion_readiness_status_after_successful_supersession"] == "pass"

    # BC-2..BC-9: passing on both axes. The script source-truth enum is
    # `pass` (not `covered`); the previous `covered` value was an
    # RI-7.7-internal alias that diverged from gp5 vocabulary
    # (Codex iter-3 absorb).
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
        assert bc_by_id[bc_id]["current_gp59_status"] == "pass", bc_id
        assert bc_by_id[bc_id]["ri77_reclassification_decision"] == "retain_as_pass", bc_id
        assert bc_by_id[bc_id]["promotion_readiness_status"] == "pass", bc_id
        assert bc_by_id[bc_id]["required_evidence_class"] == "none", bc_id

    # All three boundary surfaces stay unchanged at this slice; only the
    # contract is recorded.
    paths = {s["path"] for s in evidence["boundary_surfaces"]}
    assert paths == {"docs/PUBLIC-BETA.md", "docs/SUPPORT-BOUNDARY.md", "docs/KNOWN-BUGS.md"}
    for surface in evidence["boundary_surfaces"]:
        assert surface["ri77_edit_decision"] == "unchanged_record_contract_only"


def _load_gp5_decision_module():
    """Import scripts/gp5_platform_claim_decision.py without polluting
    sys.modules (test-time isolation pattern shared with
    tests/test_gp5_platform_claim_decision.py).
    """
    import importlib.util

    module_path = _REPO_ROOT / "scripts" / "gp5_platform_claim_decision.py"
    spec = importlib.util.spec_from_file_location("gp5_platform_claim_decision_for_ri77", module_path)
    assert spec is not None and spec.loader is not None, "cannot load gp5_platform_claim_decision module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ri77_evidence_bc_status_matches_gp5_decision_script() -> None:
    """B-path absorb (Codex thread 019e691b iter-3): each BC row's
    `current_gp59_status` in this artifact MUST equal the
    `success_criteria[].status` value that
    `scripts/gp5_platform_claim_decision.py::build_platform_claim_decision`
    reports for the same BC id. This is a machine-checked cross-ref, not
    a token grep — the iter-2 review flagged that token-only checks
    cannot prove the BC-10 row really carries `exception` (only that
    the string appears somewhere in the script). This test builds the
    full GP-5.9 decision report and walks every BC row.

    The script is the source truth; this artifact mirrors it. If the
    script changes a BC's status (e.g. BC-10 moves from `exception`
    back to `blocked`, or a new BC enters), this test surfaces the
    drift immediately.
    """
    module = _load_gp5_decision_module()
    report = module.build_platform_claim_decision(repo_root=_REPO_ROOT)
    criteria_by_id = {c["id"]: c for c in report["success_criteria"]}
    evidence = json.loads(_read(_EVIDENCE_PATH))
    bc_by_id = {bc["id"]: bc for bc in evidence["bc_baseline"]}

    # Every BC id present in either source MUST appear in the other.
    assert set(criteria_by_id) == set(bc_by_id), (
        f"BC id set mismatch: script reports {sorted(criteria_by_id)}, RI-7.7 evidence reports {sorted(bc_by_id)}"
    )

    # Per-row status must match exactly.
    for bc_id, bc in bc_by_id.items():
        script_status = criteria_by_id[bc_id]["status"]
        evidence_status = bc["current_gp59_status"]
        assert script_status == evidence_status, (
            f"{bc_id}: script reports status={script_status!r} but "
            f"RI-7.7 evidence carries current_gp59_status={evidence_status!r}"
        )

    # BC-10: exception status + empty blockers + the
    # 'real_adapter_usage_and_cost_evidence_missing' token has been
    # removed from the aggregate promotion_blockers list. This is the
    # exact contract the GPP-3c infazı established.
    bc10_script = criteria_by_id["BC-10"]
    assert bc10_script["status"] == "exception"
    assert bc10_script["blockers"] == [], f"BC-10 aggregate blockers drifted from empty: {bc10_script['blockers']!r}"
    assert "real_adapter_usage_and_cost_evidence_missing" not in report.get("promotion_blockers", []), (
        "real_adapter_usage_and_cost_evidence_missing reappeared in promotion_blockers; GPP-3c removed it"
    )

    # BC-1: blocked status + protected_live_adapter_gate_unattested
    # remains an aggregate promotion blocker.
    bc1_script = criteria_by_id["BC-1"]
    assert bc1_script["status"] == "blocked"
    assert "protected_live_adapter_gate_unattested" in report.get("promotion_blockers", []), (
        "protected_live_adapter_gate_unattested no longer in aggregate "
        "promotion_blockers; BC-1 closure path may have shifted"
    )

    # Codex iter-4 absorb: also validate the full GP-5.9 report against
    # its own schema and cross-check BC-1's per-row blockers list
    # between script and evidence (catches drift in the blocker
    # vocabulary, not just the aggregate top-level list).
    module.validate_report(report)
    bc1_evidence = bc_by_id["BC-1"]
    assert sorted(bc1_evidence.get("current_gp59_blockers", [])) == sorted(bc1_script.get("blockers", [])), (
        f"BC-1 per-row blockers drift: script={sorted(bc1_script.get('blockers', []))!r} "
        f"vs evidence={sorted(bc1_evidence.get('current_gp59_blockers', []))!r}"
    )
    bc10_evidence = bc_by_id["BC-10"]
    assert sorted(bc10_evidence.get("current_gp59_blockers", [])) == sorted(bc10_script.get("blockers", [])), (
        f"BC-10 per-row blockers drift: script={sorted(bc10_script.get('blockers', []))!r} "
        f"vs evidence={sorted(bc10_evidence.get('current_gp59_blockers', []))!r}"
    )


def test_ri77_evidence_required_evidence_refs_are_structured_and_paths_exist() -> None:
    """B-path absorb (Codex thread 019e691b iter-3): `required_evidence_refs`
    is now a structured list (object with path / ref_status /
    owner_slice / must_exist_before_reclassification), not bare
    strings. For `ref_status='existing'` entries the referenced file
    MUST exist on main today. For `ref_status='planned'` entries, the
    referenced file's owner_slice MUST be one of the named B-path
    slices (so a typo cannot disguise an invented owner).
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    valid_planned_owners = {
        "RI-7.8a",
        "RI-7.8b-bc1",
        "RI-7.8b-bc10",
        "RI-7.8c",
    }
    for bc in evidence["bc_baseline"]:
        for ref in bc.get("required_evidence_refs", []):
            assert isinstance(ref, dict), (
                f"{bc['id']}: required_evidence_refs entry is not a structured object: {ref!r}"
            )
            for key in ("path", "ref_status", "owner_slice", "must_exist_before_reclassification"):
                assert key in ref, f"{bc['id']}: required_evidence_refs entry missing {key}: {ref!r}"

            ref_path = _REPO_ROOT / ref["path"]
            if ref["ref_status"] == "existing":
                assert ref_path.exists(), f"{bc['id']}: existing ref does not exist on disk: {ref_path}"
                assert ref["owner_slice"] == "main", (
                    f"{bc['id']}: existing ref owner_slice should be 'main', got {ref['owner_slice']!r}"
                )
            elif ref["ref_status"] == "planned":
                assert ref["owner_slice"] in valid_planned_owners, (
                    f"{bc['id']}: planned ref owner_slice {ref['owner_slice']!r} "
                    f"is not in the valid B-path slice list {sorted(valid_planned_owners)}"
                )


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
