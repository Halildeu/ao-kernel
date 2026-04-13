"""Secrets provider factory — create providers by type with lazy imports."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ao_kernel._internal.secrets.provider import SecretsProvider


def create_provider(provider_type: str, **kwargs: Any) -> SecretsProvider:
    """Create a secrets provider by type.

    Supported types:
        "env"              — Environment variable provider (default)
        "vault_stub"       — JSON file provider (requires secrets_path kwarg)
        "hashicorp_vault"  — HashiCorp Vault KV v2 (requires VAULT_ADDR + VAULT_TOKEN)

    Raises ValueError for unknown provider type.
    """
    if provider_type == "env":
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        return EnvSecretsProvider(**kwargs)

    if provider_type == "vault_stub":
        from ao_kernel._internal.secrets.vault_stub_provider import VaultStubSecretsProvider
        secrets_path = kwargs.get("secrets_path")
        if secrets_path is None:
            secrets_path = Path(".secrets/vault.json")
        elif isinstance(secrets_path, str):
            secrets_path = Path(secrets_path)
        return VaultStubSecretsProvider(secrets_path=secrets_path)

    if provider_type == "hashicorp_vault":
        from ao_kernel._internal.secrets.hashicorp_vault_provider import HashiCorpVaultProvider
        return HashiCorpVaultProvider(**kwargs)

    raise ValueError(f"Unknown secrets provider type: {provider_type!r}")


def create_provider_from_env() -> SecretsProvider:
    """Auto-detect and create provider from SECRETS_PROVIDER env var.

    Defaults to "env" if not configured.
    """
    provider_type = os.environ.get("SECRETS_PROVIDER", "env").strip().lower()
    return create_provider(provider_type)
