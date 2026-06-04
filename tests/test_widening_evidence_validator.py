"""V5 Epic 3 E-3-6 invariants: recompute-not-trust validator."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel._internal.support_widening.validator import (
    WorkflowRunObservation,
    WideningEvidenceValidationContext,
    canonical_verdict_sha256,
    validation_report,
)
from ao_kernel.config import load_default

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "widening-supersession-evidence-pack.schema.v1.json"
VALIDATOR_PATH = ROOT / "ao_kernel" / "_internal" / "support_widening" / "validator.py"
VALIDATOR_V2_PATH = ROOT / "ao_kernel" / "_internal" / "support_widening" / "validator_v2.py"
SCHEMA_V2_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / "support_widening_evidence.schema.v2.json"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity_hash(verdict: dict[str, Any]) -> str:
    raw = f"{verdict['provider']}|{verdict['github_login']}|{verdict['thread_id']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _valid_pack(tmp_path: Path) -> tuple[dict[str, Any], WideningEvidenceValidationContext]:
    raw_a = tmp_path / "anthropic-raw-verdict.json"
    raw_b = tmp_path / "mavis-raw-verdict.json"
    raw_a.write_text('{"provider":"anthropic","verdict":"AGREE"}', encoding="utf-8")
    raw_b.write_text('{"provider":"mavis","verdict":"AGREE"}', encoding="utf-8")
    sha_a = _sha_file(raw_a)
    sha_b = _sha_file(raw_b)
    pack: dict[str, Any] = {
        "schema_version": "widening_supersession_evidence_pack.v1",
        "artifact_kind": "widening_supersession_evidence_pack",
        "repo": "Halildeu/ao-kernel",
        "work_package": "E-3-6",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "widening_authorized": False,
        "evidence_class": "live",
        "simulated_only": False,
        "live_call_made": False,
        "operator_authority": {
            "github_login": "Halildeu",
            "authorization_phrase": "AUTHORIZE_SUPPORT_WIDENING_SUPERSESSION",
            "commit_verification_required": True,
        },
        "implementer_provider": {"provider": "openai", "github_login": "codex-implementer"},
        "plan_digest": "a" * 64,
        "final_diff_digest": "b" * 64,
        "pr_head_sha": "c" * 40,
        "workflow_run_ids": ["100", "101"],
        "time_window_boundaries": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-08T00:00:00Z"},
        "artifacts": [
            {
                "run_id": "100",
                "artifact_id": "anthropic-raw-verdict",
                "sha256": sha_a,
                "produced_at": "2026-01-02T00:00:00Z",
                "head_sha": "c" * 40,
            },
            {
                "run_id": "101",
                "artifact_id": "mavis-raw-verdict",
                "sha256": sha_b,
                "produced_at": "2026-01-03T00:00:00Z",
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
                "raw_verdict_artifact_digest": sha_a,
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
                "raw_verdict_artifact_digest": sha_b,
                "raw_verdict_artifact_ref": "mavis-raw-verdict",
            },
        ],
        "reviewer_identity_hashes": [],
        "verdict_completeness_proof": {
            "verdicts_received_total": 2,
            "verdicts_claimed_in_consensus": 2,
            "negative_verdicts_present": False,
        },
        "consensus_status": "agree",
    }
    for verdict in pack["provider_verdicts"]:
        verdict["raw_verdict_sha256"] = canonical_verdict_sha256(verdict)
    pack["reviewer_identity_hashes"] = [_identity_hash(verdict) for verdict in pack["provider_verdicts"]]

    context = WideningEvidenceValidationContext(
        now=datetime(2026, 1, 15, tzinfo=timezone.utc),
        recomputed_plan_digest="a" * 64,
        recomputed_final_diff_digest="b" * 64,
        github_pr_head_sha="c" * 40,
        workflow_runs={
            "100": WorkflowRunObservation(
                status="completed",
                conclusion="success",
                head_sha="c" * 40,
                created_at="2026-01-02T00:00:00Z",
            ),
            "101": WorkflowRunObservation(
                status="completed",
                conclusion="success",
                head_sha="c" * 40,
                created_at="2026-01-03T00:00:00Z",
            ),
        },
        workflow_artifacts={
            "100": frozenset({"anthropic-raw-verdict"}),
            "101": frozenset({"mavis-raw-verdict"}),
        },
        artifact_paths={"anthropic-raw-verdict": raw_a, "mavis-raw-verdict": raw_b},
    )
    return pack, context


def _rejects(pack: dict[str, Any], context: WideningEvidenceValidationContext, code: str) -> bool:
    report = validation_report(pack, context=context)
    return report["valid"] is False and code in report["reason_codes"]


def test_schema_present_valid_and_recursively_strict() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:widening-supersession-evidence-pack:v1"

    def object_nodes(node: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                nodes.append(node)
            for value in node.values():
                nodes.extend(object_nodes(value))
        elif isinstance(node, list):
            for value in node:
                nodes.extend(object_nodes(value))
        return nodes

    for node in object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_valid_supersession_pack_recomputes_to_agree(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    assert not list(Draft202012Validator(_schema()).iter_errors(pack))
    report = validation_report(pack, context=context)
    assert report["valid"] is True
    assert report["decision"] == "validator_agree"
    assert report["consensus_status_recomputed"] == "agree"
    assert report["support_widening"] is False


def test_existing_support_widening_evidence_v1_is_accepted() -> None:
    payload = {
        "schema_version": "support_widening_evidence.v1",
        "artifact_kind": "support_widening_evidence",
        "generated_at": "2026-06-04T10:00:00Z",
        "repo": "Halildeu/ao-kernel",
        "surface_class": "python_version",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
        "simulated_only": True,
        "live_call_made": False,
        "evidence_dimensions": {"matrix": ["3.11"], "pytest_passed": True},
        "reviewer_providers": [],
        "recompute_inputs": {"raw_dimensions": {"matrix": ["3.11"], "pytest_passed": True}},
    }
    assert validation_report(payload)["valid"] is True


def test_v2_and_guard_flip_paths_fail_closed(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    v2 = copy.deepcopy(pack)
    v2["schema_version"] = "support_widening_evidence.v2"
    assert _rejects(v2, context, "unsupported_future_schema_in_epic_3")

    support_true = copy.deepcopy(pack)
    support_true["support_widening"] = True
    assert _rejects(support_true, context, "guard_flag_true_rejected")

    latent_authorized = copy.deepcopy(pack)
    latent_authorized["widening_authorized"] = True
    assert _rejects(latent_authorized, context, "guard_flag_true_rejected")


def test_validator_v2_absent_and_not_imported() -> None:
    assert not VALIDATOR_V2_PATH.exists()
    assert not SCHEMA_V2_PATH.exists()
    tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            rendered = ast.unparse(node)
            assert "validator_v2" not in rendered
            assert "support_widening_evidence.schema.v2" not in rendered


def test_forged_consensus_and_negative_verdict_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    pack["provider_verdicts"][0]["verdict"] = "REVISE"
    pack["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(pack["provider_verdicts"][0])
    assert _rejects(pack, context, "forged_consensus_rejected")
    assert _rejects(pack, context, "filtered_negative_verdict_rejected")


def test_self_review_identity_and_provider_overlap_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    same_provider = copy.deepcopy(pack)
    same_provider["provider_verdicts"][1]["provider"] = "anthropic"
    same_provider["provider_verdicts"][1]["raw_verdict_sha256"] = canonical_verdict_sha256(
        same_provider["provider_verdicts"][1]
    )
    same_provider["reviewer_identity_hashes"] = [_identity_hash(v) for v in same_provider["provider_verdicts"]]
    assert _rejects(same_provider, context, "same_provider_rejected")

    implementer_overlap = copy.deepcopy(pack)
    implementer_overlap["provider_verdicts"][0]["provider"] = "openai"
    implementer_overlap["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(
        implementer_overlap["provider_verdicts"][0]
    )
    implementer_overlap["reviewer_identity_hashes"] = [_identity_hash(v) for v in implementer_overlap["provider_verdicts"]]
    assert _rejects(implementer_overlap, context, "implementer_in_reviewer_rejected")

    operator_overlap = copy.deepcopy(pack)
    operator_overlap["provider_verdicts"][0]["github_login"] = "Halildeu"
    operator_overlap["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(
        operator_overlap["provider_verdicts"][0]
    )
    operator_overlap["reviewer_identity_hashes"] = [_identity_hash(v) for v in operator_overlap["provider_verdicts"]]
    assert _rejects(operator_overlap, context, "operator_login_collision_rejected")


def test_operator_alias_and_legacy_artifact_sha_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    alias = copy.deepcopy(pack)
    alias["operator_authority"]["operator_github_login"] = "Halildeu"
    assert _rejects(alias, context, "operator_alias_rejected")

    legacy = copy.deepcopy(pack)
    legacy["artifact_sha256"] = ["a" * 64]
    assert _rejects(legacy, context, "legacy_artifact_sha_array_rejected")

    nested_legacy = copy.deepcopy(pack)
    nested_legacy["provider_verdicts"][0]["artifact_sha256"] = "a" * 64
    assert _rejects(nested_legacy, context, "legacy_artifact_sha_array_rejected")


def test_mutually_exclusive_simulated_and_live_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    pack["simulated_only"] = True
    pack["live_call_made"] = True
    assert _rejects(pack, context, "mutually_exclusive_simulated_live_rejected")


def test_time_window_stale_replay_and_timestamp_race_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    stale = copy.deepcopy(pack)
    stale["time_window_boundaries"]["end"] = "2025-01-08T00:00:00Z"
    assert _rejects(stale, context, "stale_replay_rejected")

    short_window = copy.deepcopy(pack)
    short_window["time_window_boundaries"]["end"] = "2026-01-03T00:00:00Z"
    assert _rejects(short_window, context, "seven_day_window_race_rejected")

    outside_artifact = copy.deepcopy(pack)
    outside_artifact["artifacts"][0]["produced_at"] = "2026-01-10T00:00:00Z"
    assert _rejects(outside_artifact, context, "seven_day_window_race_rejected")


def test_plan_diff_head_and_workflow_context_drift_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    assert _rejects(pack, context.__class__(**{**context.__dict__, "recomputed_plan_digest": "0" * 64}), "plan_digest_drift_rejected")
    assert _rejects(
        pack,
        context.__class__(**{**context.__dict__, "recomputed_final_diff_digest": "0" * 64}),
        "final_diff_digest_drift_rejected",
    )
    assert _rejects(pack, context.__class__(**{**context.__dict__, "github_pr_head_sha": "0" * 40}), "pr_head_sha_drift_rejected")

    bad_runs = dict(context.workflow_runs)
    bad_runs["100"] = bad_runs["100"].__class__(
        status="completed",
        conclusion="failure",
        head_sha="c" * 40,
        created_at="2026-01-02T00:00:00Z",
    )
    assert _rejects(pack, context.__class__(**{**context.__dict__, "workflow_runs": bad_runs}), "workflow_run_provenance_rejected")


def test_artifact_provenance_and_hash_drift_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    orphan = copy.deepcopy(pack)
    orphan["artifacts"][0]["run_id"] = "999"
    assert _rejects(orphan, context, "orphan_artifact_rejected")

    missing_artifact = copy.deepcopy(pack)
    workflow_artifacts = dict(context.workflow_artifacts)
    workflow_artifacts["100"] = frozenset()
    assert _rejects(
        missing_artifact,
        context.__class__(**{**context.__dict__, "workflow_artifacts": workflow_artifacts}),
        "artifact_not_in_run_rejected",
    )

    sha_drift = copy.deepcopy(pack)
    sha_drift["artifacts"][0]["sha256"] = "0" * 64
    assert _rejects(sha_drift, context, "artifact_sha_drift_rejected")


def test_reviewer_hash_verdict_binding_and_raw_hash_drift_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    reviewer_hash = copy.deepcopy(pack)
    reviewer_hash["reviewer_identity_hashes"][0] = "0" * 64
    assert _rejects(reviewer_hash, context, "reviewer_hash_recomputation_rejected")

    binding = copy.deepcopy(pack)
    binding["provider_verdicts"][0]["final_diff_digest"] = "0" * 64
    binding["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(binding["provider_verdicts"][0])
    assert _rejects(binding, context, "verdict_binding_rejected")

    raw_hash = copy.deepcopy(pack)
    raw_hash["provider_verdicts"][0]["raw_verdict_sha256"] = "0" * 64
    assert _rejects(raw_hash, context, "raw_verdict_sha_rejected")


def test_raw_verdict_artifact_cross_binding_and_dangling_ref_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    digest_drift = copy.deepcopy(pack)
    digest_drift["provider_verdicts"][0]["raw_verdict_artifact_digest"] = "0" * 64
    digest_drift["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(
        digest_drift["provider_verdicts"][0]
    )
    assert _rejects(digest_drift, context, "raw_verdict_artifact_cross_binding_rejected")

    dangling = copy.deepcopy(pack)
    dangling["provider_verdicts"][0]["raw_verdict_artifact_ref"] = "missing"
    dangling["provider_verdicts"][0]["raw_verdict_sha256"] = canonical_verdict_sha256(dangling["provider_verdicts"][0])
    assert _rejects(dangling, context, "raw_verdict_artifact_ref_dangling_rejected")

    provenance = copy.deepcopy(pack)
    provenance["artifacts"][0]["head_sha"] = "0" * 40
    assert _rejects(provenance, context, "raw_verdict_artifact_provenance_rejected")


def test_cli_reports_valid_and_rejected(tmp_path: Path) -> None:
    pack, context = _valid_pack(tmp_path)
    evidence_path = tmp_path / "pack.json"
    context_path = tmp_path / "context.json"
    evidence_path.write_text(json.dumps(pack), encoding="utf-8")
    context_path.write_text(
        json.dumps(
            {
                "now": "2026-01-15T00:00:00Z",
                "recomputed_plan_digest": "a" * 64,
                "recomputed_final_diff_digest": "b" * 64,
                "github_pr_head_sha": "c" * 40,
                "workflow_runs": {
                    "100": {
                        "status": "completed",
                        "conclusion": "success",
                        "head_sha": "c" * 40,
                        "created_at": "2026-01-02T00:00:00Z",
                    },
                    "101": {
                        "status": "completed",
                        "conclusion": "success",
                        "head_sha": "c" * 40,
                        "created_at": "2026-01-03T00:00:00Z",
                    },
                },
                "workflow_artifacts": {"100": ["anthropic-raw-verdict"], "101": ["mavis-raw-verdict"]},
                "artifact_paths": {key: str(path) for key, path in context.artifact_paths.items()},
            }
        ),
        encoding="utf-8",
    )

    ok = subprocess.run(
        [sys.executable, "scripts/validate_widening_evidence.py", "--evidence", str(evidence_path), "--context", str(context_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["valid"] is True

    rejected = copy.deepcopy(pack)
    rejected["widening_authorized"] = True
    evidence_path.write_text(json.dumps(rejected), encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, "scripts/validate_widening_evidence.py", "--evidence", str(evidence_path), "--context", str(context_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1
    report = json.loads(bad.stdout)
    assert report["valid"] is False
    assert "guard_flag_true_rejected" in report["reason_codes"]
