"""AO-MA-11A plan-consensus + single operator-approval gate tests.

Covers: schema validity, unanimity recomputation (latest-round wins +
conservative dissent), self-attestation guard, duplicate/non-contiguous/
over-budget round integrity, guard-flag pinning, triple SHA-bound approval
validation (bundle + request + plan_digest tamper rejection), the four
single-gate states, I/O error paths, and a static import-allowlist guard.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import ao_kernel
from ao_kernel.orchestration.plan_consensus import (
    ApprovalDecision,
    ConsensusDecision,
    GateDecision,
    PlanConsensusError,
    _check_approval_bindings,
    _check_bundle_invariants,
    _load_schema,
    compute_unanimous_status,
    gate_status,
    sha256_of,
    validate_approval,
    validate_consensus_bundle,
)

_PKG = Path(ao_kernel.__file__).resolve().parent
_SCHEMAS = _PKG / "defaults" / "schemas"
_BUNDLE_SCHEMA = _SCHEMAS / "ao-ma-11a-plan-consensus-bundle.schema.v1.json"
_APPROVAL_SCHEMA = _SCHEMAS / "ao-ma-11a-plan-approval.schema.v1.json"
_MODULE_SRC = _PKG / "orchestration" / "plan_consensus.py"

# Pure-policy import allowlist: with only these top-level imports the module
# cannot shell out (no subprocess/os), reach the network, or call an LLM.
_ALLOWED_IMPORTS = {"__future__", "hashlib", "json", "dataclasses", "pathlib", "typing", "jsonschema"}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _verdict(
    provider: str, verdict: str = "AGREE", rnd: int = 1, objections: list[str] | None = None
) -> dict[str, Any]:
    return {
        "provider_id": provider,
        "agent_id": f"{provider}-planner",
        "verdict": verdict,
        "round_index": rnd,
        "rationale": f"{provider} round {rnd} rationale",
        "objections": objections or [],
    }


def _valid_bundle(**overrides: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": "ao-ma-11a-plan-consensus-bundle.v1",
        "artifact_kind": "ao_ma_11a_plan_consensus_bundle",
        "consensus_id": "ao-ma-plan-20260530-abc123",
        "operator_goal": "Enable governed autonomous multi-AI coding workflow",
        "plan_digest": "sha256:" + "a" * 64,
        "plan_binding": {
            "repository_full_name": "Halildeu/ao-kernel",
            "base_ref": "refs/heads/main",
            "base_sha": "b" * 40,
        },
        "acceptance_criteria": ["schemas valid", "validator tests pass"],
        "required_providers": ["anthropic", "openai", "minimax"],
        "provider_verdicts": [
            _verdict("anthropic"),
            _verdict("openai"),
            _verdict("minimax"),
        ],
        "round_budget": 3,
        "rounds_used": 1,
        "unanimous_status": "AGREE",
        "spm_anchor": {
            "spm_profile_ref": ".claude/plans/AO-MA-11G-SPM-QUALITY-PROFILE.md",
            "roadmap_item_id": "AO-MA-11A",
            "quality_targets": {
                "coverage_branch_min": 85,
                "required_test_classes": ["unit", "negative"],
                "required_evidence_classes": ["consensus_bundle", "plan_approval"],
            },
            "tracking_refs": [],
        },
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "secrets_recorded": False,
        "created_at": "2026-05-30T12:00:00Z",
    }
    bundle.update(overrides)
    return bundle


def _valid_approval(*, bundle_sha: str, plan_digest: str, request_sha: str, **overrides: Any) -> dict[str, Any]:
    approval: dict[str, Any] = {
        "schema_version": "ao-ma-11a-plan-approval.v1",
        "artifact_kind": "ao_ma_11a_plan_approval",
        "approval_id": "ao-ma-approval-20260530-xyz789",
        "consensus_id": "ao-ma-plan-20260530-abc123",
        "consensus_bundle_sha256": bundle_sha,
        "plan_digest": plan_digest,
        "approval_request_sha256": request_sha,
        "unanimous_status": "AGREE",
        "decision": "approved",
        "environment_ref": "ao-ma-plan-approval",
        "approved_by": "halildeu",
        "approved_at": "2026-05-30T12:30:00Z",
        "audit_url": "https://github.com/Halildeu/ao-kernel/actions/runs/123",
        "bypass_detected": False,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "secrets_recorded": False,
        "created_at": "2026-05-30T12:30:00Z",
    }
    approval.update(overrides)
    return approval


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _request_on_disk(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "approval_request.json"
    path.write_text(
        json.dumps({"consensus_id": "ao-ma-plan-20260530-abc123", "plan_digest": "sha256:" + "a" * 64}),
        encoding="utf-8",
    )
    return path, sha256_of(path)


def _agree_setup(tmp_path: Path) -> tuple[Path, str, str, Path, str]:
    bundle = _valid_bundle()
    bundle_path = _write(tmp_path / "bundle.v1.json", bundle)
    req_path, req_sha = _request_on_disk(tmp_path)
    return bundle_path, sha256_of(bundle_path), bundle["plan_digest"], req_path, req_sha


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def test_bundle_schema_is_valid_draft202012() -> None:
    schema = json.loads(_BUNDLE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-11a-plan-consensus-bundle:v1"
    assert schema["additionalProperties"] is False


def test_approval_schema_is_valid_draft202012() -> None:
    schema = json.loads(_APPROVAL_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-11a-plan-approval:v1"
    assert schema["properties"]["unanimous_status"]["const"] == "AGREE"


def test_valid_bundle_satisfies_schema() -> None:
    schema = json.loads(_BUNDLE_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(_valid_bundle()))
    assert errors == []


def test_bundle_schema_has_no_risk_class() -> None:
    schema = json.loads(_BUNDLE_SCHEMA.read_text(encoding="utf-8"))
    assert "risk_class" not in schema["properties"]
    assert "risk_class" not in schema["required"]


# ---------------------------------------------------------------------------
# Unanimity recomputation
# ---------------------------------------------------------------------------
def test_all_agree_yields_agree(tmp_path: Path) -> None:
    path = _write(tmp_path / "bundle.v1.json", _valid_bundle())
    decision = validate_consensus_bundle(path)
    assert isinstance(decision, ConsensusDecision)
    assert decision.unanimous_status == "AGREE"
    assert decision.can_request_approval is True


def test_one_provider_revise_yields_not_agree(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic"),
            _verdict("openai", verdict="REVISE", objections=["needs scope split"]),
            _verdict("minimax"),
        ],
        unanimous_status="NOT_AGREE",
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    decision = validate_consensus_bundle(path)
    assert decision.unanimous_status == "NOT_AGREE"
    assert decision.can_request_approval is False


def test_latest_round_wins(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic", verdict="REVISE", rnd=1, objections=["fix schema"]),
            _verdict("anthropic", verdict="AGREE", rnd=2),
            _verdict("openai", verdict="AGREE", rnd=2),
            _verdict("minimax", verdict="AGREE", rnd=1),
        ],
        rounds_used=2,
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    decision = validate_consensus_bundle(path)
    assert decision.unanimous_status == "AGREE"


def test_latest_round_wins_descending_order() -> None:
    verdicts = [
        _verdict("anthropic", verdict="AGREE", rnd=2),
        _verdict("anthropic", verdict="REVISE", rnd=1),
        _verdict("openai"),
        _verdict("minimax"),
    ]
    status = compute_unanimous_status(verdicts, ["anthropic", "openai", "minimax"])
    assert status == "AGREE"


def test_compute_unanimous_status_missing_provider() -> None:
    verdicts = [_verdict("anthropic"), _verdict("openai")]
    status = compute_unanimous_status(verdicts, ["anthropic", "openai", "minimax"])
    assert status == "NOT_AGREE"


def test_conservative_dissent_extra_provider_blocks() -> None:
    # All required AGREE, but an extra recorded provider's latest is RED.
    verdicts = [_verdict("anthropic"), _verdict("openai"), _verdict("minimax"), _verdict("google", verdict="RED")]
    status = compute_unanimous_status(verdicts, ["anthropic", "openai", "minimax"])
    assert status == "NOT_AGREE"


# ---------------------------------------------------------------------------
# Trust-boundary / integrity (fail-closed)
# ---------------------------------------------------------------------------
def test_stored_status_lie_is_rejected(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic"),
            _verdict("openai", verdict="REVISE", objections=["disagree"]),
            _verdict("minimax"),
        ],
        unanimous_status="AGREE",
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="unanimous_status mismatch"):
        validate_consensus_bundle(path)


def test_duplicate_provider_round_is_rejected(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic", rnd=1),
            _verdict("anthropic", rnd=1, objections=["dup"]),
            _verdict("openai", rnd=1),
            _verdict("minimax", rnd=1),
        ]
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="duplicate verdict"):
        validate_consensus_bundle(path)


def test_round_index_exceeds_budget_is_rejected(tmp_path: Path) -> None:
    # Contiguous rounds 1..2, rounds_used matches, but budget is only 1.
    bundle = _valid_bundle(
        round_budget=1,
        rounds_used=2,
        provider_verdicts=[
            _verdict("anthropic", rnd=1),
            _verdict("openai", rnd=1),
            _verdict("minimax", rnd=1),
            _verdict("anthropic", rnd=2),
        ],
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="exceeds round_budget"):
        validate_consensus_bundle(path)


def test_rounds_used_mismatch_is_rejected(tmp_path: Path) -> None:
    bundle = _valid_bundle(round_budget=3, rounds_used=2)  # all verdicts round 1 -> max_round 1
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="highest verdict round"):
        validate_consensus_bundle(path)


def test_round_gap_is_rejected(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        round_budget=3,
        rounds_used=3,
        provider_verdicts=[
            _verdict("anthropic", rnd=1),
            _verdict("openai", rnd=1),
            _verdict("minimax", rnd=1),
            _verdict("anthropic", rnd=3),
        ],
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="round gap"):
        validate_consensus_bundle(path)


def test_missing_required_provider_fails_schema(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic", rnd=1),
            _verdict("anthropic", rnd=2),
            _verdict("openai"),
        ],
        rounds_used=2,
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="failed schema"):
        validate_consensus_bundle(path)


def test_guard_flag_true_fails_schema(tmp_path: Path) -> None:
    bundle = _valid_bundle(
        guard_flags={
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": True,
        }
    )
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="failed schema"):
        validate_consensus_bundle(path)


def test_unknown_top_level_field_fails_schema(tmp_path: Path) -> None:
    bundle = _valid_bundle()
    bundle["sneaky_extra"] = True
    path = _write(tmp_path / "bundle.v1.json", bundle)
    with pytest.raises(PlanConsensusError, match="failed schema"):
        validate_consensus_bundle(path)


def test_invariant_backstop_rejects_quorum_tamper() -> None:
    bundle = _valid_bundle(required_providers=["anthropic", "openai", "google"])
    with pytest.raises(PlanConsensusError, match="quorum tampering"):
        _check_bundle_invariants(bundle, "crafted.json")


def test_invariant_backstop_rejects_guard_flag_flip() -> None:
    bundle = _valid_bundle()
    bundle["guard_flags"]["support_widening"] = True
    with pytest.raises(PlanConsensusError, match="no-widening contract"):
        _check_bundle_invariants(bundle, "crafted.json")


# ---------------------------------------------------------------------------
# I/O error paths
# ---------------------------------------------------------------------------
def test_missing_bundle_file_raises(tmp_path: Path) -> None:
    with pytest.raises(PlanConsensusError, match="file not found"):
        validate_consensus_bundle(tmp_path / "does-not-exist.v1.json")


def test_malformed_json_bundle_raises(tmp_path: Path) -> None:
    path = tmp_path / "bundle.v1.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises(PlanConsensusError, match="failed to read"):
        validate_consensus_bundle(path)


def test_load_schema_missing_raises() -> None:
    with pytest.raises(PlanConsensusError, match="failed to load bundled schema"):
        _load_schema("ao-ma-11a-does-not-exist.schema.v1.json")


# ---------------------------------------------------------------------------
# Approval validation (triple SHA-bound)
# ---------------------------------------------------------------------------
def test_valid_approval_proceeds(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha)
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    decision = validate_approval(approval_path, bundle_path, req_path)
    assert isinstance(decision, ApprovalDecision)
    assert decision.decision == "approved"
    assert decision.proceed is True


def test_rejected_decision_does_not_proceed(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha, decision="rejected")
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    decision = validate_approval(approval_path, bundle_path, req_path)
    assert decision.decision == "rejected"
    assert decision.proceed is False


def test_tampered_bundle_sha_is_rejected(tmp_path: Path) -> None:
    bundle_path, _bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(bundle_sha="sha256:" + "0" * 64, plan_digest=plan_digest, request_sha=req_sha)
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="consensus_bundle_sha256"):
        validate_approval(approval_path, bundle_path, req_path)


def test_tampered_request_sha_is_rejected(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, _req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha="sha256:" + "f" * 64)
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="approval_request_sha256"):
        validate_approval(approval_path, bundle_path, req_path)


def test_plan_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    bundle_path, bundle_sha, _plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(bundle_sha=bundle_sha, plan_digest="sha256:" + "d" * 64, request_sha=req_sha)
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="plan_digest"):
        validate_approval(approval_path, bundle_path, req_path)


def test_consensus_id_mismatch_is_rejected(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(
        bundle_sha=bundle_sha,
        plan_digest=plan_digest,
        request_sha=req_sha,
        consensus_id="ao-ma-plan-20260530-zzzzzz",
    )
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="consensus_id"):
        validate_approval(approval_path, bundle_path, req_path)


def test_approval_over_not_agree_bundle_is_rejected(tmp_path: Path) -> None:
    not_agree = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic"),
            _verdict("openai", verdict="RED", objections=["blocker"]),
            _verdict("minimax"),
        ],
        unanimous_status="NOT_AGREE",
    )
    bundle_path = _write(tmp_path / "bundle.v1.json", not_agree)
    req_path, req_sha = _request_on_disk(tmp_path)
    approval = _valid_approval(
        bundle_sha=sha256_of(bundle_path), plan_digest=not_agree["plan_digest"], request_sha=req_sha
    )
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="non-AGREE"):
        validate_approval(approval_path, bundle_path, req_path)


def test_bypass_detected_true_fails_schema(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval = _valid_approval(
        bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha, bypass_detected=True
    )
    approval_path = _write(tmp_path / "approval.v1.json", approval)
    with pytest.raises(PlanConsensusError, match="failed schema"):
        validate_approval(approval_path, bundle_path, req_path)


def test_approval_bindings_backstop_rejects_bypass() -> None:
    bundle = _valid_bundle()
    approval = _valid_approval(
        bundle_sha="sha256:" + "e" * 64, plan_digest=bundle["plan_digest"], request_sha="sha256:" + "9" * 64
    )
    approval["bypass_detected"] = True
    with pytest.raises(PlanConsensusError, match="bypass_detected"):
        _check_approval_bindings(approval, bundle, "sha256:" + "e" * 64, "sha256:" + "9" * 64)


def test_approval_bindings_backstop_rejects_guard_flip() -> None:
    bundle = _valid_bundle()
    approval = _valid_approval(
        bundle_sha="sha256:" + "e" * 64, plan_digest=bundle["plan_digest"], request_sha="sha256:" + "9" * 64
    )
    approval["guard_flags"]["live_adapter_execution"] = True
    with pytest.raises(PlanConsensusError, match="guard_flags"):
        _check_approval_bindings(approval, bundle, "sha256:" + "e" * 64, "sha256:" + "9" * 64)


# ---------------------------------------------------------------------------
# Single-gate states
# ---------------------------------------------------------------------------
def test_gate_awaiting_operator_approval(tmp_path: Path) -> None:
    bundle_path, _sha, _digest, _req_path, _req_sha = _agree_setup(tmp_path)
    decision = gate_status(bundle_path)
    assert isinstance(decision, GateDecision)
    assert decision.state == "awaiting_operator_approval"
    assert decision.proceed is False


def test_gate_approved_run_may_start(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval_path = _write(
        tmp_path / "approval.v1.json",
        _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha),
    )
    decision = gate_status(bundle_path, approval_path, req_path)
    assert decision.state == "approved_autonomous_run_may_start"
    assert decision.proceed is True


def test_gate_halted_operator_rejected(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, req_path, req_sha = _agree_setup(tmp_path)
    approval_path = _write(
        tmp_path / "approval.v1.json",
        _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha, decision="rejected"),
    )
    decision = gate_status(bundle_path, approval_path, req_path)
    assert decision.state == "halted_operator_rejected"
    assert decision.proceed is False


def test_gate_requires_request_path_when_approval_present(tmp_path: Path) -> None:
    bundle_path, bundle_sha, plan_digest, _req_path, req_sha = _agree_setup(tmp_path)
    approval_path = _write(
        tmp_path / "approval.v1.json",
        _valid_approval(bundle_sha=bundle_sha, plan_digest=plan_digest, request_sha=req_sha),
    )
    with pytest.raises(PlanConsensusError, match="approval_request_path is required"):
        gate_status(bundle_path, approval_path)


def test_gate_consensus_not_reached(tmp_path: Path) -> None:
    not_agree = _valid_bundle(
        provider_verdicts=[
            _verdict("anthropic"),
            _verdict("openai", verdict="PARTIAL", objections=["partial only"]),
            _verdict("minimax"),
        ],
        unanimous_status="NOT_AGREE",
    )
    bundle_path = _write(tmp_path / "bundle.v1.json", not_agree)
    decision = gate_status(bundle_path)
    assert decision.state == "consensus_not_reached"
    assert decision.proceed is False


# ---------------------------------------------------------------------------
# Static guard: pure-policy import allowlist (no shell-out / no LLM)
# ---------------------------------------------------------------------------
def _imported_top_modules(src: str) -> set[str]:
    tree = ast.parse(src)
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def test_module_import_allowlist() -> None:
    mods = _imported_top_modules(_MODULE_SRC.read_text(encoding="utf-8"))
    unexpected = mods - _ALLOWED_IMPORTS
    assert unexpected == set(), f"unexpected imports (shell-out/LLM risk): {sorted(unexpected)}"
    assert "subprocess" not in mods
    assert "os" not in mods
