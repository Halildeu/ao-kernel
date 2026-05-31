"""AO-MA-11I autonomous run governor (v1).

The safety belt for an autonomous AO-MA run. Before each step the governor is
asked whether the run may continue: it reads the run budget, the run state, an
injected ``now`` and whether the operator PAUSE flag is present, and returns a
``GovernorDecision`` of ``continue`` or ``halt``. It is a PURE-DECISION policy
— the same shape as ``plan_consensus`` and ``ao_ma_next``:

- **No side effects, deterministic, never raises** — it does not write
  checkpoints, call the network, shell out, or invoke an LLM. It validates the
  budget/state against the bundled schemas, which are read once and cached
  in-memory (a packaged resource, not mutable state), so after warm-up
  ``decide()`` does no per-call filesystem read. ``decide()`` NEVER raises:
  even an unloadable schema becomes a fail-closed ``config_invalid`` halt, so
  an exception can never escape into the autonomous loop. On ``halt`` it sets
  ``safe_stop_required`` so the *executor* (not the governor) writes the
  safe-stop checkpoint, and ``escalation_required`` so AO-MA-11H notifies the
  operator. The executor integration + atomic checkpoint write are
  AO-MA-11I-2 (this slice is the pure policy only).
- **PAUSE is highest priority** — if the operator PAUSE flag is present the run
  halts before any budget check. PAUSE is a local-authoritative file
  (``.ao/autonomous/PAUSE``); a GitHub status/issue/label is never a pause
  (a remote signal would add polling latency and an unreachable-GitHub
  ambiguity). Its content is irrelevant; presence is the signal.
- **Fail-closed** — a missing/invalid budget or state, a configured budget
  axis whose usage counter is absent from run state (``usage_axis_missing``),
  a negative elapsed time (clock anomaly), or any schema breach halts the run.
  There is no ``null = unlimited``; every budget limit is an explicit cap.
- **Counter semantics are ``used >= cap``** (not ``>``). The governor answers
  "may the NEXT autonomous action start?", so a run that has already used its
  cap must halt before starting one more — ``>`` would let one extra step
  through (Codex off-by-one). Wall-clock is also ``>=`` and additionally acts
  as the implicit last-resort brake for a consensus-round deadlock (Mavis).
- **Not release authority** — ``governor_authority`` is pinned
  ``run_continuation_only``; ``github_write_authorized`` false;
  ``side_effect_authority`` none. The governor decides run continuation,
  never merge/release, never a write.

``now`` is injected (epoch seconds) so decisions are deterministic and
testable; the governor never reads the wall clock itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"
_RUN_BUDGET_SCHEMA_NAME = "ao-ma-run-budget.schema.v1.json"
_GOVERNOR_DECISION_SCHEMA_NAME = "ao-ma-governor-decision.schema.v1.json"

# Operator kill-switch: presence of this file under the workspace root halts
# the run. It is local-authoritative; its content is optional.
PAUSE_RELATIVE_PATH = ".ao/autonomous/PAUSE"

GovernorAction = Literal["continue", "halt"]
HaltReason = Literal[
    "operator_pause_flag",
    "wall_clock_exceeded",
    "max_slices_exceeded",
    "max_consensus_rounds_exceeded",
    "max_retries_exceeded",
    "max_total_retries_exceeded",
    "max_governor_steps_exceeded",
    "max_total_output_tokens_exceeded",
    "clock_anomaly_negative_elapsed",
    "usage_axis_missing",
    "config_invalid",
    "state_invalid",
]

# Each budget cap maps to the run-state usage counter it limits and the
# halt_reason raised when that counter reaches the cap. Order matters: the
# first breach in iteration order becomes the primary halt_reason. Wall-clock
# is handled separately (it compares elapsed, not a state counter).
#
# Axis semantics (Codex post-impl review absorb — no ambiguous axis):
# - max_consensus_rounds is PER consensus cycle, so it is compared against
#   ``current_consensus_rounds_used`` (the rounds used in the ACTIVE 3-AI
#   consensus; the executor resets this to 0 when a new plan consensus
#   begins). The GLOBAL run-length ceiling is ``max_governor_steps``, so a
#   per-cycle consensus cap does not need to also bound the whole run.
# - All other counters are cumulative for the run.
_COUNTER_CHECKS: tuple[tuple[str, str, HaltReason], ...] = (
    ("max_slices", "slices_started", "max_slices_exceeded"),
    ("max_consensus_rounds", "current_consensus_rounds_used", "max_consensus_rounds_exceeded"),
    ("max_retries_per_slice", "retries_used", "max_retries_exceeded"),
    ("max_total_retries", "total_retries_used", "max_total_retries_exceeded"),
    ("max_governor_steps", "governor_steps_used", "max_governor_steps_exceeded"),
    ("max_total_output_tokens", "total_output_tokens", "max_total_output_tokens_exceeded"),
)

# Run-state usage counters that must be present + non-negative ints. Each
# corresponds to a configured budget axis; a missing one is usage_axis_missing
# (fail-closed: "don't know usage -> halt", never continue).
_REQUIRED_STATE_COUNTERS = (
    "slices_started",
    "current_consensus_rounds_used",
    "retries_used",
    "total_retries_used",
    "governor_steps_used",
    "total_output_tokens",
)
_REQUIRED_STATE_FIELDS = ("started_at_epoch", *_REQUIRED_STATE_COUNTERS)


class RunGovernorError(RuntimeError):
    """Raised for schema-load failures. Policy outcomes (halt) are NOT raised.

    A malformed budget or state is NOT raised either — it is a fail-closed
    ``halt`` decision (config_invalid / state_invalid / usage_axis_missing),
    because the governor's whole job is to stop the run safely rather than
    throw inside an autonomous loop. This error type is reserved for the
    bundled schema being unloadable.
    """


@dataclass
class GovernorDecision:
    """The governor's continue/halt decision for one check point."""

    action: GovernorAction
    halt_reason: HaltReason | None
    breached_limits: list[str]
    safe_stop_required: bool
    escalation_required: bool
    pause_present: bool
    diagnostics: list[str] = field(default_factory=list)


# Bundled schemas are loaded once and cached in-memory. After the first load
# decide() is pure over its inputs and these cached dicts — it performs no
# per-call filesystem read, no network, no subprocess, no LLM, and (see below)
# never raises. A bundled schema is a packaged resource, not mutable state.
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema(name: str) -> dict[str, Any]:
    """Load + cache a bundled schema. Raises RunGovernorError if unloadable.

    Callers inside ``decide()`` route this through ``_validate_*`` which
    converts an unloadable schema into a fail-closed halt rather than letting
    the exception escape the autonomous loop.
    """

    cached = _SCHEMA_CACHE.get(name)
    if cached is not None:
        return cached
    try:
        schema = cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunGovernorError(f"failed to load bundled schema {name!r}: {exc}") from exc
    _SCHEMA_CACHE[name] = schema
    return schema


def is_paused(workspace_root: Path) -> bool:
    """Thin I/O wrapper: True iff the operator PAUSE flag entry is present.

    "Present" means any filesystem entry at ``.ao/autonomous/PAUSE`` —
    including a **dangling symlink**. ``Path.exists()`` follows symlinks and
    returns False for a broken one, so we OR it with ``Path.is_symlink()``
    (which is True for a broken symlink). The safer reading of "the operator
    dropped a PAUSE marker" is to halt on any present entry. Kept separate
    from ``decide`` so the decision logic stays pure (no I/O).
    """

    flag = workspace_root / PAUSE_RELATIVE_PATH
    return flag.exists() or flag.is_symlink()


def _halt(
    reason: HaltReason,
    *,
    breached_limits: list[str],
    pause_present: bool,
    diagnostics: list[str],
) -> GovernorDecision:
    return GovernorDecision(
        action="halt",
        halt_reason=reason,
        breached_limits=breached_limits,
        safe_stop_required=True,
        escalation_required=True,
        pause_present=pause_present,
        diagnostics=diagnostics,
    )


def _validate_budget(budget: dict[str, Any]) -> str | None:
    """Return None if budget is schema-valid, else a short error string.

    A schema that cannot be loaded is ALSO an error string (not a raise), so
    ``decide()`` converts it into a fail-closed ``config_invalid`` halt rather
    than throwing inside the autonomous loop.
    """

    try:
        schema = _load_schema(_RUN_BUDGET_SCHEMA_NAME)
        Draft202012Validator(schema).validate(budget)
    except ValidationError as exc:
        return f"budget invalid: {exc.message} (at {list(exc.absolute_path)})"
    except RunGovernorError as exc:
        return f"budget schema unavailable: {exc}"
    return None


def _validate_state(state: dict[str, Any]) -> tuple[HaltReason, str] | None:
    """Validate run state. Return None if valid, else ``(reason, message)``.

    Distinguishes the two fail-closed cases at the point that knows them:
    - a required usage axis is ABSENT → ``usage_axis_missing`` (a configured
      cap has no usage to check; never a silent continue).
    - a field is present but malformed (non-int, bool, or negative) →
      ``state_invalid``. bool is rejected even though it subclasses int.
    """

    if not isinstance(state, dict):
        return ("state_invalid", f"run state must be an object, got {type(state).__name__}")
    for fieldname in _REQUIRED_STATE_FIELDS:
        if fieldname not in state:
            return ("usage_axis_missing", f"state.{fieldname} is absent; configured cap has no usage to check")
        value = state[fieldname]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return ("state_invalid", f"state.{fieldname} must be a non-negative integer, got {value!r}")
    return None


def decide(
    *,
    budget: dict[str, Any],
    state: dict[str, Any],
    now_epoch: int,
    pause_present: bool,
) -> GovernorDecision:
    """Decide whether the autonomous run may continue (pure, no I/O).

    Order (fail-closed, highest priority first):
    1. PAUSE present → halt (operator kill-switch, authoritative).
    2. budget schema-invalid → halt (config_invalid).
    3. state malformed / usage axis missing → halt (state_invalid).
    4. negative elapsed (now < started_at) → halt (clock_anomaly).
    5. any budget limit reached (used >= cap) → halt with breached_limits.
    6. otherwise → continue.
    """

    # 1. PAUSE — highest priority, before any other check.
    if pause_present:
        return _halt(
            "operator_pause_flag",
            breached_limits=[],
            pause_present=True,
            diagnostics=["operator PAUSE flag present; run halted (kill-switch)"],
        )

    # 2. Budget config must be schema-valid (fail-closed).
    budget_err = _validate_budget(budget)
    if budget_err is not None:
        return _halt("config_invalid", breached_limits=[], pause_present=False, diagnostics=[budget_err])

    # 3. State must be well-formed; every configured axis must report usage
    #    (usage_axis_missing rather than a silent continue). _validate_state
    #    returns the precise (reason, message) so the caller stays branch-flat.
    state_check = _validate_state(state)
    if state_check is not None:
        state_reason, state_msg = state_check
        return _halt(state_reason, breached_limits=[], pause_present=False, diagnostics=[state_msg])

    # 4. Clock anomaly: now before run start means a tampered/rewound clock.
    started_at = state["started_at_epoch"]
    if now_epoch < started_at:
        return _halt(
            "clock_anomaly_negative_elapsed",
            breached_limits=[],
            pause_present=False,
            diagnostics=[f"now_epoch {now_epoch} < started_at_epoch {started_at}; negative elapsed"],
        )

    # 5. Budget breaches — recomputed from budget + state (never trusted from
    #    input). "used >= cap" because the governor gates the NEXT action.
    breached: list[str] = []
    diagnostics: list[str] = []
    elapsed = now_epoch - started_at
    if elapsed >= budget["max_wall_clock_seconds"]:
        breached.append("max_wall_clock_seconds")
        diagnostics.append(f"elapsed {elapsed}s >= max_wall_clock_seconds {budget['max_wall_clock_seconds']}")
    for cap_key, counter_key, _reason in _COUNTER_CHECKS:
        if state[counter_key] >= budget[cap_key]:
            breached.append(cap_key)
            diagnostics.append(f"{counter_key} {state[counter_key]} >= {cap_key} {budget[cap_key]}")

    if breached:
        reason = _BREACH_REASON[breached[0]]
        return _halt(reason, breached_limits=breached, pause_present=False, diagnostics=diagnostics)

    # 6. All clear.
    return GovernorDecision(
        action="continue",
        halt_reason=None,
        breached_limits=[],
        safe_stop_required=False,
        escalation_required=False,
        pause_present=False,
        diagnostics=["within budget; run may continue"],
    )


# First-breach → halt_reason mapping. Wall-clock first (it is checked first and
# also serves as the implicit last-resort brake for a consensus deadlock), then
# the counter axes in _COUNTER_CHECKS order.
_BREACH_REASON: dict[str, HaltReason] = {
    "max_wall_clock_seconds": "wall_clock_exceeded",
    **{cap_key: reason for cap_key, _counter, reason in _COUNTER_CHECKS},
}


def decision_to_artifact(decision: GovernorDecision, *, evaluated_at: str) -> dict[str, Any]:
    """Render a GovernorDecision as a schema-valid ao-ma-governor-decision.v1 dict.

    ``evaluated_at`` is supplied by the caller (stamped from the injected now)
    so this function stays pure. The result validates against
    ``ao-ma-governor-decision.schema.v1.json``.
    """

    artifact = {
        "schema_version": "ao-ma-governor-decision.v1",
        "artifact_kind": "ao_ma_governor_decision",
        "action": decision.action,
        "halt_reason": decision.halt_reason,
        "breached_limits": decision.breached_limits,
        "safe_stop_required": decision.safe_stop_required,
        "escalation_required": decision.escalation_required,
        "pause_present": decision.pause_present,
        "evaluated_at": evaluated_at,
        "governor_authority": "run_continuation_only",
        "ai_output_release_authority": False,
        "github_write_authorized": False,
        "side_effect_authority": "none",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    schema = _load_schema(_GOVERNOR_DECISION_SCHEMA_NAME)
    try:
        Draft202012Validator(schema).validate(artifact)
    except ValidationError as exc:  # pragma: no cover - defensive; render is total by construction
        raise RunGovernorError(f"rendered governor decision failed schema: {exc.message}") from exc
    return artifact
