"""Shared fixtures for PR-B7 benchmarks.

v3.7 F1 (scaffold only): `--benchmark-mode=fast|full` pytest option
(default `fast`). Fast mode patches adapter transport via
``mock_adapter_transport``; full mode bypasses the mock so tests
marked ``@pytest.mark.full_mode`` can exercise the real subprocess
path. Collection hook skips non-matching tests per mode so the
default CI surface is identical to pre-v3.7.

**F1 ships the scaffold, not a runnable real-adapter smoke.** The
`@full_mode` marker + collection hook exist so v3.7 F2 can add the
first genuine smoke without re-pluming the harness. Under
`--benchmark-mode=full` today F1 collects 0 runnable tests.
Rationale + forward reference: `docs/BENCHMARK-FULL-MODE.md`.

v3.5 D3: scorecard collector hooks are wired here via
:mod:`ao_kernel._internal.scorecard.collector`. Primary tests tag
themselves with ``@pytest.mark.scorecard_primary`` and expose a
:class:`PrimarySidecar` via the ``benchmark_primary_sidecar`` fixture.
**Full-mode tests must NOT be `scorecard_primary`** — real-adapter
scorecard path lands in v3.7 F2.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from ao_kernel._internal.scorecard.collector import (
    PrimarySidecar,
    ScorecardRegistry,
    finalize_session,
)
from tests._driver_helpers import build_driver, install_workspace


_BUNDLED_ROOT = Path(__file__).resolve().parents[2] / "ao_kernel" / "defaults"

_REGISTRY_ATTR = "_ao_scorecard_registry"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register ``--benchmark-mode`` (v3.7 F1).

    Default ``fast`` preserves the pre-v3.7 deterministic mock-
    transport path. ``full`` bypasses the mock and dispatches to the
    real adapter subprocess path; tests carrying
    ``@pytest.mark.full_mode`` are gated by this option (collected
    only in full mode).
    """
    parser.addoption(
        "--benchmark-mode",
        action="store",
        default="fast",
        choices=["fast", "full"],
        help=(
            "Benchmark execution mode (v3.7 F1). 'fast' (default) "
            "patches adapter transport via mock_adapter_transport. "
            "'full' bypasses the mock for ops-only real-adapter runs."
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Gate benchmark tests by ``--benchmark-mode`` (v3.7 F1 absorb of
    Codex post-impl MEDIUM — code-docs parity).

    - ``fast`` (default): skip every ``@pytest.mark.full_mode`` test so
      default CI stays identical to pre-v3.7.
    - ``full``: skip every non-``@full_mode`` benchmark test so ops
      runs focus on real-subprocess smokes (mock-based fast-mode
      tests are intentionally NOT co-executed).

    Only benchmark-suite items are gated; tests elsewhere in the repo
    ignore the option entirely.
    """
    mode = config.getoption("--benchmark-mode")
    skip_full = pytest.mark.skip(
        reason="full_mode only runs under --benchmark-mode=full",
    )
    skip_fast = pytest.mark.skip(
        reason="fast-mode tests are skipped under --benchmark-mode=full",
    )
    for item in items:
        nodeid = getattr(item, "nodeid", "")
        is_benchmark = "tests/benchmarks/" in nodeid
        has_full_marker = "full_mode" in item.keywords
        if mode == "full":
            if is_benchmark and not has_full_marker:
                item.add_marker(skip_fast)
        else:  # fast
            if has_full_marker:
                item.add_marker(skip_full)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "full_mode: v3.7 F1 — mark a benchmark test as ops-only "
        "real-adapter full-mode smoke. Requires "
        "`--benchmark-mode=full` to run; skipped in default fast "
        "mode. Do NOT combine with `scorecard_primary` (real-"
        "adapter scorecard semantics land in v3.7 F2).",
    )
    config.addinivalue_line(
        "markers",
        "scorecard_primary(scenario_id=None): mark the canonical "
        "happy-path test for a scorecard scenario. Exactly one per "
        "canonical scenario; duplicates and missing primaries both "
        "fail-close at session finish.",
    )
    setattr(config, _REGISTRY_ATTR, ScorecardRegistry())


def _registry(config: pytest.Config) -> ScorecardRegistry:
    reg = getattr(config, _REGISTRY_ATTR, None)
    if reg is None:
        reg = ScorecardRegistry()
        setattr(config, _REGISTRY_ATTR, reg)
    return reg


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    """Finalize the scorecard at session end.

    Codex post-impl review BLOCKER fix: canonical-input invariant
    violations (duplicate or missing primary markers) MUST fail the
    benchmark job. Previously the exception was log-only, which made
    misconfiguration silently-green under CI. Now we propagate a
    non-zero pytest exit code via ``session.exitstatus``.

    v3.7 F2 absorb (Codex iter-2 AGREE): expected primary scenarios
    are now mode-gated. Fast mode retains the canonical full set
    (``{"governed_bugfix", "governed_review"}``); full mode only
    requires ``{"governed_review"}`` because the F2 smoke scope is
    minimal-by-design (no ``gh-cli-pr`` real-adapter wiring yet).

    F2 post-impl BLOCK absorb: if full mode runs but the smoke
    skipped due to prerequisites (system python3 lacking ao_kernel,
    missing binary, etc.) the registry is empty. Raising
    ``ScorecardCollectorError`` in that case would turn a legitimate
    env-miss skip into a usage-error fail — the opposite of the
    "graceful skip" contract. When full mode sees zero primaries
    registered we relax the expected set to empty.
    """
    from ao_kernel._internal.scorecard.collector import (
        EXPECTED_PRIMARY_SCENARIOS,
    )

    mode = session.config.getoption("--benchmark-mode")
    registry = _registry(session.config)
    if mode == "full":
        if not registry.distinct_scenarios():
            # Smoke skipped (prereq miss) → no scorecard to produce;
            # suppress the invariant instead of flagging misconfig.
            expected: frozenset[str] = frozenset()
        else:
            expected = frozenset({"governed_review"})
    else:
        expected = EXPECTED_PRIMARY_SCENARIOS

    try:
        finalize_session(registry, expected_scenarios=expected)
    except Exception as exc:
        session.config.get_terminal_writer().line(
            f"scorecard finalize failed: {exc}",
            red=True,
        )
        # pytest ExitCode.USAGE_ERROR=4 signals "misconfigured suite"
        # which is the right category here (canonical marker contract
        # broken). Respect pre-existing failures by taking the max.
        misconfig = int(pytest.ExitCode.USAGE_ERROR)
        if int(session.exitstatus or 0) < misconfig:
            session.exitstatus = pytest.ExitCode(misconfig)


@pytest.fixture
def benchmark_primary_sidecar(request: pytest.FixtureRequest) -> Callable[..., PrimarySidecar]:
    """Factory fixture — primary-marked tests call this once per run
    with the scenario_id + run_dir they exercised."""

    registry = _registry(request.config)

    def _record(
        scenario_id: str,
        run_dir: Path,
        *,
        run_state_path: Path | None = None,
        review_findings_path: Path | None = None,
    ) -> PrimarySidecar:
        sidecar = PrimarySidecar(
            scenario_id=scenario_id,
            run_dir=Path(run_dir),
            run_state_path=(Path(run_state_path) if run_state_path else None),
            review_findings_path=(Path(review_findings_path) if review_findings_path else None),
        )
        registry.record(sidecar)
        return sidecar

    return _record


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@pytest.fixture
def workspace_root(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Materialise a tmp workspace with `.ao/` + git skeleton and
    bundled policies / workflows / adapters copied in, so the
    driver + governance path reads a real filesystem.

    `install_workspace` from the shared driver helpers does the git
    init + base `.ao/` dirs; we layer the bundled defaults on top.

    v3.7 F2: under `--benchmark-mode=full` the workspace is overlaid
    with `policy_cost_tracking.v1.json::enabled=true` so the
    adapter-path `post_adapter_reconcile` middleware actually runs
    and emits `llm_spend_recorded` events with `source="adapter_path"`.
    Fast-mode keeps the bundled dormant default so pre-F2 tests
    behave identically.
    """
    install_workspace(tmp_path)
    ao = tmp_path / ".ao"
    # `install_workspace` creates workflows/adapters/evidence/runs
    # but not policies — create it before copying bundled files.
    (ao / "policies").mkdir(parents=True, exist_ok=True)
    for policy in (_BUNDLED_ROOT / "policies").glob("policy_*.v1.json"):
        shutil.copy2(policy, ao / "policies" / policy.name)
    for workflow in (_BUNDLED_ROOT / "workflows").glob("*.v1.json"):
        shutil.copy2(workflow, ao / "workflows" / workflow.name)
    for adapter in (_BUNDLED_ROOT / "adapters").glob("*.manifest.v1.json"):
        shutil.copy2(adapter, ao / "adapters" / adapter.name)

    # Benchmark-specific workflow fixtures (B7 v1 — bundled
    # bug_fix_flow needs git/pytest workspace allowlist; simpler
    # bench variant deferred from that tuning).
    bench_workflows = Path(__file__).resolve().parent / "fixtures" / "workflows"
    if bench_workflows.is_dir():
        for workflow in bench_workflows.glob("*.v1.json"):
            shutil.copy2(workflow, ao / "workflows" / workflow.name)

    # v3.7 F2 mode-gated cost policy override (Codex iter-2 AGREE).
    # Fast-mode keeps bundled dormant default; full-mode flips
    # `enabled=true` so the adapter-path reconcile middleware fires.
    mode = request.config.getoption("--benchmark-mode")
    if mode == "full":
        cost_policy_path = ao / "policies" / "policy_cost_tracking.v1.json"
        if cost_policy_path.is_file():
            policy_doc = json.loads(
                cost_policy_path.read_text(encoding="utf-8"),
            )
            if isinstance(policy_doc, dict):
                policy_doc["enabled"] = True
                cost_policy_path.write_text(
                    json.dumps(policy_doc, indent=2, sort_keys=True),
                    encoding="utf-8",
                )

    return tmp_path


@pytest.fixture
def seeded_budget() -> dict[str, Any]:
    """Canonical budget axes the benchmark runs assume.

    `fail_closed_on_exhaust=True` mirrors the real budget guard.
    `cost_usd` reconcile is deferred to B7.1 — the assertion layer
    only verifies the axis was seeded, not that spend landed on it.
    """
    return {
        "fail_closed_on_exhaust": True,
        "cost_usd": {"limit": 10.0, "remaining": 10.0},
        "tokens": {"limit": 50_000, "remaining": 50_000},
        "time_seconds": {"limit": 600, "remaining": 600},
    }


def seed_benchmark_run(
    workspace_root: Path,
    workflow_id: str,
    *,
    workflow_version: str = "1.0.0",
    budget: Mapping[str, Any],
) -> str:
    """Write a schema-minimal run record with `budget` seeded so
    `assert_budget_axis_seeded` can verify the axis later.

    Returns the new run_id.
    """
    from ao_kernel.workflow.run_store import run_revision

    run_id = str(uuid.uuid4())
    run_dir = workspace_root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workflow_version": workflow_version,
        "state": "created",
        "created_at": _now_iso(),
        "revision": "0" * 64,
        "intent": {
            "kind": "inline_prompt",
            "payload": f"benchmark {workflow_id}",
        },
        "steps": [],
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        ],
        "adapter_refs": [],
        "evidence_refs": [
            f".ao/evidence/workflows/{run_id}/events.jsonl",
        ],
        "budget": dict(budget),
    }
    record["revision"] = run_revision(record)
    (run_dir / "state.v1.json").write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return run_id


@pytest.fixture
def seeded_run(workspace_root: Path, seeded_budget: dict[str, Any]):
    """Factory — returns a callable that seeds a run for a named
    workflow and returns the run_id."""

    def _seed(workflow_id: str, *, version: str = "1.0.0") -> str:
        return seed_benchmark_run(
            workspace_root,
            workflow_id,
            workflow_version=version,
            budget=seeded_budget,
        )

    return _seed


@pytest.fixture
def benchmark_driver(workspace_root: Path):
    """Driver bound to the bundled workspace (covers `codex-stub`
    + `gh-cli-pr` for both scenarios)."""
    return build_driver(workspace_root)


@pytest.fixture
def benchmark_mode(request: pytest.FixtureRequest) -> str:
    """Resolved benchmark execution mode (v3.7 F1).

    Returns ``"fast"`` (default) or ``"full"`` based on the
    ``--benchmark-mode`` pytest option. Fast-mode tests expect
    ``mock_adapter_transport`` to patch ``invoke_cli``/``invoke_http``;
    full-mode tests dispatch to the real subprocess path.
    """
    mode = request.config.getoption("--benchmark-mode")
    return str(mode)
