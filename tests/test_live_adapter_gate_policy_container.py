from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _container_smoke_module() -> Any:
    module_path = _repo_root() / "scripts" / "live_adapter_gate_policy_container_smoke.py"
    spec = importlib.util.spec_from_file_location("live_adapter_gate_policy_container_smoke", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_service_dockerfile_hosts_wsgi_runtime_without_live_secret() -> None:
    dockerfile = _repo_root() / "deploy" / "live-adapter-gate-policy-service" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")

    assert "python:3.13-slim" in text
    assert ".[policy-service]" in text
    assert "gunicorn" in text
    assert "ao_kernel.live_adapter_gate_policy_runtime:application" in text
    assert "/healthz" in text
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in text


def test_container_smoke_defaults_to_no_secret_health_check_only() -> None:
    module = _container_smoke_module()
    parser = module.build_parser()
    args = parser.parse_args([])

    assert args.image == "ao-kernel-live-adapter-gate-policy-service:smoke"
    assert args.dockerfile == Path("deploy/live-adapter-gate-policy-service/Dockerfile")
    assert args.build_timeout_seconds == 300.0
    assert args.run_timeout_seconds == 30.0
    assert module._health_url(18080) == "http://127.0.0.1:18080/healthz"
    smoke_source = Path(module.__file__).read_text(encoding="utf-8")
    assert "timeout_seconds=args.build_timeout_seconds" in smoke_source
    assert '"secret_value_readback": False' in smoke_source
    assert '"live_adapter_execution": False' in smoke_source
    assert '"github_callback_post": False' in smoke_source
