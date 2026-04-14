"""Provider API key resolver — dual-read pattern (factory > env fallback).

Per CNS-20260414-005 D0.3: the secrets factory (``create_provider_from_env``)
became available but call-sites still read directly from ``os.environ``. A
hard switch would regress workflows where the configured provider
intentionally masks or overrides env-only values; a silent switch would hide
misconfigurations.

The dual-read pattern keeps both paths alive during migration:

    1. Ask the configured SecretsProvider (env, vault_stub, hashicorp_vault).
       - Success -> return its value (source: "factory").
       - Unknown secret id, or provider declines -> try next layer.
    2. Fall back to ``os.environ`` directly (source: "environ").
    3. Nothing found -> empty string (source: "missing").

Call-sites read the VALUE; tests can pass ``audit=True`` to also inspect
which path served it. Env fallback stays until every provider surface moves
to the factory-only contract (tracked as D0.3 follow-up).

Security notes:
  - Never log the resolved value. The ``source`` channel is safe to log.
  - Whitespace-only env values are treated as missing (matches
    EnvSecretsProvider semantics) so accidentally-exported blank secrets
    do not mask real ones.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Literal, TYPE_CHECKING, overload

if TYPE_CHECKING:
    from ao_kernel._internal.secrets.provider import SecretsProvider

# Provider id (registry-canonical) -> preferred env-variable name, plus
# accepted alternates for backward compatibility with older deployments.
_PROVIDER_TO_ENVS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    "xai": ("XAI_API_KEY",),
    "grok": ("XAI_API_KEY",),
}


def env_names_for(provider_id: str) -> tuple[str, ...]:
    """Return accepted env-variable names for a provider id.

    Unknown providers fall back to ``{PROVIDER_UPPER}_API_KEY`` — matches
    the pre-D0.3 behaviour in mcp_server.py.
    """
    canonical = _PROVIDER_TO_ENVS.get(provider_id.lower())
    if canonical:
        return canonical
    return (f"{provider_id.upper()}_API_KEY",)


@overload
def resolve_api_key(
    provider_id: str,
    *,
    environ: Mapping[str, str] | None = ...,
    secrets_provider: "SecretsProvider | None" = ...,
    audit: Literal[False] = ...,
) -> str: ...


@overload
def resolve_api_key(
    provider_id: str,
    *,
    environ: Mapping[str, str] | None = ...,
    secrets_provider: "SecretsProvider | None" = ...,
    audit: Literal[True],
) -> tuple[str, str]: ...


def resolve_api_key(
    provider_id: str,
    *,
    environ: Mapping[str, str] | None = None,
    secrets_provider: "SecretsProvider | None" = None,
    audit: bool = False,
) -> str | tuple[str, str]:
    """Resolve an API key for ``provider_id`` using dual-read precedence.

    Args:
        provider_id: Registry-canonical provider id (e.g. "openai", "claude").
        environ: Mapping to read env variables from. Defaults to ``os.environ``.
            Tests pass a dict to isolate state.
        secrets_provider: Pre-built provider to consult before env. Defaults
            to ``create_provider_from_env()`` when the caller leaves this None.
            Pass an explicit provider (e.g. vault_stub) to pin the source.
        audit: When True, returns ``(value, source)`` where source is one of
            ``"factory"``, ``"environ"``, or ``"missing"``. When False (default)
            returns only the value. Callers that just need the key pass no
            argument; call-sites that log provenance pass ``audit=True``.

    Returns:
        Empty string when no key is found (D11-compatible; callers treat
        empty as "skip the call"). See ``audit`` for provenance.
    """
    env = environ if environ is not None else os.environ

    if secrets_provider is None:
        secrets_provider = _default_provider()

    candidates = env_names_for(provider_id)

    # 1. Factory path — try each candidate env name as a canonical secret id.
    if secrets_provider is not None:
        for secret_id in candidates:
            try:
                value = secrets_provider.get(secret_id)
            except Exception:  # noqa: BLE001 — provider faults must not block env fallback
                value = None
            if value:
                stripped = value.strip()
                if stripped:
                    return (stripped, "factory") if audit else stripped

    # 2. Env fallback — preserves pre-D0.3 behaviour for callers that have
    #    not yet onboarded a SecretsProvider (vault_stub, hashicorp_vault).
    for env_var in candidates:
        raw = env.get(env_var, "")
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                return (stripped, "environ") if audit else stripped

    return ("", "missing") if audit else ""


def _default_provider() -> "SecretsProvider | None":
    """Build the factory-configured provider once. Returns None on load failure
    so that resolve_api_key still works via the env fallback path.
    """
    try:
        from ao_kernel._internal.secrets.factory import create_provider_from_env
        return create_provider_from_env()
    except Exception:  # noqa: BLE001 — factory load is best-effort
        return None


__all__ = ["resolve_api_key", "env_names_for"]


# Ensure runtime attribute access still sees SecretsProvider even outside
# TYPE_CHECKING — kept lazy to avoid import cycles at module load.
def _runtime_check() -> Any:  # pragma: no cover — smoke helper
    from ao_kernel._internal.secrets.provider import SecretsProvider  # noqa: F401
    return SecretsProvider
