"""Doc invariant test for RI-7.3 vector backend E2E evidence.

Pins the canonical RI-7.3 plan, schema, and evidence artifact so future
drift in the hardening matrix is caught.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.3-VECTOR-BACKEND-E2E-EVIDENCE.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-vector-backend-e2e-evidence.schema.v1.json"


def _read_text(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri73_plan_doc_records_eight_scenarios_and_exit_decision() -> None:
    text = _read_text(_PLAN_PATH)
    flat = " ".join(text.split())
    # The eight scenario IDs MUST be named in the plan.
    for scenario in (
        "write_happy_path",
        "stale_cleanup",
        "namespace_isolation",
        "query_hash_line_validation",
        "missing_backend_fail_closed_write",
        "missing_backend_fail_closed_query",
        "missing_api_key_fail_closed_write",
        "missing_api_key_fail_closed_query",
    ):
        assert scenario in flat, f"plan doc must record scenario: {scenario}"
    # Exit decision and closed flags.
    assert "ri7_vector_backend_e2e_ready" in flat
    assert "support_widening: false" in flat or "support_widening=false" in flat
    assert "production_platform_claim: false" in flat or "production_platform_claim=false" in flat
    assert "live_adapter_execution: false" in flat or "live_adapter_execution=false" in flat
    # No production / promotion dilution language at the slice level.
    assert "No production platform claim" in flat
    assert "No live adapter execution" in flat


def test_ri73_evidence_artifact_validates_against_schema() -> None:
    schema = json.loads(_read_text(_SCHEMA_PATH))
    evidence = json.loads(_read_text(_EVIDENCE_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri73_evidence_artifact_records_closed_boundary_and_inmemory_backend() -> None:
    evidence = json.loads(_read_text(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_vector_backend_e2e_evidence"
    assert evidence["decision"] == "ri7_vector_backend_e2e_ready"
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False
    backend = evidence["backend"]
    assert backend["type"] == "inmemory"
    assert backend["class_name"] == "InMemoryVectorStore"
    assert backend["external_api_calls"] is False
    scenario_ids = {s["id"] for s in evidence["scenarios"]}
    assert scenario_ids == {
        "write_happy_path",
        "stale_cleanup",
        "namespace_isolation",
        "query_hash_line_validation",
        "missing_backend_fail_closed_write",
        "missing_backend_fail_closed_query",
        "missing_api_key_fail_closed_write",
        "missing_api_key_fail_closed_query",
    }
    for scenario in evidence["scenarios"]:
        assert scenario["status"] == "pass"
        assert scenario["evidence_ref"], "every scenario must cite a test ref"


def test_ri73_plan_doc_records_forbidden_change_audit() -> None:
    text = _read_text(_PLAN_PATH)
    assert "Forbidden-Change Audit" in text
    # Key untouched surfaces must be named.
    assert "gpp_status.v1.json" in text
    assert "scripts/gp5_platform_claim_decision.py" in text
    assert ".github/workflows/" in text
    assert "mcp_server" in text or "MCP" in text
    assert "vector_store.py" in text


def test_ri73_evidence_test_refs_cite_real_test_files() -> None:
    """Every evidence_ref in the artifact must point at an actually-existing
    test file in the repo. This catches stale or invented refs early.
    """
    evidence = json.loads(_read_text(_EVIDENCE_PATH))
    tests_root = _REPO_ROOT / "tests"
    for scenario in evidence["scenarios"]:
        ref = scenario["evidence_ref"]
        # Refs are of the form "tests/<file>.py::<func>".
        head, _sep, _func = ref.partition("::")
        assert head.startswith("tests/"), f"evidence ref must start with tests/: {ref}"
        test_file = _REPO_ROOT / head
        assert test_file.exists(), f"evidence ref points at missing test file: {test_file}"
        # And the file must live under tests/ (no path escape).
        assert tests_root in test_file.parents
