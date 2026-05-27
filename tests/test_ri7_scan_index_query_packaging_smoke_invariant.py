"""Doc invariant test for RI-7.4 packaging smoke evidence."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.4-SCAN-INDEX-QUERY-PACKAGING-SMOKE.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.4-SCAN-INDEX-QUERY-PACKAGING-SMOKE.v1.json"
_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-scan-index-query-packaging-smoke-evidence.schema.v1.json"
)
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri74_plan_doc_records_six_scenarios_and_exit_decision() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    for scenario in (
        "entrypoint_help_exits_zero",
        "repo_scan_writes_schema_valid_repo_map",
        "repo_index_write_vectors_fails_closed_without_backend",
        "repo_query_fails_closed_without_manifest_or_backend",
        "repo_index_write_vectors_fails_closed_without_api_key",
        "repo_query_fails_closed_without_api_key",
    ):
        assert scenario in flat, scenario
    assert "ri7_scan_index_query_packaging_smoke_ready" in flat
    assert "No production platform claim" in flat
    assert "No live adapter execution" in flat
    assert "Forbidden-Change Audit" in text


def test_ri74_evidence_artifact_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri74_evidence_artifact_records_closed_boundary_and_six_scenarios() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_scan_index_query_packaging_smoke_evidence"
    assert evidence["decision"] == "ri7_scan_index_query_packaging_smoke_ready"
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False
    ids = {s["id"] for s in evidence["scenarios"]}
    assert ids == {
        "entrypoint_help_exits_zero",
        "repo_scan_writes_schema_valid_repo_map",
        "repo_index_write_vectors_fails_closed_without_backend",
        "repo_query_fails_closed_without_manifest_or_backend",
        "repo_index_write_vectors_fails_closed_without_api_key",
        "repo_query_fails_closed_without_api_key",
    }
    for s in evidence["scenarios"]:
        assert s["status"] == "pass"
    assert evidence["build_install_layer_ref"] == "scripts/packaging_smoke.py"


def test_ri74_manifest_records_packaging_smoke_true_and_operator_bound_false() -> None:
    """The RI-7 evidence manifest committed with this slice flips
    `scan_index_query_packaging_smoke` to true. Other RI-7.x evidence
    keys are owned by their own slices and may flip true independently;
    this test only pins the operator-bound flags as false because no
    docs-only slice can legitimately flip those.
    """
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["scan_index_query_packaging_smoke"] is True
    # Only the operator-bound flags are pinned False here — the
    # remaining RI-7.x evidence keys are owned by their own slices
    # (e.g. RI-7.3 vector_backend_e2e_evidence, RI-7.6 cross_lane,
    # RI-7.7 gp59/support_boundary) and may legitimately be True once
    # those slices have also landed.
    for key in (
        "explicit_operator_authorization",
        "general_purpose_platform_claim_authorization",
        "operator_verified_runtime_semantics",
    ):
        assert manifest[key] is False, key


def test_ri74_evidence_test_refs_cite_real_source_file() -> None:
    """Every evidence_ref must point at an actually-existing file under
    `tests/` or `scripts/`. RI-7.4 evidence references
    `scripts/packaging_smoke.py::_smoke_repo_intelligence_cli` as the
    wheel-installed smoke entry point.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    tests_root = _REPO_ROOT / "tests"
    scripts_root = _REPO_ROOT / "scripts"
    for s in evidence["scenarios"]:
        ref = s["evidence_ref"]
        head, _sep, _func = ref.partition("::")
        assert head.startswith("tests/") or head.startswith("scripts/"), ref
        source_file = _REPO_ROOT / head
        assert source_file.exists(), source_file
        assert tests_root in source_file.parents or scripts_root in source_file.parents


def test_ri74_packaging_smoke_script_exposes_ri7_helper() -> None:
    """The extended `scripts/packaging_smoke.py` must define the helper
    function cited by every RI-7.4 evidence_ref so the binding is real.
    """
    smoke_path = _REPO_ROOT / "scripts" / "packaging_smoke.py"
    assert smoke_path.exists(), smoke_path
    text = smoke_path.read_text(encoding="utf-8")
    assert "def _smoke_repo_intelligence_cli" in text
    # The script must write an evidence artifact that this slice's schema
    # describes so the runtime output is auditable.
    assert "ri7-packaging-smoke-evidence.v1.json" in text
    assert "ri7_scan_index_query_packaging_smoke_evidence" in text
