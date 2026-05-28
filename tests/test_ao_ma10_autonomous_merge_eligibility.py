from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ao_ma10_autonomous_merge_eligibility.py"
PLAN = ROOT / ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json"
SNAPSHOT = ROOT / ".claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json"
EVIDENCE = ROOT / ".claude/plans/AO-MA-10A1-AUTONOMOUS-MERGE-ELIGIBILITY.v1.json"
BLOCKED_FIXTURE = ROOT / "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.blocked.valid.json"
READY_FIXTURE = ROOT / "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.ready.valid.json"
SCHEMA_NAME = "ao-ma-10-autonomous-merge-eligibility.schema.v1.json"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_script_module() -> Any:
    spec = importlib.util.spec_from_file_location("ao_ma10_autonomous_merge_eligibility", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_snapshot() -> dict[str, Any]:
    snapshot = _json(SNAPSHOT)
    snapshot["readiness"]["blockers"] = []
    snapshot["readiness"]["decision"] = "ready_for_dry_run"
    snapshot["readiness"]["warnings"] = ["repository_auto_merge_disabled_merge_agent_direct_mode_required"]
    snapshot["branch_protection"]["required_approving_review_count"] = 0
    snapshot["branch_protection"]["require_code_owner_reviews"] = False
    snapshot["merge_actor"]["login"] = "gladyatore-lab"
    snapshot["merge_actor"]["permission"] = "write"
    snapshot["merge_actor"]["viewer_can_administer"] = False
    snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] = True
    snapshot["rulesets"]["bypass_actors_count"] = 0
    snapshot["rulesets"]["bypass_actors_empty"] = True
    snapshot["rulesets"]["effective_required_checks"] = [
        {"context": "ao-release-gate-technical", "integration_id": 15368},
        {"context": "ao-release-gate-review", "integration_id": 15368},
    ]
    snapshot["rulesets"]["ao_release_gate_required_check_present"] = True
    snapshot["rulesets"]["ao_release_gate_source_pinned_to_actions"] = True
    snapshot["codeowners"]["broad_default_owner_absent"] = True
    snapshot["codeowners"]["broad_default_owner_present"] = False
    snapshot["codeowners"]["governance_paths_owned"] = True
    snapshot["ssot_cross_check"]["live_snapshot_conflicts_with_prior_claim"] = False
    return snapshot


def _eligibility(snapshot: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    mod = _load_script_module()
    return cast(
        dict[str, Any],
        mod.build_eligibility(
            snapshot=snapshot,
            plan=_json(PLAN),
            changed_files=changed_files,
            generated_at="2026-05-27T20:00:00Z",
        ),
    )


def test_ao_ma10a1_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-10-autonomous-merge-eligibility:v1"


def test_ao_ma10a1_fixtures_validate_against_schema() -> None:
    validator = Draft202012Validator(_schema())
    for fixture in (BLOCKED_FIXTURE, READY_FIXTURE, EVIDENCE):
        payload = _json(fixture)
        validator.validate(payload)
        assert payload["schema_version"] == "ao-ma-10-autonomous-merge-eligibility.v1"
        assert payload["release_authority"] == "ao-release-gate+github-ruleset"
        assert payload["ai_output_release_authority"] is False
        assert payload["mutations_performed"] is False


def test_ao_ma10a1_current_snapshot_stays_blocked_with_live_blockers() -> None:
    payload = _eligibility(
        _json(SNAPSHOT),
        ["tests/test_ao_ma10_autonomous_merge_eligibility.py"],
    )
    Draft202012Validator(_schema()).validate(payload)
    blockers = set(payload["decision"]["blockers"])
    assert payload["decision"]["result"] == "blocked"
    assert "readiness_snapshot_not_ready" in blockers
    assert "merge_actor_admin_permission_observed" in blockers
    assert "unexpected_merge_actor" in blockers
    assert "dedicated_merge_actor_not_confirmed" in blockers
    assert "ao_release_gate_required_check_missing" not in blockers
    assert "ao_release_gate_technical_required_check_missing" not in blockers
    assert "ao_release_gate_review_required_check_missing" not in blockers
    assert "legacy_required_review_blocks_low_risk_autonomy" not in blockers
    assert "ssot_live_required_check_drift_detected" not in blockers


def test_ao_ma10a1_committed_evidence_records_current_fail_closed_state() -> None:
    payload = _json(EVIDENCE)
    blockers = set(payload["decision"]["blockers"])
    assert payload["decision"]["result"] == "blocked"
    assert payload["read_only"] is True
    assert payload["mutations_performed"] is False
    assert "ao_release_gate_technical_required_check_missing" not in blockers
    assert "ao_release_gate_review_required_check_missing" not in blockers
    assert "merge_actor_admin_permission_observed" in blockers
    assert "unexpected_merge_actor" in blockers
    assert "dedicated_merge_actor_not_confirmed" in blockers
    assert "readiness_snapshot_not_ready" in blockers


def test_ao_ma10a1_ready_snapshot_and_low_risk_files_are_ready_for_dry_run() -> None:
    payload = _eligibility(
        _ready_snapshot(),
        [
            "ao_kernel/defaults/schemas/ao-ma-10-autonomous-merge-eligibility.schema.v1.json",
            "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.ready.valid.json",
            "tests/test_ao_ma10_autonomous_merge_eligibility.py",
        ],
    )
    assert payload["decision"]["result"] == "ready_for_low_risk_dry_run"
    assert payload["decision"]["blockers"] == []
    assert payload["candidate_changed_files"]["low_risk"] is True
    assert payload["github_gate_requirements"] == {
        "ao_release_gate_technical_required_check_present": True,
        "ao_release_gate_technical_source_pinned_to_actions": True,
        "ao_release_gate_review_required_check_present": True,
        "ao_release_gate_review_source_pinned_to_actions": True,
        "ruleset_bypass_actors_empty": True,
        "legacy_required_review_disabled_for_low_risk": True,
        "legacy_code_owner_review_disabled_for_low_risk": True,
        "dedicated_merge_actor_non_admin": True,
        "dedicated_merge_actor_without_admin_write": True,
    }


def test_ao_ma10a1_blocks_missing_changed_files() -> None:
    payload = _eligibility(_ready_snapshot(), [])
    assert payload["decision"]["result"] == "blocked"
    assert "changed_files_missing" in payload["decision"]["blockers"]


def test_ao_ma10a1_blocks_high_risk_and_not_allowed_paths() -> None:
    payload = _eligibility(
        _ready_snapshot(),
        [
            ".github/workflows/test.yml",
            "scripts/ao_release_gate_decision.py",
            ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
            "README.md",
        ],
    )
    assert payload["candidate_changed_files"]["low_risk"] is False
    assert "changed_files_not_low_risk" in payload["decision"]["blockers"]
    assert set(payload["candidate_changed_files"]["not_allowed"]) == {
        ".github/workflows/test.yml",
        "README.md",
        "scripts/ao_release_gate_decision.py",
    }
    prohibited_paths = {item["path"] for item in payload["candidate_changed_files"]["prohibited_matches"]}
    assert prohibited_paths == {".github/workflows/test.yml", "scripts/ao_release_gate_decision.py"}
    high_risk_paths = {item["path"] for item in payload["candidate_changed_files"]["release_gate_high_risk_matches"]}
    assert high_risk_paths == {
        ".github/workflows/test.yml",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        "scripts/ao_release_gate_decision.py",
    }


def test_ao_ma10a1_blocks_invalid_paths() -> None:
    payload = _eligibility(_ready_snapshot(), ["../outside.md", "/tmp/absolute.md"])
    assert "changed_file_path_invalid" in payload["decision"]["blockers"]
    assert payload["candidate_changed_files"]["invalid_paths"] == ["../outside.md", "/tmp/absolute.md"]


def test_ao_ma10a1_blocks_review_required_check_missing() -> None:
    snapshot = _ready_snapshot()
    snapshot["rulesets"]["effective_required_checks"] = [
        {"context": "ao-release-gate-technical", "integration_id": 15368},
    ]
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "ao_release_gate_review_required_check_missing" in payload["decision"]["blockers"]
    assert payload["github_gate_requirements"]["ao_release_gate_review_required_check_present"] is False


def test_ao_ma10a1_blocks_review_required_check_wrong_source_pin() -> None:
    snapshot = _ready_snapshot()
    snapshot["rulesets"]["effective_required_checks"][1]["integration_id"] = 99999
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "ao_release_gate_review_required_check_not_source_pinned" in payload["decision"]["blockers"]
    assert payload["github_gate_requirements"]["ao_release_gate_review_source_pinned_to_actions"] is False


def test_ao_ma10a1_blocks_legacy_review_and_code_owner_review() -> None:
    snapshot = _ready_snapshot()
    snapshot["branch_protection"]["required_approving_review_count"] = 1
    snapshot["branch_protection"]["require_code_owner_reviews"] = True
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "legacy_required_review_blocks_low_risk_autonomy" in payload["decision"]["blockers"]
    assert "legacy_code_owner_review_blocks_low_risk_autonomy" in payload["decision"]["blockers"]


def test_ao_ma10a1_blocks_admin_or_unconfirmed_merge_actor() -> None:
    snapshot = _ready_snapshot()
    snapshot["merge_actor"]["permission"] = "admin"
    snapshot["merge_actor"]["viewer_can_administer"] = True
    snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] = False
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "merge_actor_admin_permission_observed" in payload["decision"]["blockers"]
    assert "dedicated_merge_actor_not_confirmed" in payload["decision"]["blockers"]


def test_ao_ma10a1_propagates_unexpected_merge_actor_from_readiness_snapshot() -> None:
    snapshot = _ready_snapshot()
    snapshot["readiness"]["decision"] = "blocked"
    snapshot["readiness"]["blockers"] = ["unexpected_merge_actor"]
    snapshot["merge_actor"]["login"] = "some-other-writer"
    snapshot["merge_actor"]["permission"] = "write"
    snapshot["merge_actor"]["viewer_can_administer"] = False
    snapshot["merge_actor"]["administration_write_absent_for_dedicated_actor"] = False
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "unexpected_merge_actor" in payload["decision"]["blockers"]
    assert "readiness_snapshot_not_ready" in payload["decision"]["blockers"]
    assert "dedicated_merge_actor_not_confirmed" in payload["decision"]["blockers"]


def test_ao_ma10a1_blocks_guard_or_authority_drift() -> None:
    snapshot = _ready_snapshot()
    snapshot["guard_flags"]["support_widening"] = True
    snapshot["ai_output_release_authority"] = True
    snapshot["release_authority"] = "claude-agree"
    payload = _eligibility(snapshot, ["tests/test_ao_ma10_autonomous_merge_eligibility.py"])
    assert "guard_flags_not_false" in payload["decision"]["blockers"]
    assert "ai_output_release_authority_observed" in payload["decision"]["blockers"]
    assert "release_authority_mismatch" in payload["decision"]["blockers"]


def test_ao_ma10a1_script_cli_returns_nonzero_when_blocked() -> None:
    proc = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--snapshot",
            str(SNAPSHOT),
            "--plan",
            str(PLAN),
            "--changed-file",
            ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["decision"]["result"] == "blocked"


def test_ao_ma10a1_fixture_rejects_mutation_or_ai_release_authority() -> None:
    validator = Draft202012Validator(_schema())
    payload = _json(READY_FIXTURE)

    mutated = copy.deepcopy(payload)
    mutated["mutations_performed"] = True
    assert list(validator.iter_errors(mutated))

    ai_authority = copy.deepcopy(payload)
    ai_authority["ai_output_release_authority"] = True
    assert list(validator.iter_errors(ai_authority))

    widened = copy.deepcopy(payload)
    widened["guard_flags"]["production_platform_claim"] = True
    assert list(validator.iter_errors(widened))


def test_ao_ma10a1_script_is_read_only_and_has_no_write_api_methods() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden_tokens = [
        "--method PATCH",
        "--method PUT",
        "--method POST",
        "--method DELETE",
        "gh pr merge",
        "enablePullRequestAutoMerge",
        "updateBranchProtectionRule",
        "updateRepositoryRuleset",
        "createRepositoryRuleset",
        "deleteRepositoryRuleset",
    ]
    for token in forbidden_tokens:
        assert token not in source
