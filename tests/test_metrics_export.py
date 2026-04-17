"""Tests for ``ao_kernel.metrics.export`` — PR-B5 C3 textfile serializer."""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.metrics.export import (
    generate_textfile,
    generate_textfile_strict,
)
from ao_kernel.metrics.errors import MetricsExtraNotInstalledError
from ao_kernel.metrics.policy import load_metrics_policy
from ao_kernel.metrics.registry import build_registry


prometheus_client = pytest.importorskip("prometheus_client")


class TestBasicSerialization:
    def test_produces_valid_prometheus_exposition(
        self, tmp_path: Path
    ) -> None:
        policy = load_metrics_policy(tmp_path)
        built = build_registry(policy)
        assert built is not None

        output = generate_textfile(
            built, metrics_dormant=False, cost_dormant=False,
        )
        # Exposition format always has HELP / TYPE blocks for each
        # family.
        assert "# HELP ao_policy_check_total" in output
        assert "# TYPE ao_policy_check_total counter" in output

    def test_parser_roundtrip_accepts_output(
        self, tmp_path: Path
    ) -> None:
        """The emitted textfile must be parseable by prometheus_client
        itself — any syntax error breaks Grafana scrape ingestion."""
        from prometheus_client.parser import text_string_to_metric_families

        policy = load_metrics_policy(tmp_path)
        built = build_registry(policy)
        assert built is not None
        output = generate_textfile(
            built, metrics_dormant=False, cost_dormant=False,
        )
        families = list(text_string_to_metric_families(output))
        # All 8 default families + their helper series parse.
        names = {f.name for f in families}
        assert "ao_policy_check" in names
        assert "ao_workflow_duration_seconds" in names


class TestDormantBanners:
    def test_metrics_dormant_banner_prepended(
        self, tmp_path: Path
    ) -> None:
        policy = load_metrics_policy(tmp_path)
        built = build_registry(policy)
        output = generate_textfile(
            built, metrics_dormant=True, cost_dormant=False,
        )
        assert output.startswith(
            "# ao-kernel metrics: dormant "
            "(policy_metrics.enabled=false)."
        )

    def test_cost_dormant_banner_and_no_llm_prefix(
        self, tmp_path: Path
    ) -> None:
        policy = load_metrics_policy(tmp_path)
        built = build_registry(policy, include_llm_metrics=False)
        output = generate_textfile(
            built, metrics_dormant=False, cost_dormant=True,
        )
        assert "cost tracking dormant" in output
        # Cost-disjunction invariant: no ao_llm_* in output when
        # cost-dormant. The cumulative textfile acceptance test.
        assert "ao_llm_" not in output


class TestExtraMissingBanner:
    def test_built_none_produces_extra_missing_banner(self) -> None:
        output = generate_textfile(
            built=None, metrics_dormant=False, cost_dormant=False,
        )
        assert "optional extra not installed" in output

    def test_strict_raises_when_extra_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ao_kernel.metrics import registry as registry_mod

        monkeypatch.setattr(
            registry_mod, "_PROMETHEUS_AVAILABLE", False, raising=False,
        )
        with pytest.raises(MetricsExtraNotInstalledError):
            generate_textfile_strict(
                None, metrics_dormant=False, cost_dormant=False,
            )
