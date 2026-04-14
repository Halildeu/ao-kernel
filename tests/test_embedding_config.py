"""Tests for ao_kernel.context.embedding_config (B1b, CNS-007)."""

from __future__ import annotations

import pytest

from ao_kernel.context.embedding_config import (
    EmbeddingConfig,
    resolve_embedding_config,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "AO_KERNEL_EMBEDDING_PROVIDER",
        "AO_KERNEL_EMBEDDING_MODEL",
        "AO_KERNEL_EMBEDDING_BASE_URL",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


class TestResolveEmbeddingConfig:
    def test_defaults(self):
        cfg = resolve_embedding_config()
        assert cfg.provider == "openai"
        assert cfg.model == "text-embedding-3-small"
        assert cfg.base_url == "https://api.openai.com/v1"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_PROVIDER", "google")
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_MODEL", "text-embedding-004")
        monkeypatch.setenv(
            "AO_KERNEL_EMBEDDING_BASE_URL",
            "https://generativelanguage.googleapis.com/v1",
        )
        cfg = resolve_embedding_config()
        assert cfg.provider == "google"
        assert cfg.model == "text-embedding-004"
        assert cfg.base_url.endswith("/v1")

    def test_injected_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_EMBEDDING_PROVIDER", "google")
        injected = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-large",
            base_url="https://api.openai.com/v1",
        )
        cfg = resolve_embedding_config(injected=injected)
        assert cfg is injected


class TestApiKeyResolution:
    def test_injected_key_returned_first(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        cfg = EmbeddingConfig(api_key="injected-key")
        assert cfg.resolve_api_key() == "injected-key"

    def test_openai_env_fallback(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        cfg = EmbeddingConfig(provider="openai")
        assert cfg.resolve_api_key() == "sk-openai"

    def test_google_primary_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "g-main")
        cfg = EmbeddingConfig(provider="google")
        assert cfg.resolve_api_key() == "g-main"

    def test_google_falls_back_to_gemini_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "g-fallback")
        cfg = EmbeddingConfig(provider="google")
        assert cfg.resolve_api_key() == "g-fallback"

    def test_empty_returned_when_nothing_set(self):
        cfg = EmbeddingConfig(provider="openai")
        assert cfg.resolve_api_key() == ""

    def test_unknown_provider_returns_empty(self):
        cfg = EmbeddingConfig(provider="unknown-provider")
        assert cfg.resolve_api_key() == ""

    def test_whitespace_only_env_treated_as_empty(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        cfg = EmbeddingConfig(provider="openai")
        assert cfg.resolve_api_key() == ""

    def test_api_key_not_in_repr(self):
        """repr=False on api_key must keep secrets out of logs."""
        secret_marker = "MARKER-for-repr-test"
        cfg = EmbeddingConfig(api_key=secret_marker)
        assert secret_marker not in repr(cfg)
