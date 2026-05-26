from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module():
    module_path = _repo_root() / "scripts" / "repo_intelligence_tier_promotion_readiness.py"
    spec = importlib.util.spec_from_file_location("repo_intelligence_tier_promotion_readiness", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    schema = load_default("schemas", "repo-intelligence-tier-promotion-readiness.schema.v1.json")
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(payload))


def test_repo_intelligence_promotion_readiness_blocks_without_evidence() -> None:
    mod = _module()

    report = mod.build_readiness(repo_root=_repo_root())

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["decision"] == "blocked_operator_bound_evidence_required"
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["live_adapter_execution"] is False
    assert report["requested_promotion"]["surface"] == "repo_intelligence_scan_index_query"
    assert report["requested_promotion"]["target_claim"] == "general_purpose_production_platform_claim"
    assert report["current_authority"]["current_wp"] == "GPP-9"
    assert report["current_authority"]["current_status"] == "closed"
    assert report["current_authority"]["support_widening_allowed"] is False
    assert "operator_authorization_record_missing" in report["promotion_blockers"]
    assert "general_purpose_platform_claim_authorization_missing" in report["promotion_blockers"]
    assert "guardrail_hardening_matrix_missing" in report["promotion_blockers"]
    assert "vector_backend_e2e_evidence_missing" in report["promotion_blockers"]
    assert "cross_lane_production_matrix_evidence_missing" in report["promotion_blockers"]
    assert "gp59_reclassification_plan_missing" in report["promotion_blockers"]


def test_repo_intelligence_promotion_readiness_schema_rejects_widening() -> None:
    mod = _module()
    report = mod.build_readiness(repo_root=_repo_root())
    report["support_widening"] = True
    report["production_platform_claim"] = True
    report["live_adapter_execution"] = True

    errors = _schema_errors(report)

    assert errors.count("False was expected") == 3


def test_repo_intelligence_promotion_readiness_manifest_can_reach_decision_ready(tmp_path: Path) -> None:
    mod = _module()
    evidence_manifest = {
        "explicit_operator_authorization": True,
        "general_purpose_platform_claim_authorization": True,
        "guardrail_hardening_matrix": True,
        "vector_backend_e2e_evidence": True,
        "scan_index_query_packaging_smoke": True,
        "operator_verified_runtime_semantics": True,
        "cross_lane_production_matrix_evidence": True,
        "gp59_reclassification_plan": True,
        "support_boundary_transition_plan": True,
    }
    manifest_path = tmp_path / "evidence-manifest.json"
    manifest_path.write_text(json.dumps(evidence_manifest), encoding="utf-8")

    report = mod.build_readiness(repo_root=_repo_root(), evidence_manifest_path=manifest_path)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "ready_for_operator_decision"
    assert report["decision"] == "ready_for_operator_promotion_decision"
    assert report["promotion_blockers"] == []
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["live_adapter_execution"] is False


def test_repo_intelligence_promotion_readiness_cli_writes_blocked_report(tmp_path: Path) -> None:
    mod = _module()
    report_path = tmp_path / "ri-tier-readiness.json"

    result = mod.main(["--output", "json", "--report-path", str(report_path)])

    assert result == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
