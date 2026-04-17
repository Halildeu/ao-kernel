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
        """Plan v4 §2.6 exit 2: corrupt evidence JSONL fail-closed."""
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
        informational banner, no crash."""
        from ao_kernel.metrics import registry as registry_mod

        monkeypatch.setattr(
            registry_mod, "_PROMETHEUS_AVAILABLE", False, raising=False,
        )
        rc = cmd_metrics_export(_args(tmp_path))
        assert rc == 3
        captured = capsys.readouterr()
        assert "[metrics] optional extra not installed" in captured.out
