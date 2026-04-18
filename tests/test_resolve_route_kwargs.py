"""PR-C4: resolve_route additive kwargs + _KINDS 27→28 plumbing.

v1 is plumbing-only — runtime downgrade is DORMANT (always
``downgrade_applied=False``, ``original_class=None``,
``downgraded_class=None``). The runtime consumer (threshold
comparison + directional ``soft_degrade.rules`` filter) lands in
C4.1 follow-up PR after the ``policy-cost-tracking`` schema widens
to include ``routing_by_cost.class_thresholds``.
"""

from __future__ import annotations

from unittest.mock import patch

from ao_kernel.executor import evidence_emitter
from ao_kernel.llm import resolve_route


class TestDefaultsOffPreservesBehavior:
    """Existing callers (mcp_server, client, intent_router) must not
    see behavioral changes from PR-C4 additive kwargs."""

    def test_existing_caller_pattern_unaffected(self) -> None:
        """Contract: calling ``resolve_route`` with the old pre-C4
        kwarg set returns a dict that still carries the legacy keys.
        Note: ``intent_router._llm_classify`` passes
        ``resolve_route(intent='FAST_TEXT')`` — 'FAST_TEXT' is a
        class name, not a recognised intent. The resolver returns a
        FAIL manifest with ``reason='UNKNOWN_INTENT'`` in this case;
        C4 just guarantees the dormant contract fields travel along
        every return path."""
        result = resolve_route(intent="FAST_TEXT")
        # Existing legacy contract: result is a dict with ``status``.
        assert "status" in result
        # C4 dormant contract: 3 additive keys present, all neutral.
        assert result.get("downgrade_applied") is False
        assert result.get("original_class") is None
        assert result.get("downgraded_class") is None


class TestAdditiveKwargsRuntimeNoOp:
    """Even with the new kwargs set, v1 runtime remains dormant."""

    def test_cross_class_downgrade_true_is_dormant(self) -> None:
        """Setting ``cross_class_downgrade=True`` without a runtime
        threshold source must still return the dormant contract
        (downgrade_applied=False). Runtime activation is C4.1 scope."""
        result = resolve_route(
            intent="DISCOVERY",  # a real intent; maps to BALANCED_TEXT
            cross_class_downgrade=True,
            budget_remaining=None,  # no threshold source anyway
        )
        assert result.get("downgrade_applied") is False
        assert result.get("original_class") is None
        assert result.get("downgraded_class") is None


class TestPlumbingForwardsKwargsToInternal:
    """The facade must pass the new kwargs through the internal
    ``resolve()`` request dict."""

    def test_forwards_budget_remaining_and_flag(self) -> None:
        from ao_kernel._internal.prj_kernel_api import llm_router

        captured: dict = {}

        def _fake_resolve(
            request, repo_root=None, now=None, workspace_root=None,
        ):
            captured.update(request)
            return {
                "status": "OK",
                "selected_class": "FAST_TEXT",
                "selected_provider": "test",
                "selected_model": "test-m",
                "provider_attempts": [],
                "probe_status_at_selection": "ok",
                "verified_at": None,
                "probe_last_at": None,
                "ttl_remaining_hours": None,
                "intent": "BASELINE",
                "perspective": None,
                "downgrade_applied": False,
                "original_class": None,
                "downgraded_class": None,
            }

        with patch.object(llm_router, "resolve", _fake_resolve):
            resolve_route(
                intent="BASELINE",
                cross_class_downgrade=True,
                budget_remaining="sentinel-budget-obj",  # plumbed through
            )

        # Both new keys forwarded to internal resolve's request dict.
        assert captured["cross_class_downgrade"] is True
        assert captured["budget_remaining"] == "sentinel-budget-obj"


class TestKindsCountIs28:
    def test_kinds_frozenset_has_new_kind(self) -> None:
        kinds = evidence_emitter._KINDS
        assert len(kinds) == 28
        assert "route_cross_class_downgrade" in kinds


class TestDormantContractOnAllReturnPaths:
    """PR-C4 v2 §3: response fields travel on every return path
    (success AND failure). Codex post-AGREE note #3 absorb."""

    def test_model_override_fail_path_carries_dormant_contract(
        self,
    ) -> None:
        from ao_kernel._internal.prj_kernel_api.llm_router import resolve

        result = resolve(request={"model": "override-model-name"})
        assert result["status"] == "FAIL"
        assert result["reason"] == "MODEL_OVERRIDE_NOT_ALLOWED"
        # Dormant contract present on this FAIL path too.
        assert result["downgrade_applied"] is False
        assert result["original_class"] is None
        assert result["downgraded_class"] is None

    def test_unknown_intent_fail_path_carries_dormant_contract(
        self,
    ) -> None:
        from ao_kernel._internal.prj_kernel_api.llm_router import resolve

        result = resolve(request={"intent": "UNKNOWN_INTENT_VALUE"})
        assert result["status"] == "FAIL"
        assert result["reason"] == "UNKNOWN_INTENT"
        assert result["downgrade_applied"] is False
        assert result["original_class"] is None
        assert result["downgraded_class"] is None
