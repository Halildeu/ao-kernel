"""Tests for ``ao-kernel metrics export`` CLI (PR-B5 C3 handler)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ao_kernel._internal.metrics.cli_handlers import cmd_metrics_export


prometheus_client = pytest.importorskip("prometheus_client")


def _args(workspace: Path, **kwargs) -> SimpleNamespace:
    ns = SimpleNamespace(
        workspace_root=str(workspace),
        output=kwargs.get("output"),
        format=kwargs.get("format", "prometheus"),
    )
    return ns


class TestStdoutHappyPath:
    def test_dormant_workspace_exit_zero_with_banner(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Plan v4 §2.6 Q2: dormant policy → exit 0 + banner."""
        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 0
        captured = capsys.readouterr()
        assert "policy_metrics.enabled=false" in captured.out


class TestOutputFlag:
    def test_atomic_output_writes_file(self, tmp_path: Path) -> None:
        output_path = tmp_path / "metrics.prom"
        rc = cmd_metrics_export(
            _args(tmp_path, output=str(output_path))
        )
        assert rc == 0
        assert output_path.is_file()
        content = output_path.read_text(encoding="utf-8")
        assert "# ao-kernel metrics" in content


class TestCorruptJSONL:
    def test_corrupt_events_returns_exit_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Plan v4 §2.6 exit 2: corrupt evidence JSONL fail-closed.

        Post-impl review absorb: evidence validation runs only when
        policy is enabled (dormant branch is banner-only to avoid
        zero-synthetic samples), so the test enables the policy to
        reach the corrupt-JSONL path.
        """
        import json

        (tmp_path / ".ao" / "policies").mkdir(parents=True)
        (
            tmp_path / ".ao" / "policies" / "policy_metrics.v1.json"
        ).write_text(
            json.dumps({
                "version": "v1",
                "enabled": True,
                "labels_advanced": {"enabled": False, "allowlist": []},
            }),
            encoding="utf-8",
        )
        evidence_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / "run-x"
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "events.jsonl").write_text(
            '{"kind": "policy_checked"}\n{ not valid\n',
            encoding="utf-8",
        )

        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 2
        captured = capsys.readouterr()
        assert "corrupt evidence" in captured.err.lower()


class TestExtraMissingInformational:
    def test_missing_prometheus_client_returns_exit_three(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Plan v4 §2.6 exit 3: `[metrics]` extra missing →
        informational banner, no crash.

        Post-impl review absorb: the extra-missing branch runs only
        when the policy is enabled (dormant branch short-circuits
        before registry construction to prevent zero-synthetic
        samples). Enable the policy so the extra-missing code path
        becomes reachable.
        """
        import json

        from ao_kernel.metrics import registry as registry_mod

        (tmp_path / ".ao" / "policies").mkdir(parents=True)
        (
            tmp_path / ".ao" / "policies" / "policy_metrics.v1.json"
        ).write_text(
            json.dumps({
                "version": "v1",
                "enabled": True,
                "labels_advanced": {"enabled": False, "allowlist": []},
            }),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            registry_mod, "_PROMETHEUS_AVAILABLE", False, raising=False,
        )
        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 3
        captured = capsys.readouterr()
        assert "[metrics] optional extra not installed" in captured.out


class TestDormantBannerOnly:
    """Post-impl review CNS-036 iter-1 A2: dormant policy → banner
    comments ONLY, no synthetic zero samples from label-less
    Gauge/Counter families."""

    def test_dormant_output_has_no_metric_samples(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`ao_claim_active_total 0.0` (Gauge) + `ao_claim_takeover_total
        0.0` (Counter) must NOT appear when policy dormant."""
        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 0
        out = capsys.readouterr().out
        # Banners still present:
        assert "policy_metrics.enabled=false" in out
        # But NO metric sample lines — only `# `-prefixed comments.
        for line in out.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            assert stripped.startswith("#"), (
                f"dormant output contains non-comment line: {stripped!r}"
            )

    def test_dormant_is_valid_prometheus_exposition(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Banner-only text still parses as Prometheus exposition
        (zero families, but no syntax error)."""
        from prometheus_client.parser import text_string_to_metric_families

        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 0
        out = capsys.readouterr().out
        families = list(text_string_to_metric_families(out))
        assert families == []


class TestWorkspaceAutoResolution:
    """Post-impl review CNS-036 iter-1 A1: `workspace_root()`
    returns the `.ao/` directory itself; `_resolve_workspace`
    must normalize to the parent so downstream path composers
    do not produce `.ao/.ao/...` doubled paths."""

    def test_auto_resolution_normalizes_dot_ao_to_parent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Simulate a workspace discovered via cwd lookup: policy at
        # `{tmp}/.ao/policies/policy_metrics.v1.json` with enabled=true,
        # an evidence event to populate `ao_policy_check_total`.
        import json

        (tmp_path / ".ao" / "policies").mkdir(parents=True)
        (
            tmp_path
            / ".ao"
            / "policies"
            / "policy_metrics.v1.json"
        ).write_text(
            json.dumps({
                "version": "v1",
                "enabled": True,
                "labels_advanced": {"enabled": False, "allowlist": []},
            }),
            encoding="utf-8",
        )
        evidence_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / "run-auto"
        )
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "events.jsonl").write_text(
            json.dumps({
                "kind": "policy_checked",
                "ts": "2026-04-17T10:00:00+00:00",
                "payload": {"violations_count": 0},
            }) + "\n",
            encoding="utf-8",
        )

        # Force workspace_root() to return the .ao/ directory itself
        # (production semantic from ao_kernel.config).
        monkeypatch.chdir(tmp_path)

        # No --workspace-root arg → exercise the auto-resolution branch.
        from types import SimpleNamespace

        rc = cmd_metrics_export(
            SimpleNamespace(workspace_root=None, output=None, format="prometheus")
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Policy should be NON-dormant — the metric family appears
        # and the dormant banner must be absent.
        assert "policy_metrics.enabled=false" not in out
        assert "ao_policy_check_total" in out
        assert 'outcome="allow"' in out
