"""Dry-run autonomous GitHub App release-gate decision helpers.

This module is intentionally side-effect free. It evaluates a PR-shaped,
service-enriched payload plus repo-owned GPP status and returns the check-run
decision a future ``ao-release-gate`` GitHub App can post.
"""

from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatch
from importlib import resources
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import Draft202012Validator

from ao_kernel.live_adapter_gate import utc_timestamp

RELEASE_GATE_SCHEMA_VERSION = "1"
RELEASE_GATE_PROGRAM_ID = "GPP-2v"
RELEASE_GATE_ARTIFACT_KIND = "ao_release_gate_decision"
RELEASE_GATE_ARTIFACT = "ao-release-gate-decision.v1.json"
RELEASE_GATE_CHECK_NAME = "ao-release-gate"
EXPECTED_REPOSITORY = "Halildeu/ao-kernel"
EXPECTED_BASE_REF = "main"

LOCAL_GATE_EVIDENCE_SCHEMA_NAME = "local-gpp-gate-evidence.schema.v1.json"
REVIEW_EVIDENCE_ACCEPTANCE_SCHEMA_NAME = "ao-release-gate-review-evidence-input.schema.v1.json"

HIGH_RISK_PATH_PATTERNS = (
    ".github/**",
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/**",
    "ao_kernel/ao_release_gate*.py",
    "scripts/ao_release_gate*.py",
    "scripts/local_gpp_gate*.py",
    "ao_kernel/defaults/schemas/*gate*.json",
    "ao_kernel/defaults/policies/**",
    "deploy/**",
)


def diff_digest(changed_paths: list[str]) -> str:
    """Return the ``sha256:`` prefixed digest of a changed-files list.

    Canonical contract between the local-gpp-gate evidence emitter and the
    ao-release-gate decision-core verifier. The digest is taken over the
    newline-joined sorted path list so the binding is stable and
    order-independent. ``scripts/local_gpp_gate.py`` imports this function
    so emitter and verifier cannot drift.
    """

    joined = "\n".join(sorted(changed_paths))
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _load_local_gate_evidence_schema() -> dict[str, Any]:
    """Load the bundled local-gpp-gate-evidence.v1 JSON Schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(LOCAL_GATE_EVIDENCE_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def _load_review_evidence_acceptance_schema() -> dict[str, Any]:
    """Load the bundled ao-release-gate review-evidence acceptance profile."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(REVIEW_EVIDENCE_ACCEPTANCE_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


ALLOW_AUTONOMOUS_MERGE_DECISION = "allow_autonomous_merge"
DENY_POLICY_VIOLATION_DECISION = "deny_policy_violation"
DENY_MISSING_EVIDENCE_DECISION = "deny_missing_evidence"
DENY_STALE_BRANCH_DECISION = "deny_stale_branch"
DENY_UNTRUSTED_CONTEXT_DECISION = "deny_untrusted_context"
ERROR_FAIL_CLOSED_DECISION = "error_fail_closed"

ReleaseGateDecisionValue = Literal[
    "allow_autonomous_merge",
    "deny_policy_violation",
    "deny_missing_evidence",
    "deny_stale_branch",
    "deny_untrusted_context",
    "error_fail_closed",
]
ReleaseGateCheckStatus = Literal["pass", "blocked"]
GithubCheckConclusion = Literal["success", "failure", "neutral"]
ConclusionMode = Literal["shadow", "enforce"]
DEFAULT_CONCLUSION_MODE: ConclusionMode = "shadow"


class AoReleaseGateInputCheck(TypedDict):
    """Normalized upstream check status used by the release gate."""

    name: str
    status: str | None
    conclusion: str | None


class AoReleaseGateHumanReview(TypedDict):
    """Normalized GitHub PR review metadata used by path-sensitive gating."""

    author: str | None
    state: str | None
    commit_oid: str | None


class AoReleaseGateCheck(TypedDict):
    """Single deterministic release-gate input check."""

    name: str
    status: ReleaseGateCheckStatus
    finding_code: str | None
    detail: str


class AoReleaseGateContext(TypedDict):
    """Extracted PR and GPP context for the dry-run release gate."""

    repository: str | None
    pull_request_number: int | None
    issue_url: str | None
    base_ref: str | None
    head_ref: str | None
    head_sha: str | None
    pr_author: str | None
    branch_up_to_date: bool | None
    from_fork: bool | None
    event_name: str | None
    changed_paths: list[str]
    high_risk_changed_paths: list[str]
    allowed_path_prefixes: list[str]
    required_checks: list[AoReleaseGateInputCheck]
    human_reviews: list[AoReleaseGateHumanReview]
    path_sensitive_human_review_enabled: bool | None
    forbidden_secret_context_detected: bool | None
    admin_bypass_requested: bool | None
    pat_backed_bot_actor: bool | None
    codex_or_claude_release_authority: bool | None
    live_adapter_execution_requested: bool | None
    reviewed_slice: str | None
    gpp_current_wp_id: str | None
    gpp_current_wp_issue: str | None
    gpp_current_wp_status: str | None
    gpp_support_widening_allowed: bool | None
    gpp_production_platform_claim_allowed: bool | None
    gpp_live_adapter_execution_allowed: bool | None


class AoReleaseGateCheckRun(TypedDict):
    """Future GitHub check-run shape, without posting it."""

    name: str
    status: str
    conclusion: GithubCheckConclusion
    title: str
    summary: str
    text: str


class AoReleaseGateDecision(TypedDict):
    """Machine-readable dry-run release-gate decision."""

    schema_version: str
    artifact_kind: str
    program_id: str
    generated_at: str
    app_slug: str
    dry_run: bool
    merge_authority_enabled: bool
    conclusion_mode: ConclusionMode
    decision: ReleaseGateDecisionValue
    allow: bool
    finding_code: str | None
    reason: str
    context: AoReleaseGateContext
    checks: list[AoReleaseGateCheck]
    findings: list[str]
    github_check_run: AoReleaseGateCheckRun


def _as_dict(payload: object) -> dict[str, Any]:
    """Return ``payload`` as a dictionary or an empty dictionary."""

    if isinstance(payload, dict):
        return cast(dict[str, Any], payload)
    return {}


def _as_list(payload: object) -> list[Any]:
    """Return ``payload`` as a list or an empty list."""

    if isinstance(payload, list):
        return payload
    return []


def _string(value: object) -> str | None:
    """Return a non-empty string value."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool(value: object) -> bool | None:
    """Return a boolean value without coercing strings."""

    if isinstance(value, bool):
        return value
    return None


def _int(value: object) -> int | None:
    """Return an integer value without coercing strings."""

    if isinstance(value, int):
        return value
    return None


def _first_string(*values: object) -> str | None:
    """Return the first non-empty string."""

    for value in values:
        candidate = _string(value)
        if candidate is not None:
            return candidate
    return None


def _first_bool(*values: object) -> bool | None:
    """Return the first explicit boolean."""

    for value in values:
        candidate = _bool(value)
        if candidate is not None:
            return candidate
    return None


def _first_int(*values: object) -> int | None:
    """Return the first explicit integer."""

    for value in values:
        candidate = _int(value)
        if candidate is not None:
            return candidate
    return None


def _strings(payload: object) -> list[str]:
    """Return a list containing only non-empty strings."""

    result: list[str] = []
    for item in _as_list(payload):
        value = _string(item)
        if value is not None:
            result.append(value)
    return result


def _normalize_ref(value: str | None) -> str | None:
    """Normalize refs/heads/main to main."""

    if value is None:
        return None
    if value.startswith("refs/heads/"):
        return value.removeprefix("refs/heads/")
    return value


def _service_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Return service-enriched release-gate context if present."""

    candidates = (
        payload.get("release_gate_context"),
        payload.get("ao_release_gate"),
        payload.get("verified_context"),
        _as_dict(payload.get("ao_kernel")).get("release_gate_context"),
    )
    for candidate in candidates:
        context = _as_dict(candidate)
        if context:
            return context
    return {}


def _normalized_checks(payload: object) -> list[AoReleaseGateInputCheck]:
    """Normalize check/status-rollup input objects."""

    checks: list[AoReleaseGateInputCheck] = []
    for item in _as_list(payload):
        raw = _as_dict(item)
        name = _first_string(raw.get("name"), raw.get("context"))
        if name is None:
            continue
        checks.append(
            {
                "name": name,
                "status": _first_string(raw.get("status")),
                "conclusion": _first_string(raw.get("conclusion"), raw.get("state")),
            }
        )
    return checks


def _normalized_human_reviews(payload: object) -> list[AoReleaseGateHumanReview]:
    """Normalize GitHub PR review objects from trusted API-derived payloads."""

    reviews: list[AoReleaseGateHumanReview] = []
    for item in _as_list(payload):
        raw = _as_dict(item)
        author = _as_dict(raw.get("author"))
        commit = _as_dict(raw.get("commit"))
        reviews.append(
            {
                "author": _first_string(author.get("login"), raw.get("author")),
                "state": _first_string(raw.get("state")),
                "commit_oid": _first_string(commit.get("oid"), raw.get("commit_oid")),
            }
        )
    return reviews


def _path_allowed(path: str, prefixes: list[str]) -> bool:
    """Return whether ``path`` is inside one explicit allowed path prefix."""

    for raw_prefix in prefixes:
        prefix = raw_prefix.strip()
        if not prefix:
            continue
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def _path_matches_pattern(path: str, pattern: str) -> bool:
    """Return whether ``path`` matches one CODEOWNERS-like high-risk pattern."""

    normalized = pattern.strip().lstrip("/")
    if not normalized:
        return False
    if normalized.endswith("/**"):
        return path.startswith(normalized.removesuffix("**"))
    if normalized.endswith("/"):
        return path.startswith(normalized)
    if any(char in normalized for char in "*?["):
        return fnmatch(path, normalized)
    return path == normalized or path.startswith(f"{normalized}/")


def _high_risk_paths(changed_paths: list[str]) -> list[str]:
    """Return changed paths that require a non-author human approval."""

    return [
        path
        for path in changed_paths
        if any(_path_matches_pattern(path, pattern) for pattern in HIGH_RISK_PATH_PATTERNS)
    ]


def _has_current_non_author_approval(context: AoReleaseGateContext) -> bool:
    """Return whether a high-risk PR has a current-head non-author approval."""

    author = context["pr_author"]
    head_sha = context["head_sha"]
    if author is None or head_sha is None:
        return False
    normalized_author = author.lower()
    for review in context["human_reviews"]:
        reviewer = review["author"]
        state = (review["state"] or "").upper()
        commit_oid = review["commit_oid"]
        if reviewer is None or reviewer.lower() == normalized_author:
            continue
        if state != "APPROVED":
            continue
        if commit_oid != head_sha:
            continue
        return True
    return False


def _path_sensitive_human_review_satisfied(context: AoReleaseGateContext) -> bool:
    """Return whether high-risk paths have required human approval."""

    if context["path_sensitive_human_review_enabled"] is not True:
        return True
    if not context["high_risk_changed_paths"]:
        return True
    return _has_current_non_author_approval(context)


def _required_checks_are_green(checks: list[AoReleaseGateInputCheck]) -> bool:
    """Return whether all non-self required checks are completed successfully."""

    relevant = [check for check in checks if check["name"] != RELEASE_GATE_CHECK_NAME]
    if not relevant:
        return False
    for check in relevant:
        status = (check["status"] or "").lower()
        conclusion = (check["conclusion"] or "").lower()
        if status not in {"completed", "success"}:
            return False
        if conclusion != "success":
            return False
    return True


def _pass(name: str, *, detail: str) -> AoReleaseGateCheck:
    """Build a passing release-gate check."""

    return {"name": name, "status": "pass", "finding_code": None, "detail": detail}


def _blocked(name: str, *, finding_code: str, detail: str) -> AoReleaseGateCheck:
    """Build a blocked release-gate check."""

    return {"name": name, "status": "blocked", "finding_code": finding_code, "detail": detail}


def _check(
    name: str, condition: bool, *, finding_code: str, pass_detail: str, blocked_detail: str
) -> AoReleaseGateCheck:
    """Build one fail-closed check."""

    if condition:
        return _pass(name, detail=pass_detail)
    return _blocked(name, finding_code=finding_code, detail=blocked_detail)


def extract_ao_release_gate_context(payload: object, gpp_status: object) -> AoReleaseGateContext:
    """Extract normalized release-gate context from dry-run inputs."""

    root = _as_dict(payload)
    service = _service_context(root)
    status = _as_dict(gpp_status)
    current_wp = _as_dict(status.get("current_wp"))
    repository = _as_dict(root.get("repository"))
    pull_request = _as_dict(root.get("pull_request"))
    base = _as_dict(pull_request.get("base"))
    head = _as_dict(pull_request.get("head"))
    head_repo = _as_dict(head.get("repo"))
    pr_author = _first_string(
        root.get("pr_author"),
        service.get("pr_author"),
        _as_dict(pull_request.get("author")).get("login"),
    )
    changed_paths = _strings(root.get("changed_paths")) or _strings(service.get("changed_paths"))
    allowed_path_prefixes = _strings(root.get("allowed_path_prefixes")) or _strings(
        service.get("allowed_path_prefixes")
    )
    human_reviews = _normalized_human_reviews(root.get("human_reviews") or root.get("reviews"))
    return {
        "repository": _first_string(
            repository.get("full_name"),
            root.get("repository_full_name"),
            service.get("repository"),
        ),
        "pull_request_number": _first_int(pull_request.get("number"), root.get("pull_request_number")),
        "issue_url": _first_string(root.get("issue_url"), service.get("issue_url")),
        "base_ref": _normalize_ref(_first_string(base.get("ref"), root.get("base_ref"), service.get("base_ref"))),
        "head_ref": _normalize_ref(_first_string(head.get("ref"), root.get("head_ref"), service.get("head_ref"))),
        "head_sha": _first_string(head.get("sha"), root.get("head_sha"), service.get("head_sha")),
        "pr_author": pr_author,
        "branch_up_to_date": _first_bool(root.get("branch_up_to_date"), service.get("branch_up_to_date")),
        "from_fork": _first_bool(root.get("from_fork"), service.get("from_fork"), head_repo.get("fork")),
        "event_name": _first_string(root.get("event_name"), service.get("event_name")),
        "changed_paths": changed_paths,
        "high_risk_changed_paths": _high_risk_paths(changed_paths),
        "allowed_path_prefixes": allowed_path_prefixes,
        "required_checks": _normalized_checks(root.get("required_checks") or root.get("checks")),
        "human_reviews": human_reviews,
        "path_sensitive_human_review_enabled": _first_bool(
            root.get("path_sensitive_human_review_enabled"),
            service.get("path_sensitive_human_review_enabled"),
        ),
        "forbidden_secret_context_detected": _first_bool(
            root.get("forbidden_secret_context_detected"),
            service.get("forbidden_secret_context_detected"),
        ),
        "admin_bypass_requested": _first_bool(
            root.get("admin_bypass_requested"), service.get("admin_bypass_requested")
        ),
        "pat_backed_bot_actor": _first_bool(root.get("pat_backed_bot_actor"), service.get("pat_backed_bot_actor")),
        "codex_or_claude_release_authority": _first_bool(
            root.get("codex_or_claude_release_authority"),
            service.get("codex_or_claude_release_authority"),
        ),
        "live_adapter_execution_requested": _first_bool(
            root.get("live_adapter_execution_requested"),
            service.get("live_adapter_execution_requested"),
        ),
        "reviewed_slice": _first_string(root.get("reviewed_slice"), service.get("reviewed_slice")),
        "gpp_current_wp_id": _first_string(current_wp.get("id")),
        "gpp_current_wp_issue": _first_string(current_wp.get("issue")),
        "gpp_current_wp_status": _first_string(current_wp.get("status")),
        "gpp_support_widening_allowed": _bool(status.get("support_widening_allowed")),
        "gpp_production_platform_claim_allowed": _bool(status.get("production_platform_claim_allowed")),
        "gpp_live_adapter_execution_allowed": _bool(status.get("live_adapter_execution_allowed")),
    }


def _evaluate_review_evidence_checks(
    review_evidence: object,
    context: AoReleaseGateContext,
) -> list[AoReleaseGateCheck]:
    """Evaluate the untrusted local-gpp-gate review evidence.

    Returns two fail-closed checks:

    1. ``review_evidence`` — present, dict, schema-valid against
       ``local-gpp-gate-evidence.schema.v1.json``, and accepting per the
       ``ao-release-gate-review-evidence-input.schema.v1.json`` profile.
    2. ``review_evidence_context_bound`` — when the first check passes,
       confirms ``context_binding`` is present and binds the evidence to
       this PR's head SHA, changed-files digest, repository, reviewed
       slice, and file count. When the first check fails the second
       check is reported with the ``..._context_unverifiable`` finding
       (a missing-evidence finding) so the decision stays in the
       missing-evidence bucket rather than wrongly escalating to
       ``deny_untrusted_context``.

    Reviewer free-text is never echoed into the check details; only
    gate-authored strings appear.
    """

    if not isinstance(review_evidence, dict):
        return [
            _blocked(
                "review_evidence",
                finding_code="ao_release_gate_review_evidence_missing",
                detail="Local-gpp-gate review evidence is missing or is not a JSON object.",
            ),
            _blocked(
                "review_evidence_context_bound",
                finding_code="ao_release_gate_review_evidence_context_unverifiable",
                detail="Context binding cannot be evaluated; review evidence is missing.",
            ),
        ]

    full_validator = Draft202012Validator(_load_local_gate_evidence_schema())
    if list(full_validator.iter_errors(review_evidence)):
        return [
            _blocked(
                "review_evidence",
                finding_code="ao_release_gate_review_evidence_schema_invalid",
                detail="Review evidence does not validate against local-gpp-gate-evidence.schema.v1.json.",
            ),
            _blocked(
                "review_evidence_context_bound",
                finding_code="ao_release_gate_review_evidence_context_unverifiable",
                detail="Context binding cannot be evaluated; review evidence failed the full local-gpp-gate-evidence schema.",
            ),
        ]

    acceptance_validator = Draft202012Validator(_load_review_evidence_acceptance_schema())
    if list(acceptance_validator.iter_errors(review_evidence)):
        return [
            _blocked(
                "review_evidence",
                finding_code="ao_release_gate_review_evidence_not_accepting",
                detail="Review evidence is not an accepting attestation (decision, reviewer AGREE, cross-provider, or guard flag failed the acceptance profile).",
            ),
            _blocked(
                "review_evidence_context_bound",
                finding_code="ao_release_gate_review_evidence_context_unverifiable",
                detail="Context binding cannot be evaluated; review evidence failed the acceptance profile.",
            ),
        ]

    accepted = _pass(
        "review_evidence",
        detail="Review evidence is a schema-valid accepting local-gpp-gate-evidence.v1 attestation.",
    )

    raw_binding = review_evidence.get("context_binding")
    binding = raw_binding if isinstance(raw_binding, dict) else None
    if binding is None:
        return [
            accepted,
            _blocked(
                "review_evidence_context_bound",
                finding_code="ao_release_gate_review_evidence_context_unbound",
                detail="Review evidence has no context_binding block; the evidence cannot be bound to this pull request.",
            ),
        ]

    head_match = context["head_sha"] is not None and binding.get("head_sha") == context["head_sha"]
    repo_match = context["repository"] is not None and review_evidence.get("repo") == context["repository"]
    slice_match = (
        context["reviewed_slice"] is not None and review_evidence.get("work_package") == context["reviewed_slice"]
    )
    digest_match = binding.get("diff_digest") == diff_digest(context["changed_paths"])
    count_match = binding.get("changed_files_count") == len(context["changed_paths"])

    if head_match and repo_match and slice_match and digest_match and count_match:
        bound = _pass(
            "review_evidence_context_bound",
            detail="Review evidence context binding matches the pull request head, repository, reviewed slice, diff digest, and changed-files count.",
        )
    else:
        bound = _blocked(
            "review_evidence_context_bound",
            finding_code="ao_release_gate_review_evidence_context_unbound",
            detail="Review evidence context binding does not match the pull request head, repository, reviewed slice, diff digest, or changed-files count.",
        )

    return [accepted, bound]


def _decision_from_findings(findings: list[str]) -> ReleaseGateDecisionValue:
    """Return the terminal release-gate decision for ordered findings."""

    if "ao_release_gate_payload_not_object" in findings:
        return cast(ReleaseGateDecisionValue, ERROR_FAIL_CLOSED_DECISION)
    if "ao_release_gate_branch_not_up_to_date" in findings:
        return cast(ReleaseGateDecisionValue, DENY_STALE_BRANCH_DECISION)
    if any(
        finding
        in {
            "ao_release_gate_wrong_repository",
            "ao_release_gate_untrusted_fork",
            "ao_release_gate_pull_request_target_context",
            "ao_release_gate_review_evidence_context_unbound",
        }
        for finding in findings
    ):
        return cast(ReleaseGateDecisionValue, DENY_UNTRUSTED_CONTEXT_DECISION)
    if any(
        finding
        in {
            "ao_release_gate_missing_pull_request",
            "ao_release_gate_missing_issue",
            "ao_release_gate_branch_freshness_unknown",
            "ao_release_gate_required_checks_missing",
            "ao_release_gate_required_checks_not_green",
            "ao_release_gate_diff_scope_missing",
            "ao_release_gate_gpp_status_missing",
            "ao_release_gate_gpp_issue_mismatch",
            "ao_release_gate_review_evidence_missing",
            "ao_release_gate_review_evidence_schema_invalid",
            "ao_release_gate_review_evidence_not_accepting",
            "ao_release_gate_review_evidence_context_unverifiable",
        }
        for finding in findings
    ):
        return cast(ReleaseGateDecisionValue, DENY_MISSING_EVIDENCE_DECISION)
    if findings:
        return cast(ReleaseGateDecisionValue, DENY_POLICY_VIOLATION_DECISION)
    return cast(ReleaseGateDecisionValue, ALLOW_AUTONOMOUS_MERGE_DECISION)


def _reason(decision: ReleaseGateDecisionValue) -> str:
    """Return a compact reason for a release-gate decision."""

    if decision == ALLOW_AUTONOMOUS_MERGE_DECISION:
        return "Dry-run release gate would allow autonomous merge; no merge or GitHub write was performed."
    if decision == DENY_STALE_BRANCH_DECISION:
        return "Release gate denied because the PR branch is stale."
    if decision == DENY_UNTRUSTED_CONTEXT_DECISION:
        return "Release gate denied because the PR context is untrusted."
    if decision == DENY_MISSING_EVIDENCE_DECISION:
        return "Release gate denied because required evidence is missing or incomplete."
    if decision == ERROR_FAIL_CLOSED_DECISION:
        return "Release gate failed closed because the input payload was malformed."
    return "Release gate denied because the PR violates autonomous release policy."


def _check_run(
    decision: ReleaseGateDecisionValue,
    findings: list[str],
    *,
    conclusion_mode: ConclusionMode = DEFAULT_CONCLUSION_MODE,
) -> AoReleaseGateCheckRun:
    """Build the future GitHub check-run output shape.

    The check-run conclusion is mode-aware:

    - ``allow_autonomous_merge`` always maps to ``success`` (both modes).
    - In ``shadow`` mode (default), every deny/error decision maps to
      ``neutral`` so advisory evidence does not surface as red CI before
      the AO-GATE-8 enforcement cutover.
    - In ``enforce`` mode, every deny/error decision maps to ``failure``
      (the original fail-closed behavior required once the check is wired
      as a required status check).
    """

    allow = decision == ALLOW_AUTONOMOUS_MERGE_DECISION
    summary = _reason(decision)
    text = "Findings: " + ", ".join(findings) if findings else "All release-gate checks passed."
    if allow:
        conclusion: GithubCheckConclusion = "success"
    elif conclusion_mode == "enforce":
        conclusion = "failure"
    else:
        conclusion = "neutral"
    return {
        "name": RELEASE_GATE_CHECK_NAME,
        "status": "completed",
        "conclusion": conclusion,
        "title": f"{RELEASE_GATE_CHECK_NAME}: {decision}",
        "summary": summary,
        "text": text,
    }


def build_ao_release_gate_decision(
    payload: object,
    gpp_status: object,
    *,
    review_evidence: object = None,
    generated_at: str | None = None,
    conclusion_mode: ConclusionMode = DEFAULT_CONCLUSION_MODE,
) -> AoReleaseGateDecision:
    """Build a fail-closed dry-run release-gate decision.

    ``conclusion_mode`` controls how deny/error decisions surface on the
    GitHub check-run: ``shadow`` (default) maps them to ``neutral`` so the
    advisory check does not produce red CI before AO-GATE-8 enforcement,
    while ``enforce`` maps them to ``failure`` (the historical behavior
    needed once the check is required on branch protection).

    ``review_evidence`` is the untrusted ``local-gpp-gate-evidence.v1``
    attestation supplied by the workflow. When absent, malformed,
    non-accepting, or not bound to this PR's head, repository, reviewed
    slice, diff digest, or changed-files count, the gate fails closed. A
    future ao-release-gate required check will pass this in from the PR
    head's committed evidence file; the dry-run callers may pass ``None``
    and accept a ``deny_missing_evidence`` decision.
    """

    context = extract_ao_release_gate_context(payload, gpp_status)
    checks = [
        _check(
            "payload_shape",
            isinstance(payload, dict),
            finding_code="ao_release_gate_payload_not_object",
            pass_detail="Release-gate payload is a JSON object.",
            blocked_detail="Release-gate payload is not a JSON object.",
        ),
        _check(
            "repository",
            context["repository"] == EXPECTED_REPOSITORY,
            finding_code="ao_release_gate_wrong_repository",
            pass_detail=f"Repository is {EXPECTED_REPOSITORY}.",
            blocked_detail="Repository is missing or is not the approved repository.",
        ),
        _check(
            "pull_request",
            context["pull_request_number"] is not None and context["head_sha"] is not None,
            finding_code="ao_release_gate_missing_pull_request",
            pass_detail="Pull request number and head SHA are present.",
            blocked_detail="Pull request number or head SHA is missing.",
        ),
        _check(
            "issue_link",
            context["issue_url"] is not None,
            finding_code="ao_release_gate_missing_issue",
            pass_detail="Work-package issue URL is present.",
            blocked_detail="Work-package issue URL is missing.",
        ),
        _check(
            "base_ref",
            context["base_ref"] == EXPECTED_BASE_REF,
            finding_code="ao_release_gate_wrong_base_ref",
            pass_detail=f"Base ref is {EXPECTED_BASE_REF}.",
            blocked_detail="Base ref is missing or is not main.",
        ),
        _check(
            "branch_freshness",
            context["branch_up_to_date"] is True,
            finding_code=(
                "ao_release_gate_branch_freshness_unknown"
                if context["branch_up_to_date"] is None
                else "ao_release_gate_branch_not_up_to_date"
            ),
            pass_detail="PR branch is declared up to date with the protected base.",
            blocked_detail="PR branch freshness is missing or stale.",
        ),
        _check(
            "fork_boundary",
            context["from_fork"] is False,
            finding_code="ao_release_gate_untrusted_fork",
            pass_detail="PR head is not a fork context.",
            blocked_detail="PR head is missing or comes from a fork context.",
        ),
        _check(
            "event_boundary",
            context["event_name"] != "pull_request_target",
            finding_code="ao_release_gate_pull_request_target_context",
            pass_detail="Payload is not from pull_request_target.",
            blocked_detail="pull_request_target context is not allowed for autonomous release gating.",
        ),
        _check(
            "required_checks",
            _required_checks_are_green(context["required_checks"]),
            finding_code=(
                "ao_release_gate_required_checks_missing"
                if not context["required_checks"]
                else "ao_release_gate_required_checks_not_green"
            ),
            pass_detail="All supplied required checks are completed successfully.",
            blocked_detail="Required checks are missing, pending, failing, or not successful.",
        ),
        _check(
            "gpp_status",
            context["gpp_current_wp_id"] is not None and context["gpp_current_wp_status"] is not None,
            finding_code="ao_release_gate_gpp_status_missing",
            pass_detail="GPP current work-package status is present.",
            blocked_detail="GPP current work-package status is missing.",
        ),
        _check(
            "gpp_issue_consistency",
            context["issue_url"] is not None and context["issue_url"] == context["gpp_current_wp_issue"],
            finding_code="ao_release_gate_gpp_issue_mismatch",
            pass_detail="Payload issue URL matches the current GPP work-package issue.",
            blocked_detail="Payload issue URL does not match the current GPP work-package issue.",
        ),
        _check(
            "gpp_closed_boundaries",
            context["gpp_support_widening_allowed"] is False
            and context["gpp_production_platform_claim_allowed"] is False
            and context["gpp_live_adapter_execution_allowed"] is False,
            finding_code="ao_release_gate_gpp_boundary_open",
            pass_detail="GPP support, production claim, and live adapter execution flags are closed.",
            blocked_detail="GPP support, production claim, or live adapter execution flag is open or missing.",
        ),
        _check(
            "diff_scope",
            bool(context["changed_paths"])
            and bool(context["allowed_path_prefixes"])
            and all(_path_allowed(path, context["allowed_path_prefixes"]) for path in context["changed_paths"]),
            finding_code=(
                "ao_release_gate_diff_scope_missing"
                if not context["changed_paths"] or not context["allowed_path_prefixes"]
                else "ao_release_gate_diff_out_of_scope"
            ),
            pass_detail="Changed paths are inside the explicit work-package allowlist.",
            blocked_detail="Changed paths or allowlist are missing, or a changed path is out of scope.",
        ),
        _check(
            "path_sensitive_human_review",
            _path_sensitive_human_review_satisfied(context),
            finding_code="ao_release_gate_high_risk_human_review_missing",
            pass_detail=(
                "The path-sensitive human-review gate is inactive, no high-risk paths changed, "
                "or a current-head non-author human approval exists for the high-risk surface."
            ),
            blocked_detail=(
                "High-risk paths changed without a current-head non-author human approval."
            ),
        ),
        _check(
            "secret_boundary",
            context["forbidden_secret_context_detected"] is False,
            finding_code="ao_release_gate_forbidden_secret_context",
            pass_detail="No forbidden secret context was detected.",
            blocked_detail="Forbidden secret context was detected or not explicitly ruled out.",
        ),
        _check(
            "admin_bypass_boundary",
            context["admin_bypass_requested"] is False,
            finding_code="ao_release_gate_admin_bypass_requested",
            pass_detail="Admin bypass is not requested.",
            blocked_detail="Admin bypass is requested or not explicitly ruled out.",
        ),
        _check(
            "bot_boundary",
            context["pat_backed_bot_actor"] is False,
            finding_code="ao_release_gate_pat_backed_bot_actor",
            pass_detail="PAT-backed bot actor is not used.",
            blocked_detail="PAT-backed bot actor is used or not explicitly ruled out.",
        ),
        _check(
            "agent_authority_boundary",
            context["codex_or_claude_release_authority"] is False,
            finding_code="ao_release_gate_agent_release_authority",
            pass_detail="Codex/Claude output is not release authority.",
            blocked_detail="Codex/Claude release authority is requested or not explicitly ruled out.",
        ),
        _check(
            "live_adapter_boundary",
            context["live_adapter_execution_requested"] is False,
            finding_code="ao_release_gate_live_adapter_execution_requested",
            pass_detail="Live adapter execution is not requested.",
            blocked_detail="Live adapter execution is requested or not explicitly ruled out.",
        ),
    ]
    checks.extend(_evaluate_review_evidence_checks(review_evidence, context))
    findings = [check["finding_code"] for check in checks if check["finding_code"] is not None]
    decision = _decision_from_findings(findings)
    allow = decision == ALLOW_AUTONOMOUS_MERGE_DECISION
    return {
        "schema_version": RELEASE_GATE_SCHEMA_VERSION,
        "artifact_kind": RELEASE_GATE_ARTIFACT_KIND,
        "program_id": RELEASE_GATE_PROGRAM_ID,
        "generated_at": generated_at or utc_timestamp(),
        "app_slug": RELEASE_GATE_CHECK_NAME,
        "dry_run": True,
        "merge_authority_enabled": False,
        "conclusion_mode": conclusion_mode,
        "decision": decision,
        "allow": allow,
        "finding_code": None if allow else decision,
        "reason": _reason(decision),
        "context": context,
        "checks": checks,
        "findings": findings,
        "github_check_run": _check_run(decision, findings, conclusion_mode=conclusion_mode),
    }


def render_ao_release_gate_decision_text(decision: AoReleaseGateDecision) -> str:
    """Render a compact human-readable dry-run release-gate decision."""

    context = decision["context"]
    lines = [
        f"decision: {decision['decision']}",
        f"allow: {str(decision['allow']).lower()}",
        f"dry_run: {str(decision['dry_run']).lower()}",
        f"merge_authority_enabled: {str(decision['merge_authority_enabled']).lower()}",
        f"conclusion_mode: {decision['conclusion_mode']}",
        f"github_check_run: {decision['github_check_run']['name']} {decision['github_check_run']['conclusion']}",
        f"repository: {context['repository'] or '<missing>'}",
        f"pull_request_number: {context['pull_request_number'] or '<missing>'}",
        f"base_ref: {context['base_ref'] or '<missing>'}",
        f"head_sha: {context['head_sha'] or '<missing>'}",
        f"issue_url: {context['issue_url'] or '<missing>'}",
        "checks:",
    ]
    for check in decision["checks"]:
        finding = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{finding}")
    if decision["findings"]:
        lines.append("findings:")
        lines.extend(f"- {finding}" for finding in decision["findings"])
    return "\n".join(lines)


def write_ao_release_gate_decision(path: Path, decision: AoReleaseGateDecision) -> None:
    """Write a release-gate decision artifact as canonical pretty JSON."""

    path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
