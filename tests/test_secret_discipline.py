"""E-2-5 secret resolution discipline tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.secrets.discipline import (
    SecretResolutionDiscipline,
    SecretResolutionError,
    SecretSerializationError,
)
from ao_kernel._internal.secrets.taint import SecretTaintSet

REPO_ROOT = Path(__file__).resolve().parents[1]


def _secret(prefix: str, length: int = 36) -> str:
    return prefix + ("A" * length)


def _teams_webhook() -> str:
    return "https://" + "example.webhook.office.com/webhookb2/" + ("A" * 24)


def test_value_based_taint_redacts_envelope_audit_log_and_telemetry(tmp_path: Path) -> None:
    secret = _secret("sk-test-", 32)
    discipline = SecretResolutionDiscipline(environ={"OPENAI_API_KEY": secret})
    resolved = discipline.resolve_provider_api_key("openai")

    assert resolved == secret

    envelope: dict[str, Any] = {
        "request": {"provider_id": "openai", "debug": f"key={secret}"},
        "cost": {"actual_cost_usd": "0.00000000"},
        "live_adapter_execution": False,
    }
    audit = {"status": "dry_run_emitted", "raw": secret, "total_tokens": 0}
    telemetry = {"span": {"attrs": ["safe", secret], "attempt": 1}}
    log_line = f"provider returned {secret}"

    rendered = "\n".join(
        [
            discipline.serialize_json(envelope),
            discipline.serialize_json(audit),
            discipline.serialize_json(telemetry),
            discipline.safe_log_line(log_line),
        ]
    )

    assert secret not in rendered
    assert "[REDACTED:provider=openai]" in rendered
    assert "\"actual_cost_usd\":\"0.00000000\"" in rendered
    assert "\"total_tokens\":0" in rendered

    out = tmp_path / "evidence" / "secret-safe.json"
    discipline.write_json(out, {"value": secret})
    assert secret not in out.read_text(encoding="utf-8")
    assert out.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("value", "placeholder"),
    [
        (_secret("AKIA", 16), "[REDACTED:pattern=aws_access_key]"),
        (_secret("sk-", 24), "[REDACTED:pattern=generic_sk_key]"),
        (_secret("sk-ant-", 24), "[REDACTED:pattern=anthropic_api_key]"),
        (_secret("sk-proj-", 24), "[REDACTED:pattern=openai_project_key]"),
        (_secret("xoxb-", 16), "[REDACTED:pattern=slack_bot_token]"),
        (_secret("glpat-", 20), "[REDACTED:pattern=gitlab_pat]"),
        (_secret("gho_", 36), "[REDACTED:pattern=github_oauth]"),
        (_secret("ghp_", 36), "[REDACTED:pattern=github_pat_classic]"),
        (_secret("github_pat_", 82), "[REDACTED:pattern=github_fine_grained_pat]"),
        (_secret("ghs_", 36), "[REDACTED:pattern=github_server_token]"),
        (_secret("ghu_", 36), "[REDACTED:pattern=github_user_token]"),
        (_secret("eyJ", 24) + ".", "[REDACTED:pattern=jwt_prefix]"),
        (_teams_webhook(), "[REDACTED:pattern=teams_webhook_url]"),
    ],
)
def test_regex_defense_in_depth_patterns(value: str, placeholder: str) -> None:
    taint = SecretTaintSet()
    redacted = taint.redact_text(f"before {value} after")

    assert value not in redacted
    assert placeholder in redacted


def test_regex_non_matching_text_is_unchanged() -> None:
    taint = SecretTaintSet()
    value = "sk-short"

    assert taint.redact_text(value) == value


def test_env_only_resolution_does_not_consult_provider_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> object:
        raise AssertionError("factory must not be called by E-2-5 discipline")

    monkeypatch.setenv("SECRETS_PROVIDER", "vault_stub")
    monkeypatch.setattr("ao_kernel._internal.secrets.factory.create_provider_from_env", _boom)
    discipline = SecretResolutionDiscipline(environ={})

    with pytest.raises(SecretResolutionError, match="required env secret"):
        discipline.resolve_provider_api_key("openai")


def test_optional_env_resolution_returns_none_without_taint() -> None:
    discipline = SecretResolutionDiscipline(environ={})

    assert discipline.resolve_provider_api_key("openai", required=False) is None
    assert discipline.taint_set.snapshot_metadata() == ()


def test_invalidate_clears_provider_taint_after_rotation() -> None:
    old_secret = _secret("sk-old-", 24)
    discipline = SecretResolutionDiscipline(environ={"OPENAI_API_KEY": old_secret})
    discipline.resolve_provider_api_key("openai")

    assert old_secret not in discipline.safe_log_line(old_secret)
    discipline.invalidate("openai")
    assert discipline.safe_log_line(old_secret) == "[REDACTED:pattern=generic_sk_key]"


def test_assert_no_taint_fails_closed_on_manual_bypass() -> None:
    secret = _secret("sk-test-", 32)
    discipline = SecretResolutionDiscipline(environ={"OPENAI_API_KEY": secret})
    discipline.resolve_provider_api_key("openai")

    with pytest.raises(SecretSerializationError):
        discipline.assert_no_taint(f"manual bypass {secret}")


def test_append_jsonl_redacts_before_write(tmp_path: Path) -> None:
    secret = _secret("sk-test-", 32)
    discipline = SecretResolutionDiscipline(environ={"OPENAI_API_KEY": secret})
    discipline.resolve_provider_api_key("openai")

    path = tmp_path / "evidence" / "audit.jsonl"
    discipline.append_jsonl(path, {"secret": secret, "count": 1})

    [row] = path.read_text(encoding="utf-8").splitlines()
    parsed = json.loads(row)
    assert parsed["secret"] == "[REDACTED:provider=openai]"
    assert parsed["count"] == 1


def test_discipline_module_does_not_import_vault_or_provider_factory() -> None:
    tree = ast.parse((REPO_ROOT / "ao_kernel" / "_internal" / "secrets" / "discipline.py").read_text())
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)

    assert "ao_kernel._internal.secrets.factory" not in imported_names
    assert "ao_kernel._internal.secrets.vault_stub_provider" not in imported_names
    assert "ao_kernel._internal.secrets.hashicorp_vault_provider" not in imported_names


def test_serialization_helpers_route_through_scan_and_redact() -> None:
    tree = ast.parse((REPO_ROOT / "ao_kernel" / "_internal" / "secrets" / "discipline.py").read_text())
    calls_by_function: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            calls: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        calls.add(child.func.attr)
                    elif isinstance(child.func, ast.Name):
                        calls.add(child.func.id)
            calls_by_function[node.name] = calls

    assert "redact_payload" in calls_by_function["serialize_json"]
    assert "serialize_json" in calls_by_function["serialize_json_line"]
    assert "redact_text" in calls_by_function["safe_log_line"]
    assert "serialize_json" in calls_by_function["write_json"]
    assert "serialize_json_line" in calls_by_function["append_jsonl"]
