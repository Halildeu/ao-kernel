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
    module_path = _repo_root() / "scripts" / "gp5_operations_support_package.py"
    spec = importlib.util.spec_from_file_location("gp5_operations_support_package", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    schema = load_default("schemas", "gp5-operations-support-package.schema.v1.json")
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(payload))


def test_gp58_operations_support_package_report_is_ready_and_schema_valid() -> None:
    mod = _module()

    report = mod.build_operations_support_package(repo_root=_repo_root())

    assert _schema_errors(report) == []
    assert report["overall_status"] == "ready"
    assert report["decision"] == "operations_package_ready_no_support_widening"
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["known_bugs"]["stable_shipped_baseline_blockers"] == 0
    assert report["known_bugs"]["open_beta_lane_bugs"] == ["KB-001", "KB-002"]
    assert report["support_boundary"]["stable_boundary_unchanged"] is True
    assert report["support_boundary"]["promoted_tiers"] == []
    assert report["promotion_decision"]["next_gate"] == "GP-5.9"
    assert all(item["status"] == "ready" for item in report["runbook_coverage"])


def test_gp58_schema_rejects_support_widening_and_production_claim() -> None:
    mod = _module()
    report = mod.build_operations_support_package(repo_root=_repo_root())
    report["support_widening"] = True
    report["production_platform_claim"] = True
    report["promotion_decision"]["support_widening_allowed"] = True
    report["promotion_decision"]["production_claim_allowed"] = True

    assert _schema_errors(report).count("False was expected") == 4


def test_gp58_detects_missing_required_runbook_token(tmp_path: Path) -> None:
    mod = _module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "OPERATIONS-RUNBOOK.md").write_text("missing required content", encoding="utf-8")

    item = mod._coverage_item(  # noqa: SLF001
        tmp_path,
        "adapter",
        "docs/OPERATIONS-RUNBOOK.md",
        ("GP-5.8 adapter incidents",),
    )

    assert item["status"] == "blocked"
    assert item["findings"] == ["missing_token:GP-5.8 adapter incidents"]


def test_gp58_cli_writes_ready_report(tmp_path: Path) -> None:
    mod = _module()
    report_path = tmp_path / "gp58-report.json"

    result = mod.main(["--output", "json", "--report-path", str(report_path)])

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _schema_errors(report) == []
    assert report["overall_status"] == "ready"


def test_gp58_docs_keep_no_support_widening_boundary() -> None:
    repo_root = _repo_root()
    program = (
        repo_root / ".claude" / "plans" / "GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md"
    ).read_text(encoding="utf-8")
    status = (
        repo_root / ".claude" / "plans" / "POST-BETA-CORRECTNESS-EXPANSION-STATUS.md"
    ).read_text(encoding="utf-8")
    plan = (
        repo_root / ".claude" / "plans" / "GP-5.8-OPERATIONS-SUPPORT-PACKAGE.md"
    ).read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "OPERATIONS-RUNBOOK.md").read_text(encoding="utf-8")
    public_beta = (repo_root / "docs" / "PUBLIC-BETA.md").read_text(encoding="utf-8")
    support_boundary = (repo_root / "docs" / "SUPPORT-BOUNDARY.md").read_text(encoding="utf-8")
    known_bugs = (repo_root / "docs" / "KNOWN-BUGS.md").read_text(encoding="utf-8")

    assert "GP-5.8" in program
    assert "GP-5.8 operations support package" in status
    assert "release_gate_impact=none" in plan
    assert "GP-5.8 operations support package" in runbook
    assert "GP-5 operations support package" in public_beta
    assert "gp5-operations-support-package.schema.v1.json" in support_boundary
    assert "GP-5.8 promotion interpretation" in known_bugs
