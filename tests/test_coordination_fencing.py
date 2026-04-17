"""Tests for ``ao_kernel.coordination.fencing`` — persistent token state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.coordination.errors import (
    ClaimCorruptedError,
    ClaimRevisionConflictError,
    ClaimStaleFencingError,
)
from ao_kernel.coordination.fencing import (
    FencingState,
    ResourceFencingState,
    empty_fencing_revision,
    fencing_state_revision,
    load_fencing_state,
    next_token,
    save_fencing_state_cas,
    set_next_token,
    update_on_release,
    validate_fencing_token,
)


def _fencing_path(tmp_path: Path) -> Path:
    return tmp_path / ".ao" / "claims" / "_fencing.v1.json"


class TestLoadFencingState:
    def test_absent_file_returns_empty_state(self, tmp_path: Path) -> None:
        state = load_fencing_state(tmp_path)
        assert state.resources == {}

    def test_valid_file_roundtrips(self, tmp_path: Path) -> None:
        doc = {
            "schema_version": "1",
            "resources": {
                "res-a": {
                    "next_token": 3,
                    "last_owner_agent_id": "agent-x",
                    "last_released_at": "2026-04-17T09:00:00+00:00",
                },
            },
        }
        path = _fencing_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))
        state = load_fencing_state(tmp_path)
        assert state.resources["res-a"].next_token == 3
        assert state.resources["res-a"].last_owner_agent_id == "agent-x"

    def test_corrupt_json_raises(self, tmp_path: Path) -> None:
        path = _fencing_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        with pytest.raises(ClaimCorruptedError) as excinfo:
            load_fencing_state(tmp_path)
        assert "JSON decode" in str(excinfo.value)

    def test_schema_invalid_raises(self, tmp_path: Path) -> None:
        path = _fencing_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Missing required ``resources`` field
        path.write_text(json.dumps({"schema_version": "1"}))
        with pytest.raises(ClaimCorruptedError) as excinfo:
            load_fencing_state(tmp_path)
        assert "schema" in str(excinfo.value).lower()


class TestNextToken:
    def test_new_resource_issues_zero(self) -> None:
        state = FencingState(resources={})
        issued, new_state = next_token(state, "res-a")
        assert issued == 0
        assert new_state.resources["res-a"].next_token == 1

    def test_existing_resource_advances(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=5),
        })
        issued, new_state = next_token(state, "res-a")
        assert issued == 5
        assert new_state.resources["res-a"].next_token == 6

    def test_monotonic_across_many_issues(self) -> None:
        state = FencingState(resources={})
        tokens = []
        for _ in range(10):
            issued, state = next_token(state, "res-a")
            tokens.append(issued)
        assert tokens == list(range(10))

    def test_per_resource_independence(self) -> None:
        state = FencingState(resources={})
        a1, state = next_token(state, "res-a")
        b1, state = next_token(state, "res-b")
        a2, state = next_token(state, "res-a")
        assert a1 == 0 and b1 == 0 and a2 == 1

    def test_pure_function_does_not_mutate_input(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=5),
        })
        next_token(state, "res-a")
        # Original must be untouched
        assert state.resources["res-a"].next_token == 5


class TestValidateFencingToken:
    def test_live_token_passes(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=3),
        })
        # Live issued token is next_token - 1 = 2. Assert the value
        # survived construction and the call returns None on success.
        assert state.resources["res-a"].next_token == 3
        assert validate_fencing_token(state, "res-a", 2) is None

    def test_stale_token_raises(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=3),
        })
        with pytest.raises(ClaimStaleFencingError) as excinfo:
            validate_fencing_token(state, "res-a", 1)
        assert excinfo.value.supplied_token == 1
        assert excinfo.value.live_token == 2

    def test_future_token_raises(self) -> None:
        """Exact-equality semantics: future / fabricated tokens reject too."""
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=3),
        })
        with pytest.raises(ClaimStaleFencingError) as excinfo:
            validate_fencing_token(state, "res-a", 5)
        assert excinfo.value.supplied_token == 5
        assert excinfo.value.live_token == 2

    def test_missing_resource_raises(self) -> None:
        state = FencingState(resources={})
        with pytest.raises(ClaimStaleFencingError) as excinfo:
            validate_fencing_token(state, "res-a", 0)
        # Sentinel -1 signals "never issued"
        assert excinfo.value.live_token == -1


class TestUpdateOnRelease:
    def test_preserves_next_token(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=5, last_owner_agent_id=None),
        })
        new_state = update_on_release(state, "res-a", "agent-y", "2026-04-17T10:00:00+00:00")
        assert new_state.resources["res-a"].next_token == 5  # unchanged
        assert new_state.resources["res-a"].last_owner_agent_id == "agent-y"
        assert new_state.resources["res-a"].last_released_at == "2026-04-17T10:00:00+00:00"


class TestForwardOnlyReconcile:
    """Forward-only invariant check via ``set_next_token`` (caller-driven)."""

    def test_set_next_token_preserves_audit_fields(self) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(
                next_token=5,
                last_owner_agent_id="agent-x",
                last_released_at="2026-04-17T09:00:00+00:00",
            ),
        })
        new_state = set_next_token(state, "res-a", 7)
        assert new_state.resources["res-a"].next_token == 7
        assert new_state.resources["res-a"].last_owner_agent_id == "agent-x"

    def test_caller_must_enforce_monotonicity(self) -> None:
        """``set_next_token`` is a primitive; reconcile callers apply the
        ``max(current, recovered+1)`` rule themselves. The function does
        not enforce monotonicity (by design — facilitates test fixtures
        for the forward-only reconcile logic in the registry)."""
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=10),
        })
        # Set to a lower value — function allows; registry's reconcile
        # helper is the guard.
        rewound = set_next_token(state, "res-a", 3)
        assert rewound.resources["res-a"].next_token == 3


class TestFencingStateRevision:
    def test_revision_is_deterministic(self) -> None:
        state_dict = {
            "schema_version": "1",
            "resources": {"res-a": {"next_token": 5, "last_owner_agent_id": None, "last_released_at": None}},
        }
        assert fencing_state_revision(state_dict) == fencing_state_revision(state_dict)

    def test_revision_ignores_schema_version(self) -> None:
        """Revision is computed over ``resources`` only — schema_version
        changes to the container must not invalidate CAS tokens."""
        a = {"schema_version": "1", "resources": {}}
        b = {"schema_version": "2", "resources": {}}
        assert fencing_state_revision(a) == fencing_state_revision(b)

    def test_different_resources_yield_different_revisions(self) -> None:
        a = {"resources": {"res-a": {"next_token": 1, "last_owner_agent_id": None, "last_released_at": None}}}
        b = {"resources": {"res-a": {"next_token": 2, "last_owner_agent_id": None, "last_released_at": None}}}
        assert fencing_state_revision(a) != fencing_state_revision(b)

    def test_empty_revision_helper_matches_manual(self) -> None:
        assert empty_fencing_revision() == fencing_state_revision({"resources": {}})


class TestSaveFencingStateCas:
    def test_first_write_with_empty_baseline(self, tmp_path: Path) -> None:
        state = FencingState(resources={
            "res-a": ResourceFencingState(next_token=1),
        })
        save_fencing_state_cas(
            tmp_path, state, expected_revision=empty_fencing_revision(),
        )
        path = _fencing_path(tmp_path)
        assert path.exists()
        on_disk = json.loads(path.read_text())
        assert on_disk["resources"]["res-a"]["next_token"] == 1

    def test_cas_conflict_on_second_write(self, tmp_path: Path) -> None:
        state1 = FencingState(resources={"res-a": ResourceFencingState(next_token=1)})
        save_fencing_state_cas(
            tmp_path, state1, expected_revision=empty_fencing_revision(),
        )
        # Second writer thinks it's still at empty baseline — conflict
        state2 = FencingState(resources={"res-a": ResourceFencingState(next_token=2)})
        with pytest.raises(ClaimRevisionConflictError):
            save_fencing_state_cas(
                tmp_path, state2, expected_revision=empty_fencing_revision(),
            )

    def test_cas_round_trip(self, tmp_path: Path) -> None:
        state1 = FencingState(resources={"res-a": ResourceFencingState(next_token=1)})
        save_fencing_state_cas(
            tmp_path, state1, expected_revision=empty_fencing_revision(),
        )
        # Second writer uses correct post-first-write revision
        on_disk_rev = fencing_state_revision(load_fencing_state(tmp_path).to_dict())
        state2 = FencingState(resources={"res-a": ResourceFencingState(next_token=2)})
        save_fencing_state_cas(tmp_path, state2, expected_revision=on_disk_rev)
        assert load_fencing_state(tmp_path).resources["res-a"].next_token == 2

    def test_corrupt_on_disk_raises_pre_cas(self, tmp_path: Path) -> None:
        path = _fencing_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        state = FencingState(resources={})
        with pytest.raises(ClaimCorruptedError):
            save_fencing_state_cas(
                tmp_path, state, expected_revision="sha256:" + "0" * 64,
            )
