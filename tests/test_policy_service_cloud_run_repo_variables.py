from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "policy_service_cloud_run_repo_variables.py"
    spec = importlib.util.spec_from_file_location("policy_service_cloud_run_repo_variables", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _complete_config() -> dict[str, str]:
    mod = _module()
    return {name: f"value-for-{name}" for name in mod.REQUIRED_REPOSITORY_VARIABLES}


def test_repo_variable_template_contains_required_and_optional_names(tmp_path: Path) -> None:
    mod = _module()
    template_path = tmp_path / "cloud-run-variables.json"

    mod.write_template(template_path)

    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert set(mod.REQUIRED_REPOSITORY_VARIABLES).issubset(template)
    assert set(mod.OPTIONAL_REPOSITORY_VARIABLES).issubset(template)
    assert all(value == "" for value in template.values())


def test_repo_variable_operations_require_all_required_handles() -> None:
    mod = _module()
    config = _complete_config()
    del config["GCP_SERVICE_ACCOUNT"]

    with pytest.raises(mod.ConfigError, match="missing required repository variables: GCP_SERVICE_ACCOUNT"):
        mod.build_operations(config)


def test_repo_variable_operations_reject_unknown_and_runtime_secret_names() -> None:
    mod = _module()
    config = _complete_config()
    config["AO_CLAUDE_CODE_CLI_AUTH"] = "should-not-be-here"
    config["NOT_A_DEPLOY_VARIABLE"] = "nope"

    with pytest.raises(mod.ConfigError) as excinfo:
        mod.build_operations(config)

    message = str(excinfo.value)
    assert "unknown repository variables: NOT_A_DEPLOY_VARIABLE" in message
    assert "secret/runtime credential names are not repository variables: AO_CLAUDE_CODE_CLI_AUTH" in message


def test_repo_variable_operations_reject_secret_looking_values() -> None:
    mod = _module()
    config = _complete_config()
    config["GCP_PROJECT_ID"] = "github_pat_example"

    with pytest.raises(mod.ConfigError, match="values look like credential material"):
        mod.build_operations(config)


def test_repo_variable_apply_uses_stdin_and_does_not_put_values_in_command() -> None:
    mod = _module()
    operations = [
        mod.RepositoryVariableOperation(name="GCP_PROJECT_ID", value="actual-project-id"),
        mod.RepositoryVariableOperation(name="POLICY_SERVICE_NAME", value="policy-service"),
    ]
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    mod.apply_operations(operations, repo="Halildeu/ao-kernel", runner=fake_run)

    assert [call["args"] for call in calls] == [
        ["gh", "variable", "set", "GCP_PROJECT_ID", "--repo", "Halildeu/ao-kernel"],
        ["gh", "variable", "set", "POLICY_SERVICE_NAME", "--repo", "Halildeu/ao-kernel"],
    ]
    assert [call["kwargs"]["input"] for call in calls] == ["actual-project-id", "policy-service"]
    assert all("actual-project-id" not in " ".join(call["args"]) for call in calls)
    assert all(call["kwargs"]["capture_output"] is True for call in calls)


def test_repo_variable_dry_run_output_lists_names_not_values(tmp_path: Path, capsys: Any) -> None:
    mod = _module()
    config_path = tmp_path / "variables.json"
    config = _complete_config()
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = mod.main(["--config-json", str(config_path), "--dry-run", "--output", "text"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "mode: dry_run" in captured.out
    assert "GCP_PROJECT_ID" in captured.out
    assert "value-for-GCP_PROJECT_ID" not in captured.out
    assert "cloud_run_deploy_executed: false" in captured.out
    assert "github_callback_post: false" in captured.out
    assert "live_adapter_execution: false" in captured.out
