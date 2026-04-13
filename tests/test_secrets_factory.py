"""Tests for secrets provider factory and HashiCorp Vault provider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ao_kernel._internal.secrets.factory import create_provider, create_provider_from_env


class TestSecretsFactory:
    def test_create_env_provider(self):
        """Factory creates EnvSecretsProvider."""
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        provider = create_provider("env")
        assert isinstance(provider, EnvSecretsProvider)

    def test_create_vault_stub_provider(self, tmp_path: Path):
        """Factory creates VaultStubSecretsProvider with path."""
        from ao_kernel._internal.secrets.vault_stub_provider import VaultStubSecretsProvider
        provider = create_provider("vault_stub", secrets_path=tmp_path / "vault.json")
        assert isinstance(provider, VaultStubSecretsProvider)

    def test_create_hashicorp_vault_provider(self):
        """Factory creates HashiCorpVaultProvider."""
        from ao_kernel._internal.secrets.hashicorp_vault_provider import HashiCorpVaultProvider
        provider = create_provider(
            "hashicorp_vault",
            vault_addr="https://vault.example.com",
            vault_token="test-token",
        )
        assert isinstance(provider, HashiCorpVaultProvider)

    def test_create_unknown_raises(self):
        """Unknown provider type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown secrets provider type"):
            create_provider("nonexistent")

    def test_create_from_env_defaults_to_env(self):
        """Default SECRETS_PROVIDER → env provider."""
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        with patch.dict("os.environ", {}, clear=False):
            provider = create_provider_from_env()
            assert isinstance(provider, EnvSecretsProvider)


class TestHashiCorpVaultProvider:
    def test_get_missing_config_returns_none(self):
        """No VAULT_ADDR/VAULT_TOKEN → None."""
        provider = create_provider("hashicorp_vault", vault_addr="", vault_token="")
        assert provider.get("openai/api-key") is None

    def test_get_invalid_secret_id_returns_none(self):
        """secret_id without '/' → None."""
        provider = create_provider(
            "hashicorp_vault", vault_addr="https://v", vault_token="t",
        )
        assert provider.get("no-slash") is None

    def test_get_success_mock_http(self):
        """Successful Vault HTTP response returns secret value."""
        provider = create_provider(
            "hashicorp_vault", vault_addr="https://vault.example.com", vault_token="t",
        )
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {"data": {"api-key": "sk-test-123"}},
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("ao_kernel._internal.secrets.hashicorp_vault_provider.urlopen", return_value=mock_response):
            result = provider.get("openai/api-key")
            assert result == "sk-test-123"

    def test_get_http_error_returns_none(self):
        """HTTP error → None (fail-safe)."""
        from urllib.error import URLError
        provider = create_provider(
            "hashicorp_vault", vault_addr="https://vault.example.com", vault_token="t",
        )
        with patch(
            "ao_kernel._internal.secrets.hashicorp_vault_provider.urlopen",
            side_effect=URLError("connection refused"),
        ):
            result = provider.get("openai/api-key")
            assert result is None
