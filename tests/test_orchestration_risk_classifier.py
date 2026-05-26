"""AO-MA-3 risk classifier unit tests."""

from __future__ import annotations

from ao_kernel.orchestration.risk_classifier import RiskClassifier


def test_empty_paths_is_low() -> None:
    assert RiskClassifier.classify([]) == "low"


def test_pure_test_only_change_is_low() -> None:
    assert RiskClassifier.classify(["tests/fixtures/foo.json"]) == "low"


def test_runtime_module_is_normal() -> None:
    # ao_kernel/orchestration/orchestrator.py is not in the high-risk set
    # (orchestration runtime is itself low-impact relative to release gate).
    assert RiskClassifier.classify(["ao_kernel/orchestration/orchestrator.py"]) == "normal"


def test_workflow_change_is_high() -> None:
    assert RiskClassifier.classify([".github/workflows/test.yml"]) == "high"


def test_codeowners_change_is_high() -> None:
    assert RiskClassifier.classify(["CODEOWNERS"]) == "high"


def test_agents_md_change_is_high() -> None:
    assert RiskClassifier.classify(["AGENTS.md"]) == "high"


def test_gpp_status_change_is_high() -> None:
    assert RiskClassifier.classify([".claude/plans/gpp_status.v1.json"]) == "high"


def test_release_gate_script_change_is_high() -> None:
    assert RiskClassifier.classify(["scripts/ao_release_gate_decision.py"]) == "high"


def test_local_gpp_gate_script_change_is_high() -> None:
    assert RiskClassifier.classify(["scripts/local_gpp_gate.py"]) == "high"


def test_live_adapter_gate_change_is_high() -> None:
    assert RiskClassifier.classify(["scripts/live_adapter_gate_policy.py"]) == "high"


def test_gate_schema_change_is_high() -> None:
    assert RiskClassifier.classify(["ao_kernel/defaults/schemas/local-gpp-gate-evidence.schema.v1.json"]) == "high"


def test_ao_ma_schema_change_is_high() -> None:
    assert RiskClassifier.classify(["ao_kernel/defaults/schemas/ao-ma-task-graph.schema.v1.json"]) == "high"


def test_two_distinct_high_families_is_critical() -> None:
    paths = [
        ".github/workflows/test.yml",  # github family
        "ao_kernel/ao_release_gate.py",  # release-gate family
    ]
    assert RiskClassifier.classify(paths) == "critical"


def test_three_distinct_high_families_is_critical() -> None:
    paths = [
        "AGENTS.md",  # governance family
        "scripts/ao_release_gate_decision.py",  # release-gate family
        "ao_kernel/defaults/policies/policy_quality_gates.v1.json",  # policies family
    ]
    assert RiskClassifier.classify(paths) == "critical"


def test_single_family_multiple_paths_stays_high() -> None:
    # Two workflow files both belong to the github family.
    paths = [
        ".github/workflows/test.yml",
        ".github/workflows/publish.yml",
    ]
    assert RiskClassifier.classify(paths) == "high"


def test_is_high_risk_path_direct_check() -> None:
    assert RiskClassifier.is_high_risk_path(".github/workflows/test.yml") is True
    assert RiskClassifier.is_high_risk_path("tests/fixtures/some.json") is False
    assert RiskClassifier.is_high_risk_path("ao_kernel/orchestration/orchestrator.py") is False
