"""Drift guards for GPP-4a claude-code-cli failure-mode matrix.

Pins:
- Schema is a valid Draft 2020-12 schema.
- emit-simulated produces a schema-valid artifact covering all seven
  canonical failure modes.
- validate mode accepts the simulated artifact and rejects mutations
  that violate the const-false guard flags, the live/simulated
  oneOf bind, or the seven `contains` invariants.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

_CANONICAL_MODES = (
    "auth_missing",
    "binary_missing",
    "timeout",
    "prompt_denied",
    "malformed_output",
    "policy_denied",
    "redaction",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema_path() -> Path:
    return _repo_root() / "ao_kernel" / "defaults" / "schemas" / "claude-code-cli-failure-mode.schema.v1.json"


def _script_path() -> Path:
    return _repo_root() / "scripts" / "claude_code_cli_failure_mode_evidence.py"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("claude_code_cli_failure_mode_evidence", _script_path())
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict[str, Any]:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema(), format_checker=FormatChecker())


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(_schema())


def test_emit_simulated_produces_schema_valid_artifact() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    errors = sorted(_validator().iter_errors(artifact), key=lambda e: list(e.path))
    assert errors == []


def test_emit_simulated_covers_all_seven_canonical_modes() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    modes = [item["failure_mode"] for item in artifact["coverage"]]
    assert sorted(modes) == sorted(_CANONICAL_MODES)


def test_emit_simulated_is_evidence_class_simulated_and_live_false() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    assert artifact["evidence_class"] == "simulated"
    assert artifact["live_adapter_execution"] is False
    assert artifact["protected_run"]["observed"] is False


def test_emit_simulated_keeps_guard_flags_false() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    assert artifact["support_widening"] is False
    assert artifact["production_platform_claim"] is False
    assert artifact["live_adapter_execution"] is False


def test_emit_simulated_observed_at_is_iso_parseable() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    datetime.fromisoformat(artifact["observed_at"].replace("Z", "+00:00"))


def test_emit_simulated_overall_status_is_coverage_pending() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    assert artifact["overall_status"] == "coverage_ready_live_evidence_pending"


def test_validate_accepts_complete_simulated_artifact() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    mod.validate_artifact(artifact)


def test_validate_rejects_missing_mode() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"] = artifact["coverage"][:6]
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_duplicate_mode() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"] = list(artifact["coverage"][:6]) + [artifact["coverage"][0]]
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_support_widening_true() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["support_widening"] = True
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_production_platform_claim_true() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["production_platform_claim"] = True
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_simulated_with_live_adapter_execution_true() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["live_adapter_execution"] = True
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_simulated_with_protected_run_observed_true() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["protected_run"]["observed"] = True
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_evidence_class_simulated_with_live_overall_status() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["overall_status"] = "live_runs_observed"
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_invalid_failure_mode_enum() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"][0]["failure_mode"] = "invented_mode"
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_invalid_surface_enum() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"][0]["surface"] = "made_up_surface"
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_empty_stable_finding_codes() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"][0]["stable_finding_codes"] = []
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_empty_evidence_refs() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["coverage"][0]["evidence_refs"] = []
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_unknown_top_level_field() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["unknown_field"] = "x"
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_validate_rejects_wrong_adapter_id() -> None:
    mod = _module()
    artifact = mod.emit_simulated()
    artifact["adapter_id"] = "some-other-adapter"
    with pytest.raises(mod.FailureMatrixError):
        mod.validate_artifact(artifact)


def test_cli_emit_simulated_smoke(tmp_path: Path) -> None:
    output = tmp_path / "matrix.json"
    completed = subprocess.run(
        [sys.executable, str(_script_path()), "emit-simulated", "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "claude-code-cli-failure-mode.v1"


def test_cli_validate_smoke(tmp_path: Path) -> None:
    output = tmp_path / "matrix.json"
    subprocess.run(
        [sys.executable, str(_script_path()), "emit-simulated", "--output", str(output)],
        check=True,
    )
    completed = subprocess.run(
        [sys.executable, str(_script_path()), "validate", "--artifact-path", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "OK"


def test_cli_validate_rejects_corrupt_artifact(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "wrong"}), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(_script_path()), "validate", "--artifact-path", str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "FAIL" in completed.stderr
