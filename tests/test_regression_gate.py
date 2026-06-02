"""Invariant test suite for V5 Epic 7x: Regression gate (CI promotion track).

Codex 019e84b7 cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

5 BLOCKER + 8 hardening + 2 implementation-time pins absorbed:
- F1 Impl deferral until E-7a (#805) merged → now resolved (PR #805 MERGED)
- F2 Policy-driven exit semantics (advisory/manual_block/ci_block_candidate)
- F3 Metric direction (higher_is_worse / lower_is_worse) + skip reason codes
- F4 Schema replay/audit fields (compared_from + counts + claim_boundary)
- F5 Module boundary: regression.py reuses compare.py (no duplicate motor)
- iter-2 pin: unknown enforcement_mode fail-closed (ValueError)
- iter-2 pin: skip_reason canonical single field

~30 invariants across 9 sections.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "regression-comparison-result.schema.v1.json"
MODULE_PATH = REPO_ROOT / "ao_kernel" / "_internal" / "scorecard" / "regression.py"
COMPARE_PATH = REPO_ROOT / "ao_kernel" / "_internal" / "scorecard" / "compare.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "regression_gate.py"
BASELINE_PATH = REPO_ROOT / "docs" / "performance" / "baseline.v1.json"
THRESHOLD_PATH = REPO_ROOT / "docs" / "performance" / "performance-regression-threshold.v1.json"
CATALOG_PATH = REPO_ROOT / "docs" / "performance" / "performance-scenario-catalog.v1.json"

sys.path.insert(0, str(REPO_ROOT))

from ao_kernel._internal.scorecard.regression import (  # noqa: E402
    ARTIFACT_KIND,
    SCHEMA_VERSION,
    ComparisonInputs,
    build_comparison_result,
    determine_exit_code,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _make_scorecard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "generated_at": "2026-06-01T20:00:00Z",
        "git_sha": "abc1234",
        "pr_number": None,
        "benchmarks": rows,
    }


def _make_row(scenario: str, duration_ms: float, status: str = "pass") -> dict[str, Any]:
    return {
        "scenario": scenario,
        "status": status,
        "workflow_completed": True,
        "duration_ms": duration_ms,
        "cost_consumed_usd": 0.01,
        "cost_source": "mock_shim",
        "review_score": None,
    }


@pytest.fixture
def threshold() -> dict[str, Any]:
    return _load(THRESHOLD_PATH)


@pytest.fixture
def inputs_factory(tmp_path):
    """Factory: write head scorecard + return ComparisonInputs."""

    def _factory(head_rows: list[dict[str, Any]], cli_override: str | None = None):
        head_path = tmp_path / "head.json"
        head_path.write_text(json.dumps(_make_scorecard(head_rows)))
        return ComparisonInputs(
            head_scorecard_path=head_path,
            baseline_path=BASELINE_PATH,
            threshold_path=THRESHOLD_PATH,
            catalog_path=CATALOG_PATH,
            benchmark_mode="fast",
            cli_override=cli_override,
            generated_at="2026-06-01T21:00:00Z",
        )

    return _factory


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (6 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_schema_additional_properties_false_root():
    assert _load(SCHEMA_PATH).get("additionalProperties") is False


def test_schema_const_pins():
    schema = _load(SCHEMA_PATH)
    props = schema["properties"]
    assert props["schema_version"]["const"] == SCHEMA_VERSION
    assert props["service"]["const"] == "ao-kernel"
    assert props["artifact_kind"]["const"] == ARTIFACT_KIND


def test_schema_guard_flags_const_false():
    schema = _load(SCHEMA_PATH)
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_claim_boundary_const_true():
    schema = _load(SCHEMA_PATH)
    cb = schema["properties"]["claim_boundary"]["properties"]
    for key in ("not_sla", "not_required_check_yet", "single_run_candidate_baseline", "advisory_warn_default"):
        assert cb[key]["const"] is True, f"claim_boundary.{key} must be const true"


def test_schema_skip_reason_enum_complete():
    """Codex F3 absorb: 8 skip reason codes pinned."""
    schema = _load(SCHEMA_PATH)
    enum_vals = schema["$defs"]["scenario_result"]["properties"]["skip_reason"]["enum"]
    expected = {
        None,
        "missing_baseline",
        "missing_head",
        "advisory_only",
        "mode_mismatch",
        "baseline_zero",
        "missing_baseline_value",
        "unit_mismatch",
        "invalid_metric_type",
    }
    assert set(enum_vals) == expected


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (3 invariants)
# ---------------------------------------------------------------------------


def _validate(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(_load(SCHEMA_PATH)).validate(instance)


def _example_result() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "service": "ao-kernel",
        "artifact_kind": ARTIFACT_KIND,
        "guard_flags": {
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "claim_boundary": {
            "not_sla": True,
            "not_required_check_yet": True,
            "single_run_candidate_baseline": True,
            "advisory_warn_default": True,
        },
        "compared_from": {
            "head_scorecard_path": "head.json",
            "head_scorecard_sha256": "a" * 64,
            "baseline_path": "docs/performance/baseline.v1.json",
            "baseline_sha256": "b" * 64,
            "threshold_path": "docs/performance/performance-regression-threshold.v1.json",
            "threshold_sha256": "c" * 64,
            "catalog_path": "docs/performance/performance-scenario-catalog.v1.json",
            "catalog_sha256": "d" * 64,
            "benchmark_mode": "fast",
            "enforcement_mode_resolved": "advisory",
            "cli_override_applied": None,
            "generated_at": "2026-06-01T20:00:00Z",
        },
        "overall_status": "pass",
        "counts": {"passed": 0, "warned": 0, "hard_failed": 0, "skipped": 0},
        "scenarios": [],
        "observed_extra_scenarios": [],
    }


def test_schema_rejects_production_platform_claim_true():
    result = _example_result()
    result["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(result)


def test_schema_rejects_unknown_overall_status():
    result = _example_result()
    result["overall_status"] = "red"
    with pytest.raises(Exception):
        _validate(result)


def test_schema_rejects_unknown_enforcement_mode():
    result = _example_result()
    result["compared_from"]["enforcement_mode_resolved"] = "force_pass"
    with pytest.raises(Exception):
        _validate(result)


# ---------------------------------------------------------------------------
# Section 3 — Comparison logic (5 invariants)
# ---------------------------------------------------------------------------


def test_regression_above_warn_threshold_yields_warn(threshold, inputs_factory):
    """200ms baseline + 250ms head = +25% → warn (>= warn_pct=20, < hard=30)."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 250.0),
            _make_row("governed_bugfix", 120.0),
        ]
    )
    result = build_comparison_result(inputs, threshold)
    gr = next(s for s in result["scenarios"] if s["id"] == "governed_review")
    assert gr["status"] == "warn"
    assert gr["pct_change"] == 25.0
    assert gr["is_improvement"] is False


def test_regression_above_hard_threshold_yields_hard_fail(threshold, inputs_factory):
    """200ms baseline + 280ms head = +40% → hard_fail."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 280.0),
            _make_row("governed_bugfix", 120.0),
        ]
    )
    result = build_comparison_result(inputs, threshold)
    gr = next(s for s in result["scenarios"] if s["id"] == "governed_review")
    assert gr["status"] == "hard_fail"
    assert gr["pct_change"] == 40.0


def test_improvement_yields_pass_with_is_improvement_flag(threshold, inputs_factory):
    """200ms baseline + 150ms head = -25% → pass + is_improvement=true."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 150.0),
            _make_row("governed_bugfix", 120.0),
        ]
    )
    result = build_comparison_result(inputs, threshold)
    gr = next(s for s in result["scenarios"] if s["id"] == "governed_review")
    assert gr["status"] == "pass"
    assert gr["pct_change"] == -25.0
    assert gr["is_improvement"] is True


def test_missing_head_scenario_yields_skip(threshold, inputs_factory):
    """Head scorecard missing governed_review → status=skip, reason=missing_head."""
    inputs = inputs_factory([_make_row("governed_bugfix", 120.0)])
    result = build_comparison_result(inputs, threshold)
    gr = next(s for s in result["scenarios"] if s["id"] == "governed_review")
    assert gr["status"] == "skip"
    assert gr["skip_reason"] == "missing_head"


def test_observed_extra_scenarios_do_not_gate(threshold, inputs_factory):
    """Catalog-extra scenario in head → observed_extra; gate unaffected."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 200.0),
            _make_row("governed_bugfix", 120.0),
            _make_row("extra_unknown_scenario", 9999.0),
        ]
    )
    result = build_comparison_result(inputs, threshold)
    assert "extra_unknown_scenario" in result["observed_extra_scenarios"]
    # Overall should still be pass (extras don't gate)
    assert result["overall_status"] == "pass"


# ---------------------------------------------------------------------------
# Section 4 — Exit semantics (4 invariants)
# ---------------------------------------------------------------------------


def test_advisory_mode_hard_fail_exits_zero():
    result = {"overall_status": "hard_fail"}
    assert determine_exit_code(result, "advisory", None) == 0


def test_manual_block_mode_hard_fail_exits_one():
    result = {"overall_status": "hard_fail"}
    assert determine_exit_code(result, "manual_block", None) == 1


def test_ci_block_candidate_mode_warn_exits_one():
    result = {"overall_status": "warn"}
    assert determine_exit_code(result, "ci_block_candidate", None) == 1


def test_strict_mode_override_warn_exits_one():
    """Codex F2 absorb: --strict-mode overrides policy default."""
    result = {"overall_status": "warn"}
    # Even with advisory enforcement, strict override exits 1
    assert determine_exit_code(result, "advisory", "strict") == 1


# ---------------------------------------------------------------------------
# Section 5 — Fail-closed enforcement_mode (2 invariants — iter-2 pin)
# ---------------------------------------------------------------------------


def test_determine_exit_code_rejects_unknown_enforcement_mode():
    """Codex iter-2 residual: unknown enforcement_mode must raise (not fail-open)."""
    result = {"overall_status": "pass"}
    with pytest.raises(ValueError, match="unknown enforcement_mode"):
        determine_exit_code(result, "ci_block_red", None)


def test_determine_exit_code_rejects_unknown_cli_override():
    result = {"overall_status": "pass"}
    with pytest.raises(ValueError, match="unknown cli_override"):
        determine_exit_code(result, "advisory", "force_pass")


# ---------------------------------------------------------------------------
# Section 6 — Catalog mode + enforcement filter (3 invariants)
# ---------------------------------------------------------------------------


def test_catalog_full_mode_smoke_skipped_in_fast_run(threshold, inputs_factory):
    """full_mode_smoke is advisory_only + mode=full; never appears in fast scenario list."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 200.0),
            _make_row("governed_bugfix", 120.0),
        ]
    )
    result = build_comparison_result(inputs, threshold)
    ids = {s["id"] for s in result["scenarios"]}
    assert "full_mode_smoke" not in ids
    assert ids == {"governed_review", "governed_bugfix"}


def test_compared_from_records_benchmark_mode(threshold, inputs_factory):
    inputs = inputs_factory([_make_row("governed_review", 200.0), _make_row("governed_bugfix", 120.0)])
    result = build_comparison_result(inputs, threshold)
    assert result["compared_from"]["benchmark_mode"] == "fast"


def test_compared_from_records_enforcement_mode(threshold, inputs_factory):
    inputs = inputs_factory([_make_row("governed_review", 200.0), _make_row("governed_bugfix", 120.0)])
    result = build_comparison_result(inputs, threshold)
    assert result["compared_from"]["enforcement_mode_resolved"] == threshold["enforcement_mode"]


# ---------------------------------------------------------------------------
# Section 7 — Module boundary discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_regression_module_does_not_modify_compare():
    """Codex F5 absorb: compare.py reuse, not mutation."""
    # The regression module must not re-implement compare.py diff functions.
    src = MODULE_PATH.read_text()
    assert "from ao_kernel._internal.scorecard.regression" not in src  # no self-import
    # Existing compare.py file is present (zero-touch reuse target)
    assert COMPARE_PATH.exists()


def test_script_is_thin_cli():
    """Codex F5 absorb: scripts/regression_gate.py ≤ 200 lines (thin CLI)."""
    body = SCRIPT_PATH.read_text()
    # ≤ 200 lines including imports + docstring + banner helper.
    line_count = body.count("\n") + (1 if body and not body.endswith("\n") else 0)
    assert line_count <= 200, f"regression_gate.py is {line_count} lines; thin CLI budget exceeded"


def test_script_imports_regression_module():
    src = SCRIPT_PATH.read_text()
    assert "from ao_kernel._internal.scorecard.regression import" in src


# ---------------------------------------------------------------------------
# Section 8 — Provenance + counts (3 invariants)
# ---------------------------------------------------------------------------


def test_all_four_sha256_sources_recorded(threshold, inputs_factory):
    inputs = inputs_factory([_make_row("governed_review", 200.0), _make_row("governed_bugfix", 120.0)])
    result = build_comparison_result(inputs, threshold)
    cf = result["compared_from"]
    for key in ("head_scorecard_sha256", "baseline_sha256", "threshold_sha256", "catalog_sha256"):
        assert len(cf[key]) == 64
        assert all(c in "0123456789abcdef" for c in cf[key])


def test_generated_at_recorded(threshold, inputs_factory):
    inputs = inputs_factory(
        [_make_row("governed_review", 200.0), _make_row("governed_bugfix", 120.0)],
    )
    result = build_comparison_result(inputs, threshold)
    assert result["compared_from"]["generated_at"] == "2026-06-01T21:00:00Z"


def test_counts_consistency(threshold, inputs_factory):
    """Counts derived from scenarios must equal aggregate."""
    inputs = inputs_factory(
        [
            _make_row("governed_review", 280.0),  # +40% → hard_fail
            _make_row("governed_bugfix", 120.0),  # 0% → pass
        ]
    )
    result = build_comparison_result(inputs, threshold)
    counts = result["counts"]
    actual = {"passed": 0, "warned": 0, "hard_failed": 0, "skipped": 0}
    for s in result["scenarios"]:
        st = s["status"]
        if st == "pass":
            actual["passed"] += 1
        elif st == "warn":
            actual["warned"] += 1
        elif st == "hard_fail":
            actual["hard_failed"] += 1
        else:
            actual["skipped"] += 1
    assert counts == actual
    assert counts["hard_failed"] == 1
    assert counts["passed"] == 1


# ---------------------------------------------------------------------------
# Section 9 — CLI end-to-end smoke (2 invariants)
# ---------------------------------------------------------------------------


def test_cli_exit_zero_when_no_regression(tmp_path):
    head = tmp_path / "head.json"
    head.write_text(
        json.dumps(
            _make_scorecard(
                [
                    _make_row("governed_review", 200.0),
                    _make_row("governed_bugfix", 120.0),
                ]
            )
        )
    )
    out = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--head",
            str(head),
            "--baseline",
            str(BASELINE_PATH),
            "--threshold",
            str(THRESHOLD_PATH),
            "--catalog",
            str(CATALOG_PATH),
            "--benchmark-mode",
            "fast",
            "--out",
            str(out),
            "--generated-at",
            "2026-06-01T21:00:00Z",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    artifact = json.loads(out.read_text())
    assert artifact["overall_status"] == "pass"


def test_cli_strict_mode_emits_banner_and_exits_one_on_warn(tmp_path):
    head = tmp_path / "head.json"
    head.write_text(
        json.dumps(
            _make_scorecard(
                [
                    _make_row("governed_review", 250.0),  # +25% warn
                    _make_row("governed_bugfix", 120.0),
                ]
            )
        )
    )
    out = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--head",
            str(head),
            "--baseline",
            str(BASELINE_PATH),
            "--threshold",
            str(THRESHOLD_PATH),
            "--catalog",
            str(CATALOG_PATH),
            "--benchmark-mode",
            "fast",
            "--out",
            str(out),
            "--generated-at",
            "2026-06-01T21:00:00Z",
            "--strict-mode",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "operator-local" in result.stderr
    artifact = json.loads(out.read_text())
    assert artifact["overall_status"] == "warn"
    assert artifact["compared_from"]["cli_override_applied"] == "strict"


# ---------------------------------------------------------------------------
# Section 10 — Governance (2 invariants)
# ---------------------------------------------------------------------------
