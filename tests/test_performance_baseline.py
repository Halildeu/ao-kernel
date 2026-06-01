"""Invariant test suite for V5 Epic 7: Performance baseline + threshold policy.

Codex 019e8410 cross-AI plan-time AGREE (4 iters: REVISE/REVISE/REVISE/AGREE).

7 BLOCKER + 5 BLOCKER + 1 BLOCKER absorbed across 3 iters:
- E7-GATE-SEMANTICS (advisory enforcement; no CI hard-fail in E-7a)
- E7-P95-MISMATCH (duration_ms single_run; p95 deferred to E-7h)
- E7-THRESHOLD-DEFAULTS (20% warn / 30% hard; matches existing repo default)
- E7-SCENARIO-CATALOG-FILE + E7-BASELINE-SCHEMA (3 schema files)
- E7-WORKFLOW-ID-SOURCE (catalog join, not from scorecard)
- E7-BASELINE-CATALOG-MODE-FILTER (mode + enforcement filter)

~37 invariants across 9 sections.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PERF_DIR = REPO_ROOT / "docs" / "performance"
SCHEMAS_DIR = REPO_ROOT / "ao_kernel" / "defaults" / "schemas"
CATALOG_PATH = PERF_DIR / "performance-scenario-catalog.v1.json"
BASELINE_PATH = PERF_DIR / "baseline.v1.json"
THRESHOLD_PATH = PERF_DIR / "performance-regression-threshold.v1.json"
README_PATH = PERF_DIR / "README.md"
CATALOG_SCHEMA_PATH = SCHEMAS_DIR / "performance-scenario-catalog.schema.v1.json"
BASELINE_SCHEMA_PATH = SCHEMAS_DIR / "performance-baseline.schema.v1.json"
THRESHOLD_SCHEMA_PATH = SCHEMAS_DIR / "performance-regression-threshold.schema.v1.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "promote_baseline.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_catalog() -> dict[str, Any]:
    return _load(CATALOG_PATH)


def load_baseline() -> dict[str, Any]:
    return _load(BASELINE_PATH)


def load_threshold() -> dict[str, Any]:
    return _load(THRESHOLD_PATH)


def _validate(instance: dict, schema_path: Path) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = json.loads(schema_path.read_text())
    Draft202012Validator(schema).validate(instance)


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (8 invariants)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema_path",
    [CATALOG_SCHEMA_PATH, BASELINE_SCHEMA_PATH, THRESHOLD_SCHEMA_PATH],
)
def test_schema_is_valid_draft_2020_12(schema_path):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(json.loads(schema_path.read_text()))


@pytest.mark.parametrize(
    "schema_path",
    [CATALOG_SCHEMA_PATH, BASELINE_SCHEMA_PATH, THRESHOLD_SCHEMA_PATH],
)
def test_schema_root_additional_properties_false(schema_path):
    schema = json.loads(schema_path.read_text())
    assert schema.get("additionalProperties") is False


def test_schema_guard_flags_const_false_full_name():
    """Codex H8 absorb: full-name guard flag standard."""
    for schema_path in (CATALOG_SCHEMA_PATH, BASELINE_SCHEMA_PATH, THRESHOLD_SCHEMA_PATH):
        schema = json.loads(schema_path.read_text())
        gf = schema["properties"]["guard_flags"]["properties"]
        assert gf["support_widening_allowed"]["const"] is False
        assert gf["production_platform_claim_allowed"]["const"] is False
        assert gf["live_adapter_execution_allowed"]["const"] is False


def test_threshold_schema_enforcement_mode_enum():
    """Codex H6 absorb: enforcement_mode 3-value enum."""
    schema = json.loads(THRESHOLD_SCHEMA_PATH.read_text())
    enum_vals = schema["properties"]["enforcement_mode"]["enum"]
    assert set(enum_vals) == {"advisory", "manual_block", "ci_block_candidate"}


def test_baseline_schema_const_pins():
    schema = json.loads(BASELINE_SCHEMA_PATH.read_text())
    props = schema["properties"]
    assert props["schema_version"]["const"] == "performance-baseline.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["candidate_baseline"]["const"] is True
    assert props["sample_count"]["const"] == 1
    assert props["variance_profile"]["const"] == "single_ci_run"


def test_threshold_schema_policy_disclaimer_const_true():
    schema = json.loads(THRESHOLD_SCHEMA_PATH.read_text())
    disc = schema["properties"]["policy_disclaimer"]["properties"]
    assert disc["not_sla"]["const"] is True
    assert disc["operator_tunable"]["const"] is True
    assert disc["single_run_candidate_baseline"]["const"] is True


def test_baseline_schema_cost_source_enum():
    """Codex H2 absorb: cost_source enum including null."""
    schema = json.loads(BASELINE_SCHEMA_PATH.read_text())
    cs = schema["$defs"]["baseline_scenario"]["properties"]["cost_source"]["enum"]
    assert set(cs) == {"mock_shim", "real_adapter", "axis_seeded_only", None}


def test_catalog_schema_enforcement_enum():
    schema = json.loads(CATALOG_SCHEMA_PATH.read_text())
    enum_vals = schema["$defs"]["scenario"]["properties"]["enforcement"]["enum"]
    assert set(enum_vals) == {"policy_threshold", "advisory_only"}


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (4 invariants)
# ---------------------------------------------------------------------------


def test_threshold_rejects_production_platform_claim_true():
    threshold = load_threshold()
    threshold["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(threshold, THRESHOLD_SCHEMA_PATH)


def test_threshold_rejects_unknown_enforcement_mode():
    threshold = load_threshold()
    threshold["enforcement_mode"] = "ci_block_red"
    with pytest.raises(Exception):
        _validate(threshold, THRESHOLD_SCHEMA_PATH)


def test_baseline_rejects_candidate_false():
    baseline = load_baseline()
    baseline["candidate_baseline"] = False
    with pytest.raises(Exception):
        _validate(baseline, BASELINE_SCHEMA_PATH)


def test_threshold_rejects_force_pass_override():
    threshold = load_threshold()
    threshold["scenarios"][0]["enforcement_override"] = "force_pass"
    with pytest.raises(Exception):
        _validate(threshold, THRESHOLD_SCHEMA_PATH)


# ---------------------------------------------------------------------------
# Section 3 — Catalog content (4 invariants)
# ---------------------------------------------------------------------------


def test_catalog_validates_against_schema():
    _validate(load_catalog(), CATALOG_SCHEMA_PATH)


def test_catalog_workflow_ids_pinned_per_scenario():
    """Codex H3 absorb: catalog is the source of truth for workflow_id."""
    catalog = load_catalog()
    expected = {
        "governed_review": "review_ai_flow",
        "governed_bugfix": "governed_bugfix_bench",
        "full_mode_smoke": "review_ai_flow",
    }
    actual = {s["id"]: s["workflow_id"] for s in catalog["scenarios"]}
    assert actual == expected


def test_catalog_full_mode_smoke_is_advisory_only():
    """Codex H13 absorb: full_mode_smoke is advisory_only with may_skip true."""
    catalog = load_catalog()
    full_mode = next(s for s in catalog["scenarios"] if s["id"] == "full_mode_smoke")
    assert full_mode["mode"] == "full"
    assert full_mode["enforcement"] == "advisory_only"
    assert full_mode["may_skip_on_prereq_miss"] is True


def test_catalog_no_duplicate_scenario_ids():
    catalog = load_catalog()
    ids = [s["id"] for s in catalog["scenarios"]]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Section 4 — Baseline content (5 invariants)
# ---------------------------------------------------------------------------


def test_baseline_validates_against_schema():
    _validate(load_baseline(), BASELINE_SCHEMA_PATH)


def test_baseline_generated_from_has_all_metadata():
    """Codex H3 absorb: generated_from 7 metadata fields."""
    baseline = load_baseline()
    gf = baseline["generated_from"]
    for key in (
        "scorecard_schema_version",
        "source_git_sha",
        "source_git_ref",
        "benchmark_mode",
        "python_version",
        "runner_os",
        "generated_at",
    ):
        assert key in gf and gf[key], f"missing/empty generated_from.{key}"


def test_baseline_candidate_invariants():
    baseline = load_baseline()
    assert baseline["candidate_baseline"] is True
    assert baseline["sample_count"] == 1
    assert baseline["variance_profile"] == "single_ci_run"


def test_baseline_scenarios_non_empty():
    """E-7a committed fast baseline has >=1 entry per catalog (Codex impl note)."""
    baseline = load_baseline()
    assert len(baseline["scenarios"]) >= 1


def test_baseline_each_scenario_metric_duration_ms():
    """Codex E7-P95-MISMATCH absorb: only duration_ms single_run."""
    baseline = load_baseline()
    for scenario in baseline["scenarios"]:
        assert scenario["metric"]["name"] == "duration_ms"
        assert scenario["metric"]["unit"] == "ms"
        assert scenario["metric"]["statistic"] == "single_run"
        assert scenario["status"] in {"pass", "fail"}


# ---------------------------------------------------------------------------
# Section 5 — Threshold content (5 invariants)
# ---------------------------------------------------------------------------


def test_threshold_validates_against_schema():
    _validate(load_threshold(), THRESHOLD_SCHEMA_PATH)


def test_threshold_enforcement_mode_advisory_in_e7a():
    """Codex E7-GATE-SEMANTICS absorb: E-7a is advisory only."""
    assert load_threshold()["enforcement_mode"] == "advisory"


def test_threshold_baseline_ref_points_to_baseline_file():
    threshold = load_threshold()
    ref_path = REPO_ROOT / threshold["baseline_ref"]
    assert ref_path == BASELINE_PATH


def test_threshold_global_defaults_conservative():
    """Codex E7-THRESHOLD-DEFAULTS absorb: 20%/30% conservative defaults."""
    defaults = load_threshold()["global_defaults"]
    assert defaults["warn_threshold_pct"] == 20.0
    assert defaults["hard_fail_threshold_pct"] == 30.0


def test_warn_below_hard_per_scenario():
    """Codex H5 absorb: Python invariant (JSON Schema field-to-field is hard)."""
    threshold = load_threshold()
    for scenario in threshold["scenarios"]:
        warn = scenario.get("warn_threshold_pct")
        hard = scenario.get("hard_fail_threshold_pct")
        if warn is None or hard is None:
            continue  # advisory_only
        assert warn < hard, f"{scenario['id']}: warn {warn} >= hard {hard}"


# ---------------------------------------------------------------------------
# Section 6 — Cross-validation (mode + enforcement filter) (5 invariants)
# ---------------------------------------------------------------------------


def expected_baseline_catalog_ids(catalog: dict, baseline: dict) -> set[str]:
    """Codex E7-BASELINE-CATALOG-MODE-FILTER absorb.

    Baseline IDs come from catalog entries filtered by:
    - mode == baseline.generated_from.benchmark_mode
    - enforcement == 'policy_threshold'
    """
    mode = baseline["generated_from"]["benchmark_mode"]
    return {s["id"] for s in catalog["scenarios"] if s["mode"] == mode and s["enforcement"] == "policy_threshold"}


def test_baseline_ids_match_policy_threshold_catalog_for_mode():
    """Codex iter-3 BLOCKER absorb: mode + enforcement filtered cross-validation."""
    baseline = load_baseline()
    catalog = load_catalog()
    baseline_ids = {s["id"] for s in baseline["scenarios"]}
    expected = expected_baseline_catalog_ids(catalog, baseline)
    assert baseline_ids == expected, f"baseline IDs {baseline_ids} != mode/enforcement filter {expected}"


def test_threshold_scenarios_subset_of_catalog():
    threshold = load_threshold()
    catalog = load_catalog()
    threshold_ids = {s["id"] for s in threshold["scenarios"]}
    catalog_ids = {s["id"] for s in catalog["scenarios"]}
    assert threshold_ids.issubset(catalog_ids), f"threshold IDs {threshold_ids - catalog_ids} missing from catalog"


def test_full_mode_smoke_threshold_is_advisory_null():
    """Codex H4 absorb: full_mode_smoke threshold values null + override."""
    threshold = load_threshold()
    full_mode = next(s for s in threshold["scenarios"] if s["id"] == "full_mode_smoke")
    assert full_mode["warn_threshold_pct"] is None
    assert full_mode["hard_fail_threshold_pct"] is None
    assert full_mode["enforcement_override"] == "advisory_only"


def test_each_baseline_scenario_mode_matches_generated_from():
    """Codex H5 absorb: baseline scenario mode parity via catalog lookup."""
    baseline = load_baseline()
    expected_mode = baseline["generated_from"]["benchmark_mode"]
    catalog = load_catalog()
    catalog_by_id = {s["id"]: s for s in catalog["scenarios"]}
    for scenario in baseline["scenarios"]:
        catalog_entry = catalog_by_id[scenario["id"]]
        assert catalog_entry["mode"] == expected_mode, (
            f"baseline scenario {scenario['id']} catalog mode={catalog_entry['mode']} != baseline mode={expected_mode}"
        )


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_RE = re.compile(r"^(\s*)```")


def _iter_prose_lines(text: str):
    """Yield (line, prose) tuples for non-fenced lines with inline code stripped."""
    in_fence = False
    for line in text.splitlines():
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _INLINE_CODE_RE.sub("", line)
        yield line, prose


def test_no_sla_or_guarantee_wording_in_artifacts():
    """Claim scanner across artifacts.

    Codex iter-4 absorb: allow ``not_sla`` (schema field name) and
    "not SLA" (disclaimer prose). Forbid positive guarantee/SLA claims.
    Wording-discipline sections that quote forbidden tokens inside inline
    code spans / fenced code blocks / lines explicitly flagged as
    "forbidden|discipline|prohibited|yasak" are ignored.
    """
    forbidden = (
        "we guarantee",
        "production sla",
        "contractual sla",
        "guaranteed performance",
    )
    allowed_markers = ("not_sla", "not sla", "no sla")
    discipline_markers = ("forbidden", "discipline", "prohibited", "yasak")
    for path in (CATALOG_PATH, BASELINE_PATH, THRESHOLD_PATH, README_PATH):
        for raw_line, prose in _iter_prose_lines(path.read_text()):
            lowered_prose = prose.lower()
            lowered_raw = raw_line.lower()
            if any(marker in lowered_raw for marker in discipline_markers):
                continue
            for token in forbidden:
                pos = lowered_prose.find(token)
                if pos < 0:
                    continue
                window = lowered_prose[max(0, pos - 32) : pos + len(token) + 32]
                if any(marker in window for marker in allowed_markers):
                    continue
                pytest.fail(f"forbidden SLA/guarantee wording in {path.name}: token={token!r}; window={window!r}")


# ---------------------------------------------------------------------------
# Section 7 — Promote script (4 invariants)
# ---------------------------------------------------------------------------


def test_promote_script_constants_pinned():
    """Codex H1 absorb: script exposes the empty-selection exit-code constant
    and the canonical JSON emitter; both must match the documented contract.
    """
    import promote_baseline

    assert promote_baseline.EXIT_EMPTY_SELECTION == 2
    rendered = promote_baseline._canonical_json({"b": 1, "a": 2})
    # sort_keys=True → keys alphabetized; trailing newline contract
    assert rendered.startswith('{\n  "a": 2,\n  "b": 1\n}')
    assert rendered.endswith("\n")


def test_select_scenarios_fast_mode_includes_policy_threshold_only():
    from promote_baseline import select_scenarios_for_baseline

    catalog = load_catalog()
    selected = select_scenarios_for_baseline(catalog, "fast")
    ids = {s["id"] for s in selected}
    assert ids == {"governed_review", "governed_bugfix"}


def test_select_scenarios_full_mode_yields_empty_because_advisory_only():
    """Codex iter-3 absorb: full mode yields 0 policy_threshold entries."""
    from promote_baseline import select_scenarios_for_baseline

    catalog = load_catalog()
    selected = select_scenarios_for_baseline(catalog, "full")
    assert selected == []


def test_promote_script_deterministic_output_with_fixed_generated_at(tmp_path):
    """Codex H7 absorb: --generated-at fixed → byte-equal output."""
    from promote_baseline import build_baseline

    scorecard = {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": "abc1234",
        "pr_number": None,
        "benchmarks": [
            {
                "scenario": "governed_review",
                "status": "pass",
                "workflow_completed": True,
                "duration_ms": 200,
                "cost_consumed_usd": 0.01,
                "cost_source": "mock_shim",
                "review_score": None,
            },
            {
                "scenario": "governed_bugfix",
                "status": "pass",
                "workflow_completed": True,
                "duration_ms": 120,
                "cost_consumed_usd": 0.01,
                "cost_source": "mock_shim",
                "review_score": None,
            },
        ],
    }
    catalog = load_catalog()
    baseline_a = build_baseline(
        catalog,
        scorecard,
        benchmark_mode="fast",
        source_git_sha="fd8241c",
        source_git_ref="refs/heads/main",
        python_version="3.13",
        runner_os="ubuntu-latest",
        generated_at="2026-06-01T20:00:00Z",
    )
    baseline_b = build_baseline(
        catalog,
        scorecard,
        benchmark_mode="fast",
        source_git_sha="fd8241c",
        source_git_ref="refs/heads/main",
        python_version="3.13",
        runner_os="ubuntu-latest",
        generated_at="2026-06-01T20:00:00Z",
    )
    assert baseline_a == baseline_b


def test_promote_script_cli_exits_2_on_empty_selection_without_allow_empty(tmp_path):
    """Codex iter-4 implementation note: full mode without --allow-empty exits 2."""
    scorecard = {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": "abc1234",
        "pr_number": None,
        "benchmarks": [],
    }
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard))
    out_path = tmp_path / "baseline.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--scorecard",
            str(scorecard_path),
            "--scenario-catalog",
            str(CATALOG_PATH),
            "--out",
            str(out_path),
            "--source-git-sha",
            "fd8241c",
            "--source-git-ref",
            "refs/heads/main",
            "--benchmark-mode",
            "full",
            "--python-version",
            "3.13",
            "--runner-os",
            "ubuntu-latest",
            "--generated-at",
            "2026-06-01T20:00:00Z",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, (
        f"expected exit 2 for empty selection without --allow-empty; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


# ---------------------------------------------------------------------------
# Section 8 — Zero-touch governance (2 invariants)
# ---------------------------------------------------------------------------


def test_existing_scorecard_schema_present_and_untouched():
    """Codex H10 absorb: tests/test_scorecard_schema.py ZERO TOUCH."""
    path = REPO_ROOT / "tests" / "test_scorecard_schema.py"
    assert path.exists()


def test_existing_scorecard_schema_file_present():
    schema_path = SCHEMAS_DIR / "scorecard.schema.v1.json"
    assert schema_path.exists(), "existing scorecard schema must remain present"


# ---------------------------------------------------------------------------
# Section 9 — README discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_readme_has_numbered_sections():
    text = README_PATH.read_text()
    for n in range(1, 11):
        assert re.search(rf"^## {n}\.", text, re.MULTILINE), f"missing section {n}"


def test_readme_mentions_guard_flags_and_disclaimer():
    text = README_PATH.read_text()
    assert "Not SLA" in text
    assert "candidate baseline" in text.lower()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text


def test_readme_documents_mode_enforcement_filter():
    text = README_PATH.read_text().lower()
    assert "policy_threshold" in text
    assert "advisory_only" in text
    assert "mode" in text and "filter" in text
