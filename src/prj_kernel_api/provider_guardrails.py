"""Provider guardrails policy loader (project scope, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.prj_kernel_api.dotenv_loader import resolve_env_value

POLICY_PATH = "policies/policy_llm_providers_guardrails.v1.json"


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _model_in_allowlist(model: str, allow_models: List[str]) -> bool:
    if "*" in allow_models:
        return True
    return model in allow_models


def validate_guardrails(obj: Any) -> None:
    if not isinstance(obj, dict):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: root must be an object")
    if obj.get("version") != "v1":
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: version must be v1")
    defaults = obj.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: defaults missing")
    if not isinstance(defaults.get("enabled"), bool):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: defaults.enabled must be boolean")
    for field in ["timeout_seconds", "max_request_bytes", "max_response_bytes", "retry_count"]:
        if not isinstance(defaults.get(field), int) or defaults.get(field) < 0:
            raise ValueError(f"PROVIDER_GUARDRAILS_INVALID: defaults.{field} must be int >= 0")
    if not _is_str_list(defaults.get("allow_models")):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: defaults.allow_models must be list of strings")
    default_model = defaults.get("default_model")
    if default_model is not None:
        if not isinstance(default_model, str) or not default_model:
            raise ValueError("PROVIDER_GUARDRAILS_INVALID: defaults.default_model must be string")
        if not _model_in_allowlist(default_model, defaults.get("allow_models", [])):
            raise ValueError("PROVIDER_GUARDRAILS_INVALID: defaults.default_model not in allow_models")

    providers = obj.get("providers")
    if not isinstance(providers, dict):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: providers must be object")
    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            raise ValueError("PROVIDER_GUARDRAILS_INVALID: provider entry must be object")
        if not isinstance(provider.get("enabled"), bool):
            raise ValueError(f"PROVIDER_GUARDRAILS_INVALID: providers.{provider_id}.enabled must be boolean")
        if not _is_str_list(provider.get("expected_env_keys")):
            raise ValueError(
                f"PROVIDER_GUARDRAILS_INVALID: providers.{provider_id}.expected_env_keys must be list of strings"
            )
        if not _is_str_list(provider.get("allow_models")):
            raise ValueError(
                f"PROVIDER_GUARDRAILS_INVALID: providers.{provider_id}.allow_models must be list of strings"
            )
        provider_default = provider.get("default_model")
        if provider_default is not None:
            if not isinstance(provider_default, str) or not provider_default:
                raise ValueError(
                    f"PROVIDER_GUARDRAILS_INVALID: providers.{provider_id}.default_model must be string"
                )
            if not _model_in_allowlist(provider_default, provider.get("allow_models", [])):
                raise ValueError(
                    f"PROVIDER_GUARDRAILS_INVALID: providers.{provider_id}.default_model not in allow_models"
                )

    live_gate = obj.get("live_gate")
    if not isinstance(live_gate, dict):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: live_gate missing")
    if not isinstance(live_gate.get("policy_live_enabled"), bool):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: live_gate.policy_live_enabled must be boolean")
    if not isinstance(live_gate.get("require_env_key_present"), bool):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: live_gate.require_env_key_present must be boolean")
    if not isinstance(live_gate.get("require_explicit_live_flag"), bool):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: live_gate.require_explicit_live_flag must be boolean")
    if not isinstance(live_gate.get("explicit_live_flag_env"), str) or not live_gate.get("explicit_live_flag_env"):
        raise ValueError("PROVIDER_GUARDRAILS_INVALID: live_gate.explicit_live_flag_env must be string")


def load_guardrails(workspace_root: str) -> Dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_policy = Path(workspace_root) / "policies" / "policy_llm_providers_guardrails.v1.json"
    policy_path = ws_policy if ws_policy.exists() else repo_root / POLICY_PATH
    if not policy_path.exists():
        raise ValueError("PROVIDER_GUARDRAILS_MISSING")
    policy = _load_json(policy_path)
    validate_guardrails(policy)
    return policy


def provider_settings(policy: Dict[str, Any], provider_id: str) -> Dict[str, Any]:
    defaults = policy.get("defaults", {}) if isinstance(policy.get("defaults"), dict) else {}
    providers = policy.get("providers", {}) if isinstance(policy.get("providers"), dict) else {}
    entry = providers.get(provider_id, {}) if isinstance(providers.get(provider_id), dict) else {}

    allow_models = entry.get("allow_models") if _is_str_list(entry.get("allow_models")) else defaults.get("allow_models")
    if not _is_str_list(allow_models):
        allow_models = ["*"]

    expected_env_keys = entry.get("expected_env_keys")
    if not _is_str_list(expected_env_keys):
        expected_env_keys = []
    default_model = None
    if isinstance(entry.get("default_model"), str) and entry.get("default_model"):
        default_model = entry.get("default_model")
    elif isinstance(defaults.get("default_model"), str) and defaults.get("default_model"):
        default_model = defaults.get("default_model")

    return {
        "enabled": bool(entry.get("enabled", defaults.get("enabled", False))),
        "allow_models": list(allow_models),
        "default_model": default_model,
        "expected_env_keys": list(expected_env_keys),
        "timeout_seconds": int(defaults.get("timeout_seconds", 20)),
        "max_request_bytes": int(defaults.get("max_request_bytes", 65536)),
        "max_response_bytes": int(defaults.get("max_response_bytes", 131072)),
        "retry_count": int(defaults.get("retry_count", 0)),
    }


def model_allowed(model: str, allow_models: List[str]) -> bool:
    if "*" in allow_models:
        return True
    return model in allow_models


def live_call_allowed(
    *,
    policy: Dict[str, Any],
    workspace_root: str,
    env_mode: str,
    api_key_present: bool,
) -> Tuple[bool, str]:
    live_gate = policy.get("live_gate", {}) if isinstance(policy.get("live_gate"), dict) else {}
    if not bool(live_gate.get("policy_live_enabled", False)):
        return False, "POLICY_LIVE_DISABLED"
    if bool(live_gate.get("require_env_key_present", True)) and not api_key_present:
        return False, "API_KEY_MISSING"
    if bool(live_gate.get("require_explicit_live_flag", True)):
        env_key = live_gate.get("explicit_live_flag_env")
        if not isinstance(env_key, str) or not env_key:
            return False, "LIVE_FLAG_MISSING"
        present, value = resolve_env_value(env_key, workspace_root, env_mode=env_mode)
        if not present or not isinstance(value, str) or value.strip() != "1":
            return False, "LIVE_FLAG_MISSING"
    return True, "OK"
