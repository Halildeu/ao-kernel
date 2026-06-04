"""V5 Epic 3 E-3-5 invariants: widening supersession consensus checklist.

E-3-5 is a future-supersession protocol artifact only. It records the
cross-provider consensus and bind-field requirements that a later operator-bound
Epic 9 PR must satisfy before any support-widening flag flip can be considered.
It does not authorize a flip, execute a live adapter, widen support, or claim
production platform readiness.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "widening-supersession-checklist.schema.v1.json"
CHECKLIST_PATH = ROOT / "ao_kernel" / "defaults" / "widening-supersession-checklist.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME

REQUIRED_BIND_FIELDS = {
    "plan_digest",
    "final_diff_digest",
    "pr_head_sha",
    "workflow_run_ids",
    "artifacts[].run_id",
    "artifacts[].artifact_id",
    "artifacts[].sha256",
    "artifacts[].produced_at",
    "artifacts[].head_sha",
    "time_window_boundaries",
    "reviewer_identity_hashes",
    "verdict_completeness_proof",
    "provider_verdicts[].plan_digest",
    "provider_verdicts[].final_diff_digest",
    "provider_verdicts[].pr_head_sha",
    "provider_verdicts[].raw_verdict_sha256",
    "provider_verdicts[].raw_verdict_artifact_digest",
    "provider_verdicts[].raw_verdict_artifact_ref",
}

REQUIRED_ASSERTIONS = {
    "operator_authority_block_present",
    "checklist_alone_does_not_authorize_flip",
    "cross_ai_distinct_provider",
    "evidence_class_live",
    "minimum_provider_live_integration_tests",
    "bind_fields_required",
    "legacy_artifact_sha_array_rejected",
    "stale_replay_rejected",
    "duplicate_reviewer_identity_rejected",
    "filtered_negative_verdict_rejected",
    "denominator_manipulation_rejected",
    "seven_day_window_race_rejected",
    "final_diff_digest_drift_rejected",
    "pr_head_sha_drift_rejected",
    "workflow_run_status_mismatch_rejected",
    "orphan_artifact_rejected",
    "artifact_not_in_run_rejected",
    "reviewer_hash_recomputation_mismatch_rejected",
    "verdict_binding_drift_rejected",
    "raw_verdict_sha_mismatch_rejected",
    "raw_verdict_canonical_self_reference_rejected",
    "raw_verdict_artifact_digest_mismatch_rejected",
    "raw_verdict_artifact_ref_dangling_rejected",
    "raw_verdict_artifact_provenance_rejected",
    "disjoint_identities_required",
    "disjoint_providers_required",
    "recompute_not_trust_consensus",
    "rollback_decision_tree_present",
}


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _checklist() -> dict[str, Any]:
    parsed = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def _parse_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identity_hash(verdict: dict[str, Any]) -> str:
    return _sha256_text(f"{verdict['provider']}|{verdict['github_login']}|{verdict['thread_id']}")


def _canonical_verdict_sha256(verdict: dict[str, Any]) -> str:
    payload = {k: v for k, v in verdict.items() if k != "raw_verdict_sha256"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stamp(day: int) -> str:
    return f"2026-01-{day:02d}T00:00:00Z"


def _valid_pack() -> dict[str, Any]:
    pack: dict[str, Any] = {
        "operator_authority": {"github_login": "Halildeu"},
        "implementer_provider": {"provider": "openai", "github_login": "codex-implementer"},
        "plan_digest": "a" * 64,
        "final_diff_digest": "b" * 64,
        "pr_head_sha": "c" * 40,
        "workflow_run_ids": ["100", "101"],
        "time_window_boundaries": {"start": _stamp(1), "end": _stamp(8)},
        "artifacts": [
            {
                "run_id": "100",
                "artifact_id": "anthropic-raw-verdict",
                "sha256": "d" * 64,
                "produced_at": _stamp(2),
                "head_sha": "c" * 40,
            },
            {
                "run_id": "101",
                "artifact_id": "mavis-raw-verdict",
                "sha256": "e" * 64,
                "produced_at": _stamp(3),
                "head_sha": "c" * 40,
            },
        ],
        "provider_verdicts": [
            {
                "provider": "anthropic",
                "github_login": "claude-reviewer",
                "thread_id": "claude-thread-1",
                "verdict": "AGREE",
                "plan_digest": "a" * 64,
                "final_diff_digest": "b" * 64,
                "pr_head_sha": "c" * 40,
                "raw_verdict_sha256": "",
                "raw_verdict_artifact_digest": "d" * 64,
                "raw_verdict_artifact_ref": "anthropic-raw-verdict",
            },
            {
                "provider": "mavis",
                "github_login": "mavis-reviewer",
                "thread_id": "mavis-thread-1",
                "verdict": "AGREE",
                "plan_digest": "a" * 64,
                "final_diff_digest": "b" * 64,
                "pr_head_sha": "c" * 40,
                "raw_verdict_sha256": "",
                "raw_verdict_artifact_digest": "e" * 64,
                "raw_verdict_artifact_ref": "mavis-raw-verdict",
            },
        ],
        "verdict_completeness_proof": {
            "verdicts_received_total": 2,
            "verdicts_claimed_in_consensus": 2,
            "negative_verdicts_present": False,
        },
    }
    for verdict in pack["provider_verdicts"]:
        verdict["raw_verdict_sha256"] = _canonical_verdict_sha256(verdict)
    pack["reviewer_identity_hashes"] = [_identity_hash(v) for v in pack["provider_verdicts"]]
    return pack


def _api_runs_for(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for run_id in pack["workflow_run_ids"]:
        runs[run_id] = {
            "status": "completed",
            "conclusion": "success",
            "head_sha": pack["pr_head_sha"],
            "created_at": _stamp(2),
        }
    return runs


def _api_artifacts_for(pack: dict[str, Any]) -> dict[str, set[str]]:
    artifacts_by_run: dict[str, set[str]] = {}
    for artifact in pack["artifacts"]:
        artifacts_by_run.setdefault(artifact["run_id"], set()).add(artifact["artifact_id"])
    return artifacts_by_run


def _evaluate_pack(
    pack: dict[str, Any],
    *,
    now: datetime | None = None,
    api_runs: dict[str, dict[str, Any]] | None = None,
    api_artifacts: dict[str, set[str]] | None = None,
    recomputed_final_diff_digest: str | None = None,
    github_pr_head_sha: str | None = None,
) -> set[str]:
    """Test-local E-3-5 negative-case evaluator.

    The production recompute module lands in E-3-6. This helper pins the
    checklist's adversarial cases without performing live GitHub API calls.
    """
    errors: set[str] = set()
    now = now or datetime(2026, 2, 15, tzinfo=timezone.utc)
    api_runs = api_runs or _api_runs_for(pack)
    api_artifacts = api_artifacts or _api_artifacts_for(pack)
    recomputed_final_diff_digest = recomputed_final_diff_digest or pack["final_diff_digest"]
    github_pr_head_sha = github_pr_head_sha or pack["pr_head_sha"]

    if "artifact_sha256" in pack:
        errors.add("legacy_artifact_sha_array_rejected")

    start = _parse_z(pack["time_window_boundaries"]["start"])
    end = _parse_z(pack["time_window_boundaries"]["end"])
    if end < now - timedelta(days=90):
        errors.add("stale_replay_rejected")
    if end - start < timedelta(days=7):
        errors.add("seven_day_window_race_rejected")
    for artifact in pack["artifacts"]:
        produced_at = _parse_z(artifact["produced_at"])
        if produced_at < start or produced_at > end:
            errors.add("seven_day_window_race_rejected")

    if pack["final_diff_digest"] != recomputed_final_diff_digest:
        errors.add("final_diff_digest_drift_rejected")
    if pack["pr_head_sha"] != github_pr_head_sha:
        errors.add("pr_head_sha_drift_rejected")

    for run_id in pack["workflow_run_ids"]:
        run = api_runs.get(run_id, {})
        if (
            run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or run.get("head_sha") != pack["pr_head_sha"]
            or _parse_z(str(run.get("created_at", _stamp(20)))) < start
            or _parse_z(str(run.get("created_at", _stamp(20)))) > end
        ):
            errors.add("workflow_run_status_mismatch_rejected")

    artifact_by_id = {artifact["artifact_id"]: artifact for artifact in pack["artifacts"]}
    for artifact in pack["artifacts"]:
        if artifact["run_id"] not in pack["workflow_run_ids"]:
            errors.add("orphan_artifact_rejected")
        if artifact["artifact_id"] not in api_artifacts.get(artifact["run_id"], set()):
            errors.add("artifact_not_in_run_rejected")

    recomputed_hashes = [_identity_hash(verdict) for verdict in pack["provider_verdicts"]]
    if len(set(pack["reviewer_identity_hashes"])) != len(pack["reviewer_identity_hashes"]):
        errors.add("duplicate_reviewer_identity_rejected")
    if pack["reviewer_identity_hashes"] != recomputed_hashes:
        errors.add("reviewer_hash_recomputation_mismatch_rejected")

    proof = pack["verdict_completeness_proof"]
    agree_count = sum(1 for verdict in pack["provider_verdicts"] if verdict["verdict"] == "AGREE")
    negative_count = sum(1 for verdict in pack["provider_verdicts"] if verdict["verdict"] in {"REVISE", "RED"})
    if proof["verdicts_received_total"] != len(pack["provider_verdicts"]):
        errors.add("denominator_manipulation_rejected")
    if proof["verdicts_claimed_in_consensus"] != agree_count:
        errors.add("denominator_manipulation_rejected")
    if proof["negative_verdicts_present"] and negative_count == 0:
        errors.add("filtered_negative_verdict_rejected")
    if not proof["negative_verdicts_present"] and negative_count:
        errors.add("filtered_negative_verdict_rejected")

    operator_login = pack["operator_authority"]["github_login"]
    implementer = pack["implementer_provider"]
    reviewer_logins = [verdict["github_login"] for verdict in pack["provider_verdicts"]]
    reviewer_providers = [verdict["provider"] for verdict in pack["provider_verdicts"]]
    if operator_login == implementer["github_login"] or operator_login in reviewer_logins:
        errors.add("disjoint_identities_required")
    if len(set(reviewer_logins)) != len(reviewer_logins):
        errors.add("disjoint_identities_required")
    if implementer["provider"] in reviewer_providers or len(set(reviewer_providers)) != len(reviewer_providers):
        errors.add("disjoint_providers_required")

    for verdict in pack["provider_verdicts"]:
        if (
            verdict["plan_digest"] != pack["plan_digest"]
            or verdict["final_diff_digest"] != pack["final_diff_digest"]
            or verdict["pr_head_sha"] != pack["pr_head_sha"]
        ):
            errors.add("verdict_binding_drift_rejected")
        if verdict["raw_verdict_sha256"] != _canonical_verdict_sha256(verdict):
            errors.add("raw_verdict_sha_mismatch_rejected")
            errors.add("raw_verdict_canonical_self_reference_rejected")
        ref = verdict["raw_verdict_artifact_ref"]
        artifact = artifact_by_id.get(ref)
        if artifact is None:
            errors.add("raw_verdict_artifact_ref_dangling_rejected")
            continue
        if verdict["raw_verdict_artifact_digest"] != artifact["sha256"]:
            errors.add("raw_verdict_artifact_digest_mismatch_rejected")
        if artifact["run_id"] not in pack["workflow_run_ids"] or artifact["head_sha"] != pack["pr_head_sha"]:
            errors.add("raw_verdict_artifact_provenance_rejected")

    return errors


def test_schema_present_valid_draft_2020_12() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:widening-supersession-checklist:v1"


def test_checklist_payload_schema_validates_and_keeps_guards_closed() -> None:
    checklist = _checklist()
    assert _is_valid(checklist)
    assert checklist["support_widening"] is False
    assert checklist["production_platform_claim"] is False
    assert checklist["live_adapter_execution"] is False
    assert checklist["widening_flip_authority"] == "operator_bound_supersession_pr_only"
    assert checklist["checklist_alone_authorizes_flip"] is False


def test_recursive_strict_closure_for_shape_defining_object_nodes() -> None:
    def object_nodes(node: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                out.append((path, node))
            for key, value in node.items():
                out.extend(object_nodes(value, f"{path}/{key}"))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                out.extend(object_nodes(value, f"{path}/{index}"))
        return out

    for path, node in object_nodes(_schema()):
        assert node.get("additionalProperties") is False, f"{path} missing additionalProperties:false"
        assert node.get("unevaluatedProperties") is False, f"{path} missing unevaluatedProperties:false"


def test_only_local_refs_are_used() -> None:
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                assert ref.startswith("#/"), f"non-local $ref forbidden: {ref}"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(_schema())


def test_assertion_list_has_required_ids_recompute_strategy_and_bind_fields() -> None:
    checklist = _checklist()
    assertions = checklist["assertions"]
    ids = {assertion["id"] for assertion in assertions}
    assert REQUIRED_ASSERTIONS <= ids
    assert len(ids) == len(assertions)
    for assertion in assertions:
        assert assertion["required"] is True
        assert assertion["recompute_strategy"].strip()
        assert assertion["bind_fields"]
        assert "artifact_sha256" not in assertion["bind_fields"]


def test_bind_field_contract_uses_canonical_names_and_rejects_legacy_alias() -> None:
    checklist = _checklist()
    bind_fields = set(checklist["evidence_pack_contract"]["bind_fields"])
    assert REQUIRED_BIND_FIELDS <= bind_fields
    assert "artifact_sha256" not in bind_fields

    bad_bind_field = copy.deepcopy(checklist)
    bad_bind_field["assertions"][0]["bind_fields"] = ["artifact_sha256"]
    assert not _is_valid(bad_bind_field)

    bad_top_level = copy.deepcopy(checklist)
    bad_top_level["artifact_sha256"] = ["f" * 64]
    assert not _is_valid(bad_top_level)


def test_operator_authority_uses_only_canonical_github_login_field() -> None:
    checklist = _checklist()
    assert checklist["operator_authority"]["github_login"] == "Halildeu"
    assert "operator_github_login" not in checklist["operator_authority"]

    alias_payload = copy.deepcopy(checklist)
    alias_payload["operator_authority"]["operator_github_login"] = "Halildeu"
    assert not _is_valid(alias_payload)


def test_schema_rejects_missing_recompute_strategy_and_empty_bind_fields() -> None:
    missing_strategy = copy.deepcopy(_checklist())
    del missing_strategy["assertions"][0]["recompute_strategy"]
    assert not _is_valid(missing_strategy)

    empty_bind_fields = copy.deepcopy(_checklist())
    empty_bind_fields["assertions"][0]["bind_fields"] = []
    assert not _is_valid(empty_bind_fields)


def test_synthetic_valid_pack_has_no_e_3_5_rejections() -> None:
    assert _evaluate_pack(_valid_pack()) == set()


def test_stale_replay_duplicate_reviewer_filtered_negative_and_denominator_reject() -> None:
    stale = _valid_pack()
    stale["time_window_boundaries"]["end"] = "2025-01-08T00:00:00Z"
    assert "stale_replay_rejected" in _evaluate_pack(stale)

    duplicate_identity = _valid_pack()
    duplicate_identity["reviewer_identity_hashes"][1] = duplicate_identity["reviewer_identity_hashes"][0]
    assert "duplicate_reviewer_identity_rejected" in _evaluate_pack(duplicate_identity)

    filtered_negative = _valid_pack()
    filtered_negative["verdict_completeness_proof"]["negative_verdicts_present"] = True
    assert "filtered_negative_verdict_rejected" in _evaluate_pack(filtered_negative)

    denominator = _valid_pack()
    denominator["verdict_completeness_proof"]["verdicts_received_total"] = 3
    assert "denominator_manipulation_rejected" in _evaluate_pack(denominator)


def test_seven_day_window_and_artifact_timestamp_race_reject() -> None:
    short_window = _valid_pack()
    short_window["time_window_boundaries"]["end"] = "2026-01-03T00:00:00Z"
    assert "seven_day_window_race_rejected" in _evaluate_pack(short_window)

    outside_artifact = _valid_pack()
    outside_artifact["artifacts"][0]["produced_at"] = "2026-01-10T00:00:00Z"
    assert "seven_day_window_race_rejected" in _evaluate_pack(outside_artifact)


def test_final_diff_digest_pr_head_and_workflow_status_drift_reject() -> None:
    diff_drift = _valid_pack()
    assert "final_diff_digest_drift_rejected" in _evaluate_pack(
        diff_drift, recomputed_final_diff_digest="9" * 64
    )

    head_drift = _valid_pack()
    assert "pr_head_sha_drift_rejected" in _evaluate_pack(head_drift, github_pr_head_sha="9" * 40)

    run_drift = _valid_pack()
    api_runs = _api_runs_for(run_drift)
    api_runs["100"]["conclusion"] = "failure"
    assert "workflow_run_status_mismatch_rejected" in _evaluate_pack(run_drift, api_runs=api_runs)


def test_orphan_artifact_and_artifact_not_in_run_reject() -> None:
    orphan = _valid_pack()
    orphan["artifacts"][0]["run_id"] = "999"
    assert "orphan_artifact_rejected" in _evaluate_pack(orphan)

    missing_in_run = _valid_pack()
    api_artifacts = _api_artifacts_for(missing_in_run)
    api_artifacts["100"] = set()
    assert "artifact_not_in_run_rejected" in _evaluate_pack(missing_in_run, api_artifacts=api_artifacts)


def test_reviewer_hash_and_verdict_binding_drift_reject() -> None:
    hash_drift = _valid_pack()
    hash_drift["reviewer_identity_hashes"][0] = "0" * 64
    assert "reviewer_hash_recomputation_mismatch_rejected" in _evaluate_pack(hash_drift)

    binding_drift = _valid_pack()
    binding_drift["provider_verdicts"][0]["final_diff_digest"] = "0" * 64
    binding_drift["provider_verdicts"][0]["raw_verdict_sha256"] = _canonical_verdict_sha256(
        binding_drift["provider_verdicts"][0]
    )
    assert "verdict_binding_drift_rejected" in _evaluate_pack(binding_drift)


def test_raw_verdict_hash_self_reference_and_artifact_binding_reject() -> None:
    sha_drift = _valid_pack()
    sha_drift["provider_verdicts"][0]["raw_verdict_sha256"] = "0" * 64
    errors = _evaluate_pack(sha_drift)
    assert "raw_verdict_sha_mismatch_rejected" in errors
    assert "raw_verdict_canonical_self_reference_rejected" in errors

    digest_drift = _valid_pack()
    digest_drift["provider_verdicts"][0]["raw_verdict_artifact_digest"] = "0" * 64
    digest_drift["provider_verdicts"][0]["raw_verdict_sha256"] = _canonical_verdict_sha256(
        digest_drift["provider_verdicts"][0]
    )
    assert "raw_verdict_artifact_digest_mismatch_rejected" in _evaluate_pack(digest_drift)

    dangling_ref = _valid_pack()
    dangling_ref["provider_verdicts"][0]["raw_verdict_artifact_ref"] = "missing-artifact"
    dangling_ref["provider_verdicts"][0]["raw_verdict_sha256"] = _canonical_verdict_sha256(
        dangling_ref["provider_verdicts"][0]
    )
    assert "raw_verdict_artifact_ref_dangling_rejected" in _evaluate_pack(dangling_ref)

    provenance_drift = _valid_pack()
    provenance_drift["artifacts"][0]["head_sha"] = "0" * 40
    assert "raw_verdict_artifact_provenance_rejected" in _evaluate_pack(provenance_drift)


def test_disjoint_identity_and_provider_requirements_reject_overlap() -> None:
    identity_overlap = _valid_pack()
    identity_overlap["provider_verdicts"][0]["github_login"] = "Halildeu"
    identity_overlap["provider_verdicts"][0]["raw_verdict_sha256"] = _canonical_verdict_sha256(
        identity_overlap["provider_verdicts"][0]
    )
    identity_overlap["reviewer_identity_hashes"] = [
        _identity_hash(verdict) for verdict in identity_overlap["provider_verdicts"]
    ]
    assert "disjoint_identities_required" in _evaluate_pack(identity_overlap)

    provider_overlap = _valid_pack()
    provider_overlap["provider_verdicts"][0]["provider"] = "openai"
    provider_overlap["provider_verdicts"][0]["raw_verdict_sha256"] = _canonical_verdict_sha256(
        provider_overlap["provider_verdicts"][0]
    )
    provider_overlap["reviewer_identity_hashes"] = [
        _identity_hash(verdict) for verdict in provider_overlap["provider_verdicts"]
    ]
    assert "disjoint_providers_required" in _evaluate_pack(provider_overlap)
