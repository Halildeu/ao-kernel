"""Tests for ``ao_kernel.workflow.state_machine``.

Exhaustive transition-matrix test plus terminal invariants and unknown-
state rejection. Uses a literal expected table (plan v2 W1) — no
schema-narrative parsing at test time.
"""

from __future__ import annotations

import pytest

from ao_kernel.workflow import (
    TERMINAL_STATES,
    TRANSITIONS,
    WorkflowTransitionError,
    allowed_next,
    is_terminal,
    validate_transition,
)

# Literal expected table — hand-maintained; mirrors the schema narrative
# in ao_kernel/defaults/schemas/workflow-run.schema.v1.json state_enum.
# Schema is PR-A0 frozen; any drift requires an explicit update here.
_EXPECTED_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"running", "cancelled"}),
    "running": frozenset(
        {"interrupted", "waiting_approval", "applying", "failed", "cancelled"}
    ),
    "interrupted": frozenset({"running", "failed", "cancelled"}),
    "waiting_approval": frozenset({"applying", "failed", "cancelled"}),
    "applying": frozenset({"verifying", "failed", "cancelled"}),
    "verifying": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class TestTransitionsTable:
    def test_transitions_match_expected_table(self) -> None:
        """TRANSITIONS constant equals the literal expected table."""
        assert dict(TRANSITIONS) == _EXPECTED_TRANSITIONS

    def test_nine_states(self) -> None:
        assert len(TRANSITIONS) == 9

    def test_terminal_states_constant(self) -> None:
        assert TERMINAL_STATES == frozenset({"completed", "failed", "cancelled"})


class TestTerminalInvariant:
    @pytest.mark.parametrize("state", list(_EXPECTED_TRANSITIONS.keys()))
    def test_terminal_matches_empty_next(self, state: str) -> None:
        """`is_terminal` agrees with `TERMINAL_STATES` and with `allowed_next == ∅`."""
        term = is_terminal(state)
        assert term == (state in TERMINAL_STATES)
        assert term == (allowed_next(state) == frozenset())


class TestValidateTransitionMatrix:
    @pytest.mark.parametrize(
        "current,new",
        [
            (c, n)
            for c, allowed in _EXPECTED_TRANSITIONS.items()
            for n in allowed
        ],
    )
    def test_allowed_transitions(self, current: str, new: str) -> None:
        """Every ``(current, new)`` pair in the expected table validates."""
        # validate_transition is void; success = no exception raised.
        validate_transition(current, new)
        # Cross-check the allowed-next set exposes the same pair.
        assert new in allowed_next(current)

    @pytest.mark.parametrize(
        "current,new",
        [
            (c, n)
            for c, allowed in _EXPECTED_TRANSITIONS.items()
            for n in _EXPECTED_TRANSITIONS
            if n not in allowed
        ],
    )
    def test_illegal_transitions_raise(self, current: str, new: str) -> None:
        """Every forbidden pair raises ``WorkflowTransitionError`` with context."""
        with pytest.raises(WorkflowTransitionError) as ei:
            validate_transition(current, new)
        err = ei.value
        assert err.current_state == current
        assert err.attempted_state == new
        assert err.allowed_next == _EXPECTED_TRANSITIONS[current]


class TestUnknownStateRejection:
    def test_unknown_current_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_transition("nonsense", "running")

    def test_unknown_new_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_transition("created", "nonsense")

    def test_unknown_is_terminal_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            is_terminal("nonsense")

    def test_unknown_allowed_next_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            allowed_next("nonsense")


class TestImmutabilityOfTransitions:
    def test_transitions_frozen_values(self) -> None:
        """Each allowed-next set is a frozenset (hashable, immutable)."""
        for state, next_set in TRANSITIONS.items():
            assert isinstance(next_set, frozenset), state
