"""v3.8 H1 tranche 1 — coverage pins for ``ao_kernel._internal.shared.utils``.

Closes omit-list gap: removing `_internal/shared/*` from coverage
omit revealed `utils.py` at 48% branch coverage (missing
write_bytes_atomic, load_policy_validated, env helpers, SHA short,
parse_iso8601 empty-string branch). These pins bring the module
above the global `fail_under=85` threshold.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ao_kernel._internal.shared.utils import (
    env_str,
    env_true,
    load_json,
    load_json_or_default,
    load_policy_validated,
    now_iso8601,
    parse_iso8601,
    sha256_file,
    sha256_short,
    sha256_text,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)


# ── write_bytes_atomic ────────────────────────────────────────────────


class TestWriteBytesAtomic:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        payload = b"hello\x00world\n"
        write_bytes_atomic(path, payload)
        assert path.read_bytes() == payload

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c.bin"
        write_bytes_atomic(deep, b"deep")
        assert deep.read_bytes() == b"deep"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"old")
        write_bytes_atomic(path, b"new")
        assert path.read_bytes() == b"new"


# ── load_policy_validated ─────────────────────────────────────────────


class TestLoadPolicyValidated:
    def _schema_file(self, tmp_path: Path) -> Path:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["version", "enabled"],
            "properties": {
                "version": {"type": "string"},
                "enabled": {"type": "boolean"},
            },
            "additionalProperties": False,
        }
        schema_path = tmp_path / "policy.schema.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        return schema_path

    def test_valid_policy_returns_parsed_dict(self, tmp_path: Path) -> None:
        schema_path = self._schema_file(tmp_path)
        policy_path = tmp_path / "policy.json"
        policy_path.write_text(
            json.dumps({"version": "v1", "enabled": True}),
            encoding="utf-8",
        )
        result = load_policy_validated(policy_path, schema_path)
        assert result == {"version": "v1", "enabled": True}

    def test_invalid_policy_raises_value_error(self, tmp_path: Path) -> None:
        schema_path = self._schema_file(tmp_path)
        policy_path = tmp_path / "policy.json"
        # Missing required "enabled"; also extra unknown key.
        policy_path.write_text(
            json.dumps({"version": "v1", "unknown_key": 1}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="schema validation"):
            load_policy_validated(policy_path, schema_path)


# ── env helpers ───────────────────────────────────────────────────────


class TestEnvHelpers:
    def test_env_true_reads_truthy_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for v in ("1", "true", "TRUE", "yes", "Yes", "YES"):
            monkeypatch.setenv("AO_TEST_FLAG", v)
            assert env_true("AO_TEST_FLAG") is True

    def test_env_true_reads_falsy_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for v in ("0", "false", "no", "", "random"):
            monkeypatch.setenv("AO_TEST_FLAG", v)
            assert env_true("AO_TEST_FLAG") is False

    def test_env_true_missing_var_returns_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AO_TEST_MISSING", raising=False)
        assert env_true("AO_TEST_MISSING") is False

    def test_env_str_default_when_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AO_TEST_STR", raising=False)
        assert env_str("AO_TEST_STR", default="fallback") == "fallback"

    def test_env_str_strips_whitespace(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AO_TEST_STR", "  hello world  ")
        assert env_str("AO_TEST_STR") == "hello world"

    def test_env_str_empty_returns_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AO_TEST_STR", "   ")
        assert env_str("AO_TEST_STR", default="fb") == "fb"


# ── hashing ───────────────────────────────────────────────────────────


class TestHashing:
    def test_sha256_short_truncates_to_default_16(self) -> None:
        full = sha256_text("hello")
        short = sha256_short("hello")
        assert len(short) == 16
        assert short == full[:16]

    def test_sha256_short_custom_length(self) -> None:
        assert len(sha256_short("hello", length=8)) == 8

    def test_sha256_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"hello")
        assert sha256_file(path) == sha256_text("hello")


# ── time helpers ──────────────────────────────────────────────────────


class TestTimeHelpers:
    def test_now_iso8601_ends_with_z(self) -> None:
        ts = now_iso8601()
        assert ts.endswith("Z")
        parsed = parse_iso8601(ts)
        assert isinstance(parsed, datetime)
        assert parsed.tzinfo is not None

    def test_parse_iso8601_round_trip(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        ts = now.isoformat().replace("+00:00", "Z")
        parsed = parse_iso8601(ts)
        assert parsed == now

    def test_parse_iso8601_empty_string_returns_none(self) -> None:
        assert parse_iso8601("") is None

    def test_parse_iso8601_invalid_returns_none(self) -> None:
        assert parse_iso8601("not a timestamp") is None

    def test_parse_iso8601_non_string_returns_none(self) -> None:
        assert parse_iso8601(None) is None  # type: ignore[arg-type]


# ── JSON loaders ──────────────────────────────────────────────────────


class TestJsonLoaders:
    def test_load_json_or_default_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.json"
        assert load_json_or_default(missing, default={"fallback": True}) == {"fallback": True}

    def test_load_json_or_default_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert load_json_or_default(bad, default=[]) == []

    def test_load_json_happy_path(self, tmp_path: Path) -> None:
        good = tmp_path / "good.json"
        good.write_text(json.dumps({"ok": 1}), encoding="utf-8")
        assert load_json(good) == {"ok": 1}

    def test_write_json_atomic_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        write_json_atomic(path, {"key": "value", "list": [1, 2, 3]})
        assert json.loads(path.read_text(encoding="utf-8")) == {
            "key": "value",
            "list": [1, 2, 3],
        }
        # sort_keys=True — file content is deterministic.
        content = path.read_text(encoding="utf-8")
        assert content.index('"key"') < content.index('"list"')


# ── write_text_atomic edge paths ──────────────────────────────────────


class TestWriteTextAtomicEdges:
    def test_cleanup_on_writer_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the write fails after tempfile.mkstemp, tmp file is
        cleaned up (except-clause branch)."""
        # Force os.replace to raise; tmp file cleanup path executes.
        import ao_kernel._internal.shared.utils as utils_module

        def _boom(*args, **kwargs):
            raise OSError("forced failure")

        monkeypatch.setattr(utils_module.os, "replace", _boom)
        path = tmp_path / "target.txt"
        with pytest.raises(OSError, match="forced failure"):
            write_text_atomic(path, "payload")
        # After cleanup, no lingering .tmp files remain
        leftovers = list(tmp_path.glob(f"{path.name}.*.tmp"))
        assert not leftovers, f"tmp files not cleaned: {leftovers}"

    def test_cleanup_when_tmp_already_gone(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """write_text_atomic cleanup: if the tmp file is already gone
        when the except-clause fires (FileNotFoundError inner except),
        swallow and re-raise the original error."""
        import ao_kernel._internal.shared.utils as utils_module

        # Force os.replace to fail AND tmp.unlink() to race —
        # manually delete tmp before the cleanup runs.
        original_replace = utils_module.os.replace

        def _delete_then_fail(src, dst):
            Path(src).unlink(missing_ok=True)
            raise OSError("replace then gone")

        monkeypatch.setattr(utils_module.os, "replace", _delete_then_fail)
        path = tmp_path / "target.txt"
        with pytest.raises(OSError, match="replace then gone"):
            write_text_atomic(path, "payload")
        # Sanity: restored original to avoid fixture teardown issues
        monkeypatch.setattr(utils_module.os, "replace", original_replace)


class TestWriteBytesAtomicEdges:
    def test_cleanup_on_writer_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """write_bytes_atomic cleanup path (lines 100-105) —
        identical contract to write_text_atomic but on bytes mode."""
        import ao_kernel._internal.shared.utils as utils_module

        def _boom(*args, **kwargs):
            raise OSError("bytes path forced failure")

        monkeypatch.setattr(utils_module.os, "replace", _boom)
        path = tmp_path / "bytes_target.bin"
        with pytest.raises(OSError, match="bytes path forced failure"):
            write_bytes_atomic(path, b"payload")
        leftovers = list(tmp_path.glob(f"{path.name}.*.tmp"))
        assert not leftovers, f"tmp files not cleaned: {leftovers}"

    def test_cleanup_when_tmp_already_gone(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bytes-mode inner FileNotFoundError branch (lines 103-104)."""
        import ao_kernel._internal.shared.utils as utils_module

        def _delete_then_fail(src, dst):
            Path(src).unlink(missing_ok=True)
            raise OSError("bytes replace then gone")

        monkeypatch.setattr(utils_module.os, "replace", _delete_then_fail)
        path = tmp_path / "bytes_target.bin"
        with pytest.raises(OSError, match="bytes replace then gone"):
            write_bytes_atomic(path, b"payload")


class TestVaultStubProviderCoverage:
    """v3.8 H1 — close vault_stub_provider coverage gaps so the
    _internal/secrets tranche cleanly beats the 85% global gate."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        provider = VaultStubSecretsProvider(
            secrets_path=tmp_path / "missing.json",
        )
        assert provider.get("ANY_KEY") is None

    def test_invalid_json_swallows_and_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text("{not valid json", encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("ANY_KEY") is None

    def test_non_dict_payload_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text('["not", "a", "dict"]', encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("KEY") is None

    def test_non_string_value_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text('{"KEY": 42}', encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("KEY") is None

    def test_empty_string_value_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text('{"KEY": "   "}', encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("KEY") is None

    def test_happy_path_strips_whitespace(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text('{"K": "  value  "}', encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("K") == "value"

    def test_missing_key_returns_none(self, tmp_path: Path) -> None:
        from ao_kernel._internal.secrets.vault_stub_provider import (
            VaultStubSecretsProvider,
        )

        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text('{"OTHER": "v"}', encoding="utf-8")
        provider = VaultStubSecretsProvider(secrets_path=secrets_path)
        assert provider.get("K") is None


class TestApiKeyResolverEnvNames:
    """v3.8 H1 — `env_names_for` branches + known-provider table."""

    def test_unknown_provider_falls_back_to_uppercase(self) -> None:
        from ao_kernel._internal.secrets.api_key_resolver import env_names_for

        result = env_names_for("cohere")
        assert result == ("COHERE_API_KEY",)

    def test_known_provider_returns_canonical_set(self) -> None:
        from ao_kernel._internal.secrets.api_key_resolver import env_names_for

        assert env_names_for("anthropic") == ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")
        assert env_names_for("google") == ("GOOGLE_API_KEY", "GEMINI_API_KEY")

    def test_case_insensitive_provider_lookup(self) -> None:
        from ao_kernel._internal.secrets.api_key_resolver import env_names_for

        assert env_names_for("OpenAI") == ("OPENAI_API_KEY",)


class TestApiKeyResolverBranches:
    """v3.8 H1 — close api_key_resolver coverage gaps (factory-path
    exception, env fallback, audit return, _default_provider failure)."""

    def test_factory_provider_exception_falls_to_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Provider raises → resolver falls through to env fallback."""
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        class _BrokenProvider:
            def get(self, secret_id: str) -> str | None:
                raise RuntimeError("provider broken")

        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback-123")
        result = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-env-fallback-123"},
            secrets_provider=_BrokenProvider(),
        )
        assert result == "sk-env-fallback-123"

    def test_audit_returns_tuple_with_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """audit=True path returns `(value, source)` tuple."""
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        result = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "  sk-audit-key  "},
            secrets_provider=None,
            audit=True,
        )
        assert result == ("sk-audit-key", "environ")

    def test_missing_key_audit_returns_missing(self) -> None:
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        result = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=None,
            audit=True,
        )
        assert result == ("", "missing")

    def test_missing_key_non_audit_returns_empty_string(self) -> None:
        """Non-audit missing path returns `""`, not tuple."""
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        result = resolve_api_key(
            "openai",
            environ={},
            secrets_provider=None,
        )
        assert result == ""

    def test_environ_none_defaults_to_os_environ(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When `environ=None`, resolver reads from `os.environ`."""
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-os-environ")
        result = resolve_api_key(
            "openai",
            secrets_provider=None,
        )
        assert result == "sk-from-os-environ"

    def test_factory_provider_empty_value_falls_to_env(self) -> None:
        """Provider returns empty-string (e.g. masked) → fall through
        to env fallback."""
        from ao_kernel._internal.secrets.api_key_resolver import resolve_api_key

        class _EmptyProvider:
            def get(self, secret_id: str) -> str | None:
                return "   "  # whitespace only → falsy after strip

        result = resolve_api_key(
            "openai",
            environ={"OPENAI_API_KEY": "sk-fallback"},
            secrets_provider=_EmptyProvider(),
        )
        assert result == "sk-fallback"

    def test_default_provider_factory_failure_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_default_provider swallows factory errors → returns None."""
        from ao_kernel._internal.secrets import api_key_resolver

        def _boom():
            raise RuntimeError("factory load boom")

        # Patch the import site so _default_provider's try/except
        # branch executes.
        monkeypatch.setattr(
            "ao_kernel._internal.secrets.factory.create_provider_from_env",
            _boom,
        )
        result = api_key_resolver._default_provider()
        assert result is None


class TestFactoryBranches:
    """v3.8 H1 — factory.py line 30/32 branches (non-env provider
    types, unknown provider raises ValueError)."""

    def test_unknown_provider_type_raises_value_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ao_kernel._internal.secrets.factory import (
            create_provider_from_env,
        )

        monkeypatch.setenv("SECRETS_PROVIDER", "not_a_real_provider")
        with pytest.raises(ValueError, match="Unknown secrets provider"):
            create_provider_from_env()

    def test_vault_stub_with_default_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """factory.py line 29-30: when `secrets_path` kwarg is absent,
        default Path('.secrets/vault.json') is used."""
        from ao_kernel._internal.secrets.factory import create_provider

        provider = create_provider("vault_stub")
        # We only pin the factory branch; provider.get() on a missing
        # default path returns None (vault_stub happy-path handled).
        assert provider is not None

    def test_vault_stub_with_string_path_coerced_to_Path(
        self,
        tmp_path: Path,
    ) -> None:
        """factory.py line 31-32: str `secrets_path` kwarg is coerced
        via Path()."""
        from ao_kernel._internal.secrets.factory import create_provider

        string_path = str(tmp_path / "my_secrets.json")
        provider = create_provider("vault_stub", secrets_path=string_path)
        assert provider is not None


class TestHashiCorpVaultProviderBranches:
    """v3.8 H1 — HashiCorpVaultProvider network-failure branches
    (lines 52, 66->69, 70, 75). No real vault server required —
    patches urlopen to exercise response-shape edge cases."""

    def test_missing_slash_returns_none(self) -> None:
        from ao_kernel._internal.secrets.hashicorp_vault_provider import (
            HashiCorpVaultProvider,
        )

        p = HashiCorpVaultProvider(
            vault_addr="http://x",
            vault_token="t",
        )
        # No slash → invalid path
        assert p.get("no_slash_here") is None
        # Empty key after slash
        assert p.get("path/") is None
        # Empty path before slash
        assert p.get("/key") is None

    def test_missing_addr_or_token_returns_none(self) -> None:
        from ao_kernel._internal.secrets.hashicorp_vault_provider import (
            HashiCorpVaultProvider,
        )

        # Missing addr
        p1 = HashiCorpVaultProvider(vault_addr="", vault_token="t")
        assert p1.get("secret/k") is None
        # Missing token
        p2 = HashiCorpVaultProvider(vault_addr="http://x", vault_token="")
        assert p2.get("secret/k") is None

    def test_non_dict_response_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """KV v2 envelope response where `body.data` is missing or
        not a dict → provider returns None."""
        from ao_kernel._internal.secrets import hashicorp_vault_provider

        class _FakeResp:
            def read(self):
                # body is a dict but body["data"] is a non-dict string
                # → `isinstance(secret_data, dict)` False on line 66,
                # skip unwrap, then `not isinstance(...)` True on line 69
                # → return None (line 70).
                return b'{"data": "not_a_dict_string"}'

            def __enter__(self):
                return self

            def __exit__(self, *a, **kw):
                return False

        monkeypatch.setattr(
            hashicorp_vault_provider,
            "urlopen",
            lambda *a, **kw: _FakeResp(),
        )
        p = hashicorp_vault_provider.HashiCorpVaultProvider(
            vault_addr="http://x",
            vault_token="t",
        )
        assert p.get("secret/key") is None

    def test_non_string_value_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ao_kernel._internal.secrets import hashicorp_vault_provider

        class _FakeResp:
            def read(self):
                return b'{"data": {"data": {"key": 42}}}'

            def __enter__(self):
                return self

            def __exit__(self, *a, **kw):
                return False

        monkeypatch.setattr(
            hashicorp_vault_provider,
            "urlopen",
            lambda *a, **kw: _FakeResp(),
        )
        p = hashicorp_vault_provider.HashiCorpVaultProvider(
            vault_addr="http://x",
            vault_token="t",
        )
        # value is int not str → return None
        assert p.get("secret/key") is None

    def test_empty_string_value_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ao_kernel._internal.secrets import hashicorp_vault_provider

        class _FakeResp:
            def read(self):
                return b'{"data": {"data": {"key": "   "}}}'

            def __enter__(self):
                return self

            def __exit__(self, *a, **kw):
                return False

        monkeypatch.setattr(
            hashicorp_vault_provider,
            "urlopen",
            lambda *a, **kw: _FakeResp(),
        )
        p = hashicorp_vault_provider.HashiCorpVaultProvider(
            vault_addr="http://x",
            vault_token="t",
        )
        # empty stripped value → return None
        assert p.get("secret/key") is None
