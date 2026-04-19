"""Success-criteria assertions for PR-B7 benchmarks.

Helpers map `docs/BENCHMARK-SUITE.md §5` contracts onto pytest
asserts. `cost_usd` reconcile is deferred to B7.1 — v1 only
verifies that the budget axis was seeded on the run (not that
actual spend landed on the axis).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


_SEVERITY_ENUM = frozenset({"error", "warning", "info", "note"})


def assert_workflow_completed(run_dir: Path) -> None:
    events = _iter_events(run_dir)
    kinds = [event.get("kind") for event in events]
    assert "workflow_completed" in kinds, (
        f"expected workflow_completed event in {run_dir / 'events.jsonl'!s}; saw: {kinds[-5:]!r}"
    )


def assert_workflow_failed(
    run_dir: Path,
    *,
    expected_category: str,
) -> None:
    """Assert a `workflow_failed` evidence event fired with the
    given error category. The event payload carries
    `{category, code, failed_step, reason}`; callers supply the
    expected `category` enum value from the runtime mapping
    (`timeout`, `invocation_failed`, `output_parse_failed`,
    `policy_denied`, `budget_exhausted`, `adapter_crash`,
    `other`)."""
    events = _iter_events(run_dir)
    terminal = [event for event in events if event.get("kind") == "workflow_failed"]
    assert terminal, f"expected workflow_failed event in {run_dir / 'events.jsonl'!s}"
    last = terminal[-1]
    payload = last.get("payload") or {}
    category = payload.get("category") or (last.get("error", {}) or {}).get("category")
    assert category == expected_category, f"expected error.category={expected_category!r}; got {category!r}"


def assert_adapter_ok(step_record: Mapping[str, Any]) -> None:
    """Assert the step completed successfully. Run-store records
    carry a `state` field ("completed" on success); the
    transport-layer "status=ok" signal is separately preserved in
    the evidence event stream via the `adapter_returned` payload."""
    state = step_record.get("state")
    assert state == "completed", (
        f"expected step state=='completed' for step {step_record.get('step_name')!r}; got {state!r}"
    )


def assert_capability_artifact(
    step_record: Mapping[str, Any],
    capability: str,
    run_dir: Path,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    refs = step_record.get("capability_output_refs") or {}
    ref = refs.get(capability)
    assert ref, (
        f"step {step_record.get('step_id')!r} missing capability_output_refs[{capability!r}]; saw keys {list(refs)!r}"
    )
    artifact_path = run_dir / ref
    assert artifact_path.is_file(), f"capability artifact file missing: {artifact_path!s}"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if schema_path is not None:
        _validate_json_schema(payload, schema_path)
    return payload


def assert_review_score(
    review_findings: Mapping[str, Any],
    *,
    expected_min_score: float = 0.5,
) -> None:
    findings = review_findings.get("findings") or []
    assert isinstance(findings, list)
    for finding in findings:
        severity = finding.get("severity")
        assert severity in _SEVERITY_ENUM, (
            f"unexpected severity {severity!r}; must be one of {sorted(_SEVERITY_ENUM)!r}"
        )
    score = review_findings.get("score")
    if score is None:
        return
    assert isinstance(score, (int, float))
    assert float(score) >= expected_min_score, f"review score {score!r} below threshold {expected_min_score!r}"


def assert_cost_consumed(
    run_state: Mapping[str, Any],
    axis: str = "cost_usd",
    *,
    min_consumed: float = 0.0,
) -> float:
    """Assert that the given budget axis has been drained by at
    least ``min_consumed``. Returns the consumed amount so callers
    can make additional assertions.

    v3.7 F2 absorb: the benchmark-only ``_maybe_consume_budget`` shim
    has been removed. Fast-mode mock runs NO LONGER drain
    ``budget.cost_usd``; call sites that used this helper against
    fast-mode runs should switch to the narrower
    :func:`assert_budget_unchanged` / :func:`assert_spend_recorded_event`
    helpers (defined below). This helper stays semantically correct —
    it checks run-state budget drain — but under the current
    fast-mode contract the drain is always 0 unless a full-mode
    adapter-path reconcile has run.
    """
    budget = run_state.get("budget") or {}
    axis_data = budget.get(axis) or {}
    limit = axis_data.get("limit")
    remaining = axis_data.get("remaining")
    assert limit is not None and remaining is not None, (
        f"budget axis {axis!r} missing limit/remaining; run_state budget={budget!r}"
    )
    consumed = float(limit) - float(remaining)
    assert consumed >= min_consumed, f"budget axis {axis!r} consumed {consumed!r} below min_consumed {min_consumed!r}"
    return consumed


def assert_budget_axis_seeded(
    run_state: Mapping[str, Any],
    axis: str,
    expected_limit: float,
) -> None:
    budget = run_state.get("budget") or {}
    axis_data = budget.get(axis) or {}
    limit = axis_data.get("limit")
    assert limit is not None, f"budget axis {axis!r} missing limit; run_state budget={budget!r}"
    assert float(limit) == float(expected_limit), f"budget axis {axis!r} limit {limit!r} != {expected_limit!r}"


def resume_past_approval_gate(
    driver: Any,
    run_id: str,
    resume_token: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    """Wrap `driver.resume_workflow(run_id, resume_token, payload=...)`
    so benchmark tests do not tangle directly with the real API
    signature if it evolves."""
    driver.resume_workflow(run_id, resume_token, payload=payload or {})


def read_awaiting_human_token(run_dir: Path) -> str:
    """Scan `events.jsonl` for the latest awaiting-human-gate event
    and return its `resume_token` so tests can feed it to
    `resume_past_approval_gate`. Raises if not found."""
    events = _iter_events(run_dir)
    for event in reversed(list(events)):
        if event.get("kind") in (
            "human_gate_awaited",
            "workflow_awaiting_human",
            "step_awaiting_human",
        ):
            token = event.get("resume_token") or event.get("token")
            if isinstance(token, str):
                return token
    raise AssertionError(f"no awaiting-human-gate event with resume_token in {run_dir / 'events.jsonl'!s}")


def _iter_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _validate_json_schema(payload: Any, schema_path: Path) -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)


# ── v3.7 F2 helpers ──────────────────────────────────────────────────


def assert_budget_unchanged(
    run_state: Mapping[str, Any],
    *,
    axis: str = "cost_usd",
) -> None:
    """Assert the given budget axis was NOT drained (limit == remaining).

    v3.7 F2: fast-mode mock runs no longer drain ``cost_usd`` after
    the ``_maybe_consume_budget`` shim was removed. Use this helper
    to pin the new fast-mode contract.
    """
    budget = run_state.get("budget") or {}
    axis_data = budget.get(axis) or {}
    limit = axis_data.get("limit")
    remaining = axis_data.get("remaining")
    assert limit is not None and remaining is not None, (
        f"budget axis {axis!r} missing limit/remaining; run_state budget={budget!r}"
    )
    assert float(limit) == float(remaining), (
        f"budget axis {axis!r} was drained "
        f"(limit={limit!r}, remaining={remaining!r}); "
        "v3.7 F2 fast-mode contract expects no drain"
    )


def assert_spend_recorded_event(
    run_dir: Path,
    *,
    source: str = "adapter_path",
) -> dict[str, Any]:
    """Assert at least one ``llm_spend_recorded`` event fired in the
    run's ``events.jsonl`` with the given ``source`` payload.

    v3.7 F2 full-mode contract — real adapter-path reconcile emits
    these events via ``ao_kernel.cost.middleware.post_adapter_reconcile``.
    Returns the matching event dict for additional assertions.
    """
    events = _iter_events(run_dir)
    for event in events:
        if event.get("kind") != "llm_spend_recorded":
            continue
        payload = event.get("payload") or {}
        if isinstance(payload, Mapping) and payload.get("source") == source:
            return dict(event)
    raise AssertionError(
        f"expected llm_spend_recorded event with source={source!r} in "
        f"{run_dir / 'events.jsonl'!s}; observed kinds: "
        f"{sorted({e.get('kind') for e in events})!r}"
    )


__all__ = [
    "assert_adapter_ok",
    "assert_budget_axis_seeded",
    "assert_budget_unchanged",
    "assert_capability_artifact",
    "assert_cost_consumed",
    "assert_review_score",
    "assert_spend_recorded_event",
    "assert_workflow_completed",
    "assert_workflow_failed",
    "read_awaiting_human_token",
    "resume_past_approval_gate",
]
