from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.live_adapter_gate import (
    BLOCKED_FINDING,
    EVIDENCE_ARTIFACT,
    ENVIRONMENT_CONTRACT_ARTIFACT,
    REHEARSAL_DECISION_ARTIFACT,
    build_live_adapter_gate_evidence_artifact,
    build_live_adapter_gate_environment_contract,
    build_live_adapter_gate_rehearsal_decision,
    build_live_adapter_gate_report,
    live_adapter_gate_report_sha256,
    load_live_adapter_gate_evidence_schema,
    load_live_adapter_gate_environment_schema,
    load_live_adapter_gate_rehearsal_decision_schema,
    render_live_adapter_gate_text,
    validate_live_adapter_gate_evidence_artifact,
    validate_live_adapter_gate_environment_contract,
    validate_live_adapter_gate_rehearsal_decision,
    write_live_adapter_gate_evidence_artifact,
    write_live_adapter_gate_environment_contract,
    write_live_adapter_gate_rehearsal_decision,
    write_live_adapter_gate_report,
)


def test_build_live_adapter_gate_report_is_explicitly_blocked() -> None:
    report = build_live_adapter_gate_report(
        target_ref="main",
        reason="release rehearsal",
        requested_by="maintainer",
        event_name="workflow_dispatch",
        head_sha="abc123",
        generated_at="2026-04-24T00:00:00Z",
    )

    assert report["schema_version"] == "1"
    assert report["program_id"] == "GP-4.1"
    assert report["adapter_id"] == "claude-code-cli"
    assert report["support_tier"] == "Beta (operator-managed)"
    assert report["overall_status"] == "blocked"
    assert report["finding_code"] == BLOCKED_FINDING
    assert report["live_execution_attempted"] is False
    assert report["support_widening"] is False
    assert report["trigger"] == {
        "event_name": "workflow_dispatch",
        "target_ref": "main",
        "head_sha": "abc123",
        "requested_by": "maintainer",
        "reason": "release rehearsal",
    }

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["live_execution"]["status"] == "blocked"
    assert checks["live_execution"]["finding_code"] == BLOCKED_FINDING
    assert checks["secret_access"]["status"] == "skipped"
    assert checks["support_boundary"]["status"] == "pass"


def test_write_live_adapter_gate_report_round_trips_json(tmp_path: Path) -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    path = tmp_path / "live-adapter-gate-contract.v1.json"

    write_live_adapter_gate_report(path, report)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == report
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_live_adapter_gate_evidence_schema_is_valid() -> None:
    schema = load_live_adapter_gate_evidence_schema()

    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:live-adapter-gate-evidence:v1"


def test_live_adapter_gate_environment_schema_is_valid() -> None:
    schema = load_live_adapter_gate_environment_schema()

    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:live-adapter-gate-environment:v1"


def test_live_adapter_gate_rehearsal_decision_schema_is_valid() -> None:
    schema = load_live_adapter_gate_rehearsal_decision_schema()

    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:live-adapter-gate-rehearsal-decision:v1"


def test_build_live_adapter_gate_evidence_artifact_is_schema_valid_and_blocked() -> None:
    report = build_live_adapter_gate_report(
        target_ref="main",
        reason="release rehearsal",
        requested_by="maintainer",
        event_name="workflow_dispatch",
        head_sha="abc123",
        generated_at="2026-04-24T00:00:00Z",
    )

    artifact = build_live_adapter_gate_evidence_artifact(report, contract_report_path="contract.json")

    validate_live_adapter_gate_evidence_artifact(artifact)
    assert artifact["schema_version"] == "1"
    assert artifact["artifact_kind"] == "live_adapter_gate_evidence"
    assert artifact["program_id"] == "GP-4.2"
    assert artifact["overall_status"] == "blocked"
    assert artifact["live_execution_attempted"] is False
    assert artifact["support_widening"] is False
    assert artifact["source_report"] == {
        "path": "contract.json",
        "schema_version": "1",
        "sha256": live_adapter_gate_report_sha256(report),
    }
    assert artifact["promotion_decision"]["support_widening_allowed"] is False
    assert artifact["promotion_decision"]["production_certified"] is False

    requirements = {item["requirement_id"]: item for item in artifact["evidence_requirements"]}
    assert requirements["gate_contract_report"]["status"] == "present"
    assert requirements["gate_contract_report"]["finding_code"] is None
    assert requirements["preflight_report"]["status"] == "blocked"
    assert requirements["preflight_report"]["finding_code"] == "live_gate_preflight_not_collected"
    assert requirements["governed_workflow_smoke_report"]["status"] == "blocked"
    assert requirements["protected_environment_attestation"]["status"] == "blocked"


def test_build_live_adapter_gate_environment_contract_is_schema_valid_and_blocked() -> None:
    contract = build_live_adapter_gate_environment_contract(
        generated_at="2026-04-24T00:00:00Z",
    )

    validate_live_adapter_gate_environment_contract(contract)
    assert contract["schema_version"] == "1"
    assert contract["artifact_kind"] == "live_adapter_gate_environment_contract"
    assert contract["program_id"] == "GP-4.3"
    assert contract["overall_status"] == "blocked"
    assert contract["finding_code"] == "live_gate_protected_environment_not_attested"
    assert contract["live_execution_allowed"] is False
    assert contract["support_widening"] is False
    assert contract["protected_environment"] == {
        "name": "ao-kernel-live-adapter-gate",
        "required": True,
        "required_reviewers": True,
        "prevent_self_review": True,
        "allowed_refs": ["main"],
        "detail": (
            "Future live execution must run through this protected GitHub "
            "environment or an explicitly approved release-gate equivalent."
        ),
    }
    assert contract["trigger_policy"]["forks_allowed"] is False
    assert contract["trigger_policy"]["pull_request_secrets_allowed"] is False
    assert "pull_request" in contract["trigger_policy"]["forbidden_events"]
    assert contract["required_secrets"] == [
        {
            "secret_id": "AO_CLAUDE_CODE_CLI_AUTH",
            "required": True,
            "exposure": "github_environment_secret",
            "secret_value_committed": False,
            "purpose": (
                "Project-owned Claude Code CLI auth material or equivalent "
                "non-API-key credential required for protected live rehearsal."
            ),
        }
    ]


def test_build_live_adapter_gate_rehearsal_decision_is_schema_valid_and_blocked() -> None:
    decision = build_live_adapter_gate_rehearsal_decision(
        generated_at="2026-04-24T00:00:00Z",
    )

    validate_live_adapter_gate_rehearsal_decision(decision)
    assert decision["schema_version"] == "1"
    assert decision["artifact_kind"] == "live_adapter_gate_rehearsal_decision"
    assert decision["program_id"] == "GP-4.4"
    assert decision["overall_status"] == "blocked"
    assert decision["decision"] == "blocked_no_rehearsal"
    assert decision["finding_code"] == "live_gate_rehearsal_blocked_missing_protected_prerequisites"
    assert decision["live_rehearsal_attempted"] is False
    assert decision["live_execution_allowed"] is False
    assert decision["support_widening"] is False
    assert decision["promotion_decision"] == {
        "support_widening_allowed": False,
        "production_certified": False,
        "next_gate": "GP-4.5",
        "reason": (
            "GP-4.4 records an explicit blocked decision because protected "
            "live rehearsal prerequisites are not attested."
        ),
    }

    prerequisites = {item["prerequisite_id"]: item for item in decision["prerequisite_status"]}
    assert prerequisites["protected_environment_attestation"]["status"] == "not_attested"
    assert prerequisites["project_owned_credential"]["status"] == "not_attested"
    assert prerequisites["protected_live_preflight"]["status"] == "blocked"
    assert prerequisites["governed_workflow_smoke"]["status"] == "blocked"


def test_live_adapter_gate_evidence_schema_rejects_support_widening() -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    artifact = build_live_adapter_gate_evidence_artifact(report)
    artifact["support_widening"] = True

    with pytest.raises(ValidationError):
        validate_live_adapter_gate_evidence_artifact(artifact)


def test_live_adapter_gate_environment_schema_rejects_fake_live_execution() -> None:
    contract = build_live_adapter_gate_environment_contract(
        generated_at="2026-04-24T00:00:00Z",
    )
    contract["live_execution_allowed"] = True

    with pytest.raises(ValidationError):
        validate_live_adapter_gate_environment_contract(contract)


def test_live_adapter_gate_rehearsal_decision_schema_rejects_fake_live_execution() -> None:
    decision = build_live_adapter_gate_rehearsal_decision(
        generated_at="2026-04-24T00:00:00Z",
    )
    decision["live_rehearsal_attempted"] = True

    with pytest.raises(ValidationError):
        validate_live_adapter_gate_rehearsal_decision(decision)


def test_write_live_adapter_gate_evidence_artifact_round_trips_json(tmp_path: Path) -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    artifact = build_live_adapter_gate_evidence_artifact(report)
    path = tmp_path / EVIDENCE_ARTIFACT

    write_live_adapter_gate_evidence_artifact(path, artifact)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == artifact
    validate_live_adapter_gate_evidence_artifact(payload)
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_live_adapter_gate_environment_contract_round_trips_json(tmp_path: Path) -> None:
    contract = build_live_adapter_gate_environment_contract(
        generated_at="2026-04-24T00:00:00Z",
    )
    path = tmp_path / ENVIRONMENT_CONTRACT_ARTIFACT

    write_live_adapter_gate_environment_contract(path, contract)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == contract
    validate_live_adapter_gate_environment_contract(payload)
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_live_adapter_gate_rehearsal_decision_round_trips_json(tmp_path: Path) -> None:
    decision = build_live_adapter_gate_rehearsal_decision(
        generated_at="2026-04-24T00:00:00Z",
    )
    path = tmp_path / REHEARSAL_DECISION_ARTIFACT

    write_live_adapter_gate_rehearsal_decision(path, decision)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == decision
    validate_live_adapter_gate_rehearsal_decision(payload)
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_render_live_adapter_gate_text_marks_no_live_execution() -> None:
    report = build_live_adapter_gate_report(generated_at="2026-04-24T00:00:00Z")
    rendered = render_live_adapter_gate_text(report)

    assert "overall_status: blocked" in rendered
    assert "live_execution_attempted: false" in rendered
    assert "support_widening: false" in rendered
    assert f"live_execution: blocked ({BLOCKED_FINDING})" in rendered


def test_script_emits_json_and_report_file(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "contract.json"
    evidence_path = tmp_path / "evidence.json"
    environment_contract_path = tmp_path / "environment.json"
    rehearsal_decision_path = tmp_path / "rehearsal-decision.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/live_adapter_gate_contract.py",
            "--output",
            "json",
            "--report-path",
            str(report_path),
            "--evidence-path",
            str(evidence_path),
            "--environment-contract-path",
            str(environment_contract_path),
            "--rehearsal-decision-path",
            str(rehearsal_decision_path),
            "--target-ref",
            "main",
            "--reason",
            "test",
            "--requested-by",
            "pytest",
            "--event-name",
            "workflow_dispatch",
            "--head-sha",
            "abc123",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    environment_payload = json.loads(environment_contract_path.read_text(encoding="utf-8"))
    rehearsal_decision_payload = json.loads(rehearsal_decision_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert stdout_payload["overall_status"] == "blocked"
    assert stdout_payload["live_execution_attempted"] is False
    validate_live_adapter_gate_evidence_artifact(evidence_payload)
    validate_live_adapter_gate_environment_contract(environment_payload)
    validate_live_adapter_gate_rehearsal_decision(rehearsal_decision_payload)
    assert evidence_payload["source_report"]["path"] == report_path.name
    assert evidence_payload["support_widening"] is False
    assert environment_payload["support_widening"] is False
    assert environment_payload["live_execution_allowed"] is False
    assert rehearsal_decision_payload["support_widening"] is False
    assert rehearsal_decision_payload["live_rehearsal_attempted"] is False


def test_live_adapter_gate_workflow_is_manual_contract_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow = (repo_root / ".github/workflows/live-adapter-gate.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow
    assert "\n  pull_request:" not in workflow
    assert "live_adapter_gate_contract.py" in workflow
    assert "live-adapter-gate-contract.v1.json" in workflow
    assert "live-adapter-gate-evidence.v1.json" in workflow
    assert "live-adapter-gate-environment-contract.v1.json" in workflow
    assert "live-adapter-gate-rehearsal-decision.v1.json" in workflow
    assert "claude_code_cli_smoke.py" not in workflow
    assert "claude_code_cli_workflow_smoke.py" not in workflow
    assert "secrets." not in workflow
    assert "\n    environment:" not in workflow
    assert "contents: read" in workflow
