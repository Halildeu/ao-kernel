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
    module_path = _repo_root() / "scripts" / "gp5_platform_claim_decision.py"
    spec = importlib.util.spec_from_file_location("gp5_platform_claim_decision", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    schema = load_default("schemas", "gp5-production-platform-claim-decision.schema.v1.json")
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(payload))


def test_gp59_platform_claim_decision_keeps_narrow_runtime() -> None:
    mod = _module()

    report = mod.build_platform_claim_decision(repo_root=_repo_root())

    assert _schema_errors(report) == []
    assert report["overall_status"] == "closed"
    assert report["decision"] == "keep_narrow_stable_runtime"
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["stable_runtime_boundary"] == "narrow_production_runtime"
    assert report["promoted_tiers"] == []
    assert report["gp58_operations_package"]["status"] == "ready"
    assert report["support_boundary"]["general_purpose_claim_granted"] is False
    assert "protected_live_adapter_gate_unattested" in report["promotion_blockers"]
    assert "real_adapter_usage_and_cost_evidence_missing" in report["promotion_blockers"]
    assert {item["id"] for item in report["success_criteria"]} == {
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


def test_gp59_schema_rejects_narrow_decision_with_widening() -> None:
    mod = _module()
    report = mod.build_platform_claim_decision(repo_root=_repo_root())
    report["support_widening"] = True
    report["production_platform_claim"] = True
    report["promoted_tiers"] = ["claude-code-cli"]

    errors = _schema_errors(report)

    assert "False was expected" in errors
    assert any("is expected to be empty" in error for error in errors)


def test_gp59_schema_rejects_general_promotion_with_blockers() -> None:
    mod = _module()
    report = mod.build_platform_claim_decision(repo_root=_repo_root())
    report["decision"] = "promote_general_purpose_platform"
    report["support_widening"] = True
    report["production_platform_claim"] = True
    report["stable_runtime_boundary"] = "general_purpose_platform"
    report["promoted_tiers"] = ["general-purpose-platform"]

    errors = _schema_errors(report)

    assert any("is expected to be empty" in error for error in errors)


def test_gp59_detects_missing_evidence_token(tmp_path: Path) -> None:
    mod = _module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SUPPORT-BOUNDARY.md").write_text("missing token", encoding="utf-8")

    item = mod._coverage_item(  # noqa: SLF001
        tmp_path,
        "support_boundary",
        "docs/SUPPORT-BOUNDARY.md",
        ("GP-5.9",),
    )

    assert item["status"] == "blocked"
    assert item["findings"] == ["missing_token:GP-5.9"]


def test_gp59_cli_writes_closed_report(tmp_path: Path) -> None:
    mod = _module()
    report_path = tmp_path / "gp59-report.json"

    result = mod.main(["--output", "json", "--report-path", str(report_path)])

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _schema_errors(report) == []
    assert report["overall_status"] == "closed"


def test_gp59_docs_record_non_promotion_boundary() -> None:
    repo_root = _repo_root()
    program = (
        repo_root / ".claude" / "plans" / "GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md"
    ).read_text(encoding="utf-8")
    status = (
        repo_root / ".claude" / "plans" / "POST-BETA-CORRECTNESS-EXPANSION-STATUS.md"
    ).read_text(encoding="utf-8")
    plan = (
        repo_root / ".claude" / "plans" / "GP-5.9-PRODUCTION-PLATFORM-CLAIM-DECISION.md"
    ).read_text(encoding="utf-8")
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(encoding="utf-8")
    known_bugs = (repo_root / "docs" / "KNOWN-BUGS.md").read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")

    assert "GP-5.9" in program
    assert "GP-5.9 production platform claim decision" in status
    assert "keep_narrow_stable_runtime" in plan
    assert "GP-5 production platform claim decision" in public_beta
    assert "production_platform_claim=false" in support_boundary
    assert "GP-5.9 closeout interpretation" in known_bugs
    assert "GP-5.9 production claim decision incidents" in runbook
