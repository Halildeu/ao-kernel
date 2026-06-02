"""V5 Epic 7 E-7-3 invariants: memory profiling harness.

tracemalloc only (stdlib, zero extras). Library mode + stub workload.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "scripts" / "run_memory_profile.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ---- 1. Harness presence + structure (4) --------------------------------


def test_harness_file_exists() -> None:
    assert HARNESS_PATH.exists()


def test_harness_help_exits_zero() -> None:
    proc = _run(["--help"])
    assert proc.returncode == 0
    assert "tracemalloc" in proc.stdout.lower()
    assert "live_adapter_execution" in proc.stdout.lower()


def test_harness_imports_cleanly() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("memprof", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run")
    assert hasattr(mod, "main")


def test_harness_docstring_pins_zero_extra_dependency() -> None:
    text = HARNESS_PATH.read_text()
    assert "tracemalloc" in text.lower()
    assert "zero extra dependencies" in text.lower() or "stdlib" in text.lower()


# ---- 2. Run report contract (7) -----------------------------------------


def test_run_small_iter_returns_report() -> None:
    proc = _run(["--iterations", "20", "--top", "5", "--json-out", "-"])
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["schema_version"] == "memory-profile-report.v1"
    assert report["iterations_completed"] == 20


def test_run_records_rss_and_traced_memory() -> None:
    proc = _run(["--iterations", "30", "--json-out", "-"])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert isinstance(report["rss_kib_start"], int)
    assert isinstance(report["rss_kib_end"], int)
    assert isinstance(report["traced_kib_current"], float)
    assert isinstance(report["traced_kib_peak"], float)
    # tracemalloc peak MUST be > 0 because the workload allocates each iter
    assert report["traced_kib_peak"] > 0


def test_run_top_allocations_structure() -> None:
    proc = _run(["--iterations", "30", "--top", "3", "--json-out", "-"])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert len(report["top_allocations"]) <= 3
    for row in report["top_allocations"]:
        assert "filename" in row
        assert "lineno" in row
        assert "size_kib" in row
        assert "count" in row
        assert isinstance(row["count"], int)


def test_run_retain_every_records_retained_count() -> None:
    proc = _run(["--iterations", "40", "--retain-every", "5", "--json-out", "-"])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    # Retained at indices 0, 5, 10, ..., 35 => 8 objects
    assert report["retained_count"] == 8
    assert report["retain_every"] == 5


def test_run_three_guard_flags_const_false() -> None:
    proc = _run(["--iterations", "10", "--json-out", "-"])
    report = json.loads(proc.stdout)
    assert report["live_adapter_execution"] is False
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False


def test_run_writes_to_file_when_path_given(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    proc = _run(["--iterations", "10", "--json-out", str(out)])
    assert proc.returncode == 0
    report = json.loads(out.read_text())
    assert report["iterations_completed"] == 10


def test_run_invalid_top_exits_two() -> None:
    proc = _run(["--iterations", "10", "--top", "0", "--json-out", "-"])
    assert proc.returncode == 2


# ---- 3. CI safety (3) ----------------------------------------------------


def test_harness_safe_default_iter_count() -> None:
    proc = _run(["--help"])
    assert "default 200" in proc.stdout or "default: 200" in proc.stdout


def test_harness_does_not_import_live_providers() -> None:
    text = HARNESS_PATH.read_text()
    forbidden = (
        "import anthropic",
        "from anthropic",
        "import openai",
        "from openai",
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
    )
    for token in forbidden:
        assert token not in text, f"harness must not import live provider: {token!r}"


def test_harness_does_not_import_optional_profilers() -> None:
    """E-7-3 ships zero extras. mprof/memray/scalene MUST NOT be imported."""
    text = HARNESS_PATH.read_text()
    forbidden = (
        "import mprof",
        "from mprof",
        "import memray",
        "from memray",
        "import scalene",
        "from scalene",
        "import objgraph",
        "from objgraph",
    )
    for token in forbidden:
        assert token not in text, f"E-7-3 ships zero extras; must not import {token!r}"
