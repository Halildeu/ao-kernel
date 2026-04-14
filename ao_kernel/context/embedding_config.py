"""Embedding configuration — decoupled from chat route.

Most chat providers (Anthropic, DeepSeek, xAI) do NOT expose an embeddings
endpoint. Propagating chat route parameters (provider/model) to the
embedding pipeline would deterministically break semantic search for
those users.

This module resolves an independent EmbeddingConfig with precedence:

    1. Constructor-injected EmbeddingConfig (client arg)
    2. Workspace policy (policy_context_memory_tiers.v1.json
                         → semantic_retrieval.embedding)
    3. Env (AO_KERNEL_EMBEDDING_PROVIDER / _MODEL / _BASE_URL / _API_KEY)
    4. Registry default (openai / text-embedding-3-small)

The API key is never read from policy or constructor-by-default —
it resolves through env (D11: secrets env-var only). Caller MAY inject
an api_key field on EmbeddingConfig for tests; production code must not.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ENV_PROVIDER = "AO_KERNEL_EMBEDDING_PROVIDER"
_ENV_MODEL = "AO_KERNEL_EMBEDDING_MODEL"
_ENV_BASE_URL = "AO_KERNEL_EMBEDDING_BASE_URL"

_DEFAULT_PROVIDER = "openai"
_DEFAULT_MODEL = "text-embedding-3-small"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"

# Provider-id → env var(s) checked in order for the API key.
# Falls back to a generic OPENAI_API_KEY when unset.
_PROVIDER_API_KEY_ENVS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


@dataclass(frozen=True)
class EmbeddingConfig:
    """Embedding provider/model/base_url resolved configuration.

    Immutable — callers clone via ``dataclasses.replace`` if they need
    per-call overrides.
    """

    provider: str = _DEFAULT_PROVIDER
    model: str = _DEFAULT_MODEL
    base_url: str = _DEFAULT_BASE_URL
    # api_key is resolved lazily at call-time from env (D11). Stored here
    # only when explicitly injected (tests, SDK callers that manage secrets
    # outside env). Do not log or serialize this field.
    api_key: str = field(default="", repr=False)

    def resolve_api_key(self) -> str:
        """Return the injected api_key if set, else look up from env.

        Returns an empty string if no key found — callers treat empty as
        "embedding unavailable" and fall back to deterministic scoring.
        """
        if self.api_key:
            return self.api_key
        candidates = _PROVIDER_API_KEY_ENVS.get(self.provider, ())
        for env_name in candidates:
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        return ""


def resolve_embedding_config(
    *,
    workspace: Path | None = None,
    injected: EmbeddingConfig | None = None,
) -> EmbeddingConfig:
    """Resolve embedding configuration via constructor > policy > env > default.

    Never raises on missing config — returns default values so that the
    semantic retrieval pipeline can decide whether to proceed (api_key
    presence is the real enablement gate for network calls).
    """
    if injected is not None:
        return injected

    policy = _load_embedding_policy(workspace)
    policy_provider = policy.get("provider") if isinstance(policy, dict) else None
    policy_model = policy.get("model") if isinstance(policy, dict) else None
    policy_base = policy.get("base_url") if isinstance(policy, dict) else None

    env_provider = os.environ.get(_ENV_PROVIDER, "").strip() or None
    env_model = os.environ.get(_ENV_MODEL, "").strip() or None
    env_base = os.environ.get(_ENV_BASE_URL, "").strip() or None

    provider = env_provider or policy_provider or _DEFAULT_PROVIDER
    model = env_model or policy_model or _DEFAULT_MODEL
    base_url = env_base or policy_base or _DEFAULT_BASE_URL

    return EmbeddingConfig(provider=provider, model=model, base_url=base_url)


def _load_embedding_policy(workspace: Path | None) -> dict[str, Any]:
    """Best-effort policy load. Returns {} on any failure (fail-open for config)."""
    try:
        from ao_kernel.config import load_with_override
        policy = load_with_override(
            "policies",
            "policy_context_memory_tiers.v1.json",
            workspace=workspace,
        )
        section = policy.get("semantic_retrieval", {})
        if not isinstance(section, dict):
            return {}
        embedding = section.get("embedding", {})
        return embedding if isinstance(embedding, dict) else {}
    except Exception as exc:  # noqa: BLE001 — config load best-effort
        logger.debug("embedding_config: policy load failed (%s); using defaults", exc)
        return {}


__all__ = ["EmbeddingConfig", "resolve_embedding_config"]
