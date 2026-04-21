"""PR-C4.1 runtime activation tests: budget-aware cross-class soft-degrade.

Verifies the router's new downgrade gating (llm_router.resolve) in
isolation via ``_load_operations_json`` monkeypatch. A separate suite
(``test_resolve_route_downgrade_caller.py``) covers the
``client.llm_call`` / ``mcp_server.handle_llm_call`` integration —
auto-route detection + fail-open evidence emit.

The 5 gates (all must hold for a downgrade):

1. ``cross_class_downgrade=True`` passed by caller
2. ``budget_remaining`` (Budget snapshot) supplied
3. ``strictness[from_class].degrade_allowed`` default True
4. Budget axis ``cost_usd`` configured with a remaining value
5. A threshold-bearing rule matches ``(from_class, intent)`` AND
   ``remaining < budget_remaining_threshold_usd`` (strict less-than)

Threshold-less rules (the bundled DISCOVERY/BASELINE ones) stay
**inert** in C4.1 — they are skipped by the rule loop even when the
other preconditions hold.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.workflow.budget import Budget, BudgetAxis


# ─── Helpers ───────────────────────────────────────────────────────────


def _budget(remaining_usd: float | None, limit_usd: float = 10.0) -> Budget:
    """Minimal Budget snapshot with a single cost_usd axis."""
    if remaining_usd is None:
        axis = None
    else:
        axis = BudgetAxis(
            limit=Decimal(str(limit_usd)),
            spent=Decimal(str(limit_usd - remaining_usd)),
            remaining=Decimal(str(remaining_usd)),
        )
    return Budget(
        tokens=None,
        tokens_input=None,
        tokens_output=None,
        cost_usd=axis,
        time_seconds=None,
        fail_closed_on_exhaust=True,
    )


def _fake_rules(
    *,
    balanced_to_fast_threshold: float | None = 2.0,
    include_inert_rule: bool = False,
    reasoning_downgrade_rule: bool = False,
) -> dict[str, Any]:
    """Return a fake resolver_rules payload with configurable
    soft_degrade rules for the gating tests.

    Keeps the bundled schema shape — intent_to_class /
    fallback_order_by_class / strictness / soft_degrade — but lets
    each test vary the threshold and intent list.
    """
    rules: list[dict[str, Any]] = []
    if balanced_to_fast_threshold is not None:
        rule: dict[str, Any] = {
            "from_class": "BALANCED_TEXT",
            "to_class": "FAST_TEXT",
            "intents": ["DISCOVERY"],
            "budget_remaining_threshold_usd": balanced_to_fast_threshold,
        }
        rules.append(rule)
    if include_inert_rule:
        # Rule without threshold → inert in C4.1
        rules.append({
            "from_class": "BALANCED_TEXT",
            "to_class": "FAST_TEXT",
            "intents": ["DISCOVERY"],
        })
    if reasoning_downgrade_rule:
        # Rule targets a degrade_allowed=false class
        rules.append({
            "from_class": "REASONING_TEXT",
            "to_class": "BALANCED_TEXT",
            "intents": ["GAP_ANALYSIS"],
            "budget_remaining_threshold_usd": 5.0,
        })

    return {
        "policy_version": "v0.1-test",
        "intent_to_class": {
            "DISCOVERY": "BALANCED_TEXT",
            "BASELINE": "FAST_TEXT",
            "GAP_ANALYSIS": "REASONING_TEXT",
        },
        "fallback_order_by_class": {
            "FAST_TEXT": ["openai"],
            "BALANCED_TEXT": ["openai"],
            "REASONING_TEXT": ["openai"],
        },
        "strictness": {
            "REASONING_TEXT": {"verified_only": True, "degrade_allowed": False},
        },
        "soft_degrade": {"enabled": True, "rules": rules},
        "ttl_hours_default": 72,
    }


def _fake_provider_map() -> dict[str, Any]:
    """Minimal eligible provider_map so resolve() returns OK."""
    model = {
        "model_id": "stub-model",
        "stage": "verified",
        "probe_status": "ok",
        "probe_last_at": "2099-01-01T00:00:00+00:00",
        "verified_at": "2099-01-01T00:00:00+00:00",
    }
    provider_entry = {
        "pinned_model_id": "stub-model",
        "models": [model],
    }
    return {
        "classes": {
            "FAST_TEXT": {"providers": {"openai": provider_entry}},
            "BALANCED_TEXT": {"providers": {"openai": provider_entry}},
            "REASONING_TEXT": {"providers": {"openai": provider_entry}},
        },
    }


def _fake_class_registry() -> dict[str, Any]:
    """Placeholder — router only reads intent_to_class from resolver_rules."""
    return {"classes": []}


@pytest.fixture
def fake_ops(monkeypatch: pytest.MonkeyPatch):
    """Install a monkeypatched operations loader + reset schema cache.

    Tests pass a `resolver_rules` dict via the ``set_rules`` callback;
    the fixture re-uses the same provider_map + class_registry across
    calls.
    """
    from ao_kernel._internal.prj_kernel_api import llm_router

    llm_router._reset_resolver_rules_cache()
    state: dict[str, dict[str, Any]] = {
        "llm_resolver_rules.v1.json": _fake_rules(),
        "llm_provider_map.v1.json": _fake_provider_map(),
        "llm_class_registry.v1.json": _fake_class_registry(),
    }

    def _fake_loader(filename: str, _repo_root, *, workspace_root=None):
        return state[filename]

    monkeypatch.setattr(llm_router, "_load_operations_json", _fake_loader)

    def _set_rules(rules: dict[str, Any]) -> None:
        state["llm_resolver_rules.v1.json"] = rules
        llm_router._reset_resolver_rules_cache()

    yield _set_rules
    llm_router._reset_resolver_rules_cache()


# ─── 1. Budget-aware downgrade gating ──────────────────────────────────


class TestBudgetThresholdGate:
    def test_budget_below_threshold_triggers_downgrade(self, fake_ops) -> None:
        """BALANCED_TEXT + DISCOVERY, remaining=1.0 < 2.0 threshold →
        downgrade to FAST_TEXT, all metadata populated."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        assert result["status"] == "OK"
        assert result["downgrade_applied"] is True
        assert result["original_class"] == "BALANCED_TEXT"
        assert result["downgraded_class"] == "FAST_TEXT"
        assert result["matched_rule_index"] == 0
        assert result["threshold_usd"] == 2.0
        assert result["budget_remaining_usd"] == pytest.approx(1.0)
        # selected_class reflects the effective class (post-downgrade)
        assert result["selected_class"] == "FAST_TEXT"

    def test_budget_above_threshold_no_downgrade(self, fake_ops) -> None:
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=5.0),
        )
        assert result["status"] == "OK"
        assert result["downgrade_applied"] is False
        assert result["original_class"] is None
        assert result["downgraded_class"] is None
        # selected_class still reflects the requested class
        assert result["selected_class"] == "BALANCED_TEXT"
        # budget snapshot was read — record it for audit
        assert result["budget_remaining_usd"] == pytest.approx(5.0)

    def test_budget_exactly_at_threshold_no_downgrade(self, fake_ops) -> None:
        """Strict ``<`` semantic: remaining == threshold → no downgrade."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=2.0),
        )
        assert result["downgrade_applied"] is False
        assert result["selected_class"] == "BALANCED_TEXT"


# ─── 2. Inert behavior for threshold-less rules ────────────────────────


class TestThresholdlessRulesInert:
    def test_rule_without_threshold_is_inert_in_c41(self, fake_ops) -> None:
        """A rule missing ``budget_remaining_threshold_usd`` must be
        skipped by the C4.1 runtime evaluator — preserves bundled
        cost-agnostic DISCOVERY/BASELINE rules at their pre-v3.3.1
        dormant behavior."""
        fake_ops(_fake_rules(
            balanced_to_fast_threshold=None,
            include_inert_rule=True,
        ))
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=0.01),  # extreme low
        )
        # Even with budget near zero, the inert rule cannot trigger
        assert result["downgrade_applied"] is False
        assert result["selected_class"] == "BALANCED_TEXT"


# ─── 3. Strictness gate ────────────────────────────────────────────────


class TestStrictnessGate:
    def test_degrade_not_allowed_class_blocks_downgrade(
        self, fake_ops,
    ) -> None:
        """REASONING_TEXT has ``strictness.degrade_allowed=false`` →
        even a matching rule with satisfied budget threshold MUST
        NOT trigger a downgrade."""
        fake_ops(_fake_rules(
            balanced_to_fast_threshold=None,
            reasoning_downgrade_rule=True,
        ))
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="GAP_ANALYSIS",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=0.0),  # below threshold
        )
        assert result["downgrade_applied"] is False
        assert result["selected_class"] == "REASONING_TEXT"


# ─── 4. Intent-mismatch + budget-absence + dormant caller ──────────────


class TestDormantPathways:
    def test_intent_not_in_rule_skipped(self, fake_ops) -> None:
        """Rule has intents=[DISCOVERY], caller passes BASELINE → no match."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="BASELINE",  # intent_to_class → FAST_TEXT, not in rule
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        assert result["downgrade_applied"] is False

    def test_budget_remaining_none_dormant(self, fake_ops) -> None:
        """cross_class_downgrade=True + budget_remaining=None →
        gating aborted, dormant behavior."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=None,
        )
        assert result["downgrade_applied"] is False
        assert result["budget_remaining_usd"] is None

    def test_cost_usd_axis_missing_silent_no_downgrade(
        self, fake_ops,
    ) -> None:
        """Budget snapshot with ``cost_usd=None`` axis → router treats
        as no-signal, no downgrade, no raise."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=None),
        )
        assert result["downgrade_applied"] is False
        assert result["budget_remaining_usd"] is None

    def test_cross_class_downgrade_false_is_dormant(self, fake_ops) -> None:
        """Caller opt-out: even with budget + rules configured, the
        flag off keeps the runtime dormant."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=False,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        assert result["downgrade_applied"] is False


# ─── 5. Response contract completeness ─────────────────────────────────


class TestResponseContract:
    def test_response_carries_downgrade_metadata_on_ok(
        self, fake_ops,
    ) -> None:
        """Every OK path response dict has the full C4.1 metadata set."""
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        for key in (
            "downgrade_applied",
            "original_class",
            "downgraded_class",
            "matched_rule_index",
            "threshold_usd",
            "budget_remaining_usd",
        ):
            assert key in result, f"missing {key!r} on OK path"

    def test_response_carries_downgrade_metadata_on_fail(
        self, fake_ops,
    ) -> None:
        """FAIL paths MUST also carry the C4.1 metadata set (empty)."""
        from ao_kernel._internal.prj_kernel_api.llm_router import resolve

        result = resolve(request={"intent": "UNKNOWN"})
        for key in (
            "downgrade_applied",
            "original_class",
            "downgraded_class",
            "matched_rule_index",
            "threshold_usd",
            "budget_remaining_usd",
        ):
            assert key in result, f"missing {key!r} on FAIL path"
        assert result["downgrade_applied"] is False

    def test_selected_class_is_effective_class_on_downgrade(
        self, fake_ops,
    ) -> None:
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=0.5),
        )
        assert result["selected_class"] == result["downgraded_class"]


# ─── 6. Schema validation (inline, cached) ─────────────────────────────


class TestClientRouteHelperIntegration:
    """Caller-side plumbing: `AoKernelClient._route` loads the run's
    budget snapshot and forwards it to `resolve_route` with
    `cross_class_downgrade=True`. Without `run_id` the snapshot load is
    skipped, so `cross_class_downgrade` stays False — router remains
    dormant."""

    def _seed_run_with_budget(self, root, run_id: str, remaining_usd: float) -> None:
        """Create a minimal run record on disk with a cost_usd axis."""
        import json
        from ao_kernel.workflow.run_store import run_revision

        run_dir = root / ".ao" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": "test_flow",
            "workflow_version": "1.0.0",
            "state": "running",
            "created_at": "2026-04-18T10:00:00+00:00",
            "revision": "0" * 64,
            "intent": {"kind": "inline_prompt", "payload": "x"},
            "steps": [],
            "policy_refs": [
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            "adapter_refs": [],
            "evidence_refs": [
                f".ao/evidence/workflows/{run_id}/events.jsonl",
            ],
            "budget": {
                "fail_closed_on_exhaust": True,
                "cost_usd": {
                    "limit": 10.0,
                    "remaining": remaining_usd,
                },
            },
        }
        record["revision"] = run_revision(record)
        (run_dir / "state.v1.json").write_text(
            json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def test_route_helper_forwards_budget_snapshot_with_run_id(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`_route(intent, run_id=...)` loads the budget and calls
        `resolve_route(cross_class_downgrade=True, budget_remaining=<Budget>)`."""
        run_id = "00000000-0000-4000-8000-0000c41a0001"
        self._seed_run_with_budget(tmp_path, run_id, remaining_usd=1.0)

        captured: dict[str, Any] = {}

        def _fake_resolve(**kw: Any) -> dict[str, Any]:
            captured.update(kw)
            return {
                "provider_id": "openai",
                "model": "gpt-4",
                "base_url": "",
                "downgrade_applied": False,
            }

        monkeypatch.setattr("ao_kernel.llm.resolve_route", _fake_resolve)

        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)
        client._route("DISCOVERY", run_id=run_id)

        assert captured["cross_class_downgrade"] is True
        assert captured["budget_remaining"] is not None
        # Budget forwarded as a Budget object (not dict)
        from ao_kernel.workflow.budget import Budget
        assert isinstance(captured["budget_remaining"], Budget)

    def test_route_helper_dormant_without_run_id(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without `run_id`, snapshot load is skipped; `_route` calls
        `resolve_route` with `cross_class_downgrade=False` →
        dormant."""
        captured: dict[str, Any] = {}

        def _fake_resolve(**kw: Any) -> dict[str, Any]:
            captured.update(kw)
            return {"provider_id": "openai", "model": "gpt-4"}

        monkeypatch.setattr("ao_kernel.llm.resolve_route", _fake_resolve)

        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)
        client._route("DISCOVERY")  # no run_id

        assert captured["cross_class_downgrade"] is False
        assert captured["budget_remaining"] is None

    def test_route_helper_dormant_on_missing_run_record(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing run record → warn-log + no-downgrade (silent)."""
        captured: dict[str, Any] = {}

        def _fake_resolve(**kw: Any) -> dict[str, Any]:
            captured.update(kw)
            return {"provider_id": "openai", "model": "gpt-4"}

        monkeypatch.setattr("ao_kernel.llm.resolve_route", _fake_resolve)

        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)
        client._route("DISCOVERY", run_id="00000000-0000-4000-8000-deadbeef0000")

        # Load failed silently → budget_remaining=None → cross_class_downgrade=False
        assert captured["cross_class_downgrade"] is False
        assert captured["budget_remaining"] is None


class TestClientLlmCallEmit:
    """`AoKernelClient.llm_call` emits `route_cross_class_downgrade`
    exactly when the auto-route path returns ``downgrade_applied=True``.

    Explicit `provider_id` + `model` overrides bypass the emit path
    entirely (no route resolution → no downgrade signal).
    """

    def _read_events(self, root, run_id: str) -> list[dict[str, Any]]:
        import json

        path = (
            root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        if not path.is_file():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _downgrade_route(self, **overrides: Any) -> dict[str, Any]:
        route = {
            "provider_id": "openai",
            "model": "gpt-4",
            "base_url": "",
            "selected_class": "FAST_TEXT",
            "downgrade_applied": True,
            "original_class": "BALANCED_TEXT",
            "downgraded_class": "FAST_TEXT",
            "matched_rule_index": 0,
            "threshold_usd": 2.0,
            "budget_remaining_usd": 0.5,
        }
        route.update(overrides)
        return route

    def test_downgrade_applied_emits_evidence_event(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c41ca001"
        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)
        monkeypatch.setattr(
            client, "_route",
            lambda intent, run_id=None: self._downgrade_route(),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.governed_call",
            lambda **kw: {"text": "", "usage": {}, "tool_calls": []},
        )
        client.llm_call(
            messages=[{"role": "user", "content": "hi"}],
            intent="DISCOVERY",
            run_id=run_id,
        )

        events = self._read_events(tmp_path, run_id)
        downgrades = [
            e for e in events if e.get("kind") == "route_cross_class_downgrade"
        ]
        assert len(downgrades) == 1
        payload = downgrades[0]["payload"]
        assert payload["intent"] == "DISCOVERY"
        assert payload["original_class"] == "BALANCED_TEXT"
        assert payload["downgraded_class"] == "FAST_TEXT"
        assert payload["threshold_usd"] == 2.0

    def test_provider_override_bypasses_emit(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit provider_id/model → auto-route branch skipped →
        no downgrade evidence emitted even if `_route` would have."""
        run_id = "00000000-0000-4000-8000-0000c41ca002"
        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)

        route_called: list[bool] = []

        def _track_route(*a: Any, **kw: Any) -> dict[str, Any]:
            route_called.append(True)
            return self._downgrade_route()

        monkeypatch.setattr(client, "_route", _track_route)
        monkeypatch.setattr(
            "ao_kernel.llm.governed_call",
            lambda **kw: {"text": "", "usage": {}, "tool_calls": []},
        )
        client.llm_call(
            messages=[{"role": "user", "content": "hi"}],
            intent="DISCOVERY",
            provider_id="openai",   # explicit override
            model="gpt-4o-mini",
            run_id=run_id,
        )

        assert route_called == []  # _route never invoked
        events = self._read_events(tmp_path, run_id)
        downgrades = [
            e for e in events if e.get("kind") == "route_cross_class_downgrade"
        ]
        assert downgrades == []

    def test_emit_failure_is_fail_open(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Evidence I/O failure during emit MUST NOT cascade to the
        caller — the fail-open wrapper must swallow the OSError and
        allow ``llm_call`` to complete normally.
        """
        run_id = "00000000-0000-4000-8000-0000c41ca003"
        from ao_kernel.client import AoKernelClient

        client = AoKernelClient(workspace_root=tmp_path)
        monkeypatch.setattr(
            client, "_route",
            lambda intent, run_id=None: self._downgrade_route(),
        )

        def _boom(*a: Any, **kw: Any) -> None:
            raise OSError("simulated evidence write failure")

        monkeypatch.setattr(
            "ao_kernel.executor.evidence_emitter.emit_event", _boom,
        )
        monkeypatch.setattr(
            "ao_kernel.llm.governed_call",
            lambda **kw: {"text": "", "usage": {}, "tool_calls": []},
        )
        # The call MUST complete — fail-open wrap catches the OSError.
        result = client.llm_call(
            messages=[{"role": "user", "content": "hi"}],
            intent="DISCOVERY",
            run_id=run_id,
        )
        assert result["status"] == "OK"
        assert result["text"] == ""
        assert result["tool_calls"] == []
        assert result["usage"] is None


class TestMultiStepDowngradeChain:
    """v3.4.0 #5: budget thresholds that cascade (PREMIUM →
    BALANCED_TEXT → FAST_TEXT) now collapse multiple hops in a single
    resolve call. Cycle protection guards against misconfigured
    rule-graphs (A → B → A)."""

    def _multistep_rules(self) -> dict[str, Any]:
        """Fake rule set with two thresholds so a single low budget
        triggers both hops."""
        return {
            "policy_version": "v0.1-multistep",
            "intent_to_class": {
                "DISCOVERY": "PREMIUM",
            },
            "fallback_order_by_class": {
                "PREMIUM": ["openai"],
                "BALANCED_TEXT": ["openai"],
                "FAST_TEXT": ["openai"],
            },
            "strictness": {},
            "soft_degrade": {
                "enabled": True,
                "rules": [
                    {
                        "from_class": "PREMIUM",
                        "to_class": "BALANCED_TEXT",
                        "intents": ["DISCOVERY"],
                        "budget_remaining_threshold_usd": 5.0,
                    },
                    {
                        "from_class": "BALANCED_TEXT",
                        "to_class": "FAST_TEXT",
                        "intents": ["DISCOVERY"],
                        "budget_remaining_threshold_usd": 2.0,
                    },
                ],
            },
            "ttl_hours_default": 72,
        }

    def test_two_hop_downgrade_chain_collapses(self, fake_ops) -> None:
        """remaining=1.0 < both thresholds → PREMIUM → BALANCED_TEXT →
        FAST_TEXT in a single resolve call. Chain captures both hops;
        final downgraded_class is FAST_TEXT."""
        fake_ops(self._multistep_rules())
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        assert result["downgrade_applied"] is True
        assert result["original_class"] == "PREMIUM"
        assert result["downgraded_class"] == "FAST_TEXT"
        assert result["selected_class"] == "FAST_TEXT"
        chain = result.get("downgrade_chain", [])
        assert len(chain) == 2
        assert chain[0]["from_class"] == "PREMIUM"
        assert chain[0]["to_class"] == "BALANCED_TEXT"
        assert chain[1]["from_class"] == "BALANCED_TEXT"
        assert chain[1]["to_class"] == "FAST_TEXT"

    def test_partial_chain_when_second_threshold_not_crossed(
        self, fake_ops,
    ) -> None:
        """remaining=3.0 < 5.0 (first hop) but >= 2.0 (second hop) →
        single-step downgrade (PREMIUM → BALANCED_TEXT only)."""
        fake_ops(self._multistep_rules())
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=3.0),
        )
        assert result["downgraded_class"] == "BALANCED_TEXT"
        chain = result["downgrade_chain"]
        assert len(chain) == 1

    def test_cycle_protection_breaks_loop(self, fake_ops) -> None:
        """A → B → A rule-graph would cycle; visited set prevents
        re-entering a class already downgraded FROM."""
        fake_ops({
            "policy_version": "v0.1-cycle",
            "intent_to_class": {"DISCOVERY": "A_CLASS"},
            "fallback_order_by_class": {
                "A_CLASS": ["openai"],
                "B_CLASS": ["openai"],
            },
            "strictness": {},
            "soft_degrade": {
                "enabled": True,
                "rules": [
                    {
                        "from_class": "A_CLASS",
                        "to_class": "B_CLASS",
                        "intents": ["DISCOVERY"],
                        "budget_remaining_threshold_usd": 10.0,
                    },
                    {
                        "from_class": "B_CLASS",
                        "to_class": "A_CLASS",  # cycle
                        "intents": ["DISCOVERY"],
                        "budget_remaining_threshold_usd": 10.0,
                    },
                ],
            },
            "ttl_hours_default": 72,
        })
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=0.0),
        )
        # First hop applies (A → B); second hop blocked by visited guard
        assert result["downgraded_class"] == "B_CLASS"
        assert len(result["downgrade_chain"]) == 1

    def test_single_step_backward_compat(self, fake_ops) -> None:
        """C4.1 single-step rules still produce a 1-element chain."""
        # default fake_ops has a single-rule setup
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent="DISCOVERY",
            cross_class_downgrade=True,
            budget_remaining=_budget(remaining_usd=1.0),
        )
        # Existing C4.1 pin (budget < threshold → downgrade applied)
        # now also exposes the chain shape
        if result["downgrade_applied"]:
            assert len(result["downgrade_chain"]) == 1


class TestWorkspaceOverride:
    """v3.4.0 #6: operators place workspace-specific routing rules
    under ``.ao/operations/`` to override bundled defaults without
    forking the package."""

    def test_workspace_override_takes_priority(
        self, tmp_path: Path,
    ) -> None:
        from ao_kernel._internal.prj_kernel_api import llm_router

        ops_dir = tmp_path / ".ao" / "operations"
        ops_dir.mkdir(parents=True, exist_ok=True)
        override_rules = {
            "policy_version": "v0.1-ws",
            "intent_to_class": {"CUSTOM_INTENT": "CUSTOM_CLASS"},
            "fallback_order_by_class": {"CUSTOM_CLASS": ["openai"]},
            "ttl_hours_default": 72,
        }
        (ops_dir / "llm_resolver_rules.v1.json").write_text(
            json.dumps(override_rules), encoding="utf-8",
        )
        (ops_dir / "llm_class_registry.v1.json").write_text(
            json.dumps({"classes": []}), encoding="utf-8",
        )
        (ops_dir / "llm_provider_map.v1.json").write_text(
            json.dumps({
                "classes": {
                    "CUSTOM_CLASS": {
                        "providers": {
                            "openai": {
                                "pinned_model_id": "stub-model",
                                "models": [{
                                    "model_id": "stub-model",
                                    "stage": "verified",
                                    "probe_status": "ok",
                                    "probe_last_at": "2099-01-01T00:00:00+00:00",
                                    "verified_at": "2099-01-01T00:00:00+00:00",
                                }],
                            },
                        },
                    },
                },
            }),
            encoding="utf-8",
        )

        llm_router._reset_resolver_rules_cache()
        try:
            from ao_kernel.llm import resolve_route

            result = resolve_route(
                intent="CUSTOM_INTENT",
                workspace_root=str(tmp_path),
            )
            assert result["status"] == "OK"
            assert result["selected_class"] == "CUSTOM_CLASS"
        finally:
            llm_router._reset_resolver_rules_cache()

    def test_malformed_override_fails_closed(
        self, tmp_path: Path,
    ) -> None:
        from ao_kernel._internal.prj_kernel_api import llm_router

        ops_dir = tmp_path / ".ao" / "operations"
        ops_dir.mkdir(parents=True, exist_ok=True)
        (ops_dir / "llm_resolver_rules.v1.json").write_text(
            "{this is not valid json",
            encoding="utf-8",
        )

        llm_router._reset_resolver_rules_cache()
        try:
            from ao_kernel.llm import resolve_route

            with pytest.raises(json.JSONDecodeError):
                resolve_route(
                    intent="DISCOVERY",
                    workspace_root=str(tmp_path),
                )
        finally:
            llm_router._reset_resolver_rules_cache()


class TestSchemaValidation:
    def test_malformed_threshold_raises_validation(self, fake_ops) -> None:
        """Negative ``budget_remaining_threshold_usd`` violates the
        additive schema's ``minimum: 0`` constraint."""
        from jsonschema import ValidationError

        fake_ops({
            "policy_version": "v0.1",
            "intent_to_class": {"DISCOVERY": "BALANCED_TEXT"},
            "fallback_order_by_class": {"BALANCED_TEXT": ["openai"]},
            "soft_degrade": {
                "enabled": True,
                "rules": [{
                    "from_class": "BALANCED_TEXT",
                    "to_class": "FAST_TEXT",
                    "intents": ["DISCOVERY"],
                    "budget_remaining_threshold_usd": -1.0,  # invalid
                }],
            },
            "ttl_hours_default": 72,
        })

        from ao_kernel.llm import resolve_route

        with pytest.raises(ValidationError):
            resolve_route(
                intent="DISCOVERY",
                cross_class_downgrade=True,
                budget_remaining=_budget(remaining_usd=1.0),
            )
