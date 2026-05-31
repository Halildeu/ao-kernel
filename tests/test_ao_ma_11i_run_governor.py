"""AO-MA-11I autonomous run governor tests.

Covers: schema validity, pure decide() continue/halt across PAUSE, clock
anomaly, every budget breach, fail-closed config/state errors, ordering
(PAUSE highest priority), is_paused() wrapper, and decision_to_artifact
schema conformance.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

import ao_kernel
from ao_kernel.orchestration.run_governor import (
    PAUSE_RELATIVE_PATH,
    GovernorDecision,
    RunGovernorError,
    decide,
    decision_to_artifact,
    is_paused,
)

_PKG = Path(ao_kernel.__file__).resolve().parent
_SCHEMAS = _PKG / "defaults" / "schemas"
_BUDGET_SCHEMA = _SCHEMAS / "ao-ma-run-budget.schema.v1.json"
_DECISION_SCHEMA = _SCHEMAS / "ao-ma-governor-decision.schema.v1.json"
_MODULE_SRC = _PKG / "orchestration" / "run_governor.py"

_ALLOWED_IMPORTS = {"__future__", "json", "dataclasses", "pathlib", "typing", "jsonschema"}


def _budget(**overrides: Any) -> dict[str, Any]:
    b: dict[str, Any] = {
        "schema_version": "ao-ma-run-budget.v1",
        "artifact_kind": "ao_ma_run_budget",
        "max_slices": 5,
        "max_consensus_rounds": 3,
        "max_retries_per_slice": 2,
        "max_total_retries": 10,
        "max_governor_steps": 100,
        "max_wall_clock_seconds": 3600,
        "max_total_output_tokens": 500000,
        "cost_tracking": {"available": False, "max_cost_usd": None},
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "github_write_authorized": False,
        "side_effect_authority": "none",
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "governor_authority": "run_continuation_only",
    }
    b.update(overrides)
    return b


def _state(**overrides: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "slices_started": 1,
        "current_consensus_rounds_used": 1,
        "retries_used": 0,
        "total_retries_used": 0,
        "governor_steps_used": 1,
        "started_at_epoch": 1_000_000,
        "total_output_tokens": 1000,
    }
    s.update(overrides)
    return s


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def test_budget_schema_valid() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-run-budget:v1"
    assert schema["additionalProperties"] is False


def test_decision_schema_valid() -> None:
    schema = json.loads(_DECISION_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-governor-decision:v1"


def test_sample_budget_satisfies_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(_budget())) == []


def test_budget_guard_flag_true_fails_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(_budget(live_adapter_execution=True)))


def test_budget_cost_available_true_fails_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    bad = _budget()
    bad["cost_tracking"] = {"available": True, "max_cost_usd": None}
    assert list(Draft202012Validator(schema).iter_errors(bad))


def test_budget_github_write_authorized_true_fails_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(_budget(github_write_authorized=True)))


def test_budget_side_effect_authority_nonnone_fails_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(_budget(side_effect_authority="executor")))


def test_budget_missing_governor_steps_cap_fails_schema() -> None:
    schema = json.loads(_BUDGET_SCHEMA.read_text(encoding="utf-8"))
    b = _budget()
    del b["max_governor_steps"]
    assert list(Draft202012Validator(schema).iter_errors(b))


def test_decision_schema_pins_three_guard_flags() -> None:
    schema = json.loads(_DECISION_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in schema["required"], f"{flag} must be required in the decision schema"
        assert props[flag]["const"] is False, f"{flag} must be const false"


# ---------------------------------------------------------------------------
# decide() — continue
# ---------------------------------------------------------------------------
def test_decide_continue_within_budget() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=False)
    assert isinstance(d, GovernorDecision)
    assert d.action == "continue"
    assert d.halt_reason is None
    assert d.breached_limits == []
    assert d.safe_stop_required is False
    assert d.escalation_required is False


# ---------------------------------------------------------------------------
# decide() — PAUSE highest priority
# ---------------------------------------------------------------------------
def test_decide_pause_halts() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=True)
    assert d.action == "halt"
    assert d.halt_reason == "operator_pause_flag"
    assert d.safe_stop_required is True
    assert d.escalation_required is True
    assert d.pause_present is True


def test_decide_pause_beats_budget_breach() -> None:
    # Even with a blown budget, PAUSE reason wins (highest priority).
    d = decide(budget=_budget(), state=_state(slices_started=999), now_epoch=9_999_999, pause_present=True)
    assert d.halt_reason == "operator_pause_flag"
    assert d.breached_limits == []


def test_decide_pause_beats_invalid_config() -> None:
    d = decide(budget={"bad": "config"}, state=_state(), now_epoch=1_000_100, pause_present=True)
    assert d.halt_reason == "operator_pause_flag"


# ---------------------------------------------------------------------------
# decide() — fail-closed config / state
# ---------------------------------------------------------------------------
def test_decide_invalid_budget_halts() -> None:
    d = decide(budget={"not": "a budget"}, state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.action == "halt"
    assert d.halt_reason == "config_invalid"


def test_decide_budget_missing_token_cap_halts() -> None:
    b = _budget()
    del b["max_total_output_tokens"]
    d = decide(budget=b, state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "config_invalid"


def test_decide_invalid_state_halts() -> None:
    # All axes present but one is negative -> state_invalid (not usage_axis_missing).
    d = decide(budget=_budget(), state=_state(slices_started=-1), now_epoch=1_000_100, pause_present=False)
    assert d.action == "halt"
    assert d.halt_reason == "state_invalid"


def test_decide_empty_state_is_usage_axis_missing() -> None:
    # A state with no counters at all -> usage_axis_missing (a configured cap
    # has no usage to check; fail-closed, never silent continue).
    d = decide(budget=_budget(), state={"started_at_epoch": 1_000_000}, now_epoch=1_000_100, pause_present=False)
    assert d.action == "halt"
    assert d.halt_reason == "usage_axis_missing"


def test_decide_unloadable_schema_halts_not_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # If the bundled schema cannot be loaded, decide() must NOT raise inside
    # the autonomous loop — it must return a fail-closed config_invalid halt.
    from ao_kernel.orchestration import run_governor

    monkeypatch.setattr(run_governor, "_SCHEMAS_DIR", tmp_path)  # empty dir, no schemas
    monkeypatch.setattr(run_governor, "_SCHEMA_CACHE", {})  # bypass warm cache
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.action == "halt"
    assert d.halt_reason == "config_invalid"


def test_artifact_carries_three_guard_flags() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=False)
    art = decision_to_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
    assert art["support_widening"] is False
    assert art["production_platform_claim"] is False
    assert art["live_adapter_execution"] is False


def test_validate_state_non_dict_is_state_invalid() -> None:
    # Defensive: a non-dict state is state_invalid (the public decide() always
    # passes a dict, so this exercises the validator's own guard directly).
    from ao_kernel.orchestration import run_governor

    result = run_governor._validate_state(cast(Any, [1, 2, 3]))
    assert result is not None
    reason, _msg = result
    assert reason == "state_invalid"


def test_decide_state_bool_is_not_int() -> None:
    # bool is a subclass of int; must be rejected as state_invalid.
    d = decide(budget=_budget(), state=_state(slices_started=True), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "state_invalid"


# ---------------------------------------------------------------------------
# decide() — clock anomaly
# ---------------------------------------------------------------------------
def test_decide_negative_elapsed_halts() -> None:
    d = decide(budget=_budget(), state=_state(started_at_epoch=2_000_000), now_epoch=1_000_000, pause_present=False)
    assert d.action == "halt"
    assert d.halt_reason == "clock_anomaly_negative_elapsed"


def test_decide_now_equals_start_is_continue() -> None:
    d = decide(budget=_budget(), state=_state(started_at_epoch=1_000_000), now_epoch=1_000_000, pause_present=False)
    assert d.action == "continue"


# ---------------------------------------------------------------------------
# decide() — each budget breach
# ---------------------------------------------------------------------------
def test_decide_wall_clock_breach() -> None:
    d = decide(budget=_budget(max_wall_clock_seconds=10), state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "wall_clock_exceeded"
    assert "max_wall_clock_seconds" in d.breached_limits


def test_decide_max_slices_breach() -> None:
    d = decide(budget=_budget(max_slices=1), state=_state(slices_started=2), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "max_slices_exceeded"
    assert "max_slices" in d.breached_limits


def test_decide_slices_equal_cap_halts() -> None:
    # used == cap must halt (>=, not >): gates whether the NEXT action may start.
    d = decide(budget=_budget(max_slices=3), state=_state(slices_started=3), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "max_slices_exceeded"


def test_decide_slices_below_cap_continues() -> None:
    # used < cap continues.
    d = decide(budget=_budget(max_slices=3), state=_state(slices_started=2), now_epoch=1_000_100, pause_present=False)
    assert d.action == "continue"


def test_decide_wall_clock_equal_cap_halts() -> None:
    # elapsed == cap must halt (>=). started_at 1_000_000, now 1_000_100 -> elapsed 100.
    d = decide(budget=_budget(max_wall_clock_seconds=100), state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.halt_reason == "wall_clock_exceeded"


def test_decide_wall_clock_below_cap_continues() -> None:
    d = decide(budget=_budget(max_wall_clock_seconds=101), state=_state(), now_epoch=1_000_100, pause_present=False)
    assert d.action == "continue"


def test_decide_total_retries_breach() -> None:
    d = decide(
        budget=_budget(max_total_retries=4),
        state=_state(total_retries_used=4),
        now_epoch=1_000_100,
        pause_present=False,
    )
    assert d.halt_reason == "max_total_retries_exceeded"
    assert "max_total_retries" in d.breached_limits


def test_decide_consensus_rounds_breach() -> None:
    # max_consensus_rounds is PER consensus cycle; compared to the current
    # cycle's round count (resets when a new plan consensus begins).
    d = decide(
        budget=_budget(max_consensus_rounds=1),
        state=_state(current_consensus_rounds_used=2),
        now_epoch=1_000_100,
        pause_present=False,
    )
    assert d.halt_reason == "max_consensus_rounds_exceeded"


def test_decide_governor_steps_is_global_run_ceiling() -> None:
    # The global run-length ceiling is max_governor_steps, independent of the
    # per-cycle consensus cap: a fresh consensus cycle (rounds=0) still halts
    # when the global step budget is exhausted.
    d = decide(
        budget=_budget(max_governor_steps=50),
        state=_state(current_consensus_rounds_used=0, governor_steps_used=50),
        now_epoch=1_000_100,
        pause_present=False,
    )
    assert d.halt_reason == "max_governor_steps_exceeded"


def test_decide_retries_breach() -> None:
    d = decide(
        budget=_budget(max_retries_per_slice=0), state=_state(retries_used=1), now_epoch=1_000_100, pause_present=False
    )
    assert d.halt_reason == "max_retries_exceeded"


def test_decide_tokens_breach() -> None:
    d = decide(
        budget=_budget(max_total_output_tokens=100),
        state=_state(total_output_tokens=101),
        now_epoch=1_000_100,
        pause_present=False,
    )
    assert d.halt_reason == "max_total_output_tokens_exceeded"


def test_decide_multiple_breaches_collected() -> None:
    d = decide(
        budget=_budget(max_slices=1, max_total_output_tokens=100),
        state=_state(slices_started=5, total_output_tokens=999),
        now_epoch=1_000_100,
        pause_present=False,
    )
    assert d.action == "halt"
    assert "max_slices" in d.breached_limits
    assert "max_total_output_tokens" in d.breached_limits


# ---------------------------------------------------------------------------
# is_paused() wrapper
# ---------------------------------------------------------------------------
def test_is_paused_false_when_absent(tmp_path: Path) -> None:
    assert is_paused(tmp_path) is False


def test_is_paused_true_when_present(tmp_path: Path) -> None:
    flag = tmp_path / PAUSE_RELATIVE_PATH
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("paused for review", encoding="utf-8")
    assert is_paused(tmp_path) is True


# ---------------------------------------------------------------------------
# decision_to_artifact
# ---------------------------------------------------------------------------
def test_artifact_continue_is_schema_valid() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=False)
    art = decision_to_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
    schema = json.loads(_DECISION_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(art)) == []
    assert art["action"] == "continue"


def test_artifact_halt_is_schema_valid() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=True)
    art = decision_to_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
    schema = json.loads(_DECISION_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(art)) == []
    assert art["action"] == "halt"
    assert art["safe_stop_required"] is True
    assert art["escalation_required"] is True


def test_artifact_governor_authority_pinned() -> None:
    d = decide(budget=_budget(), state=_state(), now_epoch=1_000_100, pause_present=False)
    art = decision_to_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
    assert art["governor_authority"] == "run_continuation_only"
    assert art["ai_output_release_authority"] is False
    assert art["github_write_authorized"] is False
    assert art["side_effect_authority"] == "none"


def test_load_schema_missing_raises() -> None:
    from ao_kernel.orchestration import run_governor

    with pytest.raises(RunGovernorError, match="failed to load bundled schema"):
        run_governor._load_schema("ao-ma-does-not-exist.schema.v1.json")


# ---------------------------------------------------------------------------
# Static guard: pure-policy import allowlist (no shell-out / no LLM)
# ---------------------------------------------------------------------------
def _imported_top_modules(src: str) -> set[str]:
    tree = ast.parse(src)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def test_module_import_allowlist() -> None:
    mods = _imported_top_modules(_MODULE_SRC.read_text(encoding="utf-8"))
    unexpected = mods - _ALLOWED_IMPORTS
    assert unexpected == set(), f"unexpected imports (shell-out/LLM risk): {sorted(unexpected)}"
    assert "subprocess" not in mods
    assert "os" not in mods
