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
    module_path = _repo_root() / "scripts" / "gpp6_read_only_e2e_preflight.py"
    spec = importlib.util.spec_from_file_location("gpp6_read_only_e2e_preflight", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict[str, Any]:
    return load_default("schemas", "gpp6-read-only-e2e-preflight.schema.v1.json")


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    errors = Draft202012Validator(_schema()).iter_errors(payload)
    return sorted(error.message for error in errors)


def _status_payload() -> dict[str, Any]:
    return json.loads((_repo_root() / ".claude" / "plans" / "gpp_status.v1.json").read_text(encoding="utf-8"))


def _write_minimal_preflight_repo(tmp_path: Path, status_payload: dict[str, Any]) -> Path:
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
    return tmp_path


def test_gpp6_preflight_is_schema_valid_and_execution_blocked() -> None:
    module = _module()

    report = module.build_gpp6_read_only_e2e_preflight(repo_root=_repo_root())

    assert _schema_errors(report) == []
    module.validate_report(report)
    assert report["overall_status"] == "ready"
    assert report["decision"] == "read_only_e2e_preflight_ready_execution_blocked_no_support_widening"
    assert report["execution_status"] == "blocked_by_upstream_gates"
    assert report["upstream_blockers"] == [
        "gpp2_protected_gate_blocked",
        "gpp4_real_adapter_read_only_decision_missing",
    ]
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False
    assert report["live_adapter_execution_allowed"] is False
    assert report["protected_workflow_dispatch_allowed"] is False
    assert report["remote_write_allowed"] is False
    assert report["gpp5d_closeout"]["status"] == "ready"
    assert all(step["status"] == "not_executed" for step in report["execution_plan"])
    assert all(step["protected_workflow_dispatch"] is False for step in report["execution_plan"])
    assert all(step["live_adapter_execution"] is False for step in report["execution_plan"])
    assert all(step["remote_side_effects"] is False for step in report["execution_plan"])
    assert report["program_flags"]["status"] == "pass"
    assert report["safety"]["status"] == "pass"


def test_gpp6_preflight_schema_rejects_support_or_runtime_claims() -> None:
    module = _module()
    validator = Draft202012Validator(_schema())
    report = module.build_gpp6_read_only_e2e_preflight(repo_root=_repo_root())

    support_claim = copy.deepcopy(report)
    support_claim["support_widening"] = True
    with pytest.raises(ValidationError):
        validator.validate(support_claim)

    dispatch_claim = copy.deepcopy(report)
    dispatch_claim["protected_workflow_dispatch_allowed"] = True
    with pytest.raises(ValidationError):
        validator.validate(dispatch_claim)

    live_claim = copy.deepcopy(report)
    live_claim["safety"] = dict(live_claim["safety"])
    live_claim["safety"]["live_adapter_execution"] = True
    with pytest.raises(ValidationError):
        validator.validate(live_claim)


def test_gpp6_preflight_blocks_missing_gpp5d_closeout(tmp_path: Path) -> None:
    module = _module()
    status_payload = _status_payload()
    status_payload["completed_wps"] = [
        item for item in status_payload["completed_wps"] if item.get("id") != "GPP-5d"
    ]
    repo_root = _write_minimal_preflight_repo(tmp_path, status_payload)

    report = module.build_gpp6_read_only_e2e_preflight(repo_root=repo_root)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["decision"] == "blocked_read_only_e2e_preflight_no_support_widening"
    assert report["gpp5d_closeout"]["status"] == "blocked"
    assert "completed_wp_missing" in report["gpp5d_closeout"]["findings"]
    assert "record_file_missing" in report["gpp5d_closeout"]["findings"]
    assert "gpp5d_closeout" in report["blocked_reason"]


def test_gpp6_preflight_blocks_program_flag_widening(tmp_path: Path) -> None:
    module = _module()
    status_payload = _status_payload()
    status_payload["support_widening_allowed"] = True
    repo_root = _write_minimal_preflight_repo(tmp_path, status_payload)

    report = module.build_gpp6_read_only_e2e_preflight(repo_root=repo_root)

    assert _schema_errors(report) == []
    assert report["overall_status"] == "blocked"
    assert report["program_flags"]["status"] == "fail"
    assert "support_widening_allowed_not_false" in report["program_flags"]["findings"]
