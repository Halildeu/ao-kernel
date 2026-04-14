"""Tests for ao_kernel._internal.secrets.api_key_resolver (B2, CNS-005 D0.3).

The resolver's job is dual-read: consult the factory-configured
SecretsProvider first, then fall back to os.environ. Every code path
here is exercised with an isolated ``environ`` dict so tests never
mutate the user's real environment.
"""

from __future__ import annotations

from ao_kernel._internal.secrets.api_key_resolver import (
    env_names_for,
    resolve_api_key,
)
from ao_kernel._internal.secrets.provider import SecretsProvider


class _DictProvider(SecretsProvider):
    """Minimal stand-in for a secrets backend (vault, etc.)."""

    def __init__(self, values: dict[str, str | None]) -> None:
        self._values = values
        self.calls: list[str] = []

    def get(self, secret_id: str) -> str | None:
        self.calls.append(secret_id)
        return self._values.get(secret_id)


class _BrokenProvider(SecretsProvider):
    """Provider that raises on every lookup — env fallback must still work."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, secret_id: str) -> str | None:
        self.calls.append(secret_id)
        raise RuntimeError(f"backend down for {secret_id}")


class TestEnvNamesMapping:
    def test_openai_canonical(self):
        assert env_names_for("openai") == ("OPENAI_API_KEY",)

    def test_claude_alias_to_anthropic(self):
        names = env_names_for("claude")
        assert "ANTHROPIC_API_KEY" in names
        assert "CLAUDE_API_KEY" in names

    def test_google_alias_to_gemini(self):
        names = env_names_for("google")
        assert "GOOGLE_API_KEY" in names
        assert "GEMINI_API_KEY" in names

    def test_qwen_alias_to_dashscope(self):
        assert "DASHSCOPE_API_KEY" in env_names_for("qwen")

    def test_xai_alias_grok(self):
        assert env_names_for("grok") == env_names_for("xai")

    def test_unknown_provider_upper_case_fallback(self):
        assert env_names_for("fictional") == ("FICTIONAL_API_KEY",)


class TestFactoryPath:
    def test_factory_returns_secret(self):
        provider = _DictProvider({"OPENAI_API_KEY": "sk-from-vault"})
        key = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=provider,
        )
        assert key == "sk-from-vault"

    def test_factory_audit_flags_source(self):
        provider = _DictProvider({"OPENAI_API_KEY": "sk-from-vault"})
        value, source = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=provider,
            audit=True,
        )
        assert value == "sk-from-vault"
        assert source == "factory"

    def test_factory_whitespace_is_ignored(self):
        """Provider returning blanks must not mask env fallback."""
        provider = _DictProvider({"OPENAI_API_KEY": "   "})
        key = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-env"},
            secrets_provider=provider,
        )
        assert key == "sk-env"

    def test_factory_tries_alternate_secret_ids(self):
        """claude -> ANTHROPIC_API_KEY primary, CLAUDE_API_KEY alternate."""
        provider = _DictProvider({
            "ANTHROPIC_API_KEY": None,
            "CLAUDE_API_KEY": "sk-legacy",
        })
        key = resolve_api_key(
            "claude",
            environ={},
            secrets_provider=provider,
        )
        assert key == "sk-legacy"
        # Resolver stopped after finding the alternate; no wasted calls.
        assert provider.calls == ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"]


class TestEnvFallback:
    def test_env_used_when_provider_empty(self):
        provider = _DictProvider({})
        key = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-env"},
            secrets_provider=provider,
        )
        assert key == "sk-env"

    def test_env_audit_source(self):
        provider = _DictProvider({})
        value, source = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-env"},
            secrets_provider=provider,
            audit=True,
        )
        assert value == "sk-env"
        assert source == "environ"

    def test_env_alternate_name_accepted(self):
        """claude: primary ANTHROPIC_API_KEY missing, CLAUDE_API_KEY present."""
        key = resolve_api_key(
            "claude",
            environ={"CLAUDE_API_KEY": "sk-legacy-env"},
            secrets_provider=_DictProvider({}),
        )
        assert key == "sk-legacy-env"

    def test_whitespace_env_is_treated_as_missing(self):
        key = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "   "},
            secrets_provider=_DictProvider({}),
        )
        assert key == ""

    def test_nothing_found_returns_empty(self):
        key = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=_DictProvider({}),
        )
        assert key == ""

    def test_nothing_found_audit_source_missing(self):
        value, source = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=_DictProvider({}),
            audit=True,
        )
        assert value == ""
        assert source == "missing"


class TestProviderFaultTolerance:
    def test_provider_exception_falls_through_to_env(self):
        """A broken vault backend must NOT take down the whole call-path."""
        provider = _BrokenProvider()
        key = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-env"},
            secrets_provider=provider,
        )
        assert key == "sk-env"
        # Resolver still attempted the factory before falling back.
        assert provider.calls == ["OPENAI_API_KEY"]

    def test_provider_exception_missing_everywhere_returns_empty(self):
        provider = _BrokenProvider()
        key = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=provider,
        )
        assert key == ""


class TestDefaultProviderInjection:
    def test_no_provider_uses_factory_from_env(self, monkeypatch):
        """With SECRETS_PROVIDER unset, create_provider_from_env builds EnvSecretsProvider."""
        monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-env")
        # No explicit environ/provider kwargs — default path.
        key = resolve_api_key("openai")
        assert key == "sk-real-env"

    def test_missing_env_returns_empty_with_default_provider(self, monkeypatch):
        monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        key = resolve_api_key("openai")
        assert key == ""
