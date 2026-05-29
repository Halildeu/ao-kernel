"""Dry-run autonomous GitHub App release-gate decision helpers.

This module is intentionally side-effect free. It evaluates a PR-shaped,
service-enriched payload plus repo-owned GPP status and returns the check-run
decision a future ``ao-release-gate`` GitHub App can post.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
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
AO_MA10_EVIDENCE_BUNDLE_SCHEMA_NAME = "ao-ma-10-evidence-bundle.schema.v1.json"
AO_MA10_HIGH_RISK_SUPERSESSION_SCHEMA_NAME = "ao-ma-10-high-risk-supersession-evidence.schema.v1.json"

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

AO_MA10_LOW_RISK_AUTONOMOUS_SMOKE_PREFIX = "docs/evidence/ao-ma-10l-autonomous-smoke/"
AO_MA10_DEDICATED_MERGE_ACTOR = "gladyatore-lab"


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


def _load_ao_ma10_evidence_bundle_schema() -> dict[str, Any]:
    """Load the bundled AO-MA-10 evidence-bundle schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(AO_MA10_EVIDENCE_BUNDLE_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def _load_ao_ma10_high_risk_supersession_schema() -> dict[str, Any]:
    """Load the bundled AO-MA-10 high-risk supersession evidence schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(
        AO_MA10_HIGH_RISK_SUPERSESSION_SCHEMA_NAME
    )
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
GithubCheckConclusion = Literal["success", "failure", "neutral", "action_required", "stale"]
ConclusionMode = Literal["shadow", "enforce"]
DEFAULT_CONCLUSION_MODE: ConclusionMode = "shadow"

# RG-CONCLUSION-SEMANTICS (Codex thread 019e65c3 absorb):
# Finding codes are categorized by the *operator action shape* they imply.
# The legacy single check-run `ao-release-gate` collapses everything to
# success/failure, which mis-signals "operator approve missing" as a CI
# failure. The new dual check-run model (`ao-release-gate-technical` +
# `ao-release-gate-review`) separates real violations (failure) from
# pending operator action (action_required) and stale branches (stale).
# A C-prime wrapper preserves the legacy job's required check name while
# shifting review-missing semantics off the failure axis (see
# wrapper_exit_code below).
FindingConclusionKind = Literal["failure", "review_action", "stale"]

# Findings that map to GitHub Checks API `action_required` conclusion.
# This conclusion does NOT satisfy a required status check, so merge is
# still blocked — but the UI signal is "needs attention", not "failing".
_REVIEW_ACTION_FINDINGS: frozenset[str] = frozenset(
    {
        "ao_release_gate_high_risk_human_review_missing",
    }
)

# Findings that map to GitHub Checks API `stale` conclusion. The branch
# needs rebase/update; not a code defect. Required check is unsatisfied,
# so merge is blocked.
_STALE_FINDINGS: frozenset[str] = frozenset(
    {
        "ao_release_gate_branch_not_up_to_date",
    }
)

# Public Checks API check-run names for the dual-publish migration (RG-1).
# The legacy ``ao-release-gate`` job is kept as a compatibility wrapper
# (see ``wrapper_exit_code``); these new names are published in parallel
# and will become the required check set after Phase 2 ruleset cutover.
RELEASE_GATE_TECHNICAL_CHECK_NAME = "ao-release-gate-technical"
RELEASE_GATE_REVIEW_CHECK_NAME = "ao-release-gate-review"


def finding_conclusion_kind(finding_code: str | None) -> FindingConclusionKind:
    """Classify a release-gate finding code by its operator action shape.

    Three kinds:

    - ``review_action`` — the operator needs to submit a CODEOWNER review
      on the current PR head. The blocker is procedural, not a code or
      governance defect.
    - ``stale`` — the PR branch needs rebase/update. Not a code defect.
    - ``failure`` — everything else: real governance violation, structural
      input error, secret boundary, scope mismatch, fork/trust violation,
      and so on.

    A finding code of ``None`` returns ``failure`` defensively so unknown
    blockers never silently map to success.
    """

    if finding_code is None:
        return "failure"
    if finding_code in _REVIEW_ACTION_FINDINGS:
        return "review_action"
    if finding_code in _STALE_FINDINGS:
        return "stale"
    return "failure"


def conclusion_for_findings(findings: list[str]) -> GithubCheckConclusion:
    """Return the Checks API conclusion for a finding-code list.

    Empty list → ``success``. Any ``failure`` finding wins (real
    violation outranks pending action). All findings ``review_action`` →
    ``action_required``. All findings ``stale`` → ``stale``. Mixed pending
    kinds (review + stale, no failure) → ``action_required`` because
    operator review is the more specific action signal.
    """

    if not findings:
        return "success"
    kinds = {finding_conclusion_kind(code) for code in findings}
    if "failure" in kinds:
        return "failure"
    if "review_action" in kinds:
        return "action_required"
    if "stale" in kinds:
        return "stale"
    return "failure"


def wrapper_exit_code(decision: ReleaseGateDecisionValue, findings: list[str]) -> int:
    """C-prime compatibility wrapper for the legacy ao-release-gate job.

    Returns 0 (success) when the gate would allow merge OR when the only
    blocker is a pending CODEOWNER review on the current PR head. Returns
    1 (failure) for any real violation, stale branch, or mixed blocker
    set.

    This function preserves the legacy ``ao-release-gate`` job's required
    status check name while shifting review-missing semantics off the
    failure axis. The downstream Checks API publishes the richer signal
    (``action_required`` / ``stale``) on the new dual check-runs. CODEOWNER
    review enforcement after this migration is supplied by GitHub's
    ``require_code_owner_reviews`` branch protection rule, not by this
    wrapper.

    Critical: the wrapper relaxes ONLY the lone-review-action case. A
    review_action blocker mixed with any other blocker still returns 1.
    Real governance violations are never softened.
    """

    if decision == ALLOW_AUTONOMOUS_MERGE_DECISION:
        return 0
    if not findings:
        return 1
    if all(finding_conclusion_kind(code) == "review_action" for code in findings):
        return 0
    return 1


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
    low_risk_autonomous_merge_requested: bool | None
    low_risk_autonomous_merge_request_valid: bool | None
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


def _normalize_binding_ref(value: object) -> str | None:
    """Normalize common local/GitHub ref spellings for context binding."""

    candidate = _string(value)
    if candidate is None:
        return None
    normalized = _normalize_ref(candidate)
    if normalized is not None and normalized.startswith("origin/"):
        return normalized.removeprefix("origin/")
    return normalized


def _autonomous_merge_request_context(
    root: dict[str, Any],
    service: dict[str, Any],
) -> tuple[bool | None, bool]:
    """Return the trusted low-risk autonomous merge request flag.

    The flag is supplied by base-ref workflow code, not by a PR-authored
    artifact. Both the explicit AO-MA-10 key and the generic lane key are
    accepted during the transition, but every provided value must be a
    boolean and duplicate keys must agree.
    """

    candidates: list[object] = []
    for source in (root, service):
        for key in ("low_risk_autonomous_merge_requested", "ao_ma10_autonomous_merge_requested"):
            if key in source:
                candidates.append(source.get(key))
    if not candidates:
        return None, True
    values: list[bool] = []
    for candidate in candidates:
        if not isinstance(candidate, bool):
            return None, False
        values.append(candidate)
    if len(set(values)) > 1:
        return None, False
    return values[0], True


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


def _is_ao_ma10_low_risk_autonomous_smoke_path(path: str) -> bool:
    """Return whether path is a direct AO-MA-10l smoke evidence markdown file."""

    if "\\" in path or path.startswith("/"):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    if not path.startswith(AO_MA10_LOW_RISK_AUTONOMOUS_SMOKE_PREFIX):
        return False
    relative = path[len(AO_MA10_LOW_RISK_AUTONOMOUS_SMOKE_PREFIX):]
    return bool(relative) and "/" not in relative and relative.endswith(".md")


def _ao_ma10_low_risk_autonomous_smoke_scope(context: AoReleaseGateContext) -> bool:
    """Return whether context is the narrow AO-MA-10l autonomous smoke lane.

    The no-human substitute is intentionally much narrower than the generic
    path allowlist. It applies only to disposable smoke evidence markdown
    authored by the dedicated non-admin merge actor. Ordinary PRs still need
    local-gpp-gate review evidence; high-risk PRs still need human review or
    high-risk supersession evidence.
    """

    pr_author = (context["pr_author"] or "").lower()
    paths = context["changed_paths"]
    return (
        context["low_risk_autonomous_merge_request_valid"] is True
        and context["low_risk_autonomous_merge_requested"] is True
        and pr_author == AO_MA10_DEDICATED_MERGE_ACTOR
        and bool(paths)
        and not context["high_risk_changed_paths"]
        and all(_is_ao_ma10_low_risk_autonomous_smoke_path(path) for path in paths)
    )


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


def _path_sensitive_human_review_satisfied(
    context: AoReleaseGateContext, *, high_risk_supersession_valid: bool = False
) -> bool:
    """Return whether high-risk paths have required approval or supersession evidence."""

    if context["path_sensitive_human_review_enabled"] is not True:
        return True
    if not context["high_risk_changed_paths"]:
        return True
    if high_risk_supersession_valid:
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
    autonomous_requested, autonomous_request_valid = _autonomous_merge_request_context(root, service)
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
        "low_risk_autonomous_merge_requested": autonomous_requested,
        "low_risk_autonomous_merge_request_valid": autonomous_request_valid,
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


def _evaluate_review_evidence_or_ao_ma10_low_risk_checks(
    review_evidence: object,
    context: AoReleaseGateContext,
) -> list[AoReleaseGateCheck]:
    """Evaluate review evidence with a narrow AO-MA-10l smoke substitute."""

    if isinstance(review_evidence, dict):
        return _evaluate_review_evidence_checks(review_evidence, context)
    if _ao_ma10_low_risk_autonomous_smoke_scope(context):
        return [
            _pass(
                "review_evidence",
                detail=(
                    "Local-gpp-gate review evidence is not required for the "
                    "AO-MA-10l dedicated-actor low-risk autonomous smoke lane."
                ),
            ),
            _pass(
                "review_evidence_context_bound",
                detail=(
                    "AO-MA-10l low-risk autonomous smoke context is bound by "
                    "API-derived payload data, required checks, dedicated PR "
                    "author, and the disposable smoke evidence path."
                ),
            ),
        ]
    return _evaluate_review_evidence_checks(review_evidence, context)


def _high_risk_supersession_binding_matches(binding: dict[str, Any], context: AoReleaseGateContext) -> bool:
    """Return whether supersession context binding matches the PR context."""

    high_risk_paths = _strings(binding.get("high_risk_changed_paths"))
    return (
        context["repository"] is not None
        and binding.get("repository_full_name") == context["repository"]
        and context["base_ref"] is not None
        and _normalize_binding_ref(binding.get("base_ref")) == _normalize_binding_ref(context["base_ref"])
        and context["head_ref"] is not None
        and _normalize_binding_ref(binding.get("head_ref")) == _normalize_binding_ref(context["head_ref"])
        and context["head_sha"] is not None
        and binding.get("head_sha") == context["head_sha"]
        and binding.get("diff_digest") == diff_digest(context["changed_paths"])
        and binding.get("changed_files_count") == len(context["changed_paths"])
        and sorted(high_risk_paths) == sorted(context["high_risk_changed_paths"])
    )


def _high_risk_supersession_bindings_equivalent(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    """Return whether two supersession bindings describe the same PR context."""

    return (
        left.get("repository_full_name") == right.get("repository_full_name")
        and _normalize_binding_ref(left.get("base_ref")) == _normalize_binding_ref(right.get("base_ref"))
        and _normalize_binding_ref(left.get("head_ref")) == _normalize_binding_ref(right.get("head_ref"))
        and left.get("head_sha") == right.get("head_sha")
        and left.get("diff_digest") == right.get("diff_digest")
        and left.get("changed_files_count") == right.get("changed_files_count")
        and sorted(_strings(left.get("high_risk_changed_paths")))
        == sorted(_strings(right.get("high_risk_changed_paths")))
    )


def _high_risk_supersession_authority_boundary_open(evidence: dict[str, Any]) -> bool:
    """Return whether the untrusted supersession evidence opens a forbidden boundary."""

    raw_guard_flags = _as_dict(evidence.get("guard_flags"))
    top_level_open = (
        ("release_authority" in evidence and evidence.get("release_authority") != "ao-release-gate+github-ruleset")
        or ("ai_output_release_authority" in evidence and evidence.get("ai_output_release_authority") is not False)
        or ("mutations_performed" in evidence and evidence.get("mutations_performed") is not False)
        or ("secrets_recorded" in evidence and evidence.get("secrets_recorded") is not False)
        or ("support_widening" in raw_guard_flags and raw_guard_flags.get("support_widening") is not False)
        or (
            "production_platform_claim" in raw_guard_flags
            and raw_guard_flags.get("production_platform_claim") is not False
        )
        or ("live_adapter_execution" in raw_guard_flags and raw_guard_flags.get("live_adapter_execution") is not False)
    )
    if top_level_open:
        return True
    for verdict in _as_list(evidence.get("provider_verdicts")):
        if not isinstance(verdict, dict):
            continue
        if (
            (
                "release_authority" in verdict
                and verdict.get("release_authority") != "ao-release-gate+github-ruleset"
            )
            or (
                "ai_output_release_authority" in verdict
                and verdict.get("ai_output_release_authority") is not False
            )
            or ("secrets_recorded" in verdict and verdict.get("secrets_recorded") is not False)
            or ("support_widening" in verdict and verdict.get("support_widening") is not False)
            or ("production_platform_claim" in verdict and verdict.get("production_platform_claim") is not False)
            or ("live_adapter_execution" in verdict and verdict.get("live_adapter_execution") is not False)
        ):
            return True
    return False


def _parse_datetime(value: object) -> datetime | None:
    """Parse an RFC3339-ish timestamp into an aware datetime."""

    candidate = _string(value)
    if candidate is None:
        return None
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _high_risk_supersession_is_fresh(evidence: dict[str, Any], *, decision_generated_at: str) -> bool:
    """Return whether supersession evidence is within its declared freshness window."""

    evidence_generated_at = _parse_datetime(evidence.get("generated_at"))
    decision_time = _parse_datetime(decision_generated_at)
    freshness = _as_dict(evidence.get("freshness"))
    max_age_seconds = freshness.get("max_age_seconds")
    if evidence_generated_at is None or decision_time is None:
        return False
    if not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
        return False
    age_seconds = (decision_time - evidence_generated_at).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def _evaluate_high_risk_supersession_checks(
    high_risk_supersession_evidence: object,
    context: AoReleaseGateContext,
    *,
    decision_generated_at: str,
) -> tuple[list[AoReleaseGateCheck], bool]:
    """Evaluate optional high-risk AI supersession evidence.

    This evidence can satisfy the path-sensitive high-risk gate only when
    it is schema-valid, context-bound to the current PR, records unanimous
    OpenAI + Anthropic AGREE verdicts, and keeps release-authority and
    guard-flag boundaries closed. AI output remains evidence; the release
    authority remains this deterministic gate plus GitHub enforcement.
    """

    if high_risk_supersession_evidence is None:
        return (
            [
                _pass(
                    "high_risk_supersession_evidence",
                    detail="High-risk supersession evidence was not supplied; the human-review path remains authoritative.",
                ),
                _pass(
                    "high_risk_supersession_schema",
                    detail="High-risk supersession schema validation is not required when evidence is absent.",
                ),
                _pass(
                    "high_risk_supersession_freshness",
                    detail="High-risk supersession freshness validation is not required when evidence is absent.",
                ),
                _pass(
                    "high_risk_supersession_consensus",
                    detail="High-risk supersession provider consensus is not required when evidence is absent.",
                ),
                _pass(
                    "high_risk_supersession_context_bound",
                    detail="High-risk supersession context binding is not required when evidence is absent.",
                ),
                _pass(
                    "high_risk_supersession_authority_boundary",
                    detail="High-risk supersession authority boundary validation is not required when evidence is absent.",
                ),
            ],
            False,
        )

    if not isinstance(high_risk_supersession_evidence, dict):
        return (
            [
                _blocked(
                    "high_risk_supersession_evidence",
                    finding_code="ao_release_gate_high_risk_supersession_evidence_missing",
                    detail="High-risk supersession evidence is supplied but is not a JSON object.",
                ),
                _pass(
                    "high_risk_supersession_schema",
                    detail="High-risk supersession schema cannot be evaluated until a JSON object is present.",
                ),
                _pass(
                    "high_risk_supersession_freshness",
                    detail="High-risk supersession freshness cannot be evaluated until a JSON object is present.",
                ),
                _pass(
                    "high_risk_supersession_consensus",
                    detail="High-risk supersession consensus cannot be evaluated until a JSON object is present.",
                ),
                _blocked(
                    "high_risk_supersession_context_bound",
                    finding_code="ao_release_gate_high_risk_supersession_context_unverifiable",
                    detail="High-risk supersession context binding cannot be evaluated; evidence is missing.",
                ),
                _pass(
                    "high_risk_supersession_authority_boundary",
                    detail="High-risk supersession authority boundary cannot be evaluated until a JSON object is present.",
                ),
            ],
            False,
        )

    evidence_present = _pass(
        "high_risk_supersession_evidence",
        detail="High-risk supersession evidence is present as a JSON object.",
    )
    if _high_risk_supersession_authority_boundary_open(high_risk_supersession_evidence):
        return (
            [
                evidence_present,
                _pass(
                    "high_risk_supersession_schema",
                    detail="High-risk supersession schema validation is deferred; authority boundary is explicitly open.",
                ),
                _pass(
                    "high_risk_supersession_freshness",
                    detail="High-risk supersession freshness is not evaluated because authority boundary is explicitly open.",
                ),
                _pass(
                    "high_risk_supersession_consensus",
                    detail="High-risk supersession consensus is not evaluated because authority boundary is explicitly open.",
                ),
                _pass(
                    "high_risk_supersession_context_bound",
                    detail="High-risk supersession context binding is not evaluated because authority boundary is explicitly open.",
                ),
                _blocked(
                    "high_risk_supersession_authority_boundary",
                    finding_code="ao_release_gate_high_risk_supersession_authority_boundary_open",
                    detail="High-risk supersession evidence opens release authority, mutation, secret, or guard-flag boundaries.",
                ),
            ],
            False,
        )

    explicit_non_agree = high_risk_supersession_evidence.get("consensus_status") not in {None, "AGREE"} or any(
        isinstance(verdict, dict) and verdict.get("verdict") not in {None, "AGREE"}
        for verdict in _as_list(high_risk_supersession_evidence.get("provider_verdicts"))
    )
    if explicit_non_agree:
        return (
            [
                evidence_present,
                _pass(
                    "high_risk_supersession_schema",
                    detail="High-risk supersession schema validation is deferred; evidence explicitly records non-AGREE consensus.",
                ),
                _pass(
                    "high_risk_supersession_freshness",
                    detail="High-risk supersession freshness is not evaluated because evidence explicitly records non-AGREE consensus.",
                ),
                _blocked(
                    "high_risk_supersession_consensus",
                    finding_code="ao_release_gate_high_risk_supersession_consensus_not_agree",
                    detail="High-risk supersession evidence does not record unanimous AGREE consensus from required providers.",
                ),
                _blocked(
                    "high_risk_supersession_context_bound",
                    finding_code="ao_release_gate_high_risk_supersession_context_unverifiable",
                    detail="High-risk supersession context binding cannot be trusted; consensus is not accepting.",
                ),
                _pass(
                    "high_risk_supersession_authority_boundary",
                    detail="High-risk supersession authority boundary remains closed.",
                ),
            ],
            False,
        )

    validator = Draft202012Validator(_load_ao_ma10_high_risk_supersession_schema())
    if list(validator.iter_errors(high_risk_supersession_evidence)):
        return (
            [
                evidence_present,
                _blocked(
                    "high_risk_supersession_schema",
                    finding_code="ao_release_gate_high_risk_supersession_schema_invalid",
                    detail=(
                        "High-risk supersession evidence does not validate against "
                        "ao-ma-10-high-risk-supersession-evidence.schema.v1.json."
                    ),
                ),
                _pass(
                    "high_risk_supersession_consensus",
                    detail="High-risk supersession consensus cannot be evaluated until schema validation passes.",
                ),
                _pass(
                    "high_risk_supersession_freshness",
                    detail="High-risk supersession freshness cannot be evaluated until schema validation passes.",
                ),
                _blocked(
                    "high_risk_supersession_context_bound",
                    finding_code="ao_release_gate_high_risk_supersession_context_unverifiable",
                    detail="High-risk supersession context binding cannot be evaluated; evidence failed schema validation.",
                ),
                _pass(
                    "high_risk_supersession_authority_boundary",
                    detail="High-risk supersession authority boundary cannot be evaluated until schema validation passes.",
                ),
            ],
            False,
        )

    schema_valid = _pass(
        "high_risk_supersession_schema",
        detail="High-risk supersession evidence validates against its JSON Schema.",
    )
    if not _high_risk_supersession_is_fresh(
        high_risk_supersession_evidence,
        decision_generated_at=decision_generated_at,
    ):
        return (
            [
                evidence_present,
                schema_valid,
                _blocked(
                    "high_risk_supersession_freshness",
                    finding_code="ao_release_gate_high_risk_supersession_stale",
                    detail=(
                        "High-risk supersession evidence is stale, generated in the future, "
                        "or has an unparsable freshness window."
                    ),
                ),
                _pass(
                    "high_risk_supersession_consensus",
                    detail="High-risk supersession consensus is not evaluated because freshness failed.",
                ),
                _blocked(
                    "high_risk_supersession_context_bound",
                    finding_code="ao_release_gate_high_risk_supersession_context_unverifiable",
                    detail="High-risk supersession context binding cannot be trusted; freshness failed.",
                ),
                _pass(
                    "high_risk_supersession_authority_boundary",
                    detail="High-risk supersession authority boundary remains closed.",
                ),
            ],
            False,
        )
    freshness_check = _pass(
        "high_risk_supersession_freshness",
        detail="High-risk supersession evidence is within its declared freshness window.",
    )
    authority_check = _pass(
        "high_risk_supersession_authority_boundary",
        detail="High-risk supersession evidence keeps release authority, mutation, secret, and guard-flag boundaries closed.",
    )

    provider_verdicts = _as_list(high_risk_supersession_evidence.get("provider_verdicts"))
    provider_ids = [item.get("provider_id") for item in provider_verdicts if isinstance(item, dict)]
    provider_ids_are_distinct = len(set(provider_ids)) == len(provider_ids)
    required_provider_ids = {"openai", "anthropic"}
    required_providers_are_present = required_provider_ids.issubset(set(provider_ids))
    if not provider_ids_are_distinct or not required_providers_are_present:
        return (
            [
                evidence_present,
                schema_valid,
                freshness_check,
                _blocked(
                    "high_risk_supersession_consensus",
                    finding_code="ao_release_gate_high_risk_supersession_same_provider_self_review",
                    detail="High-risk supersession evidence contains duplicate providers or omits OpenAI/Anthropic.",
                ),
                _blocked(
                    "high_risk_supersession_context_bound",
                    finding_code="ao_release_gate_high_risk_supersession_context_unverifiable",
                    detail="High-risk supersession context binding cannot be trusted; provider identity is not distinct.",
                ),
                authority_check,
            ],
            False,
        )

    consensus_check = _pass(
        "high_risk_supersession_consensus",
        detail="High-risk supersession evidence records unanimous AGREE from OpenAI and Anthropic providers.",
    )
    raw_binding = high_risk_supersession_evidence.get("context_binding")
    binding = raw_binding if isinstance(raw_binding, dict) else None
    provider_bindings = [
        _as_dict(verdict.get("context_binding")) for verdict in provider_verdicts if isinstance(verdict, dict)
    ]
    provider_bindings_match = bool(provider_bindings) and all(
        _high_risk_supersession_binding_matches(provider_binding, context)
        and binding is not None
        and _high_risk_supersession_bindings_equivalent(provider_binding, binding)
        for provider_binding in provider_bindings
    )
    context_bound = (
        binding is not None
        and _high_risk_supersession_binding_matches(binding, context)
        and provider_bindings_match
    )
    context_check = (
        _pass(
            "high_risk_supersession_context_bound",
            detail=(
                "High-risk supersession evidence context binding matches repository, refs, head SHA, "
                "diff digest, changed-files count, and high-risk changed paths."
            ),
        )
        if context_bound
        else _blocked(
            "high_risk_supersession_context_bound",
            finding_code="ao_release_gate_high_risk_supersession_context_unbound",
            detail=(
                "High-risk supersession evidence context binding does not match the pull request "
                "or provider verdict bindings."
            ),
        )
    )
    return (
        [evidence_present, schema_valid, freshness_check, consensus_check, context_check, authority_check],
        context_bound,
    )


def _evaluate_ao_ma10_evidence_bundle_checks(
    ao_ma10_evidence_bundle: object,
    context: AoReleaseGateContext,
) -> list[AoReleaseGateCheck]:
    """Evaluate AO-MA-10 context-bound provider consensus evidence.

    The AO-MA-10 bundle is required only for the future low-risk
    autonomous merge lane. Existing release-gate decisions stay
    backward-compatible while the low-risk autonomous lane is not
    requested and no bundle is explicitly supplied. If a bundle is supplied,
    however, it is validated fail-closed so a miswired future workflow
    cannot silently ignore malformed AI-consensus evidence.

    Provider free text is never echoed; details are gate-authored only.
    """

    request_valid = context["low_risk_autonomous_merge_request_valid"] is True
    requested = context["low_risk_autonomous_merge_requested"] is True
    supplied = ao_ma10_evidence_bundle is not None

    request_check = (
        _pass(
            "ao_ma10_autonomous_request",
            detail="Low-risk autonomous merge request flag is absent or an explicit boolean.",
        )
        if request_valid
        else _blocked(
            "ao_ma10_autonomous_request",
            finding_code="ao_release_gate_ao_ma10_autonomous_request_invalid",
            detail="Low-risk autonomous merge request flag is malformed or conflicting.",
        )
    )

    def _not_required_checks() -> list[AoReleaseGateCheck]:
        return [
            request_check,
            _pass(
                "ao_ma10_evidence_bundle",
                detail="AO-MA-10 autonomous merge evidence is not requested for this release-gate decision.",
            ),
            _pass(
                "ao_ma10_evidence_bundle_schema",
                detail="AO-MA-10 evidence bundle schema validation is not required for this release-gate decision.",
            ),
            _pass(
                "ao_ma10_consensus",
                detail="AO-MA-10 provider consensus is not required for this release-gate decision.",
            ),
            _pass(
                "ao_ma10_context_bound",
                detail="AO-MA-10 evidence context binding is not required for this release-gate decision.",
            ),
            _pass(
                "ao_ma10_authority_boundary",
                detail="AO-MA-10 authority boundary validation is not required for this release-gate decision.",
            ),
        ]

    if not requested and not supplied:
        return _not_required_checks()

    if requested and not supplied and _ao_ma10_low_risk_autonomous_smoke_scope(context):
        return [
            request_check,
            _pass(
                "ao_ma10_evidence_bundle",
                detail=(
                    "AO-MA-10 evidence bundle is not required for the narrow "
                    "dedicated-actor low-risk autonomous smoke lane."
                ),
            ),
            _pass(
                "ao_ma10_evidence_bundle_schema",
                detail=(
                    "AO-MA-10 evidence bundle schema validation is not required "
                    "for the narrow dedicated-actor low-risk autonomous smoke lane."
                ),
            ),
            _pass(
                "ao_ma10_consensus",
                detail=(
                    "AO-MA-10 provider consensus is not required for the narrow "
                    "dedicated-actor low-risk autonomous smoke lane."
                ),
            ),
            _pass(
                "ao_ma10_context_bound",
                detail=(
                    "The narrow AO-MA-10l smoke lane is context-bound by the "
                    "API-derived payload, required checks, dedicated PR author, "
                    "and disposable smoke evidence path."
                ),
            ),
            _pass(
                "ao_ma10_authority_boundary",
                detail=(
                    "AO-MA-10l low-risk smoke keeps release authority with "
                    "ao-release-gate plus the GitHub ruleset."
                ),
            ),
        ]

    if not isinstance(ao_ma10_evidence_bundle, dict):
        return [
            request_check,
            _blocked(
                "ao_ma10_evidence_bundle",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_missing",
                detail="AO-MA-10 evidence bundle is missing or is not a JSON object.",
            ),
            _pass(
                "ao_ma10_evidence_bundle_schema",
                detail="AO-MA-10 evidence bundle schema cannot be evaluated until a JSON object is present.",
            ),
            _pass(
                "ao_ma10_consensus",
                detail="AO-MA-10 provider consensus cannot be evaluated until a JSON object is present.",
            ),
            _blocked(
                "ao_ma10_context_bound",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable",
                detail="AO-MA-10 evidence context binding cannot be evaluated; bundle is missing.",
            ),
            _pass(
                "ao_ma10_authority_boundary",
                detail="AO-MA-10 authority boundary cannot be evaluated until a JSON object is present.",
            ),
        ]

    bundle_present = _pass(
        "ao_ma10_evidence_bundle",
        detail="AO-MA-10 evidence bundle is present as a JSON object.",
    )
    raw_guard_flags = _as_dict(ao_ma10_evidence_bundle.get("guard_flags"))
    authority_boundary_explicitly_open = (
        (
            "release_authority" in ao_ma10_evidence_bundle
            and ao_ma10_evidence_bundle.get("release_authority") != "ao-release-gate+github-ruleset"
        )
        or (
            "ai_output_release_authority" in ao_ma10_evidence_bundle
            and ao_ma10_evidence_bundle.get("ai_output_release_authority") is not False
        )
        or (
            "mutations_performed" in ao_ma10_evidence_bundle
            and ao_ma10_evidence_bundle.get("mutations_performed") is not False
        )
        or (
            "secrets_recorded" in ao_ma10_evidence_bundle
            and ao_ma10_evidence_bundle.get("secrets_recorded") is not False
        )
        or ("support_widening" in raw_guard_flags and raw_guard_flags.get("support_widening") is not False)
        or (
            "production_platform_claim" in raw_guard_flags
            and raw_guard_flags.get("production_platform_claim") is not False
        )
        or (
            "live_adapter_execution" in raw_guard_flags
            and raw_guard_flags.get("live_adapter_execution") is not False
        )
    )
    if authority_boundary_explicitly_open:
        return [
            request_check,
            bundle_present,
            _pass(
                "ao_ma10_evidence_bundle_schema",
                detail="AO-MA-10 evidence bundle schema validation is deferred; authority boundary is explicitly open.",
            ),
            _pass(
                "ao_ma10_consensus",
                detail="AO-MA-10 provider consensus is not evaluated because authority boundary is explicitly open.",
            ),
            _pass(
                "ao_ma10_context_bound",
                detail="AO-MA-10 evidence context binding is not evaluated because authority boundary is explicitly open.",
            ),
            _blocked(
                "ao_ma10_authority_boundary",
                finding_code="ao_release_gate_ao_ma10_authority_boundary_open",
                detail="AO-MA-10 bundle opens release authority, mutation, secret, or guard-flag boundaries.",
            ),
        ]

    validator = Draft202012Validator(_load_ao_ma10_evidence_bundle_schema())
    if list(validator.iter_errors(ao_ma10_evidence_bundle)):
        return [
            request_check,
            bundle_present,
            _blocked(
                "ao_ma10_evidence_bundle_schema",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_schema_invalid",
                detail="AO-MA-10 evidence bundle does not validate against ao-ma-10-evidence-bundle.schema.v1.json.",
            ),
            _pass(
                "ao_ma10_consensus",
                detail="AO-MA-10 provider consensus cannot be evaluated until schema validation passes.",
            ),
            _blocked(
                "ao_ma10_context_bound",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable",
                detail="AO-MA-10 evidence context binding cannot be evaluated; bundle failed schema validation.",
            ),
            _pass(
                "ao_ma10_authority_boundary",
                detail="AO-MA-10 authority boundary cannot be evaluated until schema validation passes.",
            ),
        ]

    schema_valid = _pass(
        "ao_ma10_evidence_bundle_schema",
        detail="AO-MA-10 evidence bundle validates against ao-ma-10-evidence-bundle.schema.v1.json.",
    )

    authority_ok = (
        ao_ma10_evidence_bundle.get("release_authority") == "ao-release-gate+github-ruleset"
        and ao_ma10_evidence_bundle.get("ai_output_release_authority") is False
        and ao_ma10_evidence_bundle.get("mutations_performed") is False
        and ao_ma10_evidence_bundle.get("secrets_recorded") is False
        and _as_dict(ao_ma10_evidence_bundle.get("guard_flags")).get("support_widening") is False
        and _as_dict(ao_ma10_evidence_bundle.get("guard_flags")).get("production_platform_claim") is False
        and _as_dict(ao_ma10_evidence_bundle.get("guard_flags")).get("live_adapter_execution") is False
    )
    authority_check = (
        _pass(
            "ao_ma10_authority_boundary",
            detail="AO-MA-10 bundle keeps release authority, mutation, secret, and guard-flag boundaries closed.",
        )
        if authority_ok
        else _blocked(
            "ao_ma10_authority_boundary",
            finding_code="ao_release_gate_ao_ma10_authority_boundary_open",
            detail="AO-MA-10 bundle opens release authority, mutation, secret, or guard-flag boundaries.",
        )
    )

    provider_verdicts = _as_list(ao_ma10_evidence_bundle.get("provider_verdicts"))
    provider_ids = [item.get("provider_id") for item in provider_verdicts if isinstance(item, dict)]
    required_provider_ids = _as_list(ao_ma10_evidence_bundle.get("required_reviewer_providers"))
    required_provider_ids = [item for item in required_provider_ids if isinstance(item, str)]
    provider_ids_are_distinct = len(set(provider_ids)) == len(provider_ids)
    required_providers_are_present = all(provider in provider_ids for provider in required_provider_ids)
    if not provider_ids_are_distinct or not required_providers_are_present:
        return [
            request_check,
            bundle_present,
            schema_valid,
            _blocked(
                "ao_ma10_consensus",
                finding_code="ao_release_gate_ao_ma10_same_provider_self_review",
                detail="AO-MA-10 evidence bundle contains duplicate providers or omits a required provider verdict.",
            ),
            _blocked(
                "ao_ma10_context_bound",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable",
                detail="AO-MA-10 evidence context binding cannot be trusted; provider identity is not distinct.",
            ),
            authority_check,
        ]

    all_provider_verdicts_agree = all(
        isinstance(item, dict) and item.get("verdict") == "AGREE" for item in provider_verdicts
    )
    if ao_ma10_evidence_bundle.get("consensus_status") != "AGREE" or not all_provider_verdicts_agree:
        return [
            request_check,
            bundle_present,
            schema_valid,
            _blocked(
                "ao_ma10_consensus",
                finding_code="ao_release_gate_ao_ma10_consensus_not_agree",
                detail="AO-MA-10 evidence bundle does not record unanimous AGREE consensus from required providers.",
            ),
            _blocked(
                "ao_ma10_context_bound",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable",
                detail="AO-MA-10 evidence context binding cannot be trusted; bundle consensus is not accepting.",
            ),
            authority_check,
        ]

    consensus_check = _pass(
        "ao_ma10_consensus",
        detail="AO-MA-10 evidence bundle is schema-valid and records unanimous AGREE provider consensus.",
    )

    raw_binding = ao_ma10_evidence_bundle.get("context_binding")
    binding = raw_binding if isinstance(raw_binding, dict) else None
    if binding is None:
        return [
            request_check,
            bundle_present,
            schema_valid,
            consensus_check,
            _blocked(
                "ao_ma10_context_bound",
                finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unbound",
                detail="AO-MA-10 evidence bundle has no context_binding block.",
            ),
            authority_check,
        ]

    repo_match = (
        context["repository"] is not None and binding.get("repository_full_name") == context["repository"]
    )
    base_match = (
        context["base_ref"] is not None
        and _normalize_binding_ref(binding.get("base_ref")) == _normalize_binding_ref(context["base_ref"])
    )
    head_ref_match = (
        context["head_ref"] is not None
        and _normalize_binding_ref(binding.get("head_ref")) == _normalize_binding_ref(context["head_ref"])
    )
    head_match = context["head_sha"] is not None and binding.get("head_sha") == context["head_sha"]
    digest_match = binding.get("diff_digest") == diff_digest(context["changed_paths"])
    count_match = binding.get("changed_files_count") == len(context["changed_paths"])

    if repo_match and base_match and head_ref_match and head_match and digest_match and count_match:
        bound = _pass(
            "ao_ma10_context_bound",
            detail="AO-MA-10 evidence bundle context binding matches repository, refs, head SHA, diff digest, and changed-files count.",
        )
    else:
        bound = _blocked(
            "ao_ma10_context_bound",
            finding_code="ao_release_gate_ao_ma10_evidence_bundle_context_unbound",
            detail="AO-MA-10 evidence bundle context binding does not match the pull request repository, refs, head SHA, diff digest, or changed-files count.",
        )

    return [request_check, bundle_present, schema_valid, consensus_check, bound, authority_check]


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
            "ao_release_gate_ao_ma10_evidence_bundle_context_unbound",
            "ao_release_gate_high_risk_supersession_context_unbound",
        }
        for finding in findings
    ):
        return cast(ReleaseGateDecisionValue, DENY_UNTRUSTED_CONTEXT_DECISION)
    if any(
        finding
        in {
            "ao_release_gate_ao_ma10_same_provider_self_review",
            "ao_release_gate_high_risk_supersession_same_provider_self_review",
            "ao_release_gate_high_risk_supersession_authority_boundary_open",
        }
        for finding in findings
    ):
        return cast(ReleaseGateDecisionValue, DENY_POLICY_VIOLATION_DECISION)
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
            "ao_release_gate_ao_ma10_evidence_bundle_missing",
            "ao_release_gate_ao_ma10_evidence_bundle_schema_invalid",
            "ao_release_gate_ao_ma10_consensus_not_agree",
            "ao_release_gate_ao_ma10_evidence_bundle_context_unverifiable",
            "ao_release_gate_high_risk_supersession_evidence_missing",
            "ao_release_gate_high_risk_supersession_schema_invalid",
            "ao_release_gate_high_risk_supersession_stale",
            "ao_release_gate_high_risk_supersession_consensus_not_agree",
            "ao_release_gate_high_risk_supersession_context_unverifiable",
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
    """Build the legacy GitHub check-run output shape (compatibility wrapper).

    The check-run conclusion is mode-aware:

    - ``allow_autonomous_merge`` always maps to ``success`` (both modes).
    - In ``shadow`` mode (default), every deny/error decision maps to
      ``neutral`` so advisory evidence does not surface as red CI before
      the AO-GATE-8 enforcement cutover.
    - In ``enforce`` mode, RG-CONCLUSION-SEMANTICS (C-prime) wrapper logic
      applies: a finding set whose only blockers are ``review_action``
      kind maps to ``success`` (preserves the legacy required check name
      while shifting CODEOWNER-review-missing semantics off the failure
      axis). Any real violation, stale branch, or mixed blocker still
      maps to ``failure``.

    CODEOWNER review enforcement after this migration is supplied by
    GitHub's ``require_code_owner_reviews`` branch protection rule and the
    new ``ao-release-gate-review`` check-run, NOT this legacy wrapper.
    """

    allow = decision == ALLOW_AUTONOMOUS_MERGE_DECISION
    summary = _reason(decision)
    text = "Findings: " + ", ".join(findings) if findings else "All release-gate checks passed."
    conclusion: GithubCheckConclusion
    if allow:
        conclusion = "success"
    elif conclusion_mode == "enforce":
        # C-prime wrapper: review-action-only blocker maps to success so
        # the legacy required check name does not block on operator review.
        if findings and all(finding_conclusion_kind(code) == "review_action" for code in findings):
            conclusion = "success"
        else:
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


def _findings_for_kind(findings: list[str], kind: FindingConclusionKind) -> list[str]:
    """Return the subset of finding codes that classify as ``kind``."""

    return [code for code in findings if finding_conclusion_kind(code) == kind]


def build_technical_check_run(
    decision: ReleaseGateDecisionValue,
    findings: list[str],
    *,
    conclusion_mode: ConclusionMode = DEFAULT_CONCLUSION_MODE,
) -> AoReleaseGateCheckRun:
    """Build the ``ao-release-gate-technical`` check-run shape.

    Technical check covers real governance / structural violations and
    stale-branch findings. It deliberately ignores ``review_action`` kind
    findings; CODEOWNER review pending is published on the companion
    ``ao-release-gate-review`` check, not here.

    Conclusion:

    - ``shadow`` mode: ``success`` if the gate decision allows merge;
      ``neutral`` otherwise (advisory pre-cutover).
    - ``enforce`` mode: ``success`` when no failure/stale finding exists;
      ``failure`` when any ``failure``-kind finding exists; ``stale`` when
      only stale findings (no failures) exist.
    """

    technical_findings = [code for code in findings if finding_conclusion_kind(code) != "review_action"]
    allow = decision == ALLOW_AUTONOMOUS_MERGE_DECISION
    summary = _reason(decision)
    text = (
        "Technical findings: " + ", ".join(technical_findings)
        if technical_findings
        else "All technical release-gate checks passed."
    )
    conclusion: GithubCheckConclusion
    if allow or not technical_findings:
        conclusion = "success"
    elif conclusion_mode == "enforce":
        conclusion = conclusion_for_findings(technical_findings)
    else:
        conclusion = "neutral"
    return {
        "name": RELEASE_GATE_TECHNICAL_CHECK_NAME,
        "status": "completed",
        "conclusion": conclusion,
        "title": f"{RELEASE_GATE_TECHNICAL_CHECK_NAME}: {decision}",
        "summary": summary,
        "text": text,
    }


def build_review_check_run(
    decision: ReleaseGateDecisionValue,
    findings: list[str],
    *,
    conclusion_mode: ConclusionMode = DEFAULT_CONCLUSION_MODE,
) -> AoReleaseGateCheckRun:
    """Build the ``ao-release-gate-review`` check-run shape.

    Review check covers only CODEOWNER review pending on the current PR
    head. It deliberately ignores failure / stale findings; those are
    published on the companion ``ao-release-gate-technical`` check.

    Conclusion:

    - ``shadow`` mode: ``success`` when no review-action finding;
      ``neutral`` when review pending.
    - ``enforce`` mode: ``success`` when no review-action finding;
      ``action_required`` when CODEOWNER review missing (this conclusion
      does NOT satisfy required status check; merge stays blocked).

    Operator UI signal: ``action_required`` surfaces as "needs attention"
    rather than "failing", honoring the operator HARD RULE that approve
    requires green CI.
    """

    review_findings = _findings_for_kind(findings, "review_action")
    summary = (
        "CODEOWNER review pending on current head." if review_findings else "CODEOWNER review present or not required."
    )
    text = (
        "Review findings: " + ", ".join(review_findings) if review_findings else "No review-pending findings recorded."
    )
    conclusion: GithubCheckConclusion
    if not review_findings:
        conclusion = "success"
    elif conclusion_mode == "enforce":
        conclusion = "action_required"
    else:
        conclusion = "neutral"
    return {
        "name": RELEASE_GATE_REVIEW_CHECK_NAME,
        "status": "completed",
        "conclusion": conclusion,
        "title": f"{RELEASE_GATE_REVIEW_CHECK_NAME}: {decision}",
        "summary": summary,
        "text": text,
    }


def build_ao_release_gate_decision(
    payload: object,
    gpp_status: object,
    *,
    review_evidence: object = None,
    ao_ma10_evidence_bundle: object = None,
    high_risk_supersession_evidence: object = None,
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

    ``ao_ma10_evidence_bundle`` is the untrusted
    ``ao-ma-10-evidence-bundle.v1`` provider-consensus bundle introduced
    for the future low-risk autonomous merge lane. It is required only
    when the payload's low-risk autonomous merge request flag is true or
    when a caller explicitly supplies a bundle. Missing, malformed,
    non-AGREE, authority-boundary-open, or context-mismatched bundle
    evidence fails closed without making AI output release authority.

    ``high_risk_supersession_evidence`` is the untrusted
    ``ao-ma-10-high-risk-supersession-evidence.v1`` artifact introduced
    by AO-MA-10h for the AO-MA-10i runtime slice. When schema-valid,
    context-bound, unanimous across OpenAI + Anthropic providers, and
    authority-boundary-closed, it can satisfy the path-sensitive
    high-risk gate as an alternative to a current-head non-author human
    approval. Missing evidence is backward-compatible: the existing
    human-approval path remains authoritative.
    """

    decision_generated_at = generated_at or utc_timestamp()
    context = extract_ao_release_gate_context(payload, gpp_status)
    high_risk_supersession_checks, high_risk_supersession_valid = (
        _evaluate_high_risk_supersession_checks(
            high_risk_supersession_evidence,
            context,
            decision_generated_at=decision_generated_at,
        )
    )
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
        *high_risk_supersession_checks,
        _check(
            "path_sensitive_human_review",
            _path_sensitive_human_review_satisfied(
                context, high_risk_supersession_valid=high_risk_supersession_valid
            ),
            finding_code="ao_release_gate_high_risk_human_review_missing",
            pass_detail=(
                "The path-sensitive human-review gate is inactive, no high-risk paths changed, "
                "a current-head non-author human approval exists for the high-risk surface, "
                "or valid high-risk supersession evidence is bound to this PR."
            ),
            blocked_detail=(
                "High-risk paths changed without a current-head non-author human approval "
                "or valid high-risk supersession evidence."
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
    checks.extend(_evaluate_review_evidence_or_ao_ma10_low_risk_checks(review_evidence, context))
    checks.extend(_evaluate_ao_ma10_evidence_bundle_checks(ao_ma10_evidence_bundle, context))
    findings = [check["finding_code"] for check in checks if check["finding_code"] is not None]
    decision = _decision_from_findings(findings)
    allow = decision == ALLOW_AUTONOMOUS_MERGE_DECISION
    return {
        "schema_version": RELEASE_GATE_SCHEMA_VERSION,
        "artifact_kind": RELEASE_GATE_ARTIFACT_KIND,
        "program_id": RELEASE_GATE_PROGRAM_ID,
        "generated_at": decision_generated_at,
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
