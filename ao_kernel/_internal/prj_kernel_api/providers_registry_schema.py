"""Mini validators for PRJ-KERNEL-API provider registry (project scope, stdlib-only)."""

from __future__ import annotations

from typing import Any


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_registry(obj: Any) -> None:
    errors: list[str] = []
    if not isinstance(obj, dict):
        errors.append("registry: root must be an object")
        raise ValueError("PROVIDER_REGISTRY_INVALID: registry root must be an object")
    if not _is_str(obj.get("version")):
        errors.append("registry.version must be a non-empty string")
    providers = obj.get("providers")
    if not isinstance(providers, list) or not providers:
        errors.append("registry.providers must be a non-empty list")
        raise ValueError("PROVIDER_REGISTRY_INVALID: " + "; ".join(errors))
    for idx, provider in enumerate(providers):
        if not isinstance(provider, dict):
            errors.append(f"registry.providers[{idx}] must be an object")
            continue
        if not _is_str(provider.get("id")):
            errors.append(f"registry.providers[{idx}].id must be a string")
        if not isinstance(provider.get("enabled"), bool):
            errors.append(f"registry.providers[{idx}].enabled must be boolean")
        if not _is_str(provider.get("base_url")):
            errors.append(f"registry.providers[{idx}].base_url must be a string")
        if not _is_str(provider.get("api_key_env")):
            errors.append(f"registry.providers[{idx}].api_key_env must be a string")
        if not _is_str(provider.get("default_model")):
            errors.append(f"registry.providers[{idx}].default_model must be a string")
        timeout = provider.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append(f"registry.providers[{idx}].timeout_seconds must be a positive int")
    if errors:
        raise ValueError("PROVIDER_REGISTRY_INVALID: " + "; ".join(errors))


def validate_policy(obj: Any) -> None:
    errors: list[str] = []
    if not isinstance(obj, dict):
        errors.append("policy: root must be an object")
        raise ValueError("PROVIDER_POLICY_INVALID: policy root must be an object")
    if not _is_str(obj.get("version")):
        errors.append("policy.version must be a non-empty string")
    allow = obj.get("allow_providers")
    if not isinstance(allow, list) or not all(_is_str(x) for x in allow):
        errors.append("policy.allow_providers must be a list of strings")
    if not isinstance(obj.get("default_dry_run"), bool):
        errors.append("policy.default_dry_run must be boolean")
    max_timeout = obj.get("max_timeout_seconds")
    if not isinstance(max_timeout, int) or max_timeout <= 0:
        errors.append("policy.max_timeout_seconds must be a positive int")
    max_retries = obj.get("max_retries")
    if not isinstance(max_retries, int) or max_retries < 0:
        errors.append("policy.max_retries must be a non-negative int")
    rate = obj.get("rate_limit_rps")
    if not isinstance(rate, (int, float)) or rate <= 0:
        errors.append("policy.rate_limit_rps must be > 0")
    redaction = obj.get("redaction")
    if not isinstance(redaction, dict):
        errors.append("policy.redaction must be an object")
    else:
        if not isinstance(redaction.get("enabled"), bool):
            errors.append("policy.redaction.enabled must be boolean")
        fields = redaction.get("fields")
        if not isinstance(fields, list) or not all(_is_str(x) for x in fields):
            errors.append("policy.redaction.fields must be a list of strings")
    if not isinstance(obj.get("network_required_for_live_calls"), bool):
        errors.append("policy.network_required_for_live_calls must be boolean")
    if errors:
        raise ValueError("PROVIDER_POLICY_INVALID: " + "; ".join(errors))
