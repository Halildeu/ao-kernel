"""Tests for the local GPP AI review gate (scripts/local_gpp_gate.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    module_path = _repo_root() / "scripts" / "local_gpp_gate.py"
    spec = importlib.util.spec_from_file_location("local_gpp_gate", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_template_module() -> Any:
    module_path = _repo_root() / "scripts" / "local_gpp_gate_review_template.py"
    spec = importlib.util.spec_from_file_location("local_gpp_gate_review_template", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(name: str) -> Path:
    return _repo_root() / "tests" / "fixtures" / "local_gpp_gate" / name


def _status_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "gpp_status.v1.json"


def _run_gate(argv: list[str]) -> int:
    mod = _load_module()
    return int(mod.main(argv))


def test_missing_reviewer_evidence_fails_closed(tmp_path: Path, capsys: Any) -> None:
    missing = tmp_path / "does-not-exist.json"
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(missing), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["gpp_2_status"] == "blocked"


def test_reviewer_revise_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_revise.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_reviewer_block_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_block.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_reviewer_unknown_verdict_fails_closed(tmp_path: Path) -> None:
    # An unknown verdict is rejected by the reviewer-evidence schema, so the
    # gate treats the file as schema-invalid and fails closed.
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["reviewer"]["verdict"] = "MAYBE"
    bad = tmp_path / "reviewer_unknown_verdict.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(bad), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_same_provider_review_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_same_provider.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["cross_provider_verified"] is False


def test_reviewer_agree_with_passing_checks_succeeds(tmp_path: Path, capsys: Any) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_agree.v1.json")), "--output", str(output)])

    captured = capsys.readouterr()
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "operator_may_merge"
    assert all(artifact["checks"].values())
    assert artifact["gpp_2_status"] == "blocked"
    assert artifact["support_widening"] is False
    assert artifact["production_platform_claim"] is False
    assert artifact["live_adapter_execution"] is False
    assert "operator_may_merge" in captured.out


def test_forbidden_action_flag_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_forbidden_action.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_support_widening_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_support_widening.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_production_platform_claim_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_production_claim.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_live_adapter_execution_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_live_adapter.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_tests_failed_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_tests_failed.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["tests_passed"] is False


def test_generated_evidence_contains_no_secret_material(tmp_path: Path, capsys: Any) -> None:
    # Build a reviewer evidence file whose agent label carries a unique
    # sentinel string. The gate output is structurally constrained and must
    # not propagate reviewer agent identifiers, so the sentinel must never
    # appear in the artifact or stdout. The sentinel is deliberately not a
    # real-looking credential pattern so repo secret scanners stay quiet.
    sentinel = "SENTINEL-do-not-propagate-canary-9c3f1a2b7e"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["implementer"]["agent"] = f"claude-{sentinel}"
    bad = tmp_path / "reviewer_with_sentinel.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(bad), "--output", str(output)])
    captured = capsys.readouterr()

    assert code == 0
    raw_output = output.read_text(encoding="utf-8")
    # The sentinel was placed in an agent identifier field. The gate output
    # is structurally constrained and does not echo reviewer agent
    # identifiers, so the sentinel must not appear in the artifact or stdout.
    assert sentinel not in raw_output
    assert sentinel not in captured.out
    # The gate output keys are exactly the whitelisted set.
    artifact = json.loads(raw_output)
    assert set(artifact.keys()) == {
        "schema_version",
        "decision",
        "repo",
        "work_package",
        "generated_at",
        "checks",
        "findings",
        "gpp_2_status",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
    }


def test_gpp_next_still_reports_blocked(tmp_path: Path) -> None:
    # A successful gate run must not mutate GPP state; gpp_next still
    # reports GPP-2 blocked afterward.
    output = tmp_path / "gate-evidence.json"
    code = _run_gate(["--review-evidence", str(_fixture("reviewer_agree.v1.json")), "--output", str(output)])
    assert code == 0

    gpp_next_path = _repo_root() / "scripts" / "gpp_next.py"
    spec = importlib.util.spec_from_file_location("gpp_next", gpp_next_path)
    assert spec is not None and spec.loader is not None
    gpp_next = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpp_next)

    payload = gpp_next.load_status(_status_path())
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    # The gate artifact also pins GPP-2 blocked.
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["gpp_2_status"] == "blocked"


def test_gate_output_validates_against_gate_evidence_schema(tmp_path: Path) -> None:
    mod = _load_module()
    output = tmp_path / "gate-evidence.json"
    code = mod.main(["--review-evidence", str(_fixture("reviewer_agree.v1.json")), "--output", str(output)])
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    # Round-trips cleanly through the bundled gate evidence schema validator.
    mod.validate_gate_evidence(artifact)


def test_review_template_is_schema_valid_and_fails_gate_unedited(tmp_path: Path) -> None:
    mod = _load_module()
    template_mod = _load_template_module()
    template = template_mod.build_template()

    # The blank template must itself satisfy the reviewer-evidence schema.
    mod.validate_gate_evidence  # noqa: B018 - sanity reference
    schema = mod.load_review_evidence_schema()
    from jsonschema import Draft202012Validator

    Draft202012Validator(schema).validate(template)

    # An unedited template must fail the gate closed (verdict placeholder
    # is REVISE), proving reviewers cannot pass the gate without filling it.
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"
    code = mod.main(["--review-evidence", str(template_path), "--output", str(output)])
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"


def test_no_output_path_still_prints_decision(capsys: Any) -> None:
    # Without --output the gate still runs and prints the decision.
    code = _run_gate(["--review-evidence", str(_fixture("reviewer_agree.v1.json"))])
    captured = capsys.readouterr()
    assert code == 0
    assert "operator_may_merge" in captured.out


def test_invocation_error_returns_two(tmp_path: Path, capsys: Any) -> None:
    # A non-JSON reviewer evidence file is treated as a fail-closed input,
    # not an invocation error; invocation errors (code 2) are reserved for
    # broken schema toolchain. Confirm bad JSON fails closed (code 1).
    bad = tmp_path / "not-json.json"
    bad.write_text("this is not json", encoding="utf-8")
    output = tmp_path / "gate-evidence.json"
    code = _run_gate(["--review-evidence", str(bad), "--output", str(output)])
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
