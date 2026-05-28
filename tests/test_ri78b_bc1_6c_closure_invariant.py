"""Invariant tests for RI-7.8b-bc1-6c-closure (PR-B of the two-PR split).

Per Codex thread 019e702f iter-2 (plan-time AGREE conditional on absorbed
revisions): PR-B consumes per-run evidence emitted by the workflow that
auto-fired post-merge of PR-A (PR #690 merge commit 732192a). Builds the
closure proof + spend ledger + operator activation identity + commit
verification + required-checks pass + AO-MA-10 high-risk prerequisite +
BC-1 flip attestation.

Two operator-bound edits land the actual flip:

1. ``.claude/plans/gpp_status.v1.json`` -- RI-7.8b-bc1-6b supersession
   entry transitions ``awaiting_auto_dispatch_trigger_commit -> closed``
   with ``actual_start_at`` and ``closed_at`` set.

2. ``.claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json`` --
   ``bc1_protected_live_adapter_attestation_recorded: false -> true``.

These two edits are made by the operator (Halildeu) as part of PR review.
The agent commits the closure schema + closure evidence + run evidence +
tests, then the operator pushes the two edits + approves + merges. CI
stays red until operator action; tests below enforce the closure -> flip
coherence so merge is blocked without the operator commits.

Top-level guard flags (``support_widening_allowed``,
``production_platform_claim_allowed``, ``live_adapter_execution_allowed``)
remain const false. Only the BC-1 submanifest sub-key flips.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent

CLOSURE_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc1-6c-closure-evidence.schema.v1.json"
SCENARIO_RUN_SCHEMA_PATH = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc1-6c-scenario-run-evidence.schema.v1.json"
)
CLOSURE_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-CLOSURE.v1.json"
CLEAN_RUN_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-RUN-EVIDENCE-clean_attestation.v1.json"
FAIL_RUN_EVIDENCE_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8b-bc1-6c-RUN-EVIDENCE-fail_closed_attestation.v1.json"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
SUBMANIFEST_PATH = REPO_ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"


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


def _is_6c_closure_introducer_pr() -> bool:
    """True if THIS PR is the 6c-closure introducer (adds the closure
    evidence file). Pattern parity with PR #687 runtime introducer-PR
    detection + 6c-trigger introducer."""
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
        return str(CLOSURE_EVIDENCE_PATH.relative_to(REPO_ROOT)) in added
    except (subprocess.SubprocessError, OSError):
        return False


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------


def test_6c_closure_schema_path_exists() -> None:
    assert CLOSURE_SCHEMA_PATH.exists()


def test_6c_closure_schema_is_draft_2020_12() -> None:
    schema = _load_json(CLOSURE_SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_6c_closure_evidence_path_exists() -> None:
    assert CLOSURE_EVIDENCE_PATH.exists()


def test_6c_closure_evidence_validates_against_schema() -> None:
    schema = _load_json(CLOSURE_SCHEMA_PATH)
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(evidence),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors, "; ".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)


# ---------------------------------------------------------------------------
# Run evidence existence + schema validation
# ---------------------------------------------------------------------------


def test_6c_closure_clean_run_evidence_exists_and_valid() -> None:
    assert CLEAN_RUN_EVIDENCE_PATH.exists()
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    evidence = _load_json(CLEAN_RUN_EVIDENCE_PATH)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(evidence),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors
    assert evidence["scenario"] == "clean_attestation"
    assert evidence["scenario_outcome"] == "clean_attestation_pass"


def test_6c_closure_fail_run_evidence_exists_and_valid() -> None:
    assert FAIL_RUN_EVIDENCE_PATH.exists()
    schema = _load_json(SCENARIO_RUN_SCHEMA_PATH)
    evidence = _load_json(FAIL_RUN_EVIDENCE_PATH)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(evidence),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors
    assert evidence["scenario"] == "fail_closed_attestation"
    assert evidence["scenario_outcome"] == "fail_closed_as_expected"


# ---------------------------------------------------------------------------
# Closure evidence content pins
# ---------------------------------------------------------------------------


def test_6c_closure_proof_has_both_scenarios_no_unexpected() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    outcomes = sorted(evidence["closure_proof"]["scenario_outcomes"])
    assert outcomes == ["clean_attestation_pass", "fail_closed_as_expected"]
    assert evidence["closure_proof"]["no_unexpected_failure"] is True


def test_6c_closure_spend_ledger_zero_cost_honest_marker_only() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    ledger = evidence["spend_ledger"]
    assert ledger["max_usd"] == 5.0
    assert ledger["cumulative_usd"] == 0.0
    assert ledger["billable_calls_count"] == 0
    assert ledger["cost_source"] == "no_billable_provider_call"
    assert ledger["line_items"] == []


def test_6c_closure_bounded_window_envelope_under_caps() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    env = evidence["bounded_window_envelope"]
    assert env["max_distinct_runs"] == 5
    assert env["actual_distinct_runs"] <= env["max_distinct_runs"]
    assert env["max_run_attempt"] == 1
    assert env["actual_max_run_attempt"] == 1
    assert env["max_duration_hours"] == 24
    assert env["actual_duration_hours_under_max"] is True


def test_6c_closure_operator_activation_identity_match_halildeu() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    op = evidence["operator_activation_identity"]
    assert op["merged_by_login"] == "Halildeu"
    assert op["author_login"] == "Halildeu"
    assert op["identity_match"] is True


def test_6c_closure_commit_verification_valid() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    cv = evidence["commit_verification"]
    assert cv["source"] == "github_commit_api"
    assert cv["verified"] is True
    assert cv["reason"] == "valid"


def test_6c_closure_ao_ma_10_prerequisite_resolved() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    pre = evidence["ao_ma_10_high_risk_prerequisite"]
    assert pre["pr_number"] == 687
    assert pre["raw_evidence_rebind_or_delete_resolved"] is True
    assert pre["introducer_runtime_detection_present"] is True
    assert pre["cross_ai_consensus_status"] == "AGREE"


def test_6c_closure_bc1_flip_attestation_const_pins() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    flip = evidence["bc1_flip_attestation"]
    assert flip["submanifest_key"] == "bc1_protected_live_adapter_attestation_recorded"
    assert flip["before"] is False
    assert flip["after"] is True
    # All conditions must be met
    for k, v in flip["conditions_met"].items():
        assert v is True, f"flip condition {k} must be true"
    # Top-level flags MUST remain false even when BC-1 sub-key flips
    flags = flip["top_level_flags_unchanged"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_6c_closure_status_transition_history_three_steps() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    history = evidence["status_transition_history"]
    assert len(history) == 3
    # Ordered: null_initial -> awaiting -> active -> closed
    assert history[0]["to_status"] == "awaiting_auto_dispatch_trigger_commit"
    assert history[1]["from_status"] == "awaiting_auto_dispatch_trigger_commit"
    assert history[1]["to_status"] == "active"
    assert history[2]["from_status"] == "active"
    assert history[2]["to_status"] == "closed"


# ---------------------------------------------------------------------------
# Closure -> repo state coherence (forces operator commits to land the flip)
# ---------------------------------------------------------------------------


def test_6c_closure_run_evidence_sha256_matches_committed_files() -> None:
    evidence = _load_json(CLOSURE_EVIDENCE_PATH)
    refs = {r["scenario"]: r for r in evidence["scenario_run_refs"]}
    assert refs["clean_attestation"]["run_evidence_sha256"] == _sha256_file(CLEAN_RUN_EVIDENCE_PATH)
    assert refs["fail_closed_attestation"]["run_evidence_sha256"] == _sha256_file(FAIL_RUN_EVIDENCE_PATH)


def test_6c_closure_gpp_status_supersession_entry_closed() -> None:
    """The 6c-closure PR is incomplete without the operator-bound
    gpp_status edit transitioning RI-7.8b-bc1-6b from
    ``awaiting_auto_dispatch_trigger_commit`` to ``closed``. The closure
    evidence's bc1_flip_attestation declares before=false after=true;
    this test enforces coherence: the actual gpp_status entry must show
    the post-flip state. CI stays red until the operator commits the
    transition."""
    status = _load_json(GPP_STATUS_PATH)
    entries = status.get("operator_bound_supersessions", [])
    entry = next(e for e in entries if e.get("id") == "RI-7.8b-bc1-6b")
    assert entry["status"] == "closed", (
        "RI-7.8b-bc1-6b status must be 'closed' to land 6c-closure. "
        "Operator action required: edit gpp_status entry to set "
        "status=closed + actual_start_at + closed_at."
    )
    assert entry.get("actual_start_at"), "actual_start_at must be set"
    assert entry.get("closed_at"), "closed_at must be set"


def test_6c_closure_submanifest_bc1_flip_landed() -> None:
    """The closure evidence declares the BC-1 flip (false -> true). This
    test enforces that the actual submanifest matches. CI stays red until
    the operator commits the flip. This is the forcing function: the
    closure attestation declares the intended end-state, the actual
    submanifest must match before merge is allowed."""
    sub = _load_json(SUBMANIFEST_PATH)
    assert sub["bc1_protected_live_adapter_attestation_recorded"] is True, (
        "BC-1 submanifest key must be true to land 6c-closure. "
        "Operator action required: flip "
        ".claude/plans/RI-7.8-EVIDENCE-MANIFEST.v1.json"
        "::bc1_protected_live_adapter_attestation_recorded from false to true."
    )


def test_6c_closure_top_level_guard_flags_const_false_preserved() -> None:
    """Even when BC-1 submanifest sub-key flips, top-level guard flags
    MUST remain const false. The BC-1 attestation scope is
    'protected live-adapter attestation recorded' — NOT
    'live adapter execution allowed' (the top-level kill switch)."""
    status = _load_json(GPP_STATUS_PATH)
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_6c_closure_negative_unexpected_failure_outcome_rejected_in_schema() -> None:
    """The closure proof MUST NOT accept unexpected_failure. The schema's
    scenario_outcomes is constrained to a contains/contains-pair of the two
    expected outcomes."""
    schema = _load_json(CLOSURE_SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    base = _load_json(CLOSURE_EVIDENCE_PATH)
    # Tamper: add unexpected_failure to the outcomes list (should fail enum)
    drift = json.loads(json.dumps(base))
    drift["closure_proof"]["scenario_outcomes"] = [
        "clean_attestation_pass",
        "unexpected_failure",
    ]
    errors = list(validator.iter_errors(drift))
    assert errors, "unexpected_failure must be rejected by the closure schema"


def test_6c_closure_negative_billable_calls_above_zero_rejected() -> None:
    """BC-1 marker-only path: billable_calls_count must be 0. Any positive
    count breaks the honest spend ledger semantics."""
    schema = _load_json(CLOSURE_SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    base = _load_json(CLOSURE_EVIDENCE_PATH)
    drift = json.loads(json.dumps(base))
    drift["spend_ledger"]["billable_calls_count"] = 1
    errors = list(validator.iter_errors(drift))
    assert errors, "billable_calls_count>0 must be rejected for BC-1 marker-only"


def test_6c_closure_negative_top_level_live_adapter_execution_flip_rejected() -> None:
    """Even within bc1_flip_attestation.top_level_flags_unchanged, the
    schema must keep live_adapter_execution_allowed pinned to false."""
    schema = _load_json(CLOSURE_SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    base = _load_json(CLOSURE_EVIDENCE_PATH)
    drift = json.loads(json.dumps(base))
    drift["bc1_flip_attestation"]["top_level_flags_unchanged"]["live_adapter_execution_allowed"] = True
    errors = list(validator.iter_errors(drift))
    assert errors, "live_adapter_execution_allowed=true must be rejected"
