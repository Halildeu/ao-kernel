"""Workflow state machine.

Pure functional implementation of the 9-state workflow run transition
model defined by ``workflow-run.schema.v1.json``'s ``state_enum``.

State-change validation is stateless: the function's output depends only
on its inputs. The module has no runtime mutable state; ``TRANSITIONS``
is an immutable ``frozenset``-valued mapping.

Allowed states (mirrors the schema narrative):

    created           -- initial, not yet started
    running           -- active step in progress
    interrupted       -- adapter HITL raise (adapter interrupt_token)
    waiting_approval  -- governance gate (approval_token)
    applying          -- diff apply in progress
    verifying         -- CI gate running
    completed         -- terminal success
    failed            -- terminal failure
    cancelled         -- terminal cancel

Terminal states have no outgoing transitions. ``is_terminal`` returns
``True`` for those and ``False`` for all others.

Transition table is a literal expected table (plan v2 W1 fix); we do
NOT parse the schema narrative at runtime. Schema drift is exceptional
and surfaces via the explicit transition-matrix test.
"""

from __future__ import annotations

from typing import Final, Literal, Mapping

from ao_kernel.workflow.errors import WorkflowTransitionError

WorkflowState = Literal[
    "created",
    "running",
    "interrupted",
    "waiting_approval",
    "applying",
    "verifying",
    "completed",
    "failed",
    "cancelled",
]

_ALL_STATES: Final[frozenset[str]] = frozenset({
    "created",
    "running",
    "interrupted",
    "waiting_approval",
    "applying",
    "verifying",
    "completed",
    "failed",
    "cancelled",
})

TERMINAL_STATES: Final[frozenset[str]] = frozenset({"completed", "failed", "cancelled"})


def _build_transition_table() -> Mapping[str, frozenset[str]]:
    """Build the immutable transition table.

    Literal expected table per plan v2 §5 (W1 fix); mirrors the narrative
    in ``workflow-run.schema.v1.json::state_enum.description``. Schema is
    PR-A0 frozen; any drift requires explicit test + table update.
    """
    return {
        "created": frozenset({"running", "cancelled"}),
        "running": frozenset({
            "interrupted",
            "waiting_approval",
            "applying",
            "failed",
            "cancelled",
        }),
        "interrupted": frozenset({"running", "failed", "cancelled"}),
        "waiting_approval": frozenset({"applying", "failed", "cancelled"}),
        "applying": frozenset({"verifying", "failed", "cancelled"}),
        "verifying": frozenset({"completed", "failed", "cancelled"}),
        "completed": frozenset(),
        "failed": frozenset(),
        "cancelled": frozenset(),
    }


TRANSITIONS: Final[Mapping[str, frozenset[str]]] = _build_transition_table()


def is_terminal(state: str) -> bool:
    """Return True if ``state`` is a terminal state.

    Raises ``ValueError`` if ``state`` is not a known workflow state.
    """
    _check_state(state)
    return state in TERMINAL_STATES


def allowed_next(current: str) -> frozenset[str]:
    """Return the set of states reachable from ``current`` by one transition.

    Returns an empty ``frozenset`` for terminal states. Raises
    ``ValueError`` if ``current`` is not a known workflow state.
    """
    _check_state(current)
    return TRANSITIONS[current]


def validate_transition(current: str, new: str) -> None:
    """Validate that ``current -> new`` is a legal transition.

    Raises ``WorkflowTransitionError`` if the transition is not allowed.
    Raises ``ValueError`` if either argument is not a known workflow state;
    unknown states are treated as programming errors, not illegal
    transitions.
    """
    _check_state(current)
    _check_state(new)
    allowed = TRANSITIONS[current]
    if new not in allowed:
        raise WorkflowTransitionError(
            current_state=current,
            attempted_state=new,
            allowed_next=allowed,
        )


def _check_state(state: str) -> None:
    """Reject unknown workflow state strings upfront.

    Raises ``ValueError`` (not ``WorkflowTransitionError``) because an
    unknown state is a programming bug, not a runtime lifecycle mismatch.
    """
    if state not in _ALL_STATES:
        raise ValueError(
            f"Unknown workflow state: {state!r}; "
            f"known: {sorted(_ALL_STATES)}"
        )
