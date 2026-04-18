"""Tests for ``ao-kernel policy-sim run`` CLI (PR-B4 C4)."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest

from ao_kernel._internal.policy_sim.cli_handlers import cmd_policy_sim_run
from ao_kernel.policy_sim import (
    load_bundled_scenarios,
    simulate_policy_change,
)
from ao_kernel.policy_sim.report import (
    has_tightening,
    load_policies_from_dir,
    render,
    write_atomic,
)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "scenarios": None,
        "proposed_policies": "/nonexistent",
        "baseline_source": "bundled",
        "baseline_overrides": None,
        "format": "json",
        "output": None,
        "enable_host_fs_probes": False,
        "project_root": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# --- report.render / has_tightening / write_atomic --------------------


class TestReportRender:
    def test_render_json_matches_dump(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        rendered = render(report, "json")
        # Valid JSON, same shape as to_dict output.
        parsed = json.loads(rendered)
        assert (
            parsed["scenarios_evaluated"]
            == report.scenarios_evaluated
        )

    def test_render_text_contains_header(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        rendered = render(report, "text")
        assert "Policy Simulation Report" in rendered
        assert "Transitions (all):" in rendered
        assert "Transitions per policy:" in rendered

    def test_render_unknown_format_raises(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        with pytest.raises(ValueError):
            render(report, "yaml")  # type: ignore[arg-type]


class TestHasTightening:
    def test_bundled_empty_proposed_no_tightening(
        self, tmp_path: Path
    ) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        assert has_tightening(report) is False


class TestWriteAtomic:
    def test_writes_content(self, tmp_path: Path) -> None:
        target = tmp_path / "subdir" / "report.json"
        write_atomic(target, '{"ok": true}')
        assert target.read_text(encoding="utf-8") == '{"ok": true}'

    def test_creates_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c.txt"
        write_atomic(target, "hi")
        assert target.parent.is_dir()

    def test_no_tmp_leftover(self, tmp_path: Path) -> None:
        target = tmp_path / "report.json"
        write_atomic(target, "{}")
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "report.json"]
        assert leftovers == []


class TestLoadPoliciesFromDir:
    def test_empty_dir_returns_empty_mapping(self, tmp_path: Path) -> None:
        assert load_policies_from_dir(tmp_path) == {}

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_policies_from_dir(tmp_path / "missing") == {}

    def test_loads_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text(
            json.dumps({"one": 1}), encoding="utf-8"
        )
        (tmp_path / "b.json").write_text(
            json.dumps({"two": 2}), encoding="utf-8"
        )
        mapping = load_policies_from_dir(tmp_path)
        assert mapping == {"a.json": {"one": 1}, "b.json": {"two": 2}}


# --- cmd_policy_sim_run exit codes -----------------------------------


class TestCmdPolicySimRun:
    def test_bundled_smoke_exit_0(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Bundled scenarios + empty proposed + no tightening → 0."""
        args = _args(proposed_policies=str(tmp_path))
        rc = cmd_policy_sim_run(args)
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["scenarios_evaluated"] == 3

    def test_unknown_baseline_source_exit_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        args = _args(
            proposed_policies=str(tmp_path),
            baseline_source="chaotic_neutral",
        )
        rc = cmd_policy_sim_run(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "baseline-source" in err

    def test_scenarios_path_not_found_exit_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        args = _args(
            scenarios=str(tmp_path / "not_there"),
            proposed_policies=str(tmp_path),
        )
        rc = cmd_policy_sim_run(args)
        assert rc == 1
        assert "scenario load failed" in capsys.readouterr().err

    def test_structural_invalid_proposed_exit_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        proposed_dir = tmp_path / "prop"
        proposed_dir.mkdir()
        (proposed_dir / "policy_worktree_profile.v1.json").write_text(
            json.dumps({"version": "v1"}),  # missing required keys
            encoding="utf-8",
        )
        args = _args(proposed_policies=str(proposed_dir))
        rc = cmd_policy_sim_run(args)
        assert rc == 1
        assert "simulation input error" in capsys.readouterr().err

    def test_output_file_written_atomic(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out_path = tmp_path / "out" / "report.json"
        args = _args(
            proposed_policies=str(tmp_path),
            output=str(out_path),
        )
        rc = cmd_policy_sim_run(args)
        assert rc == 0
        assert out_path.is_file()
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        assert parsed["scenarios_evaluated"] == 3
        # Stdout empty when --output used.
        assert capsys.readouterr().out == ""

    def test_host_fs_probes_flag_propagates(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        args = _args(
            proposed_policies=str(tmp_path),
            enable_host_fs_probes=True,
        )
        rc = cmd_policy_sim_run(args)
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["host_fs_dependent"] is True

    def test_format_text_output(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        args = _args(proposed_policies=str(tmp_path), format="text")
        rc = cmd_policy_sim_run(args)
        assert rc == 0
        assert "Policy Simulation Report" in capsys.readouterr().out
