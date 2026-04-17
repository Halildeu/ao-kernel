"""Tests for PR-B1 commit 4: takeover, prune, reconcile, executor fencing,
and the ``_KINDS`` evidence-taxonomy expansion (18 → 24).

Core flow tests (acquire / heartbeat / release) live in
``test_coordination_registry.py``. This file covers the paths that
require a past-grace claim on disk: takeover (both via public
``takeover_claim`` and via the acquire → past-grace delegate),
``prune_expired_claims``, the forward-only fencing reconcile helper,
and the executor's stale-fencing entry check.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.coordination import (
    ClaimConflictError,
    ClaimConflictGraceError,
    ClaimNotFoundError,
    ClaimQuotaExceededError,
    ClaimRegistry,
    claim_revision,
    load_fencing_state,
)
from ao_kernel.coordination.claim import claim_path
from ao_kernel.coordination.errors import ClaimStaleFencingError
from ao_kernel.coordination.fencing import (
    fencing_state_revision,
    save_fencing_state_cas,
    set_next_token,
)
from ao_kernel.executor.evidence_emitter import _KINDS


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: claims.lock relies on fcntl",
)


def _enabled_policy(**overrides: Any) -> dict[str, Any]:
    base = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 60,
        "takeover_grace_period_seconds": 10,
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


def _rewind_claim_heartbeat(
    workspace_root: Path,
    resource_id: str,
    seconds_ago: int,
) -> None:
    """Rewrite the claim file with ``heartbeat_at`` set ``seconds_ago``
    in the past. The revision field is restamped so the SSOT reader
    does not flag the edit as on-disk corruption.

    This is a test helper only — production code never backdates the
    heartbeat. Use it to simulate claims that have entered the grace
    window or gone past-grace without waiting in real time.
    """
    path = claim_path(workspace_root, resource_id)
    doc = json.loads(path.read_text(encoding="utf-8"))
    past = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    doc["heartbeat_at"] = past.isoformat()
    doc["revision"] = claim_revision(doc)
    path.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Public takeover_claim — live/grace gate (B1v5)
# ---------------------------------------------------------------------------


class TestTakeoverLiveGracePastGate:
    def test_takeover_on_live_claim_raises_conflict(self, tmp_path: Path) -> None:
        """Public takeover_claim on a live resource must refuse."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        with pytest.raises(ClaimConflictError) as excinfo:
            registry.takeover_claim("worktree-a", "agent-beta")
        assert excinfo.value.current_owner_agent_id == "agent-alpha"
        assert excinfo.value.current_fencing_token == first.fencing_token

    def test_takeover_on_in_grace_raises_conflict_grace(
        self, tmp_path: Path,
    ) -> None:
        """Takeover attempted inside grace window yields distinct error."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        # Rewind into grace (expiry=60, grace=10 → past-expiry but
        # still within grace at 65s ago).
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=65)
        with pytest.raises(ClaimConflictGraceError):
            registry.takeover_claim("worktree-a", "agent-beta")

    def test_takeover_on_past_grace_succeeds(self, tmp_path: Path) -> None:
        """Past-grace: takeover proceeds; fencing advances; distinct
        ``claim_takeover`` event emitted."""
        events: list[tuple[str, dict[str, Any]]] = []

        def _sink(kind: str, payload: Any) -> None:
            events.append((kind, dict(payload)))

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_sink)
        first = registry.acquire_claim("worktree-a", "agent-alpha")
        # Rewind past grace (expiry=60 + grace=10 → 75s ago = past-grace).
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)
        new_claim = registry.takeover_claim("worktree-a", "agent-beta")
        assert new_claim.owner_agent_id == "agent-beta"
        assert new_claim.resource_id == "worktree-a"
        # Fencing advanced by 1
        assert new_claim.fencing_token == first.fencing_token + 1
        # W1v2 distinct event emitted (claim_takeover, NOT claim_acquired)
        kinds = [k for k, _ in events]
        assert "claim_takeover" in kinds
        # Takeover path must NOT emit claim_acquired
        assert "claim_acquired" not in [
            k for k, p in events
            if p.get("owner_agent_id") == "agent-beta"
        ]
        # Payload includes prev_ + new_ tokens (B6v2 + W1v2)
        takeover_payload = next(p for k, p in events if k == "claim_takeover")
        assert takeover_payload["prev_owner_agent_id"] == "agent-alpha"
        assert takeover_payload["new_owner_agent_id"] == "agent-beta"
        assert takeover_payload["prev_fencing_token"] == first.fencing_token
        assert takeover_payload["new_fencing_token"] == new_claim.fencing_token

    def test_takeover_on_absent_resource_raises_not_found(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        with pytest.raises(ClaimNotFoundError):
            registry.takeover_claim("never-existed", "agent-beta")


# ---------------------------------------------------------------------------
# Acquire → past-grace delegate (W3v4 single-emit)
# ---------------------------------------------------------------------------


class TestAcquireTakeoverDelegate:
    def test_acquire_on_past_grace_delegates_to_takeover(
        self, tmp_path: Path,
    ) -> None:
        """Acquire on a past-grace claim silently takes over — caller
        sees a successful acquire, evidence records claim_takeover."""
        events: list[tuple[str, dict[str, Any]]] = []

        def _sink(kind: str, payload: Any) -> None:
            events.append((kind, dict(payload)))

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_sink)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)

        new_claim = registry.acquire_claim("worktree-a", "agent-beta")
        assert new_claim.owner_agent_id == "agent-beta"
        # Single-emit contract (W3v4): only claim_takeover, no double
        # emit from the outer delegate helper.
        takeover_events = [k for k, _ in events if k == "claim_takeover"]
        assert len(takeover_events) == 1

    def test_takeover_quota_enforced_on_both_paths(self, tmp_path: Path) -> None:
        """B1v3: quota check runs on takeover too (not just fresh acquire)."""
        _write_workspace_policy(
            tmp_path, _enabled_policy(max_claims_per_agent=1),
        )
        registry = ClaimRegistry(tmp_path)
        # agent-beta acquires their one allowed claim
        registry.acquire_claim("worktree-b", "agent-beta")
        # agent-alpha holds worktree-a which will go past-grace
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)
        # agent-beta tries to takeover — should fail quota
        with pytest.raises(ClaimQuotaExceededError):
            registry.takeover_claim("worktree-a", "agent-beta")


# ---------------------------------------------------------------------------
# prune_expired_claims
# ---------------------------------------------------------------------------


class TestPruneExpiredClaims:
    def test_prune_removes_past_grace_claims(self, tmp_path: Path) -> None:
        events: list[tuple[str, dict[str, Any]]] = []

        def _sink(kind: str, payload: Any) -> None:
            events.append((kind, dict(payload)))

        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path, evidence_sink=_sink)
        registry.acquire_claim("worktree-a", "agent-alpha")
        registry.acquire_claim("worktree-b", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)
        # worktree-b is still live
        pruned = registry.prune_expired_claims()
        assert pruned == ["worktree-a"]
        assert not claim_path(tmp_path, "worktree-a").exists()
        assert claim_path(tmp_path, "worktree-b").exists()
        expired_events = [k for k, _ in events if k == "claim_expired"]
        assert len(expired_events) == 1

    def test_prune_preserves_fencing_state(self, tmp_path: Path) -> None:
        """Pruned claim keeps its fencing entry in ``_fencing.v1.json``
        — the token authority outlives the claim so the next acquire
        gets a fresh token (not 0 again)."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)
        registry.prune_expired_claims()
        # New acquire advances: token 0 issued originally, next_token
        # now 1 so this acquire gets token 1.
        second = registry.acquire_claim("worktree-a", "agent-beta")
        assert second.fencing_token == 1

    def test_prune_respects_max_batch(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        for i in range(5):
            registry.acquire_claim(f"worktree-{i:02d}", "agent-alpha")
            _rewind_claim_heartbeat(
                tmp_path, f"worktree-{i:02d}", seconds_ago=120,
            )
        pruned_first = registry.prune_expired_claims(max_batch=3)
        assert len(pruned_first) == 3
        pruned_second = registry.prune_expired_claims(max_batch=3)
        assert len(pruned_second) == 2
        pruned_third = registry.prune_expired_claims(max_batch=3)
        assert pruned_third == []

    def test_prune_skips_live_claims(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        # No rewind — claim is fresh; prune should skip it.
        pruned = registry.prune_expired_claims()
        assert pruned == []


# ---------------------------------------------------------------------------
# Forward-only reconcile (B3v3)
# ---------------------------------------------------------------------------


class TestForwardOnlyReconcile:
    def test_reconcile_advances_to_max_claim_plus_one(
        self, tmp_path: Path,
    ) -> None:
        """Fencing state behind claim.fencing_token → reconcile catches up."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        # Simulate drift: force fencing next_token back to 0 even though
        # a claim with fencing_token=0 exists (so next should be 1).
        from ao_kernel._internal.shared.lock import file_lock
        with file_lock(tmp_path / ".ao" / "claims" / "claims.lock"):
            state = load_fencing_state(tmp_path)
            rev = fencing_state_revision(state.to_dict())
            rewound = set_next_token(state, "worktree-a", 0)
            save_fencing_state_cas(
                tmp_path, rewound, expected_revision=rev,
            )

        # Now reconcile — should set next_token back to 1 (max_claim+1)
        with file_lock(tmp_path / ".ao" / "claims" / "claims.lock"):
            registry._reconcile_fencing_with_claims_locked()

        state_after = load_fencing_state(tmp_path)
        assert state_after.resources["worktree-a"].next_token == 1

    def test_reconcile_does_not_rewind_ahead_fencing(
        self, tmp_path: Path,
    ) -> None:
        """Forward-only invariant: fencing already ahead of claims is
        preserved, not rewound to max_claim+1."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        # Bump fencing ahead to next_token=10 (simulating prior
        # acquire/release cycles whose claims are no longer on disk).
        from ao_kernel._internal.shared.lock import file_lock
        with file_lock(tmp_path / ".ao" / "claims" / "claims.lock"):
            state = load_fencing_state(tmp_path)
            rev = fencing_state_revision(state.to_dict())
            advanced = set_next_token(state, "worktree-a", 10)
            save_fencing_state_cas(
                tmp_path, advanced, expected_revision=rev,
            )

        # Reconcile should NOT rewind to max_claim+1 (= 1) — forward-only.
        with file_lock(tmp_path / ".ao" / "claims" / "claims.lock"):
            registry._reconcile_fencing_with_claims_locked()

        state_after = load_fencing_state(tmp_path)
        assert state_after.resources["worktree-a"].next_token == 10


# ---------------------------------------------------------------------------
# Evidence taxonomy 18 → 24
# ---------------------------------------------------------------------------


class TestEvidenceKindsExpansion:
    def test_all_six_claim_kinds_registered(self) -> None:
        """B1 additive expansion: 6 claim_* kinds present, PR-A 18
        kinds still present, total is 24."""
        expected_new = {
            "claim_acquired",
            "claim_released",
            "claim_heartbeat",
            "claim_expired",
            "claim_takeover",
            "claim_conflict",
        }
        assert expected_new.issubset(_KINDS)

    def test_pr_a_kinds_preserved(self) -> None:
        """Regression guard: B1 must not remove or rename any PR-A kind."""
        required_pr_a = {
            "workflow_started",
            "workflow_completed",
            "workflow_failed",
            "step_started",
            "step_completed",
            "step_failed",
            "adapter_invoked",
            "adapter_returned",
            "diff_previewed",
            "diff_applied",
            "diff_rolled_back",
            "approval_requested",
            "approval_granted",
            "approval_denied",
            "test_executed",
            "pr_opened",
            "policy_checked",
            "policy_denied",
        }
        assert required_pr_a.issubset(_KINDS)

    def test_total_kind_count_at_least_twenty_four(self) -> None:
        """PR-B1 introduced 24 kinds. Subsequent PRs (B2 +3 cost kinds)
        are additive; this regression guard pins the floor, not the
        exact count, to avoid churn on every cost/metrics/etc. kind
        addition."""
        assert len(_KINDS) >= 24


# ---------------------------------------------------------------------------
# Executor fencing entry (W1v5 no-emit)
# ---------------------------------------------------------------------------


class TestExecutorFencingEntry:
    def test_partial_kwargs_raises_value_error(self, tmp_path: Path) -> None:
        """Partial fencing context is a programmer error (fail-closed)."""
        from ao_kernel.adapters import AdapterRegistry
        from ao_kernel.executor import Executor
        from ao_kernel.workflow.registry import WorkflowRegistry

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()
        exe = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
        )
        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        with pytest.raises(ValueError, match="together or both omitted"):
            exe.run_step(
                "00000000-0000-4000-8000-000000000001",
                adapter_step,
                fencing_token=0,
                # fencing_resource_id omitted — partial
            )

        with pytest.raises(ValueError, match="together or both omitted"):
            exe.run_step(
                "00000000-0000-4000-8000-000000000001",
                adapter_step,
                fencing_resource_id="worktree-a",
                # fencing_token omitted — partial
            )

    def test_fencing_without_registry_raises_value_error(
        self, tmp_path: Path,
    ) -> None:
        """Supplying fencing kwargs without claim_registry injection is
        a programmer error — the executor cannot validate without a
        registry reference."""
        from ao_kernel.adapters import AdapterRegistry
        from ao_kernel.executor import Executor
        from ao_kernel.workflow.registry import WorkflowRegistry

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()
        exe = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            # claim_registry not supplied
        )
        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        with pytest.raises(ValueError, match="no\\s+claim_registry"):
            exe.run_step(
                "00000000-0000-4000-8000-000000000001",
                adapter_step,
                fencing_token=0,
                fencing_resource_id="worktree-a",
            )

    def test_driver_translates_stale_fencing_to_step_failed(
        self, tmp_path: Path,
    ) -> None:
        """CNS-029v4 iter-3 blocker #2 fix: MultiStepDriver's adapter
        step helper forwards fencing kwargs to Executor.run_step and
        translates ``ClaimStaleFencingError`` into ``_StepFailed`` with
        ``category="other"`` + ``code="STALE_FENCING"``. The driver
        owns the ``step_failed`` emission + ``step_record.state=
        "failed"`` CAS transition per PR-A4b error handler contract."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        from ao_kernel.adapters import AdapterRegistry
        from ao_kernel.executor import Executor
        from ao_kernel.executor.multi_step_driver import _StepFailed
        from ao_kernel.workflow.registry import WorkflowRegistry

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()
        registry = ClaimRegistry(tmp_path)
        exe = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            claim_registry=registry,
        )
        # Instantiate a driver pointing at the executor; we call its
        # private adapter-step helper directly with fencing kwargs
        # rather than orchestrate the full workflow.
        from ao_kernel.executor.multi_step_driver import MultiStepDriver

        driver = MultiStepDriver(
            tmp_path,
            registry=wf_reg,
            adapter_registry=ad_reg,
            executor=exe,
        )
        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        # No acquire performed — validate_fencing_token will raise
        # ClaimStaleFencingError (missing resource entry sentinel).
        # The driver's helper expects a (run_id, record, step_def)
        # positional chain; we pass an empty record because the
        # stale-fencing raise fires before the helper touches it.
        with pytest.raises(_StepFailed) as excinfo:
            driver._run_adapter_step(
                "00000000-0000-4000-8000-0000000b1004",
                {},
                adapter_step,
                attempt=1,
                step_id="00000000-0000-4000-8000-0000000b1004",
                context_preamble=None,
                fencing_token=0,
                fencing_resource_id="worktree-a",
            )
        assert excinfo.value.category == "other"
        assert excinfo.value.code == "STALE_FENCING"
        # Error reason carries the structured fields for audit
        assert "worktree-a" in excinfo.value.reason
        assert "supplied_token=0" in excinfo.value.reason

    def test_stale_fencing_propagates_before_any_side_effects(
        self, tmp_path: Path,
    ) -> None:
        """W1v5: stale fencing raises ClaimStaleFencingError BEFORE any
        evidence emit, worktree build, or adapter invoke. The run
        record stays untouched — no step_started, no step_failed from
        the executor itself. Driver-level emit handling is not
        exercised in this test (that lands in a future driver
        integration PR); we only assert that the primitive surfaces
        the exception for the caller to handle."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        from ao_kernel.adapters import AdapterRegistry
        from ao_kernel.executor import Executor
        from ao_kernel.workflow.registry import WorkflowRegistry

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()
        registry = ClaimRegistry(tmp_path)
        exe = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            claim_registry=registry,
        )
        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        # No acquire performed → fencing state has no entry for
        # worktree-a, so validate_fencing_token raises immediately.
        with pytest.raises(ClaimStaleFencingError):
            exe.run_step(
                "00000000-0000-4000-8000-000000000001",
                adapter_step,
                fencing_token=0,
                fencing_resource_id="worktree-a",
            )

        # No run record was created; evidence file absent; no worktree
        # was built. Asserting absence is the cleanest check.
        evidence_dir = tmp_path / ".ao" / "evidence"
        # evidence_dir may or may not exist from tmp fixtures; what we
        # really want is that no run directory was created for our id.
        assert not (
            evidence_dir / "workflows"
            / "00000000-0000-4000-8000-000000000001"
        ).exists()

    def test_driver_fencing_optout_behaves_as_pre_b1(
        self, tmp_path: Path,
    ) -> None:
        """CNS-029v4 iter-4 absorb: callers that leave fencing kwargs
        as ``None`` on ``_run_adapter_step`` must retain pre-B1
        behaviour — no fencing validation, no ``ClaimStaleFencingError``
        raise. When fencing kwargs are omitted, the driver's
        ClaimStaleFencingError catch block never fires — any exception
        that surfaces is a pre-B1 error path (run record not found,
        adapter registry miss, etc.), not a coordination failure.
        The pinning assertion here is: whatever exception bubbles up,
        it is **not** ``ClaimStaleFencingError`` and it is not a
        ``_StepFailed`` carrying ``STALE_FENCING``."""
        _write_workspace_policy(tmp_path, _enabled_policy())
        from ao_kernel.adapters import AdapterRegistry
        from ao_kernel.coordination.errors import ClaimStaleFencingError
        from ao_kernel.executor import Executor
        from ao_kernel.executor.multi_step_driver import (
            MultiStepDriver,
            _StepFailed,
        )
        from ao_kernel.workflow.registry import WorkflowRegistry

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()
        registry = ClaimRegistry(tmp_path)
        exe = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            claim_registry=registry,
        )
        driver = MultiStepDriver(
            tmp_path,
            registry=wf_reg,
            adapter_registry=ad_reg,
            executor=exe,
        )
        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        # Leave both fencing kwargs omitted. The driver must NOT raise
        # ClaimStaleFencingError nor a _StepFailed(code=STALE_FENCING);
        # any other exception (run record not found, adapter miss) is
        # fine and validates the pre-B1 pass-through behaviour.
        raised: BaseException | None = None
        try:
            driver._run_adapter_step(
                "00000000-0000-4000-8000-0000000b1005",
                {},
                adapter_step,
                attempt=1,
                step_id="00000000-0000-4000-8000-0000000b1005",
                context_preamble=None,
                # fencing_token + fencing_resource_id intentionally
                # left at their None defaults.
            )
        except BaseException as exc:  # noqa: BLE001 — test pin
            raised = exc

        # A raise occurred (the tmp_path workspace has no run record);
        # assert the raise is NOT a coordination-layer stale-fencing
        # signal. If fencing had been opted in by mistake, we would see
        # ClaimStaleFencingError or _StepFailed(STALE_FENCING).
        assert raised is not None, (
            "expected some exception when run record is absent; "
            "got None — this regresses the pre-B1 driver contract"
        )
        assert not isinstance(raised, ClaimStaleFencingError), (
            "fencing-kwargs-None path must not invoke fencing validation"
        )
        if isinstance(raised, _StepFailed):
            assert raised.code != "STALE_FENCING"
