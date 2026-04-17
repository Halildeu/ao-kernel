"""Integration tests for ``ao_kernel.coordination.registry``.

Exercises the CORE flows (acquire / heartbeat / release / get_claim /
validate_fencing_token / list_agent_claims) against the real
filesystem under ``claims.lock``. Takeover + prune + reconcile +
executor fencing land in commit 4; tests for those paths are
deferred accordingly.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.coordination import (
    ClaimAlreadyReleasedError,
    ClaimConflictError,
    ClaimCoordinationDisabledError,
    ClaimCorruptedError,
    ClaimOwnershipError,
    ClaimQuotaExceededError,
    ClaimRegistry,
    ClaimResourceIdInvalidError,
    ClaimResourcePatternError,
    ClaimStaleFencingError,
)


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: claims.lock relies on fcntl",
)


def _enabled_policy(**overrides: Any) -> dict[str, Any]:
    base = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    base.update(overrides)
    return base


def _write_workspace_policy(workspace_root: Path, doc: dict[str, Any]) -> None:
    policy_dir = workspace_root / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(doc, sort_keys=True),
    )


# ---------------------------------------------------------------------------
# Dormant-default guard
# ---------------------------------------------------------------------------


class TestDormantDefault:
    def test_acquire_fails_without_opt_in(self, tmp_path: Path) -> None:
        """Bundled policy ships enabled=false; acquire must refuse."""
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.acquire_claim("worktree-a", "agent-alpha")

    def test_heartbeat_dormant_refuses(self, tmp_path: Path) -> None:
        """Plan §5 'any public API' — heartbeat gated by dormant
        policy check (CNS-029v4 iter-3 blocker #1 fix)."""
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.heartbeat(
                "worktree-a",
                "11111111-1111-4111-8111-111111111111",
                "agent-alpha",
            )

    def test_release_dormant_refuses(self, tmp_path: Path) -> None:
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.release_claim(
                "worktree-a",
                "11111111-1111-4111-8111-111111111111",
                "agent-alpha",
            )

    def test_takeover_dormant_refuses(self, tmp_path: Path) -> None:
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.takeover_claim("worktree-a", "agent-beta")

    def test_get_claim_dormant_refuses(self, tmp_path: Path) -> None:
        """Even read-only introspection is gated — dormant means the
        registry is dormant full-stop, not 'read-only mode'."""
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.get_claim("worktree-a")

    def test_validate_fencing_token_dormant_refuses(
        self, tmp_path: Path,
    ) -> None:
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.validate_fencing_token("worktree-a", 0)

    def test_list_agent_claims_dormant_refuses(self, tmp_path: Path) -> None:
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.list_agent_claims("agent-alpha")

    def test_prune_dormant_refuses(self, tmp_path: Path) -> None:
        """Prune is a mutation pathway — dormant mode must refuse it
        (mirrors acquire / release / takeover gating, not read-only
        exception)."""
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.prune_expired_claims()

    def test_dormant_gate_fires_before_evidence_sink(
        self, tmp_path: Path,
    ) -> None:
        """CNS-029v4 iter-4 absorb: dormant gate must raise *before*
        the evidence sink is invoked — a dormant registry never emits
        claim events. We install a recording sink and assert it is
        never called when the 7 public APIs refuse under the dormant
        default policy."""
        calls: list[tuple[str, Mapping[str, Any]]] = []

        def recording_sink(kind: str, payload: Mapping[str, Any]) -> None:
            calls.append((kind, dict(payload)))

        registry = ClaimRegistry(tmp_path, evidence_sink=recording_sink)

        # Each call refuses; the sink must not be touched.
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.heartbeat(
                "worktree-a",
                "11111111-1111-4111-8111-111111111111",
                "agent-alpha",
            )
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.release_claim(
                "worktree-a",
                "11111111-1111-4111-8111-111111111111",
                "agent-alpha",
            )
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.takeover_claim("worktree-a", "agent-beta")
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.get_claim("worktree-a")
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.validate_fencing_token("worktree-a", 0)
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.list_agent_claims("agent-alpha")
        with pytest.raises(ClaimCoordinationDisabledError):
            registry.prune_expired_claims()

        # No emits: plan §5 dormant-policy contract + W2v5 redaction
        # scope narrowed to "registry emits only under enabled policy".
        assert calls == []


# ---------------------------------------------------------------------------
# resource_id validator + pattern allowlist
# ---------------------------------------------------------------------------


class TestResourceIdGuards:
    def test_path_traversal_rejected_before_pattern(self, tmp_path: Path) -> None:
        """B4v2: path-traversal guard runs first; pattern matcher never
        sees unsafe input."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimResourceIdInvalidError):
            registry.acquire_claim("../escape", "agent-alpha")

    def test_slash_rejected(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimResourceIdInvalidError):
            registry.acquire_claim("a/b", "agent-alpha")

    def test_wildcard_rejected(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimResourceIdInvalidError):
            registry.acquire_claim("prefix*", "agent-alpha")

    def test_pattern_deny_after_valid_format(self, tmp_path: Path) -> None:
        """Valid format + not matching allowlist → pattern error."""
        _write_workspace_policy(
            tmp_path,
            _enabled_policy(claim_resource_patterns=["worktree-*"]),
        )
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimResourcePatternError):
            registry.acquire_claim("run-xyz", "agent-alpha")


# ---------------------------------------------------------------------------
# Acquire happy path + file layout
# ---------------------------------------------------------------------------


class TestAcquireHappyPath:
    def test_new_resource_returns_token_zero(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        claim = registry.acquire_claim("worktree-a", "agent-alpha")
        assert claim.fencing_token == 0
        assert claim.owner_agent_id == "agent-alpha"
        assert claim.resource_id == "worktree-a"
        assert claim.revision.startswith("sha256:")

    def test_write_order_creates_three_artefacts(self, tmp_path: Path) -> None:
        """B2v2 write order: fencing → claim → index. All three exist
        after acquire completes."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        claims_dir = tmp_path / ".ao" / "claims"
        assert (claims_dir / "worktree-a.v1.json").is_file()
        assert (claims_dir / "_fencing.v1.json").is_file()
        assert (claims_dir / "_index.v1.json").is_file()

    def test_second_resource_for_same_agent_also_token_zero(
        self, tmp_path: Path,
    ) -> None:
        """Fencing tokens are per-resource — two different resources
        both start at 0."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        a = registry.acquire_claim("worktree-a", "agent-alpha")
        b = registry.acquire_claim("worktree-b", "agent-alpha")
        assert a.fencing_token == 0
        assert b.fencing_token == 0

    def test_emits_claim_acquired_event(self, tmp_path: Path) -> None:
        events: list[tuple[str, dict[str, Any]]] = []

        def _sink(kind: str, payload: Any) -> None:
            events.append((kind, dict(payload)))

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_sink)
        registry.acquire_claim("worktree-a", "agent-alpha")
        assert any(k == "claim_acquired" for k, _ in events)
        payload = next(p for k, p in events if k == "claim_acquired")
        assert payload["resource_id"] == "worktree-a"
        assert payload["owner_agent_id"] == "agent-alpha"
        assert payload["fencing_token"] == 0


# ---------------------------------------------------------------------------
# Acquire conflict paths
# ---------------------------------------------------------------------------


class TestAcquireConflict:
    def test_live_claim_blocks_second_agent(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimConflictError) as excinfo:
            registry.acquire_claim("worktree-a", "agent-beta")
        assert excinfo.value.current_owner_agent_id == "agent-alpha"
        assert excinfo.value.current_fencing_token == first.fencing_token

    def test_conflict_payload_carries_current_fencing_token(
        self, tmp_path: Path,
    ) -> None:
        """B6v2: claim_conflict evidence must include current_fencing_token
        for FAZ-B master plan §10 race test."""
        events: list[tuple[str, dict[str, Any]]] = []

        def _sink(kind: str, payload: Any) -> None:
            events.append((kind, dict(payload)))

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_sink)
        registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimConflictError):
            registry.acquire_claim("worktree-a", "agent-beta")
        conflict_events = [p for k, p in events if k == "claim_conflict"]
        assert len(conflict_events) == 1
        assert conflict_events[0]["conflict_kind"] == "CLAIM_CONFLICT"
        assert "current_fencing_token" in conflict_events[0]


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_happy_path_advances_heartbeat(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        updated = registry.heartbeat(
            "worktree-a", first.claim_id, "agent-alpha",
        )
        assert updated.heartbeat_at >= first.heartbeat_at
        assert updated.revision != first.revision

    def test_ownership_mismatch_raises(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimOwnershipError):
            registry.heartbeat("worktree-a", first.claim_id, "agent-beta")

    def test_wrong_claim_id_raises_ownership(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimOwnershipError):
            registry.heartbeat(
                "worktree-a",
                "22222222-2222-4222-8222-222222222222",  # wrong claim_id
                "agent-alpha",
            )

    def test_absent_claim_raises_already_released(self, tmp_path: Path) -> None:
        """W5v2 + B v4: absent claim file → ClaimAlreadyReleasedError
        (not silent no-op)."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimAlreadyReleasedError):
            registry.heartbeat(
                "never-existed",
                "11111111-1111-4111-8111-111111111111",
                "agent-alpha",
            )


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


class TestRelease:
    def test_happy_path_removes_claim_preserves_fencing(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        registry.release_claim(
            "worktree-a", first.claim_id, "agent-alpha",
        )
        assert registry.get_claim("worktree-a") is None

        # Fencing state retained: next acquire gets fencing_token=1
        second = registry.acquire_claim("worktree-a", "agent-beta")
        assert second.fencing_token == 1

    def test_second_release_raises_already_released(
        self, tmp_path: Path,
    ) -> None:
        """W5v2: second release on absent claim raises, not silent no-op."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        registry.release_claim(
            "worktree-a", first.claim_id, "agent-alpha",
        )
        with pytest.raises(ClaimAlreadyReleasedError):
            registry.release_claim(
                "worktree-a", first.claim_id, "agent-alpha",
            )

    def test_ownership_mismatch_on_release_raises(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimOwnershipError):
            registry.release_claim(
                "worktree-a", first.claim_id, "agent-beta",
            )

    def test_corrupt_fencing_raises_before_delete(
        self, tmp_path: Path,
    ) -> None:
        """B3v5 fail-closed order: corrupt _fencing.v1.json raises while
        the claim file is still recoverable on disk."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")

        # Corrupt the fencing state
        fencing_path = tmp_path / ".ao" / "claims" / "_fencing.v1.json"
        fencing_path.write_text("not json {{{")

        with pytest.raises(ClaimCorruptedError):
            registry.release_claim(
                "worktree-a", first.claim_id, "agent-alpha",
            )

        # Claim file NOT deleted — caller can recover after fixing fencing
        assert (
            tmp_path / ".ao" / "claims" / "worktree-a.v1.json"
        ).is_file()


# ---------------------------------------------------------------------------
# validate_fencing_token
# ---------------------------------------------------------------------------


class TestValidateFencingToken:
    def test_live_token_passes(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        claim = registry.acquire_claim("worktree-a", "agent-alpha")
        # Live issued token is fencing_token (which is next_token - 1 from
        # the fencing state perspective after acquire advances next_token).
        assert registry.validate_fencing_token(
            "worktree-a", claim.fencing_token,
        ) is None

    def test_stale_token_raises(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        registry.release_claim(
            "worktree-a", first.claim_id, "agent-alpha",
        )
        # New acquire advances fencing_token to 1; old token (0) is stale
        registry.acquire_claim("worktree-a", "agent-beta")
        with pytest.raises(ClaimStaleFencingError):
            registry.validate_fencing_token("worktree-a", 0)

    def test_future_token_raises(self, tmp_path: Path) -> None:
        """B2v3 exact-equality: supplied > live also raises."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimStaleFencingError):
            registry.validate_fencing_token("worktree-a", 99)


# ---------------------------------------------------------------------------
# list_agent_claims + live-count
# ---------------------------------------------------------------------------


class TestListAgentClaims:
    def test_returns_held_claims(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        registry.acquire_claim("worktree-b", "agent-alpha")
        registry.acquire_claim("worktree-c", "agent-beta")
        alpha_claims = registry.list_agent_claims("agent-alpha")
        resource_ids = {c.resource_id for c in alpha_claims}
        assert resource_ids == {"worktree-a", "worktree-b"}

    def test_empty_for_unknown_agent(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        assert registry.list_agent_claims("no-such-agent") == []


# ---------------------------------------------------------------------------
# Quota (B1v2 SSOT + B1v3 limit=0 unlimited)
# ---------------------------------------------------------------------------


class TestQuota:
    def test_limit_zero_is_unlimited(self, tmp_path: Path) -> None:
        """B1v3: max_claims_per_agent=0 ⇒ quota disabled."""
        _write_workspace_policy(
            tmp_path, _enabled_policy(max_claims_per_agent=0),
        )
        registry = ClaimRegistry(tmp_path)
        acquired = []
        for i in range(10):
            acquired.append(
                registry.acquire_claim(f"worktree-{i:02d}", "agent-alpha"),
            )
        # No quota exception raised; all 10 claims persisted with
        # monotonic per-resource fencing tokens (all first acquires → 0).
        assert len(acquired) == 10
        assert all(c.fencing_token == 0 for c in acquired)

    def test_positive_limit_enforced(self, tmp_path: Path) -> None:
        _write_workspace_policy(
            tmp_path, _enabled_policy(max_claims_per_agent=2),
        )
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        registry.acquire_claim("worktree-b", "agent-alpha")
        with pytest.raises(ClaimQuotaExceededError) as excinfo:
            registry.acquire_claim("worktree-c", "agent-alpha")
        assert excinfo.value.current_count == 2
        assert excinfo.value.limit == 2

    def test_released_claim_frees_quota_slot(self, tmp_path: Path) -> None:
        _write_workspace_policy(
            tmp_path, _enabled_policy(max_claims_per_agent=1),
        )
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        registry.release_claim(
            "worktree-a", first.claim_id, "agent-alpha",
        )
        # Same agent can acquire another resource after release
        second = registry.acquire_claim("worktree-b", "agent-alpha")
        assert second.owner_agent_id == "agent-alpha"


# ---------------------------------------------------------------------------
# SSOT corruption fail-closed
# ---------------------------------------------------------------------------


class TestSSOTCorruption:
    def test_corrupt_claim_file_raises(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        claim_file = tmp_path / ".ao" / "claims" / "worktree-a.v1.json"
        claim_file.write_text("not json {{{")

        with pytest.raises(ClaimCorruptedError):
            registry.get_claim("worktree-a")


# ---------------------------------------------------------------------------
# Evidence sink fail-open
# ---------------------------------------------------------------------------


class TestEvidenceSinkFailOpen:
    def test_sink_error_does_not_block_acquire(self, tmp_path: Path) -> None:
        """B3v2: evidence emit failure logged at warning; registry
        mutation succeeds regardless."""

        def _raising_sink(kind: str, payload: Any) -> None:
            raise RuntimeError("simulated evidence failure")

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_raising_sink)
        # Must succeed despite sink raising
        claim = registry.acquire_claim("worktree-a", "agent-alpha")
        assert claim.owner_agent_id == "agent-alpha"

    def test_no_sink_is_silent(self, tmp_path: Path) -> None:
        """B4v3: evidence_sink=None default is no-op, never raises."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)  # no sink
        claim = registry.acquire_claim("worktree-a", "agent-alpha")
        # Registry succeeded without a sink; assert claim carries the
        # expected identity (behavioral assertion beyond non-None).
        assert claim.owner_agent_id == "agent-alpha"
        assert claim.resource_id == "worktree-a"
        assert claim.fencing_token == 0


# ---------------------------------------------------------------------------
# Index drift + rebuild (W2v2 fail-open for derived cache)
# ---------------------------------------------------------------------------


class TestIndexDriftRebuild:
    def test_corrupt_index_rebuilds_silently(self, tmp_path: Path) -> None:
        """W2v2: corrupt _index.v1.json → rebuild from SSOT (fail-open
        for derived cache; SSOT itself must remain readable)."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        # Corrupt the derived index
        index_path = tmp_path / ".ao" / "claims" / "_index.v1.json"
        index_path.write_text("not json {{{")

        # list_agent_claims triggers _ensure_index_consistent + rebuild
        claims = registry.list_agent_claims("agent-alpha")
        assert len(claims) == 1
        assert claims[0].resource_id == "worktree-a"
