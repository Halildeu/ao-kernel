from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "policy_service_cloud_run_bootstrap_attest.py"
    spec = importlib.util.spec_from_file_location("policy_service_cloud_run_bootstrap_attest", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_variables() -> list[dict[str, str]]:
    mod = _module()
    return [
        {"name": name, "updatedAt": "2026-04-28T00:00:00Z", "value": f"hidden-{name}"}
        for name in mod.REQUIRED_REPOSITORY_VARIABLES
    ]


def test_policy_cloud_run_bootstrap_attestation_records_metadata_ready_without_values() -> None:
    mod = _module()

    attestation = mod.build_policy_service_cloud_run_bootstrap_attestation(_ready_variables())
    serialized = json.dumps(attestation, sort_keys=True)

    assert attestation["artifact_kind"] == "policy_service_cloud_run_bootstrap_attestation"
    assert attestation["program_id"] == "GPP-2ab"
    assert attestation["service_id"] == "ao-kernel-live-adapter-gate-policy-service"
    assert attestation["overall_status"] == "metadata_ready"
    assert attestation["missing_repository_variables"] == []
    assert all(item["present"] for item in attestation["required_repository_variables"])
    assert attestation["github_repository_variable_metadata_checked"] is True
    assert attestation["cloud_oidc_bootstrap_attested"] is False
    assert attestation["cloud_run_deploy_executed"] is False
    assert attestation["secret_value_readback"] is False
    assert attestation["github_callback_post"] is False
    assert attestation["live_adapter_execution"] is False
    assert attestation["support_widening"] is False
    assert attestation["production_platform_claim"] is False
    assert "hidden-" not in serialized


def test_policy_cloud_run_bootstrap_attestation_blocks_missing_required_variables() -> None:
    mod = _module()
    payload = [item for item in _ready_variables() if item["name"] != "GCP_SERVICE_ACCOUNT"]

    attestation = mod.build_policy_service_cloud_run_bootstrap_attestation(payload)

    assert attestation["overall_status"] == "blocked"
    assert attestation["finding_code"] == "policy_cloud_run_bootstrap_missing_repository_variables"
    assert attestation["missing_repository_variables"] == ["GCP_SERVICE_ACCOUNT"]
    account = next(
        item for item in attestation["required_repository_variables"] if item["name"] == "GCP_SERVICE_ACCOUNT"
    )
    assert account == {"name": "GCP_SERVICE_ACCOUNT", "present": False, "updated_at": None}


def test_policy_cloud_run_bootstrap_attestation_cli_uses_fixture_without_secret_readback(
    tmp_path: Path,
    capsys: Any,
) -> None:
    mod = _module()
    fixture_path = tmp_path / "variables.json"
    artifact_path = tmp_path / "attestation.json"
    fixture_path.write_text(json.dumps(_ready_variables()), encoding="utf-8")

    exit_code = mod.main(
        [
            "--variables-json",
            str(fixture_path),
            "--artifact-path",
            str(artifact_path),
            "--output",
            "text",
            "--fail-on-blocked",
        ]
    )

    captured = capsys.readouterr()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "overall_status: metadata_ready" in captured.out
    assert "secret_value_readback: false" in captured.out
    assert artifact["overall_status"] == "metadata_ready"
    assert artifact["secret_value_readback"] is False
    assert "hidden-" not in artifact_path.read_text(encoding="utf-8")


def test_policy_cloud_run_bootstrap_attestation_cli_can_fail_on_blocked(tmp_path: Path) -> None:
    mod = _module()
    fixture_path = tmp_path / "variables.json"
    artifact_path = tmp_path / "attestation.json"
    fixture_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = mod.main(
        [
            "--variables-json",
            str(fixture_path),
            "--artifact-path",
            str(artifact_path),
            "--fail-on-blocked",
        ]
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert artifact["overall_status"] == "blocked"
    assert artifact["secret_value_readback"] is False
    assert len(artifact["missing_repository_variables"]) == len(mod.REQUIRED_REPOSITORY_VARIABLES)


def test_policy_cloud_run_bootstrap_live_collection_does_not_request_values() -> None:
    source = (_repo_root() / "scripts" / "policy_service_cloud_run_bootstrap_attest.py").read_text(encoding="utf-8")

    assert '--json", "name,updatedAt"' in source
    assert "gcloud secrets versions access" not in source
    assert "secrets." not in source
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in source
