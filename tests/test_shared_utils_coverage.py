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
