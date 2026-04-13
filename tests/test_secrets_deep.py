"""Deep behavioral tests for secrets providers — vault stub, env mapping, edge cases."""

from __future__ import annotations

import json
from pathlib import Path


class TestVaultStubProvider:
    def test_get_existing_secret(self, tmp_path: Path):
        from ao_kernel._internal.secrets.vault_stub_provider import VaultStubSecretsProvider
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({
            "OPENAI_API_KEY": "sk-stub-openai-123",
            "ANTHROPIC_API_KEY": "sk-stub-anthropic-456",
        }))
        provider = VaultStubSecretsProvider(secrets_path=secrets_file)
        assert provider.get("OPENAI_API_KEY") == "sk-stub-openai-123"
        assert provider.get("ANTHROPIC_API_KEY") == "sk-stub-anthropic-456"

    def test_get_missing_secret_returns_none(self, tmp_path: Path):
        from ao_kernel._internal.secrets.vault_stub_provider import VaultStubSecretsProvider
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"SOME_KEY": "val"}))
        provider = VaultStubSecretsProvider(secrets_path=secrets_file)
        result = provider.get("NONEXISTENT_KEY")
        assert result is None

    def test_missing_file_returns_none(self, tmp_path: Path):
        from ao_kernel._internal.secrets.vault_stub_provider import VaultStubSecretsProvider
        provider = VaultStubSecretsProvider(secrets_path=tmp_path / "nonexistent.json")
        result = provider.get("ANY_KEY")
        assert result is None


class TestEnvProviderEdgeCases:
    def test_empty_env_value_returns_none(self, monkeypatch):
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        monkeypatch.setenv("OPENAI_API_KEY", "")
        provider = EnvSecretsProvider()
        result = provider.get("OPENAI_API_KEY")
        assert result is None  # Empty string → None

    def test_whitespace_only_returns_none(self, monkeypatch):
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        provider = EnvSecretsProvider()
        result = provider.get("OPENAI_API_KEY")
        assert result is None  # Whitespace stripped → empty → None

    def test_valid_key_with_whitespace_stripped(self, monkeypatch):
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        monkeypatch.setenv("OPENAI_API_KEY", "  sk-real-key  ")
        provider = EnvSecretsProvider()
        result = provider.get("OPENAI_API_KEY")
        assert result == "sk-real-key"

    def test_unmapped_key_returns_none(self):
        from ao_kernel._internal.secrets.env_provider import EnvSecretsProvider
        provider = EnvSecretsProvider()
        result = provider.get("TOTALLY_UNKNOWN_KEY_XYZ")
        assert result is None


class TestSecretsProviderAbstract:
    def test_cannot_instantiate_abstract_base(self):
        """SecretsProvider is ABC — direct instantiation raises TypeError."""
        from ao_kernel._internal.secrets.provider import SecretsProvider
        import pytest
        with pytest.raises(TypeError, match="abstract method"):
            SecretsProvider()

    def test_subclass_must_implement_get(self):
        """Subclass without get() cannot be instantiated."""
        from ao_kernel._internal.secrets.provider import SecretsProvider
        import pytest

        class IncompleteProvider(SecretsProvider):
            pass

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteProvider()
