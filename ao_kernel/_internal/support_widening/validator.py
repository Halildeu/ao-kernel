"""E-3-6 support-widening recompute-not-trust validator.

This module is intentionally v1-only and fail-closed. It validates two inputs:

* ``support_widening_evidence.v1`` artifacts produced by the E-3-2 smoke
  harness, by delegating to the E-3-1 parser/recompute verifier.
* ``widening_supersession_evidence_pack.v1`` artifacts used by a future
  operator-bound supersession PR. These packs do not authorize support
  widening in Epic 3; they only make evidence recomputable.

The module performs no GitHub writes, no network calls, and no live adapter
execution. Authoritative observations that would normally come from GitHub or
artifact downloads are supplied by the caller as context and recomputed here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ao_kernel._internal.support_widening.evidence import (
    SupportWideningEvidenceError,
    parse_v1 as parse_support_widening_v1,
    recompute_v1 as recompute_support_widening_v1,
)
from ao_kernel.config import load_default

SUPPORTED_SCHEMA_VERSIONS = {
    "support_widening_evidence.v1",
    "widening_supersession_evidence_pack.v1",
}
UNSUPPORTED_FUTURE_SCHEMA_REASON = "unsupported_future_schema_in_epic_3"


class WideningEvidenceValidationError(ValueError):
    """Raised when E-3-6 validation rejects an evidence artifact."""

    def __init__(self, reason_codes: list[str]):
        self.reason_codes = sorted(set(reason_codes))
        super().__init__(", ".join(self.reason_codes))


@dataclass(frozen=True)
class WorkflowRunObservation:
    """Read-only workflow-run facts supplied by the caller."""

    status: str
    conclusion: str
    head_sha: str
    created_at: str


@dataclass(frozen=True)
class WideningEvidenceValidationContext:
    """Authoritative recompute inputs for v1 supersession packs.

    These values are caller-supplied so the pure validator stays deterministic
    and side-effect free. A production caller may populate them from GitHub API
    reads and artifact downloads; tests populate them from fixtures.
    """

    now: datetime | None = None
    recomputed_plan_digest: str | None = None
    recomputed_final_diff_digest: str | None = None
    github_pr_head_sha: str | None = None
    workflow_runs: Mapping[str, WorkflowRunObservation] = field(default_factory=dict)
    workflow_artifacts: Mapping[str, frozenset[str]] = field(default_factory=dict)
    artifact_paths: Mapping[str, Path] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WideningEvidenceValidationContext":
        runs: dict[str, WorkflowRunObservation] = {}
        for run_id, run in _expect_mapping(payload.get("workflow_runs", {}), "workflow_runs").items():
            run_obj = _expect_mapping(run, f"workflow_runs.{run_id}")
            runs[str(run_id)] = WorkflowRunObservation(
                status=str(run_obj.get("status", "")),
                conclusion=str(run_obj.get("conclusion", "")),
                head_sha=str(run_obj.get("head_sha", "")),
                created_at=str(run_obj.get("created_at", "")),
            )

        artifacts: dict[str, frozenset[str]] = {}
        for run_id, values in _expect_mapping(payload.get("workflow_artifacts", {}), "workflow_artifacts").items():
            if not isinstance(values, list):
                raise WideningEvidenceValidationError(["context_workflow_artifacts_invalid"])
            artifacts[str(run_id)] = frozenset(str(value) for value in values)

        artifact_paths = {
            str(artifact_id): Path(str(path))
            for artifact_id, path in _expect_mapping(payload.get("artifact_paths", {}), "artifact_paths").items()
        }

        now_raw = payload.get("now")
        now = _parse_timestamp(str(now_raw)) if now_raw is not None else None
        return cls(
            now=now,
            recomputed_plan_digest=_optional_str(payload.get("recomputed_plan_digest")),
            recomputed_final_diff_digest=_optional_str(payload.get("recomputed_final_diff_digest")),
            github_pr_head_sha=_optional_str(payload.get("github_pr_head_sha")),
            workflow_runs=runs,
            workflow_artifacts=artifacts,
            artifact_paths=artifact_paths,
        )


def validate_widening_evidence(
    payload: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext | None = None,
) -> dict[str, Any]:
    """Validate ``payload`` and return a deterministic report.

    Raises ``WideningEvidenceValidationError`` with one or more reason codes on
    rejection. The returned report is intentionally small and gate-readable.
    """
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise WideningEvidenceValidationError([UNSUPPORTED_FUTURE_SCHEMA_REASON])

    if schema_version == "support_widening_evidence.v1":
        return _validate_support_widening_v1(payload)

    return _validate_supersession_pack_v1(payload, context=context or WideningEvidenceValidationContext())


def validation_report(
    payload: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext | None = None,
) -> dict[str, Any]:
    """Return a pass/fail report without raising."""
    try:
        report = validate_widening_evidence(payload, context=context)
    except WideningEvidenceValidationError as exc:
        return {
            "valid": False,
            "decision": "rejected",
            "reason_codes": exc.reason_codes,
            "schema_version": payload.get("schema_version"),
            "support_widening": payload.get("support_widening"),
            "production_platform_claim": payload.get("production_platform_claim"),
            "live_adapter_execution": payload.get("live_adapter_execution"),
        }
    return report


def _validate_support_widening_v1(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise WideningEvidenceValidationError(["payload_not_object"])
    try:
        schema = load_default("schemas", "support-widening-evidence.schema.v1.json")
        parse_support_widening_v1(dict(payload), schema=schema)
        recomputed = recompute_support_widening_v1(dict(payload))
    except SupportWideningEvidenceError as exc:
        raise WideningEvidenceValidationError([_normalize_support_error(str(exc))]) from exc
    if payload.get("simulated_only") is True and payload.get("live_call_made") is True:
        raise WideningEvidenceValidationError(["mutually_exclusive_simulated_live_rejected"])
    return {
        "valid": True,
        "decision": "validator_agree",
        "reason_codes": [],
        "schema_version": "support_widening_evidence.v1",
        "artifact_kind": payload.get("artifact_kind"),
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "recomputed": recomputed,
    }


def _validate_supersession_pack_v1(
    payload: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise WideningEvidenceValidationError(["payload_not_object"])

    errors: set[str] = set()
    errors.update(_schema_errors(dict(payload)))
    errors.update(_recursive_legacy_artifact_sha_rejections(payload))
    errors.update(_guard_errors(payload))

    if errors:
        raise WideningEvidenceValidationError(sorted(errors))

    pack = dict(payload)
    errors.update(_time_window_errors(pack, context=context))
    errors.update(_context_binding_errors(pack, context=context))
    errors.update(_identity_errors(pack))
    errors.update(_verdict_errors(pack))
    errors.update(_artifact_errors(pack, context=context))

    if errors:
        raise WideningEvidenceValidationError(sorted(errors))

    return {
        "valid": True,
        "decision": "validator_agree",
        "reason_codes": [],
        "schema_version": "widening_supersession_evidence_pack.v1",
        "artifact_kind": pack.get("artifact_kind"),
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "consensus_status_recomputed": _recomputed_consensus_status(pack),
        "reviewer_identity_hashes_recomputed": [_identity_hash(v) for v in pack["provider_verdicts"]],
    }


def _schema_errors(payload: dict[str, Any]) -> set[str]:
    schema = load_default("schemas", "widening-supersession-evidence-pack.schema.v1.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if not errors:
        return set()
    reason_codes: set[str] = set()
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path)
        if "operator_github_login" in error.message or path == "operator_authority":
            reason_codes.add("operator_alias_rejected")
        elif path in {"support_widening", "production_platform_claim", "live_adapter_execution", "widening_authorized"}:
            reason_codes.add("guard_flag_true_rejected")
        else:
            reason_codes.add("schema_validation_failed")
    return reason_codes


def _guard_errors(payload: Mapping[str, Any]) -> set[str]:
    errors: set[str] = set()
    for key in ("support_widening", "production_platform_claim", "live_adapter_execution", "widening_authorized"):
        if payload.get(key) is not False:
            errors.add("guard_flag_true_rejected")
    if payload.get("simulated_only") is True and payload.get("live_call_made") is True:
        errors.add("mutually_exclusive_simulated_live_rejected")
    return errors


def _time_window_errors(
    pack: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext,
) -> set[str]:
    errors: set[str] = set()
    start = _parse_timestamp(pack["time_window_boundaries"]["start"])
    end = _parse_timestamp(pack["time_window_boundaries"]["end"])
    now = context.now or datetime.now(timezone.utc)
    if end < now - timedelta(days=90):
        errors.add("stale_replay_rejected")
    if end - start < timedelta(days=7):
        errors.add("seven_day_window_race_rejected")
    for artifact in pack["artifacts"]:
        produced_at = _parse_timestamp(artifact["produced_at"])
        if produced_at < start or produced_at > end:
            errors.add("seven_day_window_race_rejected")
    return errors


def _context_binding_errors(
    pack: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext,
) -> set[str]:
    errors: set[str] = set()
    if context.recomputed_plan_digest is None:
        errors.add("plan_digest_context_missing")
    elif pack["plan_digest"] != context.recomputed_plan_digest:
        errors.add("plan_digest_drift_rejected")

    if context.recomputed_final_diff_digest is None:
        errors.add("final_diff_digest_context_missing")
    elif pack["final_diff_digest"] != context.recomputed_final_diff_digest:
        errors.add("final_diff_digest_drift_rejected")

    if context.github_pr_head_sha is None:
        errors.add("pr_head_sha_context_missing")
    elif pack["pr_head_sha"] != context.github_pr_head_sha:
        errors.add("pr_head_sha_drift_rejected")

    start = _parse_timestamp(pack["time_window_boundaries"]["start"])
    end = _parse_timestamp(pack["time_window_boundaries"]["end"])
    for run_id in pack["workflow_run_ids"]:
        run = context.workflow_runs.get(str(run_id))
        if run is None:
            errors.add("workflow_run_provenance_rejected")
            continue
        if (
            run.status != "completed"
            or run.conclusion != "success"
            or run.head_sha != pack["pr_head_sha"]
            or _parse_timestamp(run.created_at) < start
            or _parse_timestamp(run.created_at) > end
        ):
            errors.add("workflow_run_provenance_rejected")
    return errors


def _identity_errors(pack: Mapping[str, Any]) -> set[str]:
    errors: set[str] = set()
    operator_login = pack["operator_authority"]["github_login"]
    implementer = pack["implementer_provider"]
    verdicts = pack["provider_verdicts"]
    reviewer_logins = [verdict["github_login"] for verdict in verdicts]
    reviewer_providers = [verdict["provider"] for verdict in verdicts]

    if operator_login == implementer["github_login"] or operator_login in reviewer_logins:
        errors.add("operator_login_collision_rejected")
    if len(set(reviewer_logins)) != len(reviewer_logins):
        errors.add("duplicate_reviewer_identity_rejected")
    if implementer["provider"] in reviewer_providers:
        errors.add("implementer_in_reviewer_rejected")
    if len(set(reviewer_providers)) != len(reviewer_providers):
        errors.add("same_provider_rejected")

    recomputed_hashes = [_identity_hash(verdict) for verdict in verdicts]
    if len(set(pack["reviewer_identity_hashes"])) != len(pack["reviewer_identity_hashes"]):
        errors.add("duplicate_reviewer_identity_rejected")
    if list(pack["reviewer_identity_hashes"]) != recomputed_hashes:
        errors.add("reviewer_hash_recomputation_rejected")
    return errors


def _verdict_errors(pack: Mapping[str, Any]) -> set[str]:
    errors: set[str] = set()
    verdicts = pack["provider_verdicts"]
    proof = pack["verdict_completeness_proof"]
    agree_count = sum(1 for verdict in verdicts if verdict["verdict"] == "AGREE")
    negative_count = sum(1 for verdict in verdicts if verdict["verdict"] in {"REVISE", "RED"})

    if proof["verdicts_received_total"] != len(verdicts):
        errors.add("denominator_manipulation_rejected")
    if proof["verdicts_claimed_in_consensus"] != agree_count:
        errors.add("denominator_manipulation_rejected")
    if proof["negative_verdicts_present"] and negative_count == 0:
        errors.add("filtered_negative_verdict_rejected")
    if not proof["negative_verdicts_present"] and negative_count:
        errors.add("filtered_negative_verdict_rejected")
    if pack["consensus_status"] != _recomputed_consensus_status(pack):
        errors.add("forged_consensus_rejected")

    for verdict in verdicts:
        if (
            verdict["plan_digest"] != pack["plan_digest"]
            or verdict["final_diff_digest"] != pack["final_diff_digest"]
            or verdict["pr_head_sha"] != pack["pr_head_sha"]
        ):
            errors.add("verdict_binding_rejected")
        if verdict["raw_verdict_sha256"] != canonical_verdict_sha256(verdict):
            errors.add("raw_verdict_sha_rejected")
    return errors


def _artifact_errors(
    pack: Mapping[str, Any],
    *,
    context: WideningEvidenceValidationContext,
) -> set[str]:
    errors: set[str] = set()
    artifacts_by_id = {artifact["artifact_id"]: artifact for artifact in pack["artifacts"]}
    workflow_run_ids = {str(run_id) for run_id in pack["workflow_run_ids"]}

    for artifact in pack["artifacts"]:
        run_id = str(artifact["run_id"])
        artifact_id = artifact["artifact_id"]
        if run_id not in workflow_run_ids:
            errors.add("orphan_artifact_rejected")
        if artifact_id not in context.workflow_artifacts.get(run_id, frozenset()):
            errors.add("artifact_not_in_run_rejected")
        path = context.artifact_paths.get(artifact_id)
        if path is None:
            errors.add("artifact_path_context_missing")
        elif not path.is_file():
            errors.add("artifact_path_missing")
        else:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != artifact["sha256"]:
                errors.add("artifact_sha_drift_rejected")

    for verdict in pack["provider_verdicts"]:
        ref = verdict["raw_verdict_artifact_ref"]
        artifact = artifacts_by_id.get(ref)
        if artifact is None:
            errors.add("raw_verdict_artifact_ref_dangling_rejected")
            continue
        if verdict["raw_verdict_artifact_digest"] != artifact["sha256"]:
            errors.add("raw_verdict_artifact_cross_binding_rejected")
        if artifact["run_id"] not in workflow_run_ids or artifact["head_sha"] != pack["pr_head_sha"]:
            errors.add("raw_verdict_artifact_provenance_rejected")
    return errors


def canonical_verdict_sha256(verdict: Mapping[str, Any]) -> str:
    """Canonical SHA256 for provider verdicts, excluding the hash field itself."""
    payload = {str(k): v for k, v in verdict.items() if k != "raw_verdict_sha256"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _identity_hash(verdict: Mapping[str, Any]) -> str:
    value = f"{verdict['provider']}|{verdict['github_login']}|{verdict['thread_id']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _recomputed_consensus_status(pack: Mapping[str, Any]) -> str:
    verdicts = pack["provider_verdicts"]
    if verdicts and all(verdict["verdict"] == "AGREE" for verdict in verdicts):
        return "agree"
    return "not_agree"


def _recursive_legacy_artifact_sha_rejections(node: Any) -> set[str]:
    if isinstance(node, dict):
        errors = {"legacy_artifact_sha_array_rejected"} if "artifact_sha256" in node else set()
        for value in node.values():
            errors.update(_recursive_legacy_artifact_sha_rejections(value))
        return errors
    if isinstance(node, list):
        list_errors: set[str] = set()
        for item in node:
            list_errors.update(_recursive_legacy_artifact_sha_rejections(item))
        return list_errors
    return set()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WideningEvidenceValidationError(["timestamp_parse_failed"]) from exc
    if parsed.tzinfo is None:
        raise WideningEvidenceValidationError(["timestamp_timezone_missing"])
    return parsed.astimezone(timezone.utc)


def _expect_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise WideningEvidenceValidationError([f"{field_name}_invalid"])
    return value


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _normalize_support_error(message: str) -> str:
    if "schema validation failed" in message:
        return "schema_validation_failed"
    if "runtime pin re-assert failed" in message:
        return "guard_flag_true_rejected"
    if "forbidden widening key" in message:
        return "legacy_or_shadow_widening_rejected"
    if "recompute_inputs.raw_dimensions" in message or "evidence_dimensions does not match" in message:
        return "recompute_drift_rejected"
    return "support_widening_v1_rejected"
