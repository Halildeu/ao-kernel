"""Tests for _internal context store — new/upsert/prune/save lifecycle."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import ao_kernel._internal.session.context_store as context_store_module

from ao_kernel._internal.session.context_store import (
    SessionContextError,
    compute_context_sha256,
    is_expired,
    new_context,
    prune_expired_decisions,
    renew_context,
    save_context_atomic,
    load_context,
    upsert_decision,
)

FIXED_CONTEXT_NOW = "2026-04-22T12:00:00Z"
FIXED_RENEW_NOW = "2026-04-22T12:30:00Z"


class TestNewContext:
    def test_creates_valid_context(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            context_store_module,
            "_now_iso8601",
            lambda: FIXED_CONTEXT_NOW,
        )
        ctx = new_context("sess-001", str(tmp_path), 3600)
        assert ctx["session_id"] == "sess-001"
        assert ctx["version"] == "v1"
        assert ctx["ttl_seconds"] == 3600
        assert ctx["created_at"] == FIXED_CONTEXT_NOW
        assert ctx["updated_at"] == FIXED_CONTEXT_NOW
        assert ctx["expires_at"] == "2026-04-22T13:00:00Z"
        assert ctx["ephemeral_decisions"] == []
        assert len(ctx["hashes"]["session_context_sha256"]) == 64

    def test_empty_session_id_raises(self, tmp_path: Path):
        with pytest.raises(SessionContextError, match="non-empty"):
            new_context("", str(tmp_path), 3600)

    def test_invalid_ttl_raises(self, tmp_path: Path):
        with pytest.raises(SessionContextError, match="ttl_seconds"):
            new_context("sess", str(tmp_path), 10)  # < 60 minimum

    def test_ttl_too_large_raises(self, tmp_path: Path):
        with pytest.raises(SessionContextError):
            new_context("sess", str(tmp_path), 999999)  # > 604800

    def test_predecessor_stored(self, tmp_path: Path):
        ctx = new_context("child", str(tmp_path), 3600, predecessor_session_id="parent")
        assert ctx["predecessor_session_id"] == "parent"


class TestUpsertDecision:
    def _ctx(self, tmp_path: Path) -> dict:
        return new_context("test", str(tmp_path), 3600)

    def test_insert_new_decision(self, tmp_path: Path):
        ctx = self._ctx(tmp_path)
        ctx = upsert_decision(ctx, "lang", "python", "agent")
        decisions = ctx["ephemeral_decisions"]
        assert len(decisions) == 1
        assert decisions[0]["key"] == "lang"
        assert decisions[0]["value"] == "python"

    def test_update_existing_with_history(self, tmp_path: Path):
        ctx = self._ctx(tmp_path)
        ctx = upsert_decision(ctx, "version", "1.0", "agent")
        ctx = upsert_decision(ctx, "version", "2.0", "agent")
        d = next(d for d in ctx["ephemeral_decisions"] if d["key"] == "version")
        assert d["value"] == "2.0"
        assert len(d["history"]) == 1
        assert d["history"][0]["value"] == "1.0"

    def test_invalid_source_raises(self, tmp_path: Path):
        ctx = self._ctx(tmp_path)
        with pytest.raises(SessionContextError, match="source"):
            upsert_decision(ctx, "key", "val", "invalid_source")

    def test_list_value_raises(self, tmp_path: Path):
        ctx = self._ctx(tmp_path)
        with pytest.raises(SessionContextError, match="value_json"):
            upsert_decision(ctx, "key", [1, 2, 3], "agent")

    def test_none_value_raises(self, tmp_path: Path):
        ctx = self._ctx(tmp_path)
        with pytest.raises(SessionContextError, match="value_json"):
            upsert_decision(ctx, "key", None, "agent")


class TestPruneExpired:
    def test_removes_expired_decisions(self, tmp_path: Path):
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat().replace("+00:00", "Z")
        far_future = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
        past = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        ctx = new_context("prune-test", str(tmp_path), 3600)
        # Add a decision that won't expire soon
        ctx["ephemeral_decisions"] = [
            {
                "key": "keep",
                "value": "yes",
                "source": "agent",
                "created_at": now_iso,
                "ttl_seconds": 86400,
                "expires_at": far_future,
            },
            {
                "key": "expired_key",
                "value": "old",
                "source": "agent",
                "created_at": past,
                "ttl_seconds": 60,
                "expires_at": past,
            },
        ]
        ctx = prune_expired_decisions(ctx, now_iso)
        keys = [d["key"] for d in ctx["ephemeral_decisions"]]
        assert "keep" in keys
        assert "expired_key" not in keys

    def test_keeps_valid_decisions(self, tmp_path: Path):
        ctx = new_context("prune-keep", str(tmp_path), 3600)
        ctx = upsert_decision(ctx, "valid", True, "agent")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        ctx = prune_expired_decisions(ctx, now)
        assert len(ctx["ephemeral_decisions"]) == 1


class TestIsExpired:
    def test_not_expired(self, tmp_path: Path):
        ctx = new_context("exp-test", str(tmp_path), 3600)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        assert is_expired(ctx, now) is False

    def test_expired_after_ttl(self, tmp_path: Path):
        ctx = new_context("exp-test", str(tmp_path), 60)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        assert is_expired(ctx, future) is True

    def test_missing_expires_at(self):
        assert is_expired({}, "2026-01-01T00:00:00Z") is True


class TestSaveLoadRoundtrip:
    def test_save_and_load(self, tmp_path: Path):
        ctx = new_context("roundtrip", str(tmp_path), 3600)
        ctx = upsert_decision(ctx, "test_key", "test_val", "agent")
        path = tmp_path / "session.json"
        save_context_atomic(path, ctx)
        loaded = load_context(path)
        assert loaded["session_id"] == "roundtrip"
        assert len(loaded["ephemeral_decisions"]) == 1
        assert loaded["hashes"]["session_context_sha256"] == compute_context_sha256(loaded)

    def test_corrupted_hash_raises(self, tmp_path: Path):
        ctx = new_context("corrupt", str(tmp_path), 3600)
        path = tmp_path / "session.json"
        save_context_atomic(path, ctx)
        # Tamper with hash
        data = json.loads(path.read_text())
        data["hashes"]["session_context_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
        with pytest.raises(SessionContextError, match="does not match"):
            load_context(path)


class TestRenewContext:
    def test_renew_extends_ttl(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            context_store_module,
            "_now_iso8601",
            lambda: FIXED_CONTEXT_NOW,
        )
        ctx = new_context("renew", str(tmp_path), 600)
        assert ctx["expires_at"] == "2026-04-22T12:10:00Z"
        monkeypatch.setattr(
            context_store_module,
            "_now_iso8601",
            lambda: FIXED_RENEW_NOW,
        )
        ctx = renew_context(ctx, 7200)
        assert ctx["ttl_seconds"] == 7200
        assert ctx["updated_at"] == FIXED_RENEW_NOW
        assert ctx["expires_at"] == "2026-04-22T14:30:00Z"

    def test_renew_invalid_ttl_raises(self, tmp_path: Path):
        ctx = new_context("renew-bad", str(tmp_path), 3600)
        with pytest.raises(SessionContextError):
            renew_context(ctx, 10)  # too small
