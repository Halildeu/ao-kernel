"""Tests for ``ao_kernel.metrics.registry`` — PR-B5 C2 adapter.

Covers: prometheus_client availability cache, 8 metric family
registration, advanced-label expansion driven by
``MetricsPolicy.advanced_allowlist``, cost-disjunction gate
(``include_llm_metrics=False`` → LLM families absent), histogram
bucket configuration, and the no-op path when the extra is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.metrics import registry as metrics_registry
from ao_kernel.metrics.policy import (
    LabelsAdvanced,
    MetricsPolicy,
    load_metrics_policy,
)


# prometheus-client ships in ao_kernel[metrics]; skip this whole
# module if the dev environment hasn't installed it.
prometheus_client = pytest.importorskip("prometheus_client")


def _bundled_policy(tmp_path: Path) -> MetricsPolicy:
    return load_metrics_policy(tmp_path)


def _advanced_policy(*allowed: str) -> MetricsPolicy:
    return MetricsPolicy(
        enabled=True,
        labels_advanced=LabelsAdvanced(
            enabled=True,
            allowlist=tuple(allowed),
        ),
    )


class TestAvailability:
    def test_is_metrics_available_true(self) -> None:
        """prometheus-client installed in dev env → True."""
        assert metrics_registry.is_metrics_available() is True

    def test_availability_is_cached(self) -> None:
        """Module-level cache: two calls return the same bool without
        re-running the import. Covers the performance invariant the
        CLI relies on (export hot path must not re-import on every
        call)."""
        first = metrics_registry._check_prometheus()
        second = metrics_registry._check_prometheus()
        assert first is second is True


class TestBuildRegistryDefaultLabels:
    def test_build_returns_registry_when_extra_present(
        self, tmp_path: Path
    ) -> None:
        built = metrics_registry.build_registry(_bundled_policy(tmp_path))
        assert built is not None
        assert isinstance(built.registry, prometheus_client.CollectorRegistry)

    def test_eight_families_present(self, tmp_path: Path) -> None:
        """Plan v4 §2.2: 8 metric families under default policy."""
        built = metrics_registry.build_registry(_bundled_policy(tmp_path))
        assert built is not None
        assert built.llm_call_duration is not None
        assert built.llm_tokens_used is not None
        assert built.llm_cost_usd is not None
        assert built.llm_usage_missing is not None
        assert built.policy_check is not None
        assert built.workflow_duration is not None
        assert built.claim_active is not None
        assert built.claim_takeover is not None

    def test_default_low_cardinality_labels(
        self, tmp_path: Path
    ) -> None:
        """Bundled policy (labels_advanced disabled) → default low-
        cardinality label set. No ``model`` / ``agent_id`` labels."""
        built = metrics_registry.build_registry(_bundled_policy(tmp_path))
        assert built is not None
        assert built.llm_call_duration._labelnames == ("provider",)
        assert built.llm_tokens_used._labelnames == ("provider", "direction")
        assert built.llm_cost_usd._labelnames == ("provider",)
        assert built.llm_usage_missing._labelnames == ("provider",)
        assert built.policy_check._labelnames == ("outcome",)
        assert built.workflow_duration._labelnames == ("final_state",)
        assert built.claim_active._labelnames == ()
        assert built.claim_takeover._labelnames == ()


class TestBuildRegistryAdvancedLabels:
    def test_model_advanced_expands_llm_labels(self) -> None:
        """Allowlist=['model'] → llm families add ``model`` label."""
        built = metrics_registry.build_registry(_advanced_policy("model"))
        assert built is not None
        assert built.llm_call_duration._labelnames == ("provider", "model")
        assert built.llm_tokens_used._labelnames == (
            "provider", "direction", "model",
        )
        assert built.llm_cost_usd._labelnames == ("provider", "model")
        assert built.llm_usage_missing._labelnames == ("provider", "model")
        # claim_active should NOT gain model — only agent_id is in its
        # advanced candidate set.
        assert built.claim_active._labelnames == ()

    def test_agent_id_advanced_expands_claim_active(self) -> None:
        """Allowlist=['agent_id'] → claim_active gauge gains agent_id."""
        built = metrics_registry.build_registry(_advanced_policy("agent_id"))
        assert built is not None
        assert built.claim_active._labelnames == ("agent_id",)
        # LLM families stay on the default provider-only surface.
        assert built.llm_cost_usd._labelnames == ("provider",)

    def test_both_advanced_labels_expand_independently(self) -> None:
        built = metrics_registry.build_registry(
            _advanced_policy("model", "agent_id")
        )
        assert built is not None
        assert built.llm_call_duration._labelnames == ("provider", "model")
        assert built.claim_active._labelnames == ("agent_id",)


class TestCostDisjunction:
    def test_include_llm_metrics_false_omits_llm_families(
        self, tmp_path: Path
    ) -> None:
        """Plan v4 §2 cost-disjunction: cost tracking dormant →
        ``ao_llm_*`` families absent from the registry. Prevents
        zero-synthetic series in the textfile output."""
        built = metrics_registry.build_registry(
            _bundled_policy(tmp_path),
            include_llm_metrics=False,
        )
        assert built is not None
        assert built.llm_call_duration is None
        assert built.llm_tokens_used is None
        assert built.llm_cost_usd is None
        assert built.llm_usage_missing is None
        # Non-LLM families stay populated.
        assert built.policy_check is not None
        assert built.workflow_duration is not None
        assert built.claim_active is not None
        assert built.claim_takeover is not None

    def test_cost_dormant_textfile_lacks_llm_prefix(
        self, tmp_path: Path
    ) -> None:
        """With LLM families omitted the Prometheus exposition must
        not mention ``ao_llm_`` — the strongest acceptance criterion
        for "LLM metric family absent" (plan v4 iter-2 A3)."""
        built = metrics_registry.build_registry(
            _bundled_policy(tmp_path),
            include_llm_metrics=False,
        )
        assert built is not None
        output = prometheus_client.generate_latest(built.registry).decode(
            "utf-8"
        )
        assert "ao_llm_" not in output


class TestHistogramBuckets:
    def test_llm_duration_upper_is_600_seconds(
        self, tmp_path: Path
    ) -> None:
        """Plan v4 §2.2: LLM upper bucket = 600s (GPT-4-turbo outlier
        tolerance; raised from 300s in v3)."""
        built = metrics_registry.build_registry(_bundled_policy(tmp_path))
        assert built is not None
        # prometheus_client appends +Inf so we check the explicit
        # bucket tuple we configured.
        assert built.llm_call_duration._upper_bounds[-2] == 600.0

    def test_workflow_duration_upper_is_7200_seconds(
        self, tmp_path: Path
    ) -> None:
        built = metrics_registry.build_registry(_bundled_policy(tmp_path))
        assert built is not None
        assert built.workflow_duration._upper_bounds[-2] == 7200.0


class TestExtraMissingFallback:
    def test_build_returns_none_when_prometheus_client_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Dev environment has prometheus-client, but the runtime
        check is monkey-patched to emulate a vanilla wheel install.
        Callers translate ``None`` into the exit-3 informational
        banner (plan v4 §2.6)."""
        monkeypatch.setattr(
            metrics_registry,
            "_PROMETHEUS_AVAILABLE",
            False,
            raising=False,
        )
        policy = _bundled_policy(tmp_path)
        assert metrics_registry.build_registry(policy) is None
