from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "internal_gate_host_health_probe.py"
    spec = importlib.util.spec_from_file_location("internal_gate_host_health_probe", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_response(program_id: str) -> bytes:
    return json.dumps({"status": "ok", "program_id": program_id}).encode("utf-8")


def test_build_health_urls_uses_internal_gate_public_paths() -> None:
    mod = _module()

    policy_url, release_gate_url = mod.build_health_urls("gate.example.test")

    assert policy_url == "https://gate.example.test/policy/healthz"
    assert release_gate_url == "https://gate.example.test/release-gate/healthz"


def test_health_probe_accepts_public_https_evidence_without_side_effects() -> None:
    mod = _module()

    def transport(url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        if url.endswith("/policy/healthz"):
            return 200, _json_response("GPP-2q")
        if url.endswith("/release-gate/healthz"):
            return 200, _json_response("GPP-2w")
        raise AssertionError(f"unexpected URL {url}")

    payload = mod.build_evidence(
        policy_url="https://gate.example.test/policy/healthz",
        release_gate_url="https://gate.example.test/release-gate/healthz",
        transport=transport,
    )

    assert payload["status"] == "hosted_health_ready"
    assert payload["policy_health_evidence"] is True
    assert payload["release_gate_health_evidence"] is True
    assert payload["public_https_hosting_evidence"] is True
    assert payload["secret_value_readback"] is False
    assert payload["github_webhook_configured"] is False
    assert payload["github_callback_post"] is False
    assert payload["github_check_run_post"] is False
    assert payload["branch_protection_cutover"] is False
    assert payload["protected_workflow_dispatch"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["findings"] == []


def test_health_probe_blocks_public_http_without_requesting_endpoint() -> None:
    mod = _module()

    def transport(_url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        raise AssertionError("invalid public HTTP URL should not be requested")

    payload = mod.build_evidence(
        policy_url="http://gate.example.test/policy/healthz",
        release_gate_url="http://gate.example.test/release-gate/healthz",
        transport=transport,
    )

    assert payload["status"] == "blocked"
    assert payload["policy_health_evidence"] is False
    assert payload["public_https_hosting_evidence"] is False
    assert any(
        finding["service"] == "live-adapter-gate-policy"
        and finding["code"] == "internal_gate_host_health_url_not_https"
        for finding in payload["findings"]
    )


def test_health_probe_allows_local_http_without_public_https_claim() -> None:
    mod = _module()

    def transport(url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        if url.endswith("/policy/healthz"):
            return 200, _json_response("GPP-2q")
        if url.endswith("/release-gate/healthz"):
            return 200, _json_response("GPP-2w")
        raise AssertionError(f"unexpected URL {url}")

    payload = mod.build_evidence(
        policy_url="http://127.0.0.1:8000/policy/healthz",
        release_gate_url="http://127.0.0.1:8000/release-gate/healthz",
        allow_http_localhost=True,
        transport=transport,
    )

    assert payload["status"] == "local_health_ready"
    assert payload["policy_health_evidence"] is True
    assert payload["release_gate_health_evidence"] is True
    assert payload["public_https_hosting_evidence"] is False
    assert payload["github_webhook_configured"] is False
    assert payload["github_callback_post"] is False
    assert payload["github_check_run_post"] is False


def test_health_probe_does_not_treat_loopback_https_as_public_evidence() -> None:
    mod = _module()

    def transport(url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        if url.endswith("/policy/healthz"):
            return 200, _json_response("GPP-2q")
        if url.endswith("/release-gate/healthz"):
            return 200, _json_response("GPP-2w")
        raise AssertionError(f"unexpected URL {url}")

    payload = mod.build_evidence(
        policy_url="https://localhost/policy/healthz",
        release_gate_url="https://localhost/release-gate/healthz",
        transport=transport,
    )

    assert payload["status"] == "local_health_ready"
    assert payload["policy_health_evidence"] is True
    assert payload["release_gate_health_evidence"] is True
    assert payload["public_https_hosting_evidence"] is False


def test_health_probe_blocks_wrong_program_id() -> None:
    mod = _module()

    def transport(url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        if url.endswith("/policy/healthz"):
            return 200, _json_response("wrong-program")
        if url.endswith("/release-gate/healthz"):
            return 200, _json_response("GPP-2w")
        raise AssertionError(f"unexpected URL {url}")

    payload = mod.build_evidence(
        policy_url="https://gate.example.test/policy/healthz",
        release_gate_url="https://gate.example.test/release-gate/healthz",
        transport=transport,
    )

    assert payload["status"] == "blocked"
    assert payload["policy_health_evidence"] is False
    assert payload["release_gate_health_evidence"] is True
    assert payload["public_https_hosting_evidence"] is False
    assert any(
        finding["service"] == "live-adapter-gate-policy"
        and finding["code"] == "internal_gate_host_health_program_id_mismatch"
        for finding in payload["findings"]
    )


def test_health_probe_cli_writes_json_artifact(tmp_path: Path, capsys: Any, monkeypatch: Any) -> None:
    mod = _module()
    artifact = tmp_path / "health-evidence.json"

    def transport(url: str, _timeout_seconds: float) -> tuple[int, bytes]:
        if url.endswith("/policy/healthz"):
            return 200, _json_response("GPP-2q")
        if url.endswith("/release-gate/healthz"):
            return 200, _json_response("GPP-2w")
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(mod, "urllib_health_get", transport)

    result = mod.main(
        [
            "--host",
            "gate.example.test",
            "--artifact-path",
            str(artifact),
            "--output",
            "text",
            "--fail-on-blocked",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["status"] == "hosted_health_ready"
    assert payload["public_https_hosting_evidence"] is True
    assert "public_https_hosting_evidence: true" in captured.out
