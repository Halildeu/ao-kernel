"""V5 Epic 7 E-7-2 invariants: long-running session stress harness.

Library-mode only; stub LLM route; live_adapter_execution stays false.
Tests exercise the harness over small iteration counts so CI is fast.
The 24h+ operator profile is invoked manually via --iterations +
--duration-seconds and never scheduled in this slice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "scripts" / "run_stress_session.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ---- 1. Harness presence + module structure (4) -------------------------


def test_harness_file_exists() -> None:
    assert HARNESS_PATH.exists(), f"stress harness missing at {HARNESS_PATH}"


def test_harness_help_exits_zero() -> None:
    proc = _run(["--help"])
    assert proc.returncode == 0
    assert "stress" in proc.stdout.lower()
    assert "live_adapter_execution" in proc.stdout.lower()


def test_harness_imports_module_cleanly() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("stress_session", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run")
    assert hasattr(mod, "main")


def test_harness_module_docstring_pins_guard_flag_constraints() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("stress_session", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = (mod.__doc__ or "").lower()
    assert "live_adapter_execution" in doc
    assert "stub" in doc
    assert "library mode" in doc


# ---- 2. Run report contract (6) -----------------------------------------


def test_run_small_iteration_count_returns_report() -> None:
    proc = _run(["--iterations", "5", "--json-out", "-"])
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["schema_version"] == "stress-session-report.v1"
    assert report["iterations_requested"] == 5
    assert report["iterations_completed"] == 5


def test_run_records_rss_and_duration() -> None:
    proc = _run(["--iterations", "10", "--json-out", "-"])
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert isinstance(report["rss_kib_start"], int)
    assert isinstance(report["rss_kib_end"], int)
    assert isinstance(report["rss_kib_delta"], int)
    assert isinstance(report["duration_seconds_actual"], float)
    assert report["duration_seconds_actual"] >= 0


def test_run_records_three_guard_flags_const_false() -> None:
    proc = _run(["--iterations", "3", "--json-out", "-"])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["live_adapter_execution"] is False
    assert report["support_widening"] is False
    assert report["production_platform_claim"] is False


def test_run_writes_to_file_when_path_given(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    proc = _run(["--iterations", "3", "--json-out", str(out)])
    assert proc.returncode == 0
    report = json.loads(out.read_text())
    assert report["iterations_completed"] == 3


def test_run_duration_budget_short_circuits() -> None:
    """Even with a high iteration count, a tiny duration budget caps the
    actual completed iterations."""
    proc = _run(["--iterations", "10000000", "--duration-seconds", "0.05", "--json-out", "-"])
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["iterations_completed"] < 10000000
    # Allow some scheduler slop; budget is 0.05s, loop should not run
    # for more than ~5s under any reasonable runner.
    assert report["duration_seconds_actual"] < 5.0


def test_run_invalid_iterations_exits_two() -> None:
    proc = _run(["--iterations", "0", "--json-out", "-"])
    assert proc.returncode == 2


# ---- 3. CI safety (3) ----------------------------------------------------


def test_harness_has_safe_default_iteration_count() -> None:
    """Default --iterations must be small enough for CI."""
    proc = _run(["--help"])
    assert proc.returncode == 0
    assert "default 50" in proc.stdout or "default: 50" in proc.stdout


def test_harness_never_imports_live_provider_clients() -> None:
    """E-7-2 must not import anthropic/openai/etc client modules."""
    text = HARNESS_PATH.read_text()
    forbidden = (
        "import anthropic",
        "from anthropic",
        "import openai",
        "from openai",
        "import requests",
        "from requests",
    )
    for token in forbidden:
        assert token not in text, f"harness must not import live provider: {token!r}"
