"""Tests for Faz 3 — canonical decision store."""

from __future__ import annotations

from pathlib import Path

from ao_kernel.context.canonical_store import (
    CanonicalDecision,
    load_store,
    promote_decision,
    promote_from_ephemeral,
    query,
    save_store,
)


class TestStoreLifecycle:
    def test_empty_store(self, tmp_path: Path):
        store = load_store(tmp_path)
        assert store["version"] == "v1"
        assert store["decisions"] == {}
        assert store["facts"] == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        store = load_store(tmp_path)
        store["decisions"]["test.key"] = {"value": "hello"}
        save_store(tmp_path, store)

        loaded = load_store(tmp_path)
        assert "test.key" in loaded["decisions"]
        assert loaded["decisions"]["test.key"]["value"] == "hello"
        assert "updated_at" in loaded

    def test_corrupted_file_raises(self, tmp_path: Path):
        """CNS-010 iter-2 blocking fix: silent-empty fallback removed.

        A corrupted store is a data-loss hazard, not a normal path. Callers
        that want to recover catch CanonicalStoreCorruptedError explicitly
        and invoke a repair workflow.
        """
        import pytest
        from ao_kernel.errors import CanonicalStoreCorruptedError
        (tmp_path / "canonical_decisions.v1.json").write_text("{{invalid")
        with pytest.raises(CanonicalStoreCorruptedError):
            load_store(tmp_path)


class TestPromoteDecision:
    def test_promote_basic(self, tmp_path: Path):
        cd = promote_decision(
            tmp_path,
            key="runtime.python",
            value="3.11",
            category="runtime",
            session_id="sess-001",
        )
        assert isinstance(cd, CanonicalDecision)
        assert cd.key == "runtime.python"
        assert cd.value == "3.11"
        assert cd.category == "runtime"
        assert cd.promoted_from == "sess-001"
        assert len(cd.promoted_at) > 0
        assert len(cd.fresh_until) > 0
        assert len(cd.expires_at) > 0

    def test_promote_persists(self, tmp_path: Path):
        promote_decision(tmp_path, key="arch.pattern", value="microservices")
        store = load_store(tmp_path)
        assert "arch.pattern" in store["decisions"]

    def test_promote_fact_goes_to_facts(self, tmp_path: Path):
        promote_decision(tmp_path, key="repo.files", value=300, category="fact")
        store = load_store(tmp_path)
        assert "repo.files" in store["facts"]
        assert "repo.files" not in store["decisions"]

    def test_promote_overwrites_existing(self, tmp_path: Path):
        promote_decision(tmp_path, key="version", value="1.0")
        promote_decision(tmp_path, key="version", value="2.0")
        store = load_store(tmp_path)
        assert store["decisions"]["version"]["value"] == "2.0"

    def test_supersedes_tracking(self, tmp_path: Path):
        promote_decision(tmp_path, key="deploy.target", value="staging")
        cd = promote_decision(
            tmp_path,
            key="deploy.target",
            value="production",
            supersedes="deploy.target",
        )
        assert cd.supersedes == "deploy.target"

    def test_provenance_stored(self, tmp_path: Path):
        cd = promote_decision(
            tmp_path,
            key="test.prov",
            value="ok",
            provenance={"evidence_id": "req-123", "turn": 3},
        )
        assert cd.provenance["evidence_id"] == "req-123"


class TestQuery:
    def _setup_store(self, tmp_path: Path):
        promote_decision(tmp_path, key="runtime.python", value="3.11", category="runtime")
        promote_decision(tmp_path, key="runtime.os", value="linux", category="runtime")
        promote_decision(tmp_path, key="arch.pattern", value="monolith", category="architecture")
        promote_decision(tmp_path, key="repo.files", value=300, category="fact")

    def test_query_all(self, tmp_path: Path):
        self._setup_store(tmp_path)
        results = query(tmp_path)
        assert len(results) == 4

    def test_query_pattern(self, tmp_path: Path):
        self._setup_store(tmp_path)
        results = query(tmp_path, key_pattern="runtime.*")
        assert len(results) == 2
        assert all("runtime." in r["key"] for r in results)

    def test_query_category(self, tmp_path: Path):
        self._setup_store(tmp_path)
        results = query(tmp_path, category="architecture")
        assert len(results) == 1
        assert results[0]["key"] == "arch.pattern"

    def test_query_facts_only(self, tmp_path: Path):
        self._setup_store(tmp_path)
        results = query(tmp_path, category="fact")
        assert len(results) == 1
        assert results[0]["key"] == "repo.files"

    def test_query_returns_list(self, tmp_path: Path):
        promote_decision(tmp_path, key="first", value=1)
        promote_decision(tmp_path, key="second", value=2)
        results = query(tmp_path)
        assert len(results) == 2
        keys = {r["key"] for r in results}
        assert "first" in keys
        assert "second" in keys

    def test_empty_store_returns_empty(self, tmp_path: Path):
        results = query(tmp_path)
        assert results == []


class TestPromoteFromEphemeral:
    def test_batch_promote_above_threshold(self, tmp_path: Path):
        ephemeral = [
            {"key": "llm.status", "value": "approved", "confidence": 0.9, "source": "agent"},
            {"key": "llm.note", "value": "maybe", "confidence": 0.3, "source": "agent"},
            {"key": "llm.version", "value": "3.11", "confidence": 0.8, "source": "agent"},
        ]
        promoted = promote_from_ephemeral(
            tmp_path,
            ephemeral,
            min_confidence=0.7,
            session_id="batch-001",
        )
        assert len(promoted) == 2  # only 0.9 and 0.8
        keys = {cd.key for cd in promoted}
        assert "llm.status" in keys
        assert "llm.version" in keys
        assert "llm.note" not in keys

    def test_batch_promote_empty(self, tmp_path: Path):
        promoted = promote_from_ephemeral(tmp_path, [])
        assert promoted == []

    def test_batch_promote_all_below_threshold(self, tmp_path: Path):
        ephemeral = [
            {"key": "low", "value": "x", "confidence": 0.1},
        ]
        promoted = promote_from_ephemeral(tmp_path, ephemeral, min_confidence=0.5)
        assert promoted == []


class TestFactDecisionSeparation:
    def test_decision_and_fact_separate_stores(self, tmp_path: Path):
        promote_decision(tmp_path, key="plan.approved", value=True, category="approved_plan")
        promote_decision(tmp_path, key="ci.status", value="green", category="fact")

        store = load_store(tmp_path)
        assert "plan.approved" in store["decisions"]
        assert "ci.status" in store["facts"]
        assert "plan.approved" not in store["facts"]
        assert "ci.status" not in store["decisions"]
