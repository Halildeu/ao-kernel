from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _container_smoke_module() -> Any:
    module_path = _repo_root() / "scripts" / "ao_release_gate_container_smoke.py"
    spec = importlib.util.spec_from_file_location("ao_release_gate_container_smoke", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ao_release_gate_dockerfile_hosts_wsgi_runtime_without_live_secret() -> None:
    dockerfile = _repo_root() / "deploy" / "ao-release-gate-service" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")

    assert "python:3.13-slim" in text
    assert ".[release-gate-service]" in text
    assert "gunicorn" in text
    assert "ao_kernel.ao_release_gate_runtime:application" in text
    assert "/healthz" in text
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in text
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET" not in text
    assert "AO_GITHUB_APP_PRIVATE_KEY" not in text


def test_release_gate_container_smoke_defaults_to_no_secret_health_check_only() -> None:
    module = _container_smoke_module()
    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.image == "ao-kernel-ao-release-gate-service:smoke"
    assert args.dockerfile == Path("deploy/ao-release-gate-service/Dockerfile")
    assert args.build_timeout_seconds == 300.0
    assert args.run_timeout_seconds == 30.0
    assert module._health_url(18080) == "http://127.0.0.1:18080/healthz"
    smoke_source = Path(module.__file__).read_text(encoding="utf-8")
    assert "timeout_seconds=args.build_timeout_seconds" in smoke_source
    assert '"secret_value_readback": False' in smoke_source
    assert '"live_adapter_execution": False' in smoke_source
    assert '"github_check_run_post": False' in smoke_source
    assert '"merge_authority_enabled": False' in smoke_source
    assert '"branch_protection_cutover": False' in smoke_source


def test_test_workflow_runs_release_gate_container_smoke_without_secret_context() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "release-gate-container-smoke:" in workflow
    assert "scripts/ao_release_gate_container_smoke.py" in workflow
    assert "ao-kernel-ao-release-gate-service:ci" in workflow
    release_gate_job = workflow.split("release-gate-container-smoke:", 1)[1].split("\n  typecheck:", 1)[0]
    assert "secrets." not in release_gate_job
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in release_gate_job
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET" not in release_gate_job
