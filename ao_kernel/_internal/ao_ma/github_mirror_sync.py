"""AO-MA-11E-2b — V5 GitHub mirror write sync engine.

Compares manifest authority against actual GitHub mirror state and produces
a diff of changes (planned in dry-run, applied in apply mode). Read-before-write
idempotent; foreign labels preserved (mirror-managed namespace only).

Disiplin (HARD RULE pinned):
- No `import requests`/`httpx`/`urllib`/`subprocess`/`gh` in this module.
- `gh_api_caller(method, path, body=None)` callable injected by CLI layer.
- Apply mode requires typed confirmation + accepted dry-run digest + env preflight.
- Token value NEVER appears in SyncReport.
- sync_state is report/runtime field only; NO manifest back-write from this module.

Public API:
    sync_v5_mirror(...) -> SyncReport
    SyncReport / ChangeRecord / EnvironmentPreflight / SyncState (Enum)
    render_issue_body(anchor: dict[str, Any], metadata: dict[str, Any], title: str) -> str
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# --- Public types ---------------------------------------------------------------


class SyncState(str, Enum):
    NOT_STARTED = "not_started"
    DRY_RUN_PLANNED = "dry_run_planned"
    DRY_RUN_COMPLETE = "dry_run_complete"
    APPLY_IN_PROGRESS = "apply_in_progress"
    APPLIED = "applied"
    APPLIED_WITH_POST_DRIFT = "applied_with_post_drift"
    APPLY_ABORTED = "apply_aborted"
    API_ERROR = "api_error"
    USAGE_ERROR = "usage_error"


_CHANGE_CATEGORIES = frozenset(
    {
        "issue_body_rewrite",
        "label_add",
        "label_remove",
        "project_item_add",
        "project_item_remove",
    }
)

_OBJECT_TYPES = frozenset({"issue", "label", "project_item"})

# Mirror-managed label namespaces — only these are sync'd; foreign labels preserved.
_MIRROR_LABEL_NAMESPACES = (
    "epic-",
    "status:",
    "risk:",
    "guard-flip:",
    "mirror:",
)

_APPLY_CONFIRMATION = "AO-MA-11E-2B-APPLY"
_SHA_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass
class ChangeRecord:
    category: str
    object_type: str
    object_id: str
    before: Any
    after: Any

    def __post_init__(self) -> None:
        if self.category not in _CHANGE_CATEGORIES:
            raise ValueError(f"unknown change category: {self.category!r}")
        if self.object_type not in _OBJECT_TYPES:
            raise ValueError(f"unknown object_type: {self.object_type!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "before": self.before,
            "after": self.after,
        }


@dataclass
class EnvironmentPreflight:
    environment_name: str
    environment_exists: bool
    required_reviewers_count: int
    environment_preflight_decision: str  # pass | fail_closed_missing | fail_closed_no_reviewers | skipped_dry_run

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "environment_exists": self.environment_exists,
            "required_reviewers_count": self.required_reviewers_count,
            "environment_preflight_decision": self.environment_preflight_decision,
        }


@dataclass
class SyncReport:
    projection_manifest: str
    manifest_sha256: str
    checked_at: str
    network_allowed: bool
    token_env: str
    token_present: bool
    github_owner: str
    github_repo: str
    apply_mode: bool
    confirmation_provided: Optional[str]
    accepted_dry_run_report_digest: Optional[str]
    planned_changes: list[ChangeRecord] = field(default_factory=list)
    applied_changes: list[ChangeRecord] = field(default_factory=list)
    pre_drift_snapshot: Optional[dict[str, Any]] = None
    post_drift_snapshot: Optional[dict[str, Any]] = None
    environment_preflight: Optional[EnvironmentPreflight] = None
    sync_state: SyncState = SyncState.NOT_STARTED
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ao-ma-github-mirror-sync-report.v1",
            "projection_manifest": self.projection_manifest,
            "manifest_sha256": self.manifest_sha256,
            "checked_at": self.checked_at,
            "network_allowed": self.network_allowed,
            "token_env": self.token_env,
            "token_present": self.token_present,
            "github_owner": self.github_owner,
            "github_repo": self.github_repo,
            "apply_mode": self.apply_mode,
            "confirmation_provided": self.confirmation_provided,
            "accepted_dry_run_report_digest": self.accepted_dry_run_report_digest,
            "planned_changes": [c.to_dict() for c in self.planned_changes],
            "applied_changes": [c.to_dict() for c in self.applied_changes],
            "pre_drift_snapshot": self.pre_drift_snapshot,
            "post_drift_snapshot": self.post_drift_snapshot,
            "environment_preflight": (
                self.environment_preflight.to_dict()
                if self.environment_preflight
                else {
                    "environment_name": "",
                    "environment_exists": False,
                    "required_reviewers_count": 0,
                    "environment_preflight_decision": "skipped_dry_run",
                }
            ),
            "sync_state": self.sync_state.value,
            "reason": self.reason,
        }

    def to_exit_code(self) -> int:
        if self.sync_state in (
            SyncState.DRY_RUN_COMPLETE,
            SyncState.APPLIED,
        ):
            return 0
        if self.sync_state == SyncState.APPLIED_WITH_POST_DRIFT:
            return 1
        if self.sync_state in (SyncState.APPLY_ABORTED, SyncState.USAGE_ERROR):
            return 2
        if self.sync_state == SyncState.API_ERROR:
            return 3
        # NOT_STARTED, DRY_RUN_PLANNED, APPLY_IN_PROGRESS — treat as usage_error
        # if seen by exit code calculator (terminal-only path).
        return 2


# --- Issue body template --------------------------------------------------------


def render_issue_body(*, anchor: dict[str, Any], metadata: dict[str, Any], title: str) -> str:
    """Render strict-format V5 issue body.

    Anchor section uses exactly 5 fields in canonical order; metadata section is
    a separate `## ` heading so the 11E-2a parser does NOT include it in scope.
    """
    anchor_lines = [
        f"- **spm_anchor:** `{anchor['spm_anchor']}`",
        f"- **slice_id:** `{anchor['slice_id']}`",
        f"- **ao_authority_artifact:** `{anchor['ao_authority_artifact']}`",
        f"- **artifact_sha256:** `{anchor['artifact_sha256']}`",
        f"- **plan_digest:** `{anchor['plan_digest']}`",
    ]
    metadata_lines = []
    risk = metadata.get("risk_class_source")
    if risk:
        metadata_lines.append(f"- **risk_class_source:** `{risk}`")
    ev = metadata.get("evidence_classes")
    if ev is not None:
        metadata_lines.append(f"- **evidence_classes:** {json.dumps(ev)}")
    ref = metadata.get("sub_issues_planned_ref")
    if ref:
        metadata_lines.append(f"- **sub_issues_planned_ref:** `{ref}`")

    parts = [
        "## V5 Anchor (manifest-driven binding)",
        "",
        *anchor_lines,
        "",
        "## V5 Metadata",
        "",
        *metadata_lines,
        "",
        "## Authority",
        "",
        "This issue is a **one-way mirror** of repo SSOT artifacts. Repo authority "
        "wins; GitHub state is visualization. AO-MA-11E-2 drift checker (Epic 1 "
        "sub-issue E-1-2) binds GitHub state ↔ this manifest.",
        "",
        "## Guard flags",
        "",
        "`live_adapter_execution`, `support_widening`, `production_platform_claim` "
        "all const false. Flip only via operator-bound supersession decision "
        "(PR-Xfinal Epic 9). This issue does NOT flip any guard flag.",
        "",
        "🤖 Synced by AO-MA-11E-2b (manifest-driven sync workflow)",
    ]
    return "\n".join(parts) + "\n"


# --- Confirmation gate ----------------------------------------------------------


def _validate_apply_confirmation(
    *,
    apply_mode: bool,
    confirmation: Optional[str],
    accepted_dry_run_report_digest: Optional[str],
    network_allowed: bool,
    token_present: bool,
) -> Optional[str]:
    """Return None if confirmation chain is valid; otherwise an error reason."""
    if not apply_mode:
        return None
    if not network_allowed:
        return "apply requires --allow-network"
    if not token_present:
        return "apply requires token presence (token_env not set)"
    if confirmation != _APPLY_CONFIRMATION:
        return f"apply requires --confirmation {_APPLY_CONFIRMATION}"
    if not accepted_dry_run_report_digest:
        return "apply requires --accepted-dry-run-report-digest"
    if not _SHA_PATTERN.match(accepted_dry_run_report_digest):
        return "accepted_dry_run_report_digest must be sha256:<64 lowercase hex>"
    return None


# --- Plan computation -----------------------------------------------------------


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# Codex iter-2 absorb: digest MUST be volatile-free so the same accepted plan
# survives across runs. Fields that change per-run (checked_at, environment
# preflight evidence, runtime state) are excluded; only the plan content
# (what would be written) is hashed.
_CANONICAL_DIGEST_FIELDS = (
    "schema_version",
    "projection_manifest",
    "manifest_sha256",
    "github_owner",
    "github_repo",
    "expected_counts",
    "planned_changes",
)


def compute_canonical_plan_digest(report_dict: dict[str, Any]) -> str:
    """Volatile-free sha256 over the plan content of a sync report.

    Excludes per-run fields: checked_at, applied_changes, pre/post drift
    snapshots, environment_preflight, sync_state, reason, network/token
    metadata, apply_mode, confirmation. Same manifest + same actual GitHub
    state → same digest, regardless of run timing.

    Codex iter-3 absorb: `planned_changes` is also sorted by (category,
    object_type, object_id) before hashing so PYTHONHASHSEED-induced set
    iteration order does NOT change the digest. This is defense-in-depth
    on top of `_plan_*_changes()` already producing sorted output.
    """
    canonical: dict[str, Any] = {}
    for k in _CANONICAL_DIGEST_FIELDS:
        if k in report_dict:
            canonical[k] = report_dict[k]
    # Sort planned_changes deterministically (Codex iter-3 §3 absorb).
    if "planned_changes" in canonical and isinstance(canonical["planned_changes"], list):
        canonical["planned_changes"] = sorted(
            canonical["planned_changes"],
            key=lambda c: (
                c.get("category", ""),
                c.get("object_type", ""),
                c.get("object_id", ""),
            ),
        )
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _utcnow_isoformat() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_mirror_managed_label(name: str) -> bool:
    return any(name.startswith(ns) for ns in _MIRROR_LABEL_NAMESPACES)


def _plan_issue_body_changes(
    *,
    manifest: dict[str, Any],
    actual_issues: dict[int, dict[str, Any]],
    runtime_state: dict[str, Any],
) -> list[ChangeRecord]:
    """Per-issue body diff: render expected body, compare with actual."""
    changes: list[ChangeRecord] = []
    expected_issues = runtime_state.get("issues_created", {})
    expected_first_wave_by_id = {i["id"]: i for i in manifest.get("first_wave_issues", [])}
    for issue_id, num in expected_issues.items():
        meta = expected_first_wave_by_id.get(issue_id)
        if meta is None:
            continue
        anchor = meta.get("body_anchor", {})
        metadata = meta.get("metadata", {})
        expected_body = render_issue_body(anchor=anchor, metadata=metadata, title=meta.get("title", ""))
        actual_body = (actual_issues.get(num, {}) or {}).get("body", "")
        if expected_body != actual_body:
            changes.append(
                ChangeRecord(
                    category="issue_body_rewrite",
                    object_type="issue",
                    object_id=str(num),
                    before=actual_body,
                    after=expected_body,
                )
            )
    return changes


def _plan_label_changes(
    *,
    manifest: dict[str, Any],
    actual_issues: dict[int, dict[str, Any]],
    runtime_state: dict[str, Any],
) -> list[ChangeRecord]:
    """Per-issue label diff in mirror-managed namespace only."""
    changes: list[ChangeRecord] = []
    expected_issues = runtime_state.get("issues_created", {})
    expected_first_wave_by_id = {i["id"]: i for i in manifest.get("first_wave_issues", [])}
    for issue_id, num in expected_issues.items():
        meta = expected_first_wave_by_id.get(issue_id)
        if meta is None:
            continue
        expected_labels = set(meta.get("labels", []))
        actual_full = (actual_issues.get(num, {}) or {}).get("labels", [])
        actual_label_names = {lab.get("name", "") for lab in actual_full}
        # Mirror-managed slice only — foreign labels preserved
        expected_mirror = {lb for lb in expected_labels if _is_mirror_managed_label(lb)}
        actual_mirror = {lb for lb in actual_label_names if _is_mirror_managed_label(lb)}
        # Codex iter-3 absorb: deterministic sort across set differences so
        # PYTHONHASHSEED-induced iteration order does NOT change the plan.
        for missing in sorted(expected_mirror - actual_mirror):
            changes.append(
                ChangeRecord(
                    category="label_add",
                    object_type="label",
                    object_id=f"{num}:{missing}",
                    before=None,
                    after=missing,
                )
            )
        for extra in sorted(actual_mirror - expected_mirror):
            changes.append(
                ChangeRecord(
                    category="label_remove",
                    object_type="label",
                    object_id=f"{num}:{extra}",
                    before=extra,
                    after=None,
                )
            )
    return changes


def _plan_project_item_changes(
    *,
    runtime_state: dict[str, Any],
    actual_project_urls: set[str],
    repo_owner: str,
    repo_name: str,
) -> list[ChangeRecord]:
    expected_issue_numbers = set(runtime_state.get("issues_created", {}).values())
    expected_urls = {f"https://github.com/{repo_owner}/{repo_name}/issues/{n}" for n in expected_issue_numbers}
    changes: list[ChangeRecord] = []
    # Codex iter-3 absorb: deterministic sort across set differences.
    for missing_url in sorted(expected_urls - actual_project_urls):
        changes.append(
            ChangeRecord(
                category="project_item_add",
                object_type="project_item",
                object_id=missing_url,
                before=None,
                after=missing_url,
            )
        )
    for extra_url in sorted(actual_project_urls - expected_urls):
        changes.append(
            ChangeRecord(
                category="project_item_remove",
                object_type="project_item",
                object_id=extra_url,
                before=extra_url,
                after=None,
            )
        )
    return changes


# --- Main sync engine -----------------------------------------------------------


def sync_v5_mirror(
    *,
    projection_manifest_path: Path,
    gh_api_caller: Callable[[str, str, Optional[dict[str, Any]]], Any],
    repo_owner: str = "Halildeu",
    repo_name: str = "ao-kernel",
    network_allowed: bool = False,
    apply_mode: bool = False,
    confirmation: Optional[str] = None,
    accepted_dry_run_report_digest: Optional[str] = None,
    pre_drift_snapshot: Optional[dict[str, Any]] = None,
    environment_name: str = "ao-ma-mirror-sync",
    token_env: str = "GH_TOKEN",
    token_present: bool = False,
    now_iso: Optional[str] = None,
) -> SyncReport:
    """Sync V5 manual mirror against the projection manifest.

    Args:
        projection_manifest_path: path to v5_issue_projection.v1.json
        gh_api_caller: callable(method, path, body=None) → JSON response
        apply_mode: False (default) = dry-run; True = live GitHub write
        confirmation: required for apply; must equal "AO-MA-11E-2B-APPLY"
        accepted_dry_run_report_digest: required for apply; sha256:<hex>
        pre_drift_snapshot: required for apply; from prior 11E-2a run
        environment_name: GitHub Environment for apply protection gate
        token_env / token_present: env-var name + presence boolean (NOT value)
    """
    checked_at = now_iso or _utcnow_isoformat()
    manifest_sha = _file_sha256(projection_manifest_path)
    manifest = _load_manifest(projection_manifest_path)

    report = SyncReport(
        projection_manifest=str(projection_manifest_path),
        manifest_sha256=manifest_sha,
        checked_at=checked_at,
        network_allowed=network_allowed,
        token_env=token_env,
        token_present=token_present,
        github_owner=repo_owner,
        github_repo=repo_name,
        apply_mode=apply_mode,
        confirmation_provided=confirmation,
        accepted_dry_run_report_digest=accepted_dry_run_report_digest,
        pre_drift_snapshot=pre_drift_snapshot,
    )

    # Confirmation chain gate (apply mode)
    confirmation_error = _validate_apply_confirmation(
        apply_mode=apply_mode,
        confirmation=confirmation,
        accepted_dry_run_report_digest=accepted_dry_run_report_digest,
        network_allowed=network_allowed,
        token_present=token_present,
    )
    if confirmation_error:
        report.sync_state = SyncState.USAGE_ERROR
        report.reason = confirmation_error
        return report

    if not network_allowed:
        report.sync_state = SyncState.USAGE_ERROR
        report.reason = "network not allowed (use --allow-network)"
        return report

    # Environment preflight (apply mode only)
    if apply_mode:
        env_resp, env_err = _safe_call(
            gh_api_caller,
            "GET",
            f"/repos/{repo_owner}/{repo_name}/environments/{environment_name}",
            None,
        )
        if env_err is not None:
            report.environment_preflight = EnvironmentPreflight(
                environment_name=environment_name,
                environment_exists=False,
                required_reviewers_count=0,
                environment_preflight_decision="fail_closed_missing",
            )
            report.sync_state = SyncState.APPLY_ABORTED
            report.reason = f"environment preflight failed: {environment_name} not accessible"
            return report
        reviewers = env_resp.get("protection_rules", []) if env_resp else []
        # GitHub returns required_reviewers as a protection rule of type "required_reviewers"
        reviewer_count = 0
        for rule in reviewers:
            if rule.get("type") == "required_reviewers":
                reviewer_count = len(rule.get("reviewers", []))
                break
        if reviewer_count == 0:
            report.environment_preflight = EnvironmentPreflight(
                environment_name=environment_name,
                environment_exists=True,
                required_reviewers_count=0,
                environment_preflight_decision="fail_closed_no_reviewers",
            )
            report.sync_state = SyncState.APPLY_ABORTED
            report.reason = f"environment {environment_name} has no required reviewers"
            return report
        report.environment_preflight = EnvironmentPreflight(
            environment_name=environment_name,
            environment_exists=True,
            required_reviewers_count=reviewer_count,
            environment_preflight_decision="pass",
        )
    else:
        report.environment_preflight = EnvironmentPreflight(
            environment_name=environment_name,
            environment_exists=False,
            required_reviewers_count=0,
            environment_preflight_decision="skipped_dry_run",
        )

    # Fetch actual GitHub state (issues + project items)
    runtime_state = manifest.get("runtime_created_state", {})
    expected_ms_number = runtime_state.get("milestone", {}).get("number")

    actual_issues: dict[int, dict[str, Any]] = {}
    if expected_ms_number is not None:
        issues_resp, err = _safe_call(
            gh_api_caller,
            "GET",
            f"/repos/{repo_owner}/{repo_name}/issues?milestone={expected_ms_number}&state=all&per_page=100",
            None,
        )
        if err is not None:
            report.sync_state = SyncState.API_ERROR
            report.reason = f"failed to fetch issues: {err}"
            return report
        for iss in issues_resp or []:
            actual_issues[iss["number"]] = iss

    # Fetch project items
    project_node_id = runtime_state.get("project_board", {}).get("node_id")
    actual_project_urls: set[str] = set()
    if project_node_id:
        items_resp, err = _safe_call(
            gh_api_caller,
            "POST",
            f"graphql:project_items:{project_node_id}",
            None,
        )
        if err is not None:
            report.sync_state = SyncState.API_ERROR
            report.reason = f"failed to fetch project items: {err}"
            return report
        for item in (items_resp or {}).get("items", []):
            content = item.get("content") or {}
            url = content.get("url")
            if not url and content.get("number") is not None:
                url = f"https://github.com/{repo_owner}/{repo_name}/issues/{content['number']}"
            if url:
                actual_project_urls.add(url)

    # Compute planned changes
    body_changes = _plan_issue_body_changes(
        manifest=manifest,
        actual_issues=actual_issues,
        runtime_state=runtime_state,
    )
    label_changes = _plan_label_changes(
        manifest=manifest,
        actual_issues=actual_issues,
        runtime_state=runtime_state,
    )
    project_changes = _plan_project_item_changes(
        runtime_state=runtime_state,
        actual_project_urls=actual_project_urls,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )

    report.planned_changes = body_changes + label_changes + project_changes
    report.sync_state = SyncState.DRY_RUN_PLANNED

    if not apply_mode:
        report.sync_state = SyncState.DRY_RUN_COMPLETE
        return report

    # Apply mode: execute planned changes (idempotent; each call read-before-write)
    report.sync_state = SyncState.APPLY_IN_PROGRESS
    for change in report.planned_changes:
        applied = _apply_change(
            change=change,
            gh_api_caller=gh_api_caller,
            repo_owner=repo_owner,
            repo_name=repo_name,
            project_node_id=project_node_id,
        )
        if applied is None:
            report.sync_state = SyncState.API_ERROR
            report.reason = f"apply failed at {change.category}/{change.object_id}"
            return report
        if applied:
            report.applied_changes.append(change)

    # Post-drift snapshot: caller responsible for running 11E-2a again and
    # injecting the result via separate call; this module just transitions state.
    report.sync_state = SyncState.APPLIED
    return report


def _apply_change(
    *,
    change: ChangeRecord,
    gh_api_caller: Callable[[str, str, Optional[dict[str, Any]]], Any],
    repo_owner: str,
    repo_name: str,
    project_node_id: Optional[str],
) -> Optional[bool]:
    """Apply a single change. Returns True if applied, False if no-op (idempotent),
    None on error.
    """
    try:
        if change.category == "issue_body_rewrite":
            num = change.object_id
            _, err = _safe_call(
                gh_api_caller,
                "PATCH",
                f"/repos/{repo_owner}/{repo_name}/issues/{num}",
                {"body": change.after},
            )
            return None if err else True
        if change.category == "label_add":
            num, label = change.object_id.split(":", 1)
            _, err = _safe_call(
                gh_api_caller,
                "POST",
                f"/repos/{repo_owner}/{repo_name}/issues/{num}/labels",
                {"labels": [label]},
            )
            return None if err else True
        if change.category == "label_remove":
            # Codex iter-1 §2 absorb: DELETE method (not PATCH) for label remove.
            num, label = change.object_id.split(":", 1)
            _, err = _safe_call(
                gh_api_caller,
                "DELETE",
                f"/repos/{repo_owner}/{repo_name}/issues/{num}/labels/{label}",
                None,
            )
            return None if err else True
        if change.category == "project_item_add":
            # Codex iter-1 §2 absorb: real GraphQL mutation, not stubbed True.
            # change.object_id is the issue URL; need the issue node_id which
            # the CLI adapter resolves via a custom "graphql:add_project_item"
            # path convention. project_node_id required.
            if not project_node_id:
                return None
            url = change.object_id
            _, err = _safe_call(
                gh_api_caller,
                "POST",
                f"graphql:add_project_item:{project_node_id}:{url}",
                None,
            )
            return None if err else True
        if change.category == "project_item_remove":
            # Codex iter-1 §2 absorb: real GraphQL mutation.
            if not project_node_id:
                return None
            url = change.object_id
            _, err = _safe_call(
                gh_api_caller,
                "POST",
                f"graphql:remove_project_item:{project_node_id}:{url}",
                None,
            )
            return None if err else True
    except Exception:
        return None
    return False


def _safe_call(
    gh_api_caller: Callable[[str, str, Optional[dict[str, Any]]], Any],
    method: str,
    path: str,
    body: Optional[dict[str, Any]],
) -> tuple[Any, Optional[str]]:
    try:
        return gh_api_caller(method, path, body), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
