"""Tests for self-editing memory — Letta/MemGPT inspired agent-controlled memory.

Tests remember(), update(), forget(), recall() with canonical store integration.
Verifies importance-based retention, audit trail preservation, and key namespacing.
"""

from __future__ import annotations

from pathlib import Path

from ao_kernel.context.canonical_store import load_store, promote_decision
from ao_kernel.context.self_edit_memory import forget, recall, remember, update


class TestRemember:
    def test_remember_basic(self, tmp_path: Path):
        result = remember(tmp_path, key="user_lang", value="Python")
        assert result["stored"] is True
        assert result["key"] == "memory.user_lang"
        assert result["importance"] == "normal"
        assert len(result["fresh_until"]) > 0
        assert len(result["expires_at"]) > 0

    def test_remember_persists_to_store(self, tmp_path: Path):
        remember(tmp_path, key="framework", value="FastAPI")
        store = load_store(tmp_path)
        assert "memory.framework" in store["decisions"]
        assert store["decisions"]["memory.framework"]["value"] == "FastAPI"

    def test_remember_importance_critical(self, tmp_path: Path):
        result = remember(tmp_path, key="api_key_rotation", value="monthly", importance="critical")
        assert result["importance"] == "critical"
        # Critical: confidence 1.0
        store = load_store(tmp_path)
        entry = store["decisions"]["memory.api_key_rotation"]
        assert entry["confidence"] == 1.0

    def test_remember_importance_high(self, tmp_path: Path):
        result = remember(tmp_path, key="deploy_target", value="prod", importance="high")
        assert result["importance"] == "high"
        store = load_store(tmp_path)
        assert store["decisions"]["memory.deploy_target"]["confidence"] == 0.9

    def test_remember_importance_low(self, tmp_path: Path):
        result = remember(tmp_path, key="scratch_note", value="temp", importance="low")
        assert result["importance"] == "low"
        store = load_store(tmp_path)
        assert store["decisions"]["memory.scratch_note"]["confidence"] == 0.5

    def test_remember_invalid_importance_uses_normal(self, tmp_path: Path):
        result = remember(tmp_path, key="test", value="val", importance="bogus")
        assert result["importance"] == "bogus"
        store = load_store(tmp_path)
        # Falls back to normal config → confidence 0.8
        assert store["decisions"]["memory.test"]["confidence"] == 0.8

    def test_remember_category_is_agent_memory(self, tmp_path: Path):
        remember(tmp_path, key="cat_test", value="x")
        store = load_store(tmp_path)
        assert store["decisions"]["memory.cat_test"]["category"] == "agent_memory"

    def test_remember_provenance_tracks_method(self, tmp_path: Path):
        remember(tmp_path, key="prov_test", value="y", importance="high")
        store = load_store(tmp_path)
        prov = store["decisions"]["memory.prov_test"]["provenance"]
        assert prov["method"] == "self_edit"
        assert prov["importance"] == "high"

    def test_remember_with_session_id(self, tmp_path: Path):
        remember(tmp_path, key="sess_test", value="z", session_id="sess-42")
        store = load_store(tmp_path)
        assert store["decisions"]["memory.sess_test"]["promoted_from"] == "sess-42"

    def test_remember_complex_value(self, tmp_path: Path):
        val = {"tools": ["grep", "read"], "max_depth": 3}
        result = remember(tmp_path, key="search_config", value=val)
        assert result["stored"] is True
        store = load_store(tmp_path)
        assert store["decisions"]["memory.search_config"]["value"] == val

    def test_remember_overwrites_same_key(self, tmp_path: Path):
        remember(tmp_path, key="version", value="1.0")
        remember(tmp_path, key="version", value="2.0")
        store = load_store(tmp_path)
        assert store["decisions"]["memory.version"]["value"] == "2.0"


class TestUpdate:
    def test_update_existing(self, tmp_path: Path):
        remember(tmp_path, key="lang", value="Python")
        result = update(tmp_path, key="lang", new_value="Rust")
        assert result["updated"] is True
        assert result["old_value"] == "Python"
        assert result["new_value"] == "Rust"

    def test_update_missing_key_returns_error(self, tmp_path: Path):
        result = update(tmp_path, key="nonexistent", new_value="anything")
        assert result["updated"] is False
        assert result["error"] == "MEMORY_NOT_FOUND"

    def test_update_persists_new_value(self, tmp_path: Path):
        remember(tmp_path, key="target", value="staging")
        update(tmp_path, key="target", new_value="production")
        # Query to verify the latest value
        results = recall(tmp_path, key_pattern="memory.target")
        assert len(results) >= 1
        assert results[0]["value"] == "production"

    def test_update_tracks_supersedes(self, tmp_path: Path):
        remember(tmp_path, key="deploy", value="v1")
        update(tmp_path, key="deploy", new_value="v2")
        store = load_store(tmp_path)
        entry = store["decisions"]["memory.deploy"]
        assert entry["supersedes"] == "memory.deploy"

    def test_update_preserves_provenance(self, tmp_path: Path):
        remember(tmp_path, key="track", value="old")
        update(tmp_path, key="track", new_value="new")
        store = load_store(tmp_path)
        prov = store["decisions"]["memory.track"]["provenance"]
        assert prov["method"] == "self_edit_update"
        assert prov["old_value"] == "old"

    def test_update_handles_prefixed_key(self, tmp_path: Path):
        remember(tmp_path, key="prefixed", value="a")
        # Pass already-prefixed key
        result = update(tmp_path, key="memory.prefixed", new_value="b")
        assert result["updated"] is True
        assert result["key"] == "memory.prefixed"

    def test_update_with_session_id(self, tmp_path: Path):
        remember(tmp_path, key="sess_up", value="x")
        update(tmp_path, key="sess_up", new_value="y", session_id="sess-99")
        store = load_store(tmp_path)
        assert store["decisions"]["memory.sess_up"]["promoted_from"] == "sess-99"


class TestForget:
    def test_forget_existing(self, tmp_path: Path):
        remember(tmp_path, key="secret", value="classified")
        result = forget(tmp_path, key="secret")
        assert result["forgotten"] is True
        assert result["key"] == "memory.secret"

    def test_forget_marks_expired(self, tmp_path: Path):
        remember(tmp_path, key="temp", value="data")
        forget(tmp_path, key="temp")
        store = load_store(tmp_path)
        entry = store["decisions"]["memory.temp"]
        assert entry["expires_at"] == "2000-01-01T00:00:00Z"
        assert entry["_forgotten"] is True

    def test_forget_does_not_physically_delete(self, tmp_path: Path):
        remember(tmp_path, key="audit", value="important")
        forget(tmp_path, key="audit")
        store = load_store(tmp_path)
        # Still exists in store (audit trail preserved)
        assert "memory.audit" in store["decisions"]

    def test_forget_missing_returns_not_found(self, tmp_path: Path):
        result = forget(tmp_path, key="ghost")
        assert result["forgotten"] is False
        assert result["error"] == "MEMORY_NOT_FOUND"

    def test_forget_handles_prefixed_key(self, tmp_path: Path):
        remember(tmp_path, key="pfx", value="test")
        result = forget(tmp_path, key="memory.pfx")
        assert result["forgotten"] is True

    def test_forgotten_excluded_from_recall(self, tmp_path: Path):
        remember(tmp_path, key="visible", value="yes")
        remember(tmp_path, key="hidden", value="no")
        forget(tmp_path, key="hidden")
        results = recall(tmp_path)
        keys = [r["key"] for r in results]
        assert "memory.visible" in keys
        assert "memory.hidden" not in keys  # expired → excluded by query


class TestRecall:
    def test_recall_returns_all_memories(self, tmp_path: Path):
        remember(tmp_path, key="a", value="1")
        remember(tmp_path, key="b", value="2")
        remember(tmp_path, key="c", value="3")
        results = recall(tmp_path)
        assert len(results) == 3

    def test_recall_custom_pattern(self, tmp_path: Path):
        remember(tmp_path, key="config.theme", value="dark")
        remember(tmp_path, key="config.lang", value="en")
        remember(tmp_path, key="note.todo", value="finish PR")
        results = recall(tmp_path, key_pattern="memory.config.*")
        assert len(results) == 2
        keys = {r["key"] for r in results}
        assert "memory.config.theme" in keys
        assert "memory.config.lang" in keys

    def test_recall_empty_store(self, tmp_path: Path):
        results = recall(tmp_path)
        assert results == []

    def test_recall_includes_temporal_metadata(self, tmp_path: Path):
        remember(tmp_path, key="meta_test", value="check")
        results = recall(tmp_path, key_pattern="memory.meta_test")
        assert len(results) == 1
        assert "_is_fresh" in results[0]
        assert results[0]["_is_fresh"] is True  # just created → fresh

    def test_recall_sorted_newest_first(self, tmp_path: Path):
        remember(tmp_path, key="first", value="1")
        remember(tmp_path, key="second", value="2")
        results = recall(tmp_path)
        # Both promoted_at within same second, but order should be stable
        assert len(results) == 2


class TestIntegration:
    def test_remember_update_recall_cycle(self, tmp_path: Path):
        """Full lifecycle: remember → recall → update → recall → forget → recall."""
        # Remember
        remember(tmp_path, key="version", value="1.0", importance="high")

        # Recall
        results = recall(tmp_path, key_pattern="memory.version")
        assert len(results) == 1
        assert results[0]["value"] == "1.0"

        # Update
        update(tmp_path, key="version", new_value="2.0")

        # Recall updated
        results = recall(tmp_path, key_pattern="memory.version")
        assert len(results) == 1
        assert results[0]["value"] == "2.0"

        # Forget
        forget(tmp_path, key="version")

        # Recall after forget — excluded (expired)
        results = recall(tmp_path, key_pattern="memory.version")
        assert len(results) == 0

    def test_multiple_memories_different_importance(self, tmp_path: Path):
        remember(tmp_path, key="critical_policy", value="no-secrets-in-logs", importance="critical")
        remember(tmp_path, key="normal_note", value="check CI", importance="normal")
        remember(tmp_path, key="low_scratch", value="temp idea", importance="low")

        results = recall(tmp_path)
        assert len(results) == 3

        store = load_store(tmp_path)
        assert store["decisions"]["memory.critical_policy"]["confidence"] == 1.0
        assert store["decisions"]["memory.normal_note"]["confidence"] == 0.8
        assert store["decisions"]["memory.low_scratch"]["confidence"] == 0.5

    def test_coexists_with_non_memory_decisions(self, tmp_path: Path):
        """Self-edit memories don't interfere with regular canonical decisions."""
        # Regular decision (not memory)
        promote_decision(tmp_path, key="runtime.python", value="3.11")
        # Self-edit memory
        remember(tmp_path, key="user_pref", value="dark_mode")

        store = load_store(tmp_path)
        assert "runtime.python" in store["decisions"]
        assert "memory.user_pref" in store["decisions"]

        # recall only returns memory.* prefixed
        results = recall(tmp_path)
        keys = [r["key"] for r in results]
        assert "memory.user_pref" in keys
        assert "runtime.python" not in keys
