"""Additional coverage tests for _internal/session/context_store.py.

Targets PR-C2: lift coverage from ~52% toward 85%. The base suite in
``test_context_store_internal.py`` covers new/upsert/prune/save. This
file adds coverage for the less-exercised mutators: provider/actor
state upserts, compaction marker, context renewal, parent linkage,
and parent decision inheritance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ao_kernel._internal.session.context_store import (
    SessionContextError,
    inherit_parent_decisions,
    link_to_parent,
    mark_compaction,
    new_context,
    prune_expired_decisions,
    renew_context,
    upsert_actor_state,
    upsert_decision,
    upsert_provider_state,
)


# ── upsert_provider_state ───────────────────────────────────────────


class TestUpsertProviderState:
    def test_sets_provider_and_wire_api(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = upsert_provider_state(ctx, provider="openai", wire_api="chat")
        assert out["provider_state"]["provider"] == "openai"
        assert out["provider_state"]["wire_api"] == "chat"
        assert out["memory_strategy"] == "hybrid"

    def test_optional_fields_round_trip(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = upsert_provider_state(
            ctx,
            provider="claude",
            wire_api="anthropic",
            conversation_id="conv-1",
            last_response_id="resp-1",
            summary_ref="workspace/summary.md",
        )
        state = out["provider_state"]
        assert state["conversation_id"] == "conv-1"
        assert state["last_response_id"] == "resp-1"
        assert state["summary_ref"] == "workspace/summary.md"

    def test_non_dict_context_raises(self):
        with pytest.raises(SessionContextError, match="context must be a dict"):
            upsert_provider_state("not-a-dict", provider="x", wire_api="y")  # type: ignore[arg-type]

    def test_empty_provider_raises(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        with pytest.raises(SessionContextError, match="provider"):
            upsert_provider_state(ctx, provider="   ", wire_api="chat")

    def test_empty_wire_api_raises(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        with pytest.raises(SessionContextError, match="wire_api"):
            upsert_provider_state(ctx, provider="openai", wire_api="")


# ── upsert_actor_state ──────────────────────────────────────────────


class TestUpsertActorState:
    def test_sets_actor_state_minimal(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = upsert_actor_state(
            ctx, role="architect", actor="alpha", provider="openai", model="gpt-4",
        )
        state = out["actor_state"]
        assert state["role"] == "architect"
        assert state["actor"] == "alpha"
        assert state["provider"] == "openai"
        assert state["model"] == "gpt-4"

    def test_optional_fields_included(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = upsert_actor_state(
            ctx, role="implementer", actor="beta", provider="claude", model="sonnet",
            target_id="target-7", selection_reason="highest-confidence",
            fallback_used=True,
        )
        state = out["actor_state"]
        assert state["target_id"] == "target-7"
        assert state["selection_reason"] == "highest-confidence"
        assert state["fallback_used"] is True

    def test_invalid_role_raises(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        with pytest.raises(SessionContextError, match="role"):
            upsert_actor_state(
                ctx, role="bogus", actor="a", provider="p", model="m",
            )

    def test_missing_fields_raise(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        for bad in ({"actor": ""}, {"provider": ""}, {"model": ""}):
            kwargs = {
                "role": "executor",
                "actor": "a",
                "provider": "p",
                "model": "m",
                **bad,
            }
            with pytest.raises(SessionContextError):
                upsert_actor_state(ctx, **kwargs)


# ── mark_compaction ────────────────────────────────────────────────


class TestMarkCompaction:
    def test_sets_compaction_block(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = mark_compaction(
            ctx, summary_ref="summary.md", trigger="auto", source="router",
            approx_input_tokens=12_000,
        )
        comp = out["compaction"]
        assert comp["status"] == "completed"
        assert comp["summary_ref"] == "summary.md"
        assert comp["trigger"] == "auto"
        assert comp["source"] == "router"
        assert comp["approx_input_tokens"] == 12_000

    def test_non_dict_context_raises(self):
        with pytest.raises(SessionContextError):
            mark_compaction(None, summary_ref="s", trigger="t", source="r")  # type: ignore[arg-type]


# ── renew_context ──────────────────────────────────────────────────


class TestRenewContext:
    def test_renew_updates_ttl_and_expiry(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        original_expiry = ctx["expires_at"]
        renewed = renew_context(ctx, 7200)
        assert renewed["ttl_seconds"] == 7200
        assert renewed["expires_at"] > original_expiry
        # hashes refreshed
        assert len(renewed["hashes"]["session_context_sha256"]) == 64

    def test_renew_prunes_expired_decisions(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        # Insert an already-expired decision.
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        ctx["ephemeral_decisions"].append({
            "key": "old",
            "value": "x",
            "source": "agent",
            "created_at": past,
            "ttl_seconds": 60,
            "expires_at": past,
        })
        renewed = renew_context(ctx, 3600)
        assert all(d["key"] != "old" for d in renewed["ephemeral_decisions"])

    def test_invalid_ttl_raises(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        with pytest.raises(SessionContextError, match="ttl_seconds"):
            renew_context(ctx, 10)


# ── link_to_parent / inherit_parent_decisions ──────────────────────


class TestLinkToParent:
    def test_link_sets_parent_session_ref(self, tmp_path: Path):
        ctx = new_context("child", str(tmp_path), 3600)
        out = link_to_parent(ctx, parent_workspace_root="/workspace/parent", parent_session_id="p-1")
        assert out["parent_session_ref"]["workspace_root"] == "/workspace/parent"
        assert out["parent_session_ref"]["session_id"] == "p-1"
        assert out["parent_session_ref"]["relationship"] == "parent"

    def test_link_default_session_id(self, tmp_path: Path):
        ctx = new_context("child", str(tmp_path), 3600)
        out = link_to_parent(ctx, parent_workspace_root="/workspace/parent")
        assert out["parent_session_ref"]["session_id"] == "default"

    def test_link_empty_parent_raises(self, tmp_path: Path):
        ctx = new_context("child", str(tmp_path), 3600)
        with pytest.raises(SessionContextError):
            link_to_parent(ctx, parent_workspace_root="")


class TestInheritParentDecisions:
    def _fresh_decision(self, key: str, value: str, ttl: int = 3600) -> dict:
        now = datetime.now(timezone.utc)
        created = now.isoformat().replace("+00:00", "Z")
        expires = (now + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z")
        return {
            "key": key, "value": value, "source": "agent",
            "created_at": created, "ttl_seconds": ttl, "expires_at": expires,
        }

    def test_inherits_parent_decisions(self, tmp_path: Path):
        child = new_context("child", str(tmp_path), 3600)
        parent = new_context("parent", str(tmp_path), 3600)
        parent["ephemeral_decisions"].append(self._fresh_decision("shared", "v"))
        out = inherit_parent_decisions(child, parent_context=parent)
        keys = [d["key"] for d in out["ephemeral_decisions"]]
        assert "shared" in keys

    def test_does_not_overwrite_child_by_default(self, tmp_path: Path):
        child = new_context("child", str(tmp_path), 3600)
        child = upsert_decision(child, key="shared", value="child_value", source="agent")
        parent = new_context("parent", str(tmp_path), 3600)
        parent["ephemeral_decisions"].append(self._fresh_decision("shared", "parent_value"))
        out = inherit_parent_decisions(child, parent_context=parent)
        shared = next(d for d in out["ephemeral_decisions"] if d["key"] == "shared")
        assert shared["value"] == "child_value"

    def test_overwrite_existing_replaces_child_value(self, tmp_path: Path):
        child = new_context("child", str(tmp_path), 3600)
        child = upsert_decision(child, key="shared", value="child_value", source="agent")
        parent = new_context("parent", str(tmp_path), 3600)
        parent["ephemeral_decisions"].append(self._fresh_decision("shared", "parent_value"))
        out = inherit_parent_decisions(child, parent_context=parent, overwrite_existing=True)
        shared = next(d for d in out["ephemeral_decisions"] if d["key"] == "shared")
        assert shared["value"] == "parent_value"

    def test_expired_parent_decisions_skipped(self, tmp_path: Path):
        child = new_context("child", str(tmp_path), 3600)
        parent = new_context("parent", str(tmp_path), 3600)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        parent["ephemeral_decisions"].append({
            "key": "expired", "value": "x", "source": "agent",
            "created_at": past, "ttl_seconds": 60, "expires_at": past,
        })
        out = inherit_parent_decisions(child, parent_context=parent)
        assert all(d["key"] != "expired" for d in out["ephemeral_decisions"])

    def test_missing_parent_decisions_noop(self, tmp_path: Path):
        child = new_context("child", str(tmp_path), 3600)
        parent = new_context("parent", str(tmp_path), 3600)
        out = inherit_parent_decisions(child, parent_context=parent)
        assert out["ephemeral_decisions"] == []


# ── prune_expired_decisions edges ─────────────────────────────────


class TestPruneExpiredDecisionsEdges:
    def test_non_dict_context_passthrough(self):
        assert prune_expired_decisions(None, "2026-04-14T00:00:00Z") is None  # type: ignore[arg-type]

    def test_invalid_now_iso_passthrough(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        out = prune_expired_decisions(ctx, "not-a-timestamp")
        # Same structure returned unchanged
        assert out is ctx

    def test_non_list_decisions_passthrough(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        ctx["ephemeral_decisions"] = "corrupt"  # type: ignore[assignment]
        out = prune_expired_decisions(ctx, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        assert out is ctx

    def test_non_dict_decision_entries_dropped(self, tmp_path: Path):
        ctx = new_context("s", str(tmp_path), 3600)
        ctx["ephemeral_decisions"] = ["oops", {"key": "k", "value": "v", "source": "agent"}]
        out = prune_expired_decisions(ctx, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        assert all(isinstance(d, dict) for d in out["ephemeral_decisions"])
