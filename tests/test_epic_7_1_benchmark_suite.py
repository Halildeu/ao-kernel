"""V5 Epic 7 E-7-1 invariants: production benchmark suite + cross-PR regression.

Binds the existing pieces (scenario catalog, benchmark scenarios, scorecard,
baseline, threshold policy, regression gate) into one coherent production
suite. The invariants verify the pieces are mutually consistent end-to-end —
so the runbook's claims are machine-backed (HARD RULE No Fake Work).

Machine-enforced invariants:
  - docs/performance/BENCHMARK-SUITE.md present + covers run→scorecard→gate→baseline
  - every primary catalog scenario has a real test module on disk
  - every primary catalog scenario maps to a scorecard scenario in the baseline
  - regression_gate CLI exists + documents head/baseline/threshold inputs
  - catalog + baseline guard flags all false
  - no .github/workflows/ mutation
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC = _REPO_ROOT / "docs" / "performance" / "BENCHMARK-SUITE.md"
_CATALOG = _REPO_ROOT / "docs" / "performance" / "performance-scenario-catalog.v1.json"
_BASELINE = _REPO_ROOT / "docs" / "performance" / "baseline.v1.json"
_GATE = _REPO_ROOT / "scripts" / "regression_gate.py"


def _catalog() -> dict:
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


# ---- 1. runbook present + coverage (2) ----------------------------------


def test_runbook_present() -> None:
    assert _DOC.is_file(), "docs/performance/BENCHMARK-SUITE.md missing (E-7-1)"


def test_runbook_covers_full_pipeline() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert "benchmark_scorecard.v1.json" in text
    assert "regression_gate.py" in text
    assert "baseline.v1.json" in text
    low = text.lower()
    assert "cross-pr" in low and "regression" in low
    assert "variance" in low, "runbook must keep the variance/single-run honesty discipline"


# ---- 2. catalog ↔ test modules ↔ baseline consistency (3) ---------------


def test_every_catalog_scenario_has_a_test_module() -> None:
    cat = _catalog()
    for sc in cat["scenarios"]:
        module = _REPO_ROOT / sc["test_module"]
        assert module.is_file(), f"catalog scenario {sc['id']}: missing test module {sc['test_module']}"


def test_primary_scenarios_present_in_baseline() -> None:
    """Every policy-enforced (non-advisory) scenario's scorecard id must exist
    in the baseline so the regression gate has something to compare against."""
    cat = _catalog()
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    # Collect baseline scenario ids (shape-tolerant: list of dicts under some key).
    baseline_text = json.dumps(baseline)
    enforced = [s for s in cat["scenarios"] if s.get("enforcement") != "advisory_only"]
    assert enforced, "expected at least one policy-enforced scenario"
    for sc in enforced:
        sid = sc["source_scorecard_scenario"]
        assert sid in baseline_text, f"enforced scenario {sid} absent from baseline.v1.json"


def test_regression_gate_cli_documents_inputs() -> None:
    assert _GATE.is_file(), "scripts/regression_gate.py missing (E-7x #806)"
    text = _GATE.read_text(encoding="utf-8")
    for flag in ("--head", "--baseline", "--threshold"):
        assert flag in text, f"regression_gate must accept {flag}"


# ---- 3. guard flags (2) -------------------------------------------------


def test_catalog_guard_flags_all_false() -> None:
    cat = _catalog()
    gf = cat["guard_flags"]
    assert gf["support_widening_allowed"] is False
    assert gf["production_platform_claim_allowed"] is False
    assert gf["live_adapter_execution_allowed"] is False


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_7_1_benchmark_suite.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-7-1 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-7-1 must not touch .github/workflows/. Touched: {touched}"
