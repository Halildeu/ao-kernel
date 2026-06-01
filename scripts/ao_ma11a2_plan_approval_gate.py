#!/usr/bin/env python3
"""AO-MA-11A-2 — Plan Approval Gate canonical CLI emitter.

7-stage validation that produces a schema-bound gate_report.json artifact
captured by the .github/workflows/ao-ma-11a-plan-approval.yml `approve` job.

Stages:
    1. Path containment (3 paths repo-relative; absolute/.. reject; symlink-safe)
    2. Raw SHA recompute (sha256 of plan_path + consensus_bundle_path + approval_request_path)
    3. Plan binding + stale-main guard (bundle.plan_binding.base_sha == github.sha)
    4. validate_consensus_bundle() — unanimous AGREE check
    5. GitHub approval review history fetch (retry 3-5; eventual consistency)
    6. Construct approval.json from API response (NOT validate_approval yet)
    7. validate_approval(approval.json, bundle, request) — FINAL stage

HARD RULE pin:
    - Pure stdlib + DI gh_api_caller
    - No GitHub write at runtime (read-only API; artifact emission only)
    - Token NEVER in JSON/log/report (env-var name + boolean presence only)
    - prevent_self_review enforced via triggering_actor != approving_user check
    - bypass detection 3-field separation (no single overclaim)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.orchestration.plan_consensus import (  # noqa: E402
    PlanConsensusError,
    validate_approval,
    validate_consensus_bundle,
)

_ENVIRONMENT_NAME = "ao-ma-plan-approval"
_APPLY_CONFIRMATION = "AO-MA-11A-2-APPROVE"
_API_RETRY_ATTEMPTS = 5
_API_RETRY_BACKOFF_SECONDS = 2.0


@dataclass
class GateReport:
    schema_version: str = "ao-ma-11a-2-plan-approval-gate-report.v1"
    final_decision: str = "usage_error"
    path_containment_pass: bool = False
    sha_recompute_pass: bool = False
    plan_binding_pass: bool = False
    consensus_validator_pass: bool = False
    approval_validator_pass: bool = False
    approval_api_state: str = "empty"
    approving_login: Optional[str] = None
    approving_at: Optional[str] = None
    no_bypass_state_observed: bool = False
    self_review_rejected: bool = False
    required_reviewer_configured: bool = False
    bypass_detected: bool = True
    environment_name: str = _ENVIRONMENT_NAME
    run_id: str = ""
    repository_full_name: str = ""
    base_sha: str = "0" * 40
    triggering_actor: Optional[str] = None
    audit_url: str = ""
    stage_fail_reason: Optional[str] = "not_started"

    def compute_bypass(self) -> None:
        """bypass_detected = NOT(all 3 absence-of-bypass conditions)."""
        self.bypass_detected = not (
            self.no_bypass_state_observed
            and self.self_review_rejected
            and self.required_reviewer_configured
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "final_decision": self.final_decision,
            "path_containment_pass": self.path_containment_pass,
            "sha_recompute_pass": self.sha_recompute_pass,
            "plan_binding_pass": self.plan_binding_pass,
            "consensus_validator_pass": self.consensus_validator_pass,
            "approval_validator_pass": self.approval_validator_pass,
            "approval_api_state": self.approval_api_state,
            "approving_login": self.approving_login,
            "approving_at": self.approving_at,
            "no_bypass_state_observed": self.no_bypass_state_observed,
            "self_review_rejected": self.self_review_rejected,
            "required_reviewer_configured": self.required_reviewer_configured,
            "bypass_detected": self.bypass_detected,
            "environment_name": self.environment_name,
            "run_id": self.run_id,
            "repository_full_name": self.repository_full_name,
            "base_sha": self.base_sha,
            "triggering_actor": self.triggering_actor,
            "audit_url": self.audit_url,
            "stage_fail_reason": self.stage_fail_reason,
        }

    def to_exit_code(self) -> int:
        return 0 if self.final_decision == "approved" else 1


# --- Path containment (stage 1) ----------------------------------------------


def validate_path_containment(path_str: str, repo_root: Path) -> tuple[bool, str]:
    """Reject absolute / `..` segment / symlink kaçış."""
    if path_str.startswith("/"):
        return False, f"absolute path rejected: {path_str}"
    p = Path(path_str)
    if any(part == ".." for part in p.parts):
        return False, f".. segment rejected: {path_str}"
    # Resolve through filesystem (symlink-safe)
    abs_path = (repo_root / path_str).resolve()
    try:
        abs_path.relative_to(repo_root.resolve())
    except ValueError:
        return False, f"path escapes repo root: {path_str}"
    if not abs_path.exists():
        return False, f"path does not exist: {path_str}"
    return True, ""


# --- SHA recompute (stage 2) -------------------------------------------------


def compute_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# --- Plan binding (stage 3) --------------------------------------------------


def validate_plan_binding(
    bundle: dict[str, Any],
    *,
    plan_digest: str,
    github_repository: str,
    github_sha: str,
) -> tuple[bool, str]:
    binding = bundle.get("plan_binding", {})
    repo = binding.get("repository_full_name", "")
    if repo != github_repository:
        return False, f"repository mismatch: bundle={repo} vs github={github_repository}"
    base_ref = binding.get("base_ref", "")
    if base_ref != "refs/heads/main":
        return False, f"base_ref MUST be refs/heads/main; got {base_ref}"
    base_sha = binding.get("base_sha", "")
    if base_sha != github_sha:
        return False, f"stale main: bundle.base_sha={base_sha} vs github.sha={github_sha}"
    bundle_plan_digest = bundle.get("plan_digest", "")
    if bundle_plan_digest != plan_digest:
        return False, f"plan_digest mismatch: bundle={bundle_plan_digest} vs input={plan_digest}"
    return True, ""


# --- GitHub approval API (stage 5) -------------------------------------------


def fetch_approvals(
    *,
    gh_api_caller: Callable[[str, str], Any],
    repo_full_name: str,
    run_id: str,
    retries: int = _API_RETRY_ATTEMPTS,
    backoff_seconds: float = _API_RETRY_BACKOFF_SECONDS,
) -> tuple[Optional[list[dict[str, Any]]], str]:
    """Fetch approvals with bounded retry/backoff (Codex iter-3 implementation pin).

    Returns (approvals_list, error_or_empty_string). Empty list triggers retry up
    to `retries` times before giving up.
    """
    path = f"/repos/{repo_full_name}/actions/runs/{run_id}/approvals"
    last_resp = None
    for attempt in range(retries):
        try:
            resp = gh_api_caller("GET", path)
        except Exception as exc:  # noqa: BLE001
            return None, f"api_error: {exc!s}"
        if resp is None:
            return None, "api_error: null response"
        if isinstance(resp, list) and len(resp) > 0:
            return resp, ""
        last_resp = resp
        if attempt < retries - 1:
            time.sleep(backoff_seconds)
    return last_resp if isinstance(last_resp, list) else [], ""


def parse_approval_from_history(
    approvals: list[dict[str, Any]],
    *,
    target_environment: str,
) -> tuple[Optional[dict[str, Any]], str]:
    """Find first approved review for the target environment.

    Returns (parsed_dict_or_None, state_string).
    """
    if not approvals:
        return None, "empty"
    for entry in approvals:
        envs = entry.get("environments", [])
        env_names = {e.get("name", "") for e in envs}
        if target_environment not in env_names:
            continue
        state = entry.get("state", "")
        if state == "approved":
            user = entry.get("user", {})
            return {
                "approving_login": user.get("login"),
                "approving_at": entry.get("created_at"),
                "approval_api_state": "approved",
            }, "approved"
        # Match environment but not approved → return state for diagnostic
        return {"approval_api_state": state}, state
    # No entry matches target environment
    return {"approval_api_state": "wrong_environment"}, "wrong_environment"


# --- Run metadata (triggering_actor) -----------------------------------------


def fetch_triggering_actor(
    *,
    gh_api_caller: Callable[[str, str], Any],
    repo_full_name: str,
    run_id: str,
) -> tuple[Optional[str], str]:
    try:
        resp = gh_api_caller("GET", f"/repos/{repo_full_name}/actions/runs/{run_id}")
    except Exception as exc:  # noqa: BLE001
        return None, f"api_error: {exc!s}"
    if not resp:
        return None, "empty"
    actor = resp.get("triggering_actor") or {}
    return actor.get("login"), ""


# --- Environment preflight (stage 5 prereq) ----------------------------------


def fetch_environment_preflight(
    *,
    gh_api_caller: Callable[[str, str], Any],
    repo_full_name: str,
    environment_name: str,
) -> tuple[bool, str]:
    try:
        resp = gh_api_caller(
            "GET", f"/repos/{repo_full_name}/environments/{environment_name}"
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"api_error: {exc!s}"
    if not resp:
        return False, "environment_not_found"
    rules = resp.get("protection_rules", [])
    reviewer_count = 0
    for rule in rules:
        if rule.get("type") == "required_reviewers":
            for _ in rule.get("reviewers", []):
                reviewer_count += 1
    if reviewer_count < 1:
        return False, "no_required_reviewers"
    return True, ""


# --- Main 7-stage runner -----------------------------------------------------


def run_gate(
    *,
    plan_path: str,
    consensus_bundle_path: str,
    approval_request_path: str,
    plan_digest: str,
    consensus_bundle_sha256: str,
    approval_request_sha256: str,
    github_run_id: str,
    github_repository: str,
    github_sha: str,
    gh_api_caller: Callable[[str, str], Any],
    repo_root: Path,
    environment_name: str = _ENVIRONMENT_NAME,
) -> GateReport:
    report = GateReport(
        run_id=github_run_id,
        repository_full_name=github_repository,
        base_sha=github_sha,
        audit_url=f"https://github.com/{github_repository}/actions/runs/{github_run_id}",
        stage_fail_reason="not_started",
    )

    # --- Stage 1: path containment ---
    for label, p in [
        ("plan_path", plan_path),
        ("consensus_bundle_path", consensus_bundle_path),
        ("approval_request_path", approval_request_path),
    ]:
        ok, err = validate_path_containment(p, repo_root)
        if not ok:
            report.final_decision = "rejected_path"
            report.stage_fail_reason = f"{label}: {err}"
            report.compute_bypass()
            return report
    report.path_containment_pass = True

    # --- Stage 2: raw SHA recompute ---
    fs_plan_sha = compute_sha256(repo_root / plan_path)
    fs_bundle_sha = compute_sha256(repo_root / consensus_bundle_path)
    fs_request_sha = compute_sha256(repo_root / approval_request_path)
    if fs_plan_sha != plan_digest:
        report.final_decision = "rejected_sha"
        report.stage_fail_reason = f"plan_path sha mismatch: fs={fs_plan_sha} vs input={plan_digest}"
        report.compute_bypass()
        return report
    if fs_bundle_sha != consensus_bundle_sha256:
        report.final_decision = "rejected_sha"
        report.stage_fail_reason = (
            f"consensus_bundle sha mismatch: fs={fs_bundle_sha} vs input={consensus_bundle_sha256}"
        )
        report.compute_bypass()
        return report
    if fs_request_sha != approval_request_sha256:
        report.final_decision = "rejected_sha"
        report.stage_fail_reason = (
            f"approval_request sha mismatch: fs={fs_request_sha} vs input={approval_request_sha256}"
        )
        report.compute_bypass()
        return report
    report.sha_recompute_pass = True

    # --- Stage 3: plan binding + stale-main guard ---
    bundle = json.loads((repo_root / consensus_bundle_path).read_text(encoding="utf-8"))
    ok, err = validate_plan_binding(
        bundle,
        plan_digest=plan_digest,
        github_repository=github_repository,
        github_sha=github_sha,
    )
    if not ok:
        report.final_decision = "rejected_binding"
        report.stage_fail_reason = err
        report.compute_bypass()
        return report
    report.plan_binding_pass = True

    # --- Stage 4: validate_consensus_bundle (unanimous AGREE) ---
    try:
        validate_consensus_bundle(repo_root / consensus_bundle_path)
    except PlanConsensusError as exc:
        report.final_decision = "rejected_consensus"
        report.stage_fail_reason = f"consensus_validator: {exc!s}"
        report.compute_bypass()
        return report
    report.consensus_validator_pass = True

    # --- Stage 4b: environment preflight (required for stage 5) ---
    env_ok, env_err = fetch_environment_preflight(
        gh_api_caller=gh_api_caller,
        repo_full_name=github_repository,
        environment_name=environment_name,
    )
    report.required_reviewer_configured = env_ok
    if not env_ok:
        report.final_decision = "rejected_identity"
        report.stage_fail_reason = f"environment_preflight: {env_err}"
        report.compute_bypass()
        return report

    # --- Stage 5: GitHub approval review history fetch (with retry) ---
    approvals, err = fetch_approvals(
        gh_api_caller=gh_api_caller,
        repo_full_name=github_repository,
        run_id=github_run_id,
    )
    if err:
        report.final_decision = "api_error"
        report.approval_api_state = "api_error"
        report.stage_fail_reason = err
        report.compute_bypass()
        return report
    parsed, api_state = parse_approval_from_history(
        approvals or [], target_environment=environment_name
    )
    report.approval_api_state = api_state
    if api_state != "approved":
        report.final_decision = "rejected_identity"
        report.stage_fail_reason = f"approval_api_state={api_state}"
        report.compute_bypass()
        return report
    assert parsed is not None  # api_state=='approved' branch invariant
    report.approving_login = parsed["approving_login"]
    report.approving_at = parsed["approving_at"]
    # GitHub approval API response does not currently expose admin-bypass field;
    # absence is the strongest signal we can offer (Codex iter-2 §5 absorb).
    report.no_bypass_state_observed = True

    # Triggering actor for self-review check
    triggering_actor, _ = fetch_triggering_actor(
        gh_api_caller=gh_api_caller,
        repo_full_name=github_repository,
        run_id=github_run_id,
    )
    report.triggering_actor = triggering_actor
    if triggering_actor and triggering_actor != report.approving_login:
        report.self_review_rejected = True
    else:
        # Self-review detected OR no triggering actor → can't prove non-self-review
        report.self_review_rejected = False

    report.compute_bypass()
    if report.bypass_detected:
        report.final_decision = "rejected_identity"
        report.stage_fail_reason = (
            f"bypass_detected: no_bypass={report.no_bypass_state_observed} "
            f"self_review_rejected={report.self_review_rejected} "
            f"required_reviewer_configured={report.required_reviewer_configured}"
        )
        return report

    # --- Stage 6: construct approval.json ---
    # approval_id derived from run_id + first 6 chars of bundle consensus_id hash
    consensus_id = bundle.get("consensus_id", "ao-ma-plan-unknown")
    short_hash = hashlib.sha256(consensus_id.encode()).hexdigest()[:6]
    approval_id = f"ao-ma-approval-{report.approving_at[:10].replace('-', '') if report.approving_at else '20260601'}-{short_hash}"

    approval = {
        "schema_version": "ao-ma-11a-plan-approval.v1",
        "artifact_kind": "ao_ma_11a_plan_approval",
        "approval_id": approval_id,
        "consensus_id": consensus_id,
        "consensus_bundle_sha256": consensus_bundle_sha256,
        "approval_request_sha256": approval_request_sha256,
        "plan_digest": plan_digest,
        "unanimous_status": "AGREE",
        "decision": "approved",
        "environment_ref": environment_name,
        "approved_by": report.approving_login,
        "approved_at": report.approving_at,
        "audit_url": report.audit_url,
        "bypass_detected": False,
        "guard_flags": bundle.get(
            "guard_flags",
            {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        ),
        "release_authority": "ao-release-gate+github-ruleset",
        "ai_output_release_authority": False,
        "secrets_recorded": False,
        "created_at": report.approving_at or "2026-06-01T00:00:00Z",
    }

    # Persist approval dict to temp file so validate_approval can re-read
    # raw bytes for SHA recompute (validator signature is path-based).
    approval_path = repo_root / "_gate_approval_tmp.json"
    approval_path.write_text(json.dumps(approval, indent=2), encoding="utf-8")

    # --- Stage 7: validate_approval (FINAL) ---
    try:
        validate_approval(
            approval_path,
            repo_root / consensus_bundle_path,
            repo_root / approval_request_path,
        )
    except PlanConsensusError as exc:
        report.final_decision = "rejected_approval_validator"
        report.stage_fail_reason = f"approval_validator: {exc!s}"
        return report
    finally:
        # Clean up temp file (defensive; even on success)
        try:
            approval_path.unlink()
        except OSError:
            pass

    report.approval_validator_pass = True
    report.final_decision = "approved"
    report.stage_fail_reason = None
    return report


# --- CLI ---------------------------------------------------------------------


def _gh_api_caller(method: str, path: str) -> Any:
    """gh CLI subprocess adapter."""
    proc = subprocess.run(
        ["gh", "api", "-X", method, path],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(f"gh api failed: {stderr}")
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AO-MA-11A-2 plan approval gate CLI")
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--consensus-bundle-path", required=True)
    parser.add_argument("--approval-request-path", required=True)
    parser.add_argument("--plan-digest", required=True)
    parser.add_argument("--consensus-bundle-sha256", required=True)
    parser.add_argument("--approval-request-sha256", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--github-repository", default="Halildeu/ao-kernel")
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--environment-name", default=_ENVIRONMENT_NAME)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.allow_network:
        report = GateReport(
            run_id=args.github_run_id,
            repository_full_name=args.github_repository,
            base_sha=args.github_sha,
            audit_url=f"https://github.com/{args.github_repository}/actions/runs/{args.github_run_id}",
            final_decision="usage_error",
            stage_fail_reason="--allow-network required",
        )
        report.compute_bypass()
        out = json.dumps(report.to_dict(), indent=2)
        if args.output:
            args.output.write_text(out + "\n", encoding="utf-8")
        else:
            print(out)
        return report.to_exit_code()

    report = run_gate(
        plan_path=args.plan_path,
        consensus_bundle_path=args.consensus_bundle_path,
        approval_request_path=args.approval_request_path,
        plan_digest=args.plan_digest,
        consensus_bundle_sha256=args.consensus_bundle_sha256,
        approval_request_sha256=args.approval_request_sha256,
        github_run_id=args.github_run_id,
        github_repository=args.github_repository,
        github_sha=args.github_sha,
        gh_api_caller=_gh_api_caller,
        repo_root=args.repo_root,
        environment_name=args.environment_name,
    )
    out = json.dumps(report.to_dict(), indent=2)
    if args.output:
        args.output.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return report.to_exit_code()


if __name__ == "__main__":
    sys.exit(main())
