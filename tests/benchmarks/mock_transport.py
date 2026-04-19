"""Mock transport for PR-B7 benchmarks.

Public-function boundary: `ao_kernel.executor.executor.invoke_cli`
and `invoke_http` are patched at the executor's local import site
(the executor binds `from adapter_invoker import invoke_cli` at
module load, so patching the executor alias is the only place an
unittest.mock hook actually intercepts). Orchestrator + driver +
executor + adapter_invoker call site chain stays real; only the
final wrapper fn is substituted for tests.

- Missing key → `MockEnvelopeNotFoundError` (fixture/mock drift,
  test bug).
- `canned[key] is _TransportError` → dispatcher raises
  `AdapterInvocationFailedError(reason="subprocess_crash")` so the
  driver walks the `AdapterInvocationFailedError` →
  `error.category="adapter_crash"` mapping in
  `multi_step_driver._run_adapter_step`.
- Envelope dict → dispatcher synthesises an `InvocationResult` via
  the real walker (`adapter_invoker._invocation_from_envelope`) so
  missing-`review_findings` negative tests pin the actual
  `output_parse` contract, not a mock-side approximation.

**v3.7 F1 convention — fast-mode vs full-mode:**

Tests in fast mode (the CI default, `--benchmark-mode=fast`) enter
`mock_adapter_transport(...)` as a context manager to patch the
transport layer. Tests marked ``@pytest.mark.full_mode`` run only
under ``--benchmark-mode=full`` and MUST NOT invoke
``mock_adapter_transport``; the real subprocess path dispatches
with env-gated secrets + a real ``context_pack_ref`` resolved from
an upstream ``compile_context`` step. Full-mode smoke tests live
in a dedicated module (``test_full_mode_smoke.py``) to keep the
fast-path suite deterministic.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
from unittest.mock import patch

from ao_kernel.executor.adapter_invoker import (
    AdapterInvocationFailedError,
    AdapterManifest,
    AdapterOutputParseError,
    InvocationResult,
    _invocation_from_envelope,
)
from ao_kernel.workflow.run_store import run_revision


CannedKey = tuple[str, str, int]
"""(scenario_id, adapter_id, attempt) — mock dispatcher lookup."""


class MockEnvelopeNotFoundError(Exception):
    """Raised by the dispatcher when the canned dict has no entry for
    the current (scenario_id, adapter_id, attempt) key. Signals that
    the fixture and the scenario test drifted — treat as a test-bug
    rather than as a simulated transport failure."""


class _TransportError:
    """Sentinel — `canned[key] = _TransportError` tells the
    dispatcher to raise `AdapterInvocationFailedError` instead of
    returning an envelope. Deliberately-failing fixture path,
    distinct from the `MockEnvelopeNotFoundError` drift surface."""


@contextmanager
def mock_adapter_transport(
    canned: Mapping[CannedKey, object],
    scenario_id: str,
) -> Iterator[None]:
    """Patch `invoke_cli` + `invoke_http` at the executor's local
    import site for the duration of the block.

    Per-adapter attempt counters are scoped to the context so
    sequenced canned entries resolve correctly; exiting the
    block restores the original implementations (and also clears
    counters for the next test)."""
    counters: dict[str, int] = {}

    def _next_attempt(adapter_id: str) -> int:
        counters[adapter_id] = counters.get(adapter_id, 0) + 1
        return counters[adapter_id]

    def _dispatch(
        *,
        manifest: AdapterManifest,
        input_envelope: Mapping[str, Any],
        log_path: Path,
    ) -> InvocationResult:
        adapter_id = manifest.adapter_id
        attempt = _next_attempt(adapter_id)
        key: CannedKey = (scenario_id, adapter_id, attempt)

        if key not in canned:
            raise MockEnvelopeNotFoundError(f"no canned envelope for {key!r} — fixture / mock drift (test-side bug)")

        value = canned[key]
        if value is _TransportError:
            raise AdapterInvocationFailedError(
                reason="subprocess_crash",
                detail=f"benchmark negative fixture for {key!r}",
            )

        if not isinstance(value, Mapping):
            raise AssertionError(f"canned envelope for {key!r} must be a dict; got {type(value).__name__}")

        envelope_dict: Mapping[str, Any] = value
        # Delegate to the real walker so missing-payload tests pin
        # the actual output_parse contract.
        return _invocation_from_envelope(
            envelope_dict,
            log_path=log_path,
            elapsed=float(
                envelope_dict.get("cost_actual", {}).get(
                    "time_seconds",
                    0.0,
                )
            ),
            command=f"benchmark-mock[{adapter_id}]",
            manifest=manifest,
        )

    def _cli_dispatcher(
        *,
        manifest: AdapterManifest,
        input_envelope: Mapping[str, Any],
        sandbox: Any,
        worktree: Any,
        budget: Any,
        workspace_root: Path,
        run_id: str,
    ) -> tuple[InvocationResult, Any]:
        log_path = _benchmark_log_path(workspace_root, run_id, manifest.adapter_id)
        _ensure_log_parent(log_path)
        _write_empty_log(log_path)
        # PR-B7.1 cost shim: pull the envelope back out (canned
        # under the dispatcher key) so the budget axis update
        # happens exactly when the adapter "returns" from the
        # benchmark's perspective.
        adapter_id = manifest.adapter_id
        current_attempt = counters.get(adapter_id, 0) + 1
        canned_entry = canned.get((scenario_id, adapter_id, current_attempt))
        try:
            result = _dispatch(
                manifest=manifest,
                input_envelope=input_envelope,
                log_path=log_path,
            )
        except AdapterOutputParseError:
            raise
        except AdapterInvocationFailedError:
            raise
        if isinstance(canned_entry, Mapping):
            _maybe_consume_budget(workspace_root, run_id, canned_entry)
        return result, budget

    def _http_dispatcher(
        *,
        manifest: AdapterManifest,
        input_envelope: Mapping[str, Any],
        sandbox: Any,
        worktree: Any,
        budget: Any,
        workspace_root: Path,
        run_id: str,
    ) -> tuple[InvocationResult, Any]:
        # Shares counters with the CLI dispatcher — a single
        # adapter may stream responses across transports in theory;
        # the bundled benchmark suite doesn't exercise that path.
        return _cli_dispatcher(
            manifest=manifest,
            input_envelope=input_envelope,
            sandbox=sandbox,
            worktree=worktree,
            budget=budget,
            workspace_root=workspace_root,
            run_id=run_id,
        )

    with patch(
        "ao_kernel.executor.executor.invoke_cli",
        side_effect=_cli_dispatcher,
    ):
        with patch(
            "ao_kernel.executor.executor.invoke_http",
            side_effect=_http_dispatcher,
        ):
            yield


def _maybe_consume_budget(
    workspace_root: Path,
    run_id: str,
    envelope: Mapping[str, Any],
) -> None:
    """BENCHMARK-ONLY SHIM — drain ``budget.cost_usd.remaining``
    by the envelope's ``cost_actual.cost_usd`` value.

    The real reconcile path lives in
    :func:`ao_kernel.cost.middleware.post_response_reconcile`,
    which only runs behind :func:`ao_kernel.llm.governed_call`.
    The adapter transport path (:func:`invoke_cli` /
    :func:`invoke_http`) does not reconcile ``cost_usd`` — it
    only accrues ``time_seconds``. Until **FAZ-C PR-C3** closes
    that integration gap, this shim is what lets benchmark
    assertions (`assert_cost_consumed`) observe budget drain
    end-to-end.

    Bypass note: this shim writes `state.v1.json` directly
    rather than going through
    :func:`ao_kernel.workflow.run_store.save_run`. Benchmark
    scenarios are strictly single-threaded under pytest, so the
    absence of `write_text_atomic` + file-lock is acceptable;
    a real concurrency scenario would need the full store path.
    """
    cost_usd = (envelope.get("cost_actual") or {}).get("cost_usd")
    if cost_usd is None:
        return
    state_path = workspace_root / ".ao" / "runs" / run_id / "state.v1.json"
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    axis = (state.get("budget") or {}).get("cost_usd")
    if not isinstance(axis, dict):
        return
    remaining = float(axis.get("remaining", 0.0)) - float(cost_usd)
    axis["remaining"] = max(0.0, remaining)
    state["revision"] = run_revision(state)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _benchmark_log_path(
    workspace_root: Path,
    run_id: str,
    adapter_id: str,
) -> Path:
    return workspace_root / ".ao" / "evidence" / "workflows" / run_id / f"adapter-{adapter_id}.stdout.log"


def _ensure_log_parent(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)


def _write_empty_log(log_path: Path) -> None:
    # Keep the file present — some downstream artefact helpers
    # stat the path; real adapters always leave non-empty output.
    log_path.write_text(
        json.dumps({"_benchmark_mock": True}),
        encoding="utf-8",
    )


__all__ = [
    "CannedKey",
    "MockEnvelopeNotFoundError",
    "_TransportError",
    "mock_adapter_transport",
]
