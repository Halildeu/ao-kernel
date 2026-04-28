from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "internal_gate_host_bootstrap_attest.py"
    spec = importlib.util.spec_from_file_location("internal_gate_host_bootstrap_attest", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle_dir() -> Path:
    return _repo_root() / "deploy" / "internal-gate-host"


def test_internal_gate_host_bundle_attests_metadata_ready_without_side_effects() -> None:
    mod = _module()

    payload = mod.build_attestation(_bundle_dir())

    assert payload["status"] == "metadata_ready"
    assert payload["operator_owned_platform_infrastructure"] is True
    assert payload["end_user_self_host_required"] is False
    assert payload["uses_repo_owned_container_packages"] is True
    assert payload["uses_internal_vault_secret_ids"] is True
    assert payload["secret_value_readback"] is False
    assert payload["github_callback_post"] is False
    assert payload["github_check_run_post"] is False
    assert payload["protected_workflow_dispatch"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["findings"] == []


def test_internal_gate_host_bundle_uses_secret_ids_without_direct_secret_envs() -> None:
    compose = (_bundle_dir() / "compose.yaml").read_text(encoding="utf-8")
    env_example = (_bundle_dir() / ".env.example").read_text(encoding="utf-8")
    caddyfile = (_bundle_dir() / "Caddyfile.example").read_text(encoding="utf-8")

    assert "ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service" in compose
    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service" in compose
    assert "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID" in compose
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET_ID" in compose
    assert "AO_GITHUB_APP_PRIVATE_KEY_PEM_ID" in compose
    assert "AO_RELEASE_GATE_GPP_STATUS_PATH" in compose
    assert "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET:" not in compose
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET:" not in compose
    assert "AO_GITHUB_APP_PRIVATE_KEY_PEM:" not in compose
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in compose
    assert "BEGIN PRIVATE KEY" not in env_example
    assert "/github/deployment-protection" in caddyfile
    assert "/github/ao-release-gate" in caddyfile


def test_internal_gate_host_attestation_blocks_missing_bundle_file(tmp_path: Path) -> None:
    mod = _module()
    copied = tmp_path / "internal-gate-host"
    shutil.copytree(_bundle_dir(), copied)
    (copied / "compose.yaml").unlink()

    payload = mod.build_attestation(copied)

    assert payload["status"] == "blocked"
    assert any(
        finding["code"] == "internal_gate_host_required_file_missing" and finding["detail"] == "Missing compose.yaml."
        for finding in payload["findings"]
    )


def test_internal_gate_host_attestation_blocks_direct_secret_markers(tmp_path: Path) -> None:
    mod = _module()
    copied = tmp_path / "internal-gate-host"
    shutil.copytree(_bundle_dir(), copied)
    compose = copied / "compose.yaml"
    compose.write_text(
        compose.read_text(encoding="utf-8") + "\n      AO_RELEASE_GATE_WEBHOOK_SECRET: ${BAD}\n",
        encoding="utf-8",
    )

    payload = mod.build_attestation(copied)

    assert payload["status"] == "blocked"
    assert any(
        finding["code"] == "internal_gate_host_forbidden_secret_marker"
        and "AO_RELEASE_GATE_WEBHOOK_SECRET:" in finding["detail"]
        for finding in payload["findings"]
    )


def test_internal_gate_host_attestation_cli_writes_json_artifact(tmp_path: Path, capsys: Any) -> None:
    mod = _module()
    artifact = tmp_path / "attestation.json"

    result = mod.main(["--artifact-path", str(artifact), "--output", "text", "--fail-on-blocked"])

    captured = capsys.readouterr()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["status"] == "metadata_ready"
    assert "status: metadata_ready" in captured.out
