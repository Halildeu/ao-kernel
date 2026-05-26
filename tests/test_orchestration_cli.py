"""AO-MA-3 CLI handler tests (end-to-end CLI smoke)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ao_kernel.cli import main as cli_main
from ao_kernel.orchestration.cli_handlers import _parse_declared_specs

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_declared_specs_single() -> None:
    specs = _parse_declared_specs(["task-001:ao_kernel/foo.py,tests/test_foo.py:Fix foo"])
    assert specs is not None
    assert len(specs) == 1
    spec = specs[0]
    assert spec.task_id == "task-001"
    assert spec.write_paths == ["ao_kernel/foo.py", "tests/test_foo.py"]
    assert spec.description == "Fix foo"


def test_parse_declared_specs_multiple() -> None:
    specs = _parse_declared_specs(
        [
            "task-001:ao_kernel/a.py:slice A",
            "task-002:tests/test_b.py:slice B",
        ]
    )
    assert specs is not None
    assert len(specs) == 2


def test_parse_declared_specs_default_description() -> None:
    specs = _parse_declared_specs(["task-001:ao_kernel/foo.py"])
    assert specs is not None
    assert specs[0].description == "Slice task-001"


def test_parse_declared_specs_empty_returns_none() -> None:
    assert _parse_declared_specs(None) is None
    assert _parse_declared_specs([]) is None


def test_parse_declared_specs_invalid_format_exits() -> None:
    with pytest.raises(SystemExit, match="<task_id>:<comma-paths>"):
        _parse_declared_specs(["bad-input"])


def test_cli_plan_emits_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    rc = cli_main(
        [
            "orchestration",
            "plan",
            "--goal",
            "AO-MA-3 unit test smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    # Find the produced task_graph_id directory
    subdirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(subdirs) == 1
    subdir = subdirs[0]
    assert (subdir / "task_graph.v1.json").exists()
    assert (subdir / "manifest.v1.json").exists()
    manifest = json.loads((subdir / "manifest.v1.json").read_text(encoding="utf-8"))
    assert manifest["task_graph_id"].startswith("ao-ma-")


def test_cli_plan_overlap_exit_nonzero(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    rc = cli_main(
        [
            "orchestration",
            "plan",
            "--goal",
            "overlap smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--declared-spec",
            "task-001:ao_kernel/foo.py:A",
            "--declared-spec",
            "task-002:ao_kernel/foo.py:B",
            "--format",
            "json",
        ]
    )
    assert rc == 1


def test_thin_wrapper_script_invocation(tmp_path: Path) -> None:
    """scripts/ao_orchestrator.py thin wrapper forwards to canonical CLI."""

    out_dir = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ao_orchestrator.py"),
            "plan",
            "--goal",
            "thin wrapper smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, f"stderr: {completed.stderr}"
    assert "task_graph_id" in completed.stdout
