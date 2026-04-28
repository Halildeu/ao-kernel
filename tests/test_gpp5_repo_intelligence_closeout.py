from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.config import load_default


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "gpp5_repo_intelligence_closeout.py"
    spec = importlib.util.spec_from_file_location("gpp5_repo_intelligence_closeout", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict[str, Any]:
    return load_default("schemas", "gpp5-repo-intelligence-closeout.schema.v1.json")


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    errors = Draft202012Validator(_schema()).iter_errors(payload)
    return sorted(error.message for error in errors)


def _status_payload() -> dict[str, Any]:
    return json.loads((_repo_root() / ".claude" / "plans" / "gpp_status.v1.json").read_text(encoding="utf-8"))


def _write_minimal_closeout_repo(tmp_path: Path, status_payload: dict[str, Any]) -> Path:
    plans = tmp_path / ".claude" / "plans"
    plans.mkdir(parents=True)
    (plans / "gpp_status.v1.json").write_text(
        json.dumps(status_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for item in status_payload.get("completed_wps", []):
        record = item.get("record")
        if isinstance(record, str):
            record_path = tmp_path / record
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(f"# {item['id']}\n", encoding="utf-8")
    workflows = tmp_path / "ao_kernel" / "defaults" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "minimal.v1.json").write_text('{"workflow_id":"minimal"}\n', encoding="utf-8")
    return tmp_path


def test_closeout_report_is_schema_valid_and_keeps_gpp6_blocked() -> None:
    module = _module()

    report = module.build_gpp5_repo_intelligence_closeout(repo_root=_repo_root())

    assert _schema_errors(report) == []
    module.validate_report(report)
    assert report["overall_status"] == "closed"
    assert report["decision"] == "repo_intelligence_read_only_workflow_surface_closed_no_support_widening"
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["live_adapter_execution_allowed"] is False
    assert {item["id"] for item in report["work_packages"]} == {"GPP-5a", "GPP-5b", "GPP-5c"}
    assert all(item["status"] == "ready" and item["findings"] == [] for item in report["work_packages"])
    assert {item["surface"] for item in report["contract_surfaces"]} == {
        "product_onboarding",
        "explicit_workflow_context",
        "read_only_workflow_surface",
    }
    assert all(item["status"] == "ready" and item["findings"] == [] for item in report["contract_surfaces"])
    assert all(item["status"] == "pass" and item["findings"] == [] for item in report["negative_runtime_guards"])
    assert report["program_flags"] == {
        "status": "pass",
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
        "findings": [],
    }
    assert report["gpp6_readiness"]["status"] == "blocked_by_upstream_gates"
    assert report["gpp6_readiness"]["blockers"] == [
        "gpp2_protected_gate_blocked",
        "gpp4_real_adapter_read_only_decision_missing",
    ]


def test_closeout_schema_rejects_support_or_runtime_widening() -> None:
    module = _module()
    validator = Draft202012Validator(_schema())
    report = module.build_gpp5_repo_intelligence_closeout(repo_root=_repo_root())

    support_claim = copy.deepcopy(report)
    support_claim["support_widening"] = True
    with pytest.raises(ValidationError):
        validator.validate(support_claim)

    runtime_claim = copy.deepcopy(report)
    runtime_claim["live_adapter_execution_allowed"] = True
    with pytest.raises(ValidationError):
        validator.validate(runtime_claim)


def test_closeout_blocks_missing_required_work_package(tmp_path: Path) -> None:
    module = _module()
    status_payload = _status_payload()
    status_payload["completed_wps"] = [
        item for item in status_payload["completed_wps"] if item.get("id") != "GPP-5c"
    ]
    repo_root = _write_minimal_closeout_repo(tmp_path, status_payload)

    report = module.build_gpp5_repo_intelligence_closeout(repo_root=repo_root)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["decision"] == "blocked_repo_intelligence_closeout_no_support_widening"
    gpp5c = next(item for item in report["work_packages"] if item["id"] == "GPP-5c")
    assert gpp5c["status"] == "blocked"
    assert "completed_wp_missing" in gpp5c["findings"]
    assert "record_file_missing" in gpp5c["findings"]
    assert "GPP-5c" in report["blocked_reason"]


def test_closeout_blocks_hidden_workflow_auto_feed_token(tmp_path: Path) -> None:
    module = _module()
    repo_root = _write_minimal_closeout_repo(tmp_path, _status_payload())
    workflow_path = repo_root / "ao_kernel" / "defaults" / "workflows" / "hidden-feed.v1.json"
    workflow_path.write_text(
        json.dumps({"workflow_id": "hidden", "repo_intelligence_context": {"enabled": True}}),
        encoding="utf-8",
    )

    report = module.build_gpp5_repo_intelligence_closeout(repo_root=repo_root)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    workflow_guard = next(
        item
        for item in report["negative_runtime_guards"]
        if item["guard"] == "workflow_definitions_no_repo_intelligence_auto_feed"
    )
    assert workflow_guard["status"] == "fail"
    assert "hidden-feed.v1.json:repo_intelligence_context" in workflow_guard["findings"]
