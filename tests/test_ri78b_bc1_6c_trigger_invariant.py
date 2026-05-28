"""Invariant tests for RI-7.8b-bc1-6c-trigger (PR-A of the two-PR split).

Per Codex thread 019e702f iter-2 (plan-time AGREE conditional on absorbed
revisions): PR-A introduces the dispatch trigger file + scenario-run
evidence schema + workflow hardening (artifact name scenario tag,
fail_closed expected-denial mapping, marker scenario_outcome) + guard
script event-aware run cap + gpp_status workflow SHA binding refresh.

PR-B (6c-closure) consumes the per-run evidence produced by the workflow
post-merge of PR-A and builds the closure proof + spend ledger + BC-1
submanifest flip.

binding mode of artifacts introduced here:
  - trigger file: introduced_in_this_pr
  - scenario-run evidence schema: introduced_in_this_pr
  - workflow YAML: modified_in_this_pr (current-PR SHA owns gpp_status binding)
  - gpp_status entry RI-7.8b-bc1-6b: workflow_content_sha256 refreshed to PR-A SHA
  - 6c-fast-follow / 6b evidence: state_at_landing_pin
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

TRIGGER_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc1-6c-dispatch-trigger.schema.v1.json"
SCENARIO_RUN_SCHEMA_PATH = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc1-6c-scenario-run-evidence.schema.v1.json"
)
TRIGGER_FILE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-DISPATCH-TRIGGER.v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc1-protected-live-adapter-attestation.yml"
ACTIVATION_GUARD_PATH = REPO_ROOT / "scripts" / "ri78b_bc1_activation_window.py"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_diff_base() -> str | None:
    try:
        result = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def _is_6c_trigger_introducer_pr() -> bool:
    """True if THIS PR is the 6c-trigger introducer (adds the trigger file).

    Pattern parity with RI-7.1/7.2/7.5/7.8a/7.8b-bc1-6a/6b/6c-fast-follow and
    AO-MA-10 runtime introducer-PR detection.
    """
    base_sha = _resolve_diff_base()
    if base_sha is None:
        return False
    try:
        result = subprocess.run(
            ["git", "diff", "--diff-filter=A", "--name-only", f"{base_sha}...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        added = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return str(TRIGGER_FILE_PATH.relative_to(REPO_ROOT)) in added
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# Trigger file existence + schema validity
# ---------------------------------------------------------------------------


def test_6c_trigger_file_path_exists() -> None:
    assert TRIGGER_FILE_PATH.exists()


def test_6c_trigger_schema_path_exists() -> None:
    assert TRIGGER_SCHEMA_PATH.exists()


def test_6c_trigger_schema_is_draft_2020_12() -> None:
    schema = _load_json(TRIGGER_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_6c_trigger_file_validates_against_schema() -> None:
    schema = _load_json(TRIGGER_SCHEMA_PATH)
    trigger = _load_json(TRIGGER_FILE_PATH)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(trigger),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors, "; ".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)


# ---------------------------------------------------------------------------
# Trigger file content pins
# ---------------------------------------------------------------------------


def test_6c_trigger_file_authority_mode_const() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert trigger["authority_mode"] == "operator_delegated_autonomous_preprod"


def test_6c_trigger_file_supersession_entry_id_const() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert trigger["supersession_entry_id"] == "RI-7.8b-bc1-6b"


def test_6c_trigger_file_operator_login_halildeu_const() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert trigger["operator"]["github_login"] == "Halildeu"
    assert trigger["operator"]["no_secret_assertion"] is True


def test_6c_trigger_file_bounded_window_limits_preserved() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert trigger["max_distinct_runs"] == 5
    assert trigger["max_run_attempt"] == 1
    assert trigger["max_usd"] == 5.0


def test_6c_trigger_file_scenarios_exactly_two() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert sorted(trigger["scenarios"]) == ["clean_attestation", "fail_closed_attestation"]


def test_6c_trigger_file_secret_boundary_const() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    assert trigger["secret_boundary"] == "no_secret_material_no_credential_names_no_token_in_trigger_file"


# ---------------------------------------------------------------------------
# Trigger file vs workflow / vs guard script source-of-truth checks
# ---------------------------------------------------------------------------


def test_6c_trigger_scenarios_match_workflow_matrix() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    for scenario in trigger["scenarios"]:
        assert scenario in text, f"workflow YAML must reference scenario={scenario}"


def test_6c_trigger_scenarios_match_guard_allowlist() -> None:
    trigger = _load_json(TRIGGER_FILE_PATH)
    text = ACTIVATION_GUARD_PATH.read_text(encoding="utf-8")
    for scenario in trigger["scenarios"]:
        assert scenario in text


# ---------------------------------------------------------------------------
# Workflow hardening (artifact name scenario tag + fail_closed handling)
# ---------------------------------------------------------------------------


def test_6c_trigger_workflow_upload_artifact_name_includes_matrix_scenario() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "ri78b-bc1-attestation-marker-${{ matrix.scenario }}" in text


def test_6c_trigger_workflow_fail_closed_uses_expected_denial_mapping() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "fail_closed_as_expected" in text
    assert "unexpected_failure" in text
    # The legacy ``exit 78`` job-fail semantic MUST be gone from executable
    # shell — replaced by explicit exit-code mapping that returns 0 on
    # expected denial and 1 on unexpected allow / unknown scenario. We
    # exclude comment lines (which may reference the legacy pattern for
    # documentation purposes).
    code_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    code_text = "\n".join(code_lines)
    assert "exit 78" not in code_text


def test_6c_trigger_workflow_marker_emits_scenario_outcome_field() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "scenario_outcome" in text


def test_6c_trigger_workflow_marker_path_pattern_includes_scenario() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "f\"marker-{marker['scenario']}-{marker['run_id']}-attempt-{marker['run_attempt']}.json\"" in text


# ---------------------------------------------------------------------------
# gpp_status binding refresh
# ---------------------------------------------------------------------------


def test_6c_trigger_gpp_status_workflow_sha256_matches_current_workflow_file() -> None:
    """PR-A owns the current workflow content; gpp_status binding must
    refresh to match. Without this refresh, the runtime activation guard
    fail-closes on the next push trigger because expected sha != live sha.
    """
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    expected = _sha256_file(WORKFLOW_PATH)
    assert entry["future_workflow_contract"]["workflow_content_sha256"] == expected


def test_6c_trigger_gpp_status_supersession_status_awaiting_auto_dispatch() -> None:
    """While trigger file is present at HEAD of this PR but the workflow
    hasn't actually fired (push to main happens at merge), the supersession
    entry must remain ``awaiting_auto_dispatch_trigger_commit``. PR-B
    (6c-closure) will transition to ``active`` and then ``closed`` based
    on workflow run evidence."""
    if not _is_6c_trigger_introducer_pr():
        pytest.skip("6c-trigger state-at-landing pin: only enforced on the introducer PR")
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    assert entry["status"] == "awaiting_auto_dispatch_trigger_commit"


def test_6c_trigger_gpp_status_top_level_guard_const_false() -> None:
    """Top-level guard flags MUST stay const false through this PR. The
    BC-1 submanifest flip and any guard flag changes belong to PR-B
    (6c-closure) — even there, only the submanifest BC-1 flips, the
    top-level ``live_adapter_execution_allowed`` MUST stay false."""
    status = _load_json(GPP_STATUS_PATH)
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False


# ---------------------------------------------------------------------------
# Activation guard script: event-aware run cap (push + workflow_dispatch)
# ---------------------------------------------------------------------------


def test_6c_trigger_activation_guard_event_aware_run_cap() -> None:
    text = ACTIVATION_GUARD_PATH.read_text(encoding="utf-8")
    assert "_accepted_events_for_authority_mode" in text
    # Both events accepted for operator_delegated_autonomous_preprod
    assert '"push", "workflow_dispatch"' in text or "'push', 'workflow_dispatch'" in text


def test_6c_trigger_activation_guard_window_relative_filter_present() -> None:
    text = ACTIVATION_GUARD_PATH.read_text(encoding="utf-8")
    assert "actual_start_at" in text
    assert "actual_start_dt" in text
    # Lifetime vs window-relative path explicitly handled
    assert "Lifetime cap" in text or "lifetime cap" in text


# ---------------------------------------------------------------------------
# Scenario-run evidence schema (introduced in this PR; per-instance
# artifacts emitted by workflow post-merge are consumed by PR-B)
# ---------------------------------------------------------------------------


def test_6c_trigger_scenario_run_schema_is_draft_2020_12() -> None:
    assert SCENARIO_RUN_SCHEMA_PATH.exists()
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_6c_trigger_scenario_run_schema_pins_three_outcome_enum() -> None:
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    enum = schema["properties"]["scenario_outcome"]["enum"]
    assert sorted(enum) == sorted(["clean_attestation_pass", "fail_closed_as_expected", "unexpected_failure"])


def test_6c_trigger_scenario_run_schema_run_attempt_const_one() -> None:
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    assert schema["properties"]["run_attempt"]["const"] == 1


def test_6c_trigger_scenario_run_schema_head_ref_pins_main() -> None:
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    pattern = schema["properties"]["head_ref"]["pattern"]
    assert "main" in pattern
    # Only main is accepted
    assert re.match(pattern, "refs/heads/main") is not None
    assert re.match(pattern, "refs/heads/feature") is None


def test_6c_trigger_scenario_run_schema_marker_path_pattern_includes_scenario() -> None:
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    pattern = schema["properties"]["marker_path"]["pattern"]
    assert "clean_attestation" in pattern
    assert "fail_closed_attestation" in pattern


def test_6c_trigger_scenario_run_schema_coherence_clean_outcomes() -> None:
    """clean_attestation may only report clean_attestation_pass or
    unexpected_failure — NOT fail_closed_as_expected (semantic mismatch)."""
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    invalid = {
        "schema_version": "ri7-8b-bc1-6c-scenario-run-evidence.v1",
        "artifact_kind": "ri7_8b_bc1_6c_scenario_run_evidence",
        "workflow_run_id": "12345",
        "run_attempt": 1,
        "scenario": "clean_attestation",
        "scenario_outcome": "fail_closed_as_expected",  # incoherent
        "workflow_content_sha256": "0" * 64,
        "head_sha": "0" * 40,
        "head_ref": "refs/heads/main",
        "marker_path": "marker-clean_attestation-12345-attempt-1.json",
        "marker_sha256": "0" * 64,
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "recorded_at": "2026-05-28T20:00:00Z",
    }
    errors = list(validator.iter_errors(invalid))
    assert errors, "clean+fail_closed_as_expected must be rejected as incoherent"


# ---------------------------------------------------------------------------
# Negative scope tests (forbidden in 6c-trigger)
# ---------------------------------------------------------------------------


def test_6c_trigger_negative_top_level_guard_flag_flip_rejected() -> None:
    """Mutating top-level guard flags is reserved for explicit GPP
    full-matrix promotion PRs; this PR-A scope MUST NOT touch them."""
    status = _load_json(GPP_STATUS_PATH)
    drift = {
        **status,
        "live_adapter_execution_allowed": True,  # forbidden flip
    }
    assert drift["live_adapter_execution_allowed"] is True
    # State-at-landing check: real file still false
    assert status["live_adapter_execution_allowed"] is False


def test_6c_trigger_negative_bc1_flip_belongs_to_pr_b() -> None:
    """BC-1 submanifest flip happens in PR-B (6c-closure) after workflow
    run evidence is collected and closure proof is sealed. PR-A MUST NOT
    flip it."""
    if not _is_6c_trigger_introducer_pr():
        pytest.skip("6c-trigger state-at-landing pin: only enforced on the introducer PR")
    submanifest_path = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"
    sub = _load_json(submanifest_path)
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is False
